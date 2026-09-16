"""
test_sci_frame_accumulator.py — Monte-Carlo accumulator: cumulative mean,
Target N done-flag, button reset, and upstream-tick auto-reset.
"""
import os
import sys
import importlib.util

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_plugin_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'plugins', 'sci_frame_accumulator.py'
)
_spec = importlib.util.spec_from_file_location('plugins.sci_frame_accumulator', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules['plugins.sci_frame_accumulator'] = _mod
_spec.loader.exec_module(_mod)


def _frame(val, shape=(8, 8)):
    return np.full(shape, val, dtype=np.uint8)


def _feed(node, frames, **params):
    base = {'mode': 0, 'cumulative': True}
    base.update(params)
    out = None
    for f in frames:
        out = node.process({'image': f}, base)
    return out


def test_cumulative_mean_converges_over_all_frames():
    # Arrange: alternating 0 / 200 → mean should approach 100 over many frames
    node = _mod.FrameAccumulatorNode()
    frames = [_frame(0 if i % 2 == 0 else 200) for i in range(100)]

    # Act
    out = _feed(node, frames)

    # Assert: cumulative mean ≈ 100 (window-free, all 100 frames counted)
    assert out['frame_count'] == 100
    assert abs(float(out['main'].mean()) - 100) < 2


def test_target_n_sets_done_and_freezes_count():
    # Arrange
    node = _mod.FrameAccumulatorNode()

    # Act: feed 10 frames with Target N = 5
    last = None
    dones = []
    for i in range(10):
        last = node.process({'image': _frame(50)}, {'mode': 0, 'cumulative': True, 'target_n': 5})
        dones.append(last['done'])

    # Assert: count caps at 5, done flips to 1 once reached and stays
    assert last['frame_count'] == 5
    assert dones[4] == 1.0
    assert dones[-1] == 1.0
    assert dones[0] == 0.0


def test_reset_button_clears_state():
    # Arrange: accumulate, then press reset (trigger pulse 0→1)
    node = _mod.FrameAccumulatorNode()
    node.process({'image': _frame(80)}, {'mode': 0, 'cumulative': True})
    node.process({'image': _frame(80)}, {'mode': 0, 'cumulative': True})

    # Act: rising-edge reset
    out = node.process({'image': _frame(10)}, {'mode': 0, 'cumulative': True, 'reset': 1})

    # Assert: buffer cleared then this frame counted fresh → count == 1, mean == 10
    assert out['frame_count'] == 1
    assert abs(float(out['main'].mean()) - 10) < 1


def test_upstream_tick_drop_auto_resets():
    # Arrange: accumulate while tick rises, then tick drops to 0 (driver restart)
    node = _mod.FrameAccumulatorNode()
    for t in (1, 2, 3):
        node.process({'image': _frame(200), 'tick': t}, {'mode': 0, 'cumulative': True})

    # Act: upstream Reset → tick back to 0, new frame value 40
    out = node.process({'image': _frame(40), 'tick': 0}, {'mode': 0, 'cumulative': True})

    # Assert: auto-cleared, only the post-reset frame counts
    assert out['frame_count'] == 1
    assert abs(float(out['main'].mean()) - 40) < 1


def test_window_mode_still_slides():
    # Arrange: non-cumulative keeps only the last W frames
    node = _mod.FrameAccumulatorNode()

    # Act: 10 frames, window 4
    out = _feed(node, [_frame(100) for _ in range(10)], cumulative=False, window=4)

    # Assert: buffer never exceeds window
    assert out['frame_count'] == 4


# ── Std mode: σ must be recoverable in input units (MC uncertainty map) ────────
# The Monte-Carlo uncertainty product needs σ_P in probability units. Mode 3 used to
# only emit a max-normalised map (255·σ/σ_max), which is a *relative* quantity: its
# maximum is pinned to 255 on every tick, so it cannot decrease as N grows and any
# downstream SE = ⟨σ⟩/√N is wrong by an unreported, run-dependent factor 1/σ_max.
#
# Recovery contract, uniform across modes:   value_in_input_units = main / 255 * scale
#   normalize=True  → scale = σ_max (input units)
#   normalize=False → scale = 255   (main already carries σ directly)

def _std_frames(n, shape=(8, 8)):
    """Half the pixels alternate 0/255 (σ = 127.5), half stay 0 (σ = 0)."""
    frames = []
    for i in range(n):
        f = np.zeros(shape, dtype=np.uint8)
        f[: shape[0] // 2, :] = 255 if i % 2 else 0
        frames.append(f)
    return frames


def test_std_unnormalised_emits_sigma_in_input_units():
    # Arrange: alternating 0/255 on the top half → population σ = 127.5 there, 0 below
    node = _mod.FrameAccumulatorNode()

    # Act
    out = _feed(node, _std_frames(100), mode=3, normalize=False)

    # Assert: σ is carried directly, not rescaled to fill the 0-255 range
    top = float(out['main'][:4, :].mean())
    bottom = float(out['main'][4:, :].mean())
    assert abs(top - 127.5) < 1.5, f'expected σ≈127.5 in input units, got {top}'
    assert bottom == 0.0
    assert out['scale'] == 255.0


def test_std_normalised_is_recoverable_via_scale():
    # Arrange: same scene, default (legacy) normalised output
    node = _mod.FrameAccumulatorNode()

    # Act
    out = _feed(node, _std_frames(100), mode=3, normalize=True)

    # Assert: normalised map saturates at 255, and scale recovers the true σ
    assert float(out['main'].max()) == 255.0
    recovered = float(out['main'][:4, :].mean()) / 255.0 * out['scale']
    assert abs(recovered - 127.5) < 1.5, f'scale must recover σ, got {recovered}'


def test_std_probability_units_round_trip():
    # Arrange: 0/255 masks → σ in probability units must land on √(p(1-p)) = 0.5
    node = _mod.FrameAccumulatorNode()

    # Act
    out = _feed(node, _std_frames(100), mode=3, normalize=False)

    # Assert: σ_P = main * scale / 255**2  (the documented recovery formula)
    sigma_p = float(out['main'][:4, :].mean()) * out['scale'] / (255.0 ** 2)
    assert abs(sigma_p - 0.5) < 0.01, f'expected σ_P≈0.5, got {sigma_p}'


def test_scale_is_emitted_for_every_mode():
    # Arrange: non-std modes carry values directly → scale is the identity 255
    node = _mod.FrameAccumulatorNode()

    # Act
    out = _feed(node, [_frame(100) for _ in range(5)], mode=0)

    # Assert
    assert out['scale'] == 255.0
    assert abs(float(out['main'].mean()) / 255.0 * out['scale'] - 100) < 1


def test_mean_rounds_instead_of_truncating():
    # Arrange: 2 of 7 frames water → P = 2/7 → 72.857; truncation gives 72, rounding 73
    node = _mod.FrameAccumulatorNode()
    frames = [_frame(255), _frame(255)] + [_frame(0)] * 5

    # Act
    out = _feed(node, frames, mode=0)

    # Assert: no systematic downward bias from the uint8 cast
    assert int(out['main'][0, 0]) == 73
