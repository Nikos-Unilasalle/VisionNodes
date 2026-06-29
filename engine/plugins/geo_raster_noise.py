"""
geo_raster_noise.py — Generic per-band Gaussian perturbation of a float raster.

A domain-agnostic noise node: adds Gaussian noise to every band of a geotiff dict
in *physical* (float) units — unlike the 8-bit image noise nodes which clip to
[0, 255] and would destroy surface-reflectance values.

Noise model (per band, per pixel):
    σ_eff = sigma_abs + sigma_rel · |ρ|
    ρ'    = ρ + N(0, σ_eff)

`sigma_abs` is an additive floor (e.g. dark-signal / radiometric noise) and
`sigma_rel` a multiplicative term proportional to the signal (e.g. a 2 % sensor
uncertainty). Both are in the band's own units (reflectance in [0,1] if the
raster has been normalised).

This node is *stochastic and realtime*: it redraws fresh noise on every engine
tick (its type is in REALTIME_NODE_TYPES, so the engine never caches it). Placed
upstream of an index → vote → frame-accumulator chain, repeated ticks form a
Monte-Carlo ensemble that propagates input uncertainty into a calibrated
per-pixel probability (accumulator mean) and an uncertainty map (accumulator std).

Reproducibility: with a fixed `seed` (≥ 0), the per-tick draws follow the
deterministic sequence seed, seed+1, seed+2, … so an N-tick run is reproducible.
With seed = -1 the draws use OS entropy.
"""
from __future__ import annotations
import numpy as np
import cv2
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='geo_raster_noise',
    label='Raster Gaussian Noise',
    category='geography',
    icon='Ghost',
    description=(
        "Adds per-band Gaussian noise to a float raster in physical units "
        "(σ = sigma_abs + sigma_rel·|value|). Generic, domain-agnostic sensor-noise "
        "model. Stochastic/realtime: redraws each tick — drive a Monte-Carlo ensemble "
        "by feeding an index/threshold/frame-accumulator chain downstream."
    ),
    inputs=[{'id': 'geotiff', 'color': 'geotiff', 'label': 'Raster (float)'}],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Perturbed raster'},
        {'id': 'preview', 'color': 'image',   'label': 'Noise preview (band 1)'},
        {'id': 'tick',    'color': 'scalar',  'label': 'Realisation # (0-based)'},
    ],
    params=[
        {'id': 'toggle_run', 'type': 'trigger', 'default': 0,
         'label': '▶ Start / ⏸ Stop (Monte-Carlo)'},
        {'id': 'max_ticks', 'type': 'int', 'default': 0, 'min': 0, 'max': 1_000_000, 'step': 1,
         'label': 'Target N (0 = run forever)'},
        {'id': 'reset', 'type': 'trigger', 'default': 0,
         'label': '↺ Reset run (tick → 0, resume)'},
        {'id': 'sigma_abs', 'type': 'float', 'default': 0.01, 'min': 0.0, 'max': 1e6, 'step': 0.001,
         'label': 'σ absolute (additive floor)'},
        {'id': 'sigma_rel', 'type': 'float', 'default': 0.02, 'min': 0.0, 'max': 10.0, 'step': 0.01,
         'label': 'σ relative (× |value|)'},
        {'id': 'clip_negative', 'type': 'bool', 'default': True,
         'label': 'Clip negatives to 0'},
        {'id': 'seed', 'type': 'int', 'default': -1, 'min': -1, 'max': 2_000_000_000,
         'label': 'Base seed (-1 = entropy)'},
        {'id': 'node_note', 'type': 'string', 'default': '', 'label': 'Note'},
    ],
    resizable=True, min_width=240, min_height=150,
)
class RasterNoiseNode(NodeProcessor):

    def __init__(self):
        super().__init__()
        self._tick = 0
        self._running = True          # Monte-Carlo runs by default on load
        self._prev_trigger = 0.0
        self._prev_reset = 0.0
        self._paused = False
        self._last_output = None

    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        if not isinstance(geo, dict) or 'bands' not in geo:
            return {'geotiff': None, 'preview': None, 'tick': self._tick}

        # Reset button (trigger): rising edge zeroes the realisation counter and
        # resumes the run. Emitting `tick` downstream lets the accumulator auto-clear
        # when it sees tick == 0, so a single Reset press re-runs the whole MC chain.
        reset_trig = float(params.get('reset', 0) or 0)
        if reset_trig > 0.5 and self._prev_reset <= 0.5:
            self._tick = 0
            self._running = True
            self._last_output = None
        self._prev_reset = reset_trig

        # Start/Stop button (trigger): each press is a 0→1 pulse. Flip the running
        # state on the rising edge. When stopped, mark the node paused so the engine
        # treats it as cacheable (REALTIME nodes are normally re-run every tick) — the
        # whole MC chain downstream then freezes on the last frame, CPU drops to idle.
        trig = float(params.get('toggle_run', 0) or 0)
        if trig > 0.5 and self._prev_trigger <= 0.5:
            self._running = not self._running
        self._prev_trigger = trig

        # Auto-stop: once Target N realisations are drawn, pause. The downstream
        # accumulator has by then aggregated exactly N frames into P(water).
        max_ticks = int(params.get('max_ticks', 0) or 0)
        if max_ticks > 0 and self._tick >= max_ticks:
            self._running = False

        self._paused = not self._running
        if self._paused and self._last_output is not None:
            return self._last_output

        bands = np.asarray(geo['bands'], dtype=np.float32)
        if bands.ndim == 2:
            bands = bands[np.newaxis]

        sigma_abs = float(params.get('sigma_abs', 0.01))
        sigma_rel = float(params.get('sigma_rel', 0.02))
        clip_neg  = bool(params.get('clip_negative', True))
        base_seed = int(params.get('seed', -1))

        # Deterministic per-tick sequence when seeded; OS entropy otherwise.
        if base_seed >= 0:
            rng = np.random.default_rng(base_seed + self._tick)
        else:
            rng = np.random.default_rng()
        self._tick += 1

        sigma = sigma_abs + sigma_rel * np.abs(bands)
        noisy = bands + rng.standard_normal(bands.shape).astype(np.float32) * sigma
        if clip_neg:
            np.clip(noisy, 0.0, None, out=noisy)

        out_geo = {**geo, 'bands': noisy, 'count': int(noisy.shape[0]), 'dtype': 'float32'}

        # Preview of band 1 (auto-stretched for display only)
        b0 = noisy[0]
        finite = b0[np.isfinite(b0)]
        if finite.size:
            lo, hi = float(np.percentile(finite, 2)), float(np.percentile(finite, 98))
        else:
            lo, hi = 0.0, 1.0
        span = (hi - lo) or 1.0
        prev = np.clip((b0 - lo) / span * 255.0, 0, 255).astype(np.uint8)
        preview = cv2.applyColorMap(prev, cv2.COLORMAP_BONE)

        self._last_output = {'geotiff': out_geo, 'preview': preview, 'tick': self._tick}
        return self._last_output
