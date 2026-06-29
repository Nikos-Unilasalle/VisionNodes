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
