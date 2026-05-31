"""
geo_alert_scorer.py — Multi-criteria weighted risk scorer.

Accepts up to 6 dynamic geotiff/raster inputs. Each input gets a weight (0–1)
and an optional invert flag (high value = low risk). Outputs a composite score
0–100 with a green→yellow→red preview.

Typical uses:
  - Harpie orpaillage risk map (river proximity + geology + historical sites)
  - Any spatial MCDA problem (flood risk, fire risk, site suitability)

Inputs (dynamic): a–f rasters (geotiff dict or numpy array)
Outputs:
  score    — geotiff, float32, 0–100
  preview  — BGR image, green = low risk, red = high risk
  stats    — dict: mean score, % by tier (low/medium/high)
"""
from __future__ import annotations

import numpy as np
import cv2

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = "geo_alert_scorer"
_SLOTS = ["a", "b", "c", "d", "e", "f"]
_SLOT_LABELS = ["Layer A", "Layer B", "Layer C", "Layer D", "Layer E", "Layer F"]


def _slot_params() -> list[dict]:
    out: list[dict] = []
    for i, slot in enumerate(_SLOTS):
        label = _SLOT_LABELS[i]
        out += [
            {
                "id": f"{slot}_weight",
                "type": "float",
                "default": 1.0,
                "min": 0.0,
                "max": 1.0,
                "label": f"Weight {label}",
                "slot": slot,
            },
            {
                "id": f"{slot}_invert",
                "type": "bool",
                "default": False,
                "label": f"Invert {label}",
                "slot": slot,
            },
        ]
    return out


def _extract_band(val: object) -> np.ndarray | None:
    if val is None:
        return None
    if isinstance(val, dict):
        raw = val.get("bands")
        if raw is None:
            return None
        arr = np.asarray(raw, dtype=np.float32)
        return arr[0] if arr.ndim == 3 else arr
    if isinstance(val, np.ndarray):
        arr = val.astype(np.float32)
        if arr.ndim == 3:
            arr = arr[0]
        return arr
    return None


def _normalize(arr: np.ndarray) -> np.ndarray:
    lo, hi = float(np.nanmin(arr)), float(np.nanmax(arr))
    if hi - lo < 1e-9:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


def _risk_preview(score_0_100: np.ndarray) -> np.ndarray:
    """Map 0–100 score to green→yellow→red BGR image."""
    t = (score_0_100 / 100.0).clip(0.0, 1.0).astype(np.float32)
    H, W = t.shape
    bgr = np.zeros((H, W, 3), dtype=np.uint8)
    # green (0,128,0) → yellow (0,255,255) → red (0,0,255) in BGR
    half = t < 0.5
    t2 = np.where(half, t * 2.0, (t - 0.5) * 2.0)
    # green→yellow: R 0→255, G 128→255, B 0
    bgr[:, :, 2] = np.where(half, (t2 * 255).astype(np.uint8), 255)          # R
    bgr[:, :, 1] = np.where(half, (128 + t2 * 127).astype(np.uint8), (255 - t2 * 255).astype(np.uint8))  # G
    bgr[:, :, 0] = 0                                                          # B
    return bgr


@vision_node(
    type_id="geo_alert_scorer",
    label="Alert Scorer",
    category="geography",
    icon="AlertTriangle",
    description=(
        "Multi-criteria weighted risk score. Connect up to 6 raster layers. "
        "Each layer contributes according to its weight (0–1). "
        "Enable Invert when high values mean low risk (e.g. distance to river = safer). "
        "Output score is 0 (no risk) → 100 (maximum risk)."
    ),
    dynamic_inputs=True,
    inputs=[
        {"id": "a", "color": "geotiff", "label": "Layer A"},
    ],
    outputs=[
        {"id": "score",   "color": "geotiff", "label": "Risk score (0–100)"},
        {"id": "preview", "color": "image",   "label": "Risk map"},
        {"id": "stats",   "color": "scalar",  "label": "Stats"},
    ],
    params=[
        {
            "id": "normalize_inputs",
            "type": "bool",
            "default": True,
            "label": "Normalize each input 0–1",
        },
    ] + _slot_params(),
    resizable=True,
    min_width=240,
    min_height=200,
)
class AlertScorerNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        _static_keys = {"a", "score", "preview", "stats"}
        normalize_inputs = bool(params.get("normalize_inputs", True))

        # Collect (band, slot_index) in connection order
        layers: list[tuple[np.ndarray, int]] = []

        band_a = _extract_band(inputs.get("a"))
        if band_a is not None:
            layers.append((band_a, 0))

        dyn_items = sorted(
            [(k, v) for k, v in inputs.items() if k not in _static_keys and v is not None],
            key=lambda x: x[0],
        )
        for i, (_, val) in enumerate(dyn_items):
            band = _extract_band(val)
            if band is not None:
                layers.append((band, i + 1))

        if not layers:
            send_notification("AlertScorer: connect at least one layer", notif_id=_NOTIF)
            return {}

        # Reference shape from first layer
        H, W = layers[0][0].shape
        weighted_sum = np.zeros((H, W), dtype=np.float32)
        total_weight = 0.0

        for band, slot_idx in layers:
            slot = _SLOTS[min(slot_idx, len(_SLOTS) - 1)]
            weight = float(params.get(f"{slot}_weight", 1.0))
            invert = bool(params.get(f"{slot}_invert", False))

            if weight < 1e-6:
                continue

            # Resize to reference shape if needed
            if band.shape != (H, W):
                band = cv2.resize(band, (W, H), interpolation=cv2.INTER_LINEAR)

            arr = band.copy()
            if normalize_inputs:
                arr = _normalize(arr)

            if invert:
                if normalize_inputs:
                    arr = 1.0 - arr
                else:
                    arr = float(np.nanmax(arr)) - arr

            weighted_sum += arr * weight
            total_weight += weight

        if total_weight < 1e-9:
            send_notification("AlertScorer: all weights are zero", notif_id=_NOTIF)
            return {}

        raw_score = weighted_sum / total_weight

        # Scale to 0–100
        if normalize_inputs:
            score_100 = (raw_score * 100.0).clip(0.0, 100.0)
        else:
            score_100 = (_normalize(raw_score) * 100.0).clip(0.0, 100.0)

        # Stats
        low_pct    = float(np.mean(score_100 < 33.0)) * 100.0
        medium_pct = float(np.mean((score_100 >= 33.0) & (score_100 < 66.0))) * 100.0
        high_pct   = float(np.mean(score_100 >= 66.0)) * 100.0
        stats = {
            "mean_score":  round(float(np.mean(score_100)), 1),
            "low_pct":     round(low_pct, 1),
            "medium_pct":  round(medium_pct, 1),
            "high_pct":    round(high_pct, 1),
            "n_layers":    len(layers),
        }

        # Geotiff output — carry geo metadata from first geotiff input
        first_geo = inputs.get("a")
        if not isinstance(first_geo, dict):
            first_geo = next(
                (v for v in inputs.values() if isinstance(v, dict) and "bands" in v), {}
            )
        out_geo = {
            **first_geo,
            "bands": score_100[np.newaxis],
            "count": 1,
            "band_names": ["risk_score"],
            "dtype": "float32",
        }

        preview = _risk_preview(score_100)

        return {"score": out_geo, "preview": preview, "stats": stats}
