"""
07_sinnamary_template_smoke.py
==============================

Programmatic end-to-end smoke of the Sinnamary Mangrove Dynamics template
(`public/templates/Guyane Phase 1/sinnamary_mangrove_dynamics.vn`).

Instantiates the Phase 1 nodes outside VNStudio and pipes them in the same
order the .vn graph wires them. Confirms the full chain succeeds and saves
the four output panels as PNGs for visual QC.
"""
from __future__ import annotations
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))

import time
import plugins.geo_copernicus              as gc_mod
import plugins.s1_polarization_features    as pf_mod
import plugins.geo_time_align              as ta_mod

OUT = ROOT / "paper" / "experiments" / "out" / "sinnamary_panels"
OUT.mkdir(parents=True, exist_ok=True)

BBOX = "-53.30,4.40,-52.60,5.50"     # Sinnamary union
RES  = 30                              # 30 m for the smoke (faster than 20)


def step(name: str):
    print(f"\n── {name} ──", flush=True)


def _wait_async(node, params, max_wait_s: int = 600):
    """geo_copernicus uses a background fetch thread — poll until result ready."""
    node.process({}, params)
    for _ in range(max_wait_s // 2):
        time.sleep(2)
        out = node.process({}, params)
        if out.get("geotiff") is not None:
            return out
    return out


def main():
    # 1. S1 RTC 2024 — annual median via geo_copernicus STAC backend (collection 5)
    step("S1 RTC 2024  (geo_copernicus, collection 5)")
    s1_node = gc_mod.GeoCopernicusNode()
    s1_out = _wait_async(s1_node, {
        "bbox": BBOX, "collection": 5,
        "date_start": "2024-01-01", "date_end": "2024-12-31",
        "resolution": RES, "stac_polarization": 0, "stac_orbit": 0,
        "stac_composite": 0, "stac_to_db": True, "stac_max_scenes": 12,
        "cache_dir": "copernicus_cache", "fetch": 1,
    })
    print("  bands:", s1_out["geotiff"]["band_names"])
    print("  shape:", s1_out["geotiff"]["bands"].shape)

    # 2. S1 polarization features
    step("S1 Polarization Features")
    pf = pf_mod.S1PolarizationFeaturesNode()
    pf_out = pf.process({"geotiff": s1_out["geotiff"]}, {
        "rvi": True, "span": True, "span_db": True,
        "nrpb": True, "pdi": True, "pri": False, "dpsvi": True,
        "output_db": True, "cache_dir": "copernicus_cache",
    })
    print("  bands:", pf_out["geotiff"]["band_names"])
    cv2.imwrite(str(OUT / "panel_1_s1_pol_rgb.png"), pf_out["preview"])

    def _lulc_summary(out: dict) -> dict:
        """Compute per-class share for a LULC output."""
        arr = out["geotiff"]["bands"][0].astype(np.int32)
        vals, counts = np.unique(arr, return_counts=True)
        total = arr.size
        return {int(v): round(100.0 * c / total, 3) for v, c in zip(vals, counts)}

    # 3. ESA WorldCover 2021 (ground truth) — geo_copernicus collection 6
    step("ESA WorldCover 2021  (geo_copernicus, collection 6)")
    wc_node = gc_mod.GeoCopernicusNode()
    wc_out = _wait_async(wc_node, {
        "bbox": BBOX, "collection": 6,
        "date_start": "2021-01-01", "date_end": "2021-12-31",
        "resolution": RES, "stac_polarization": 0, "stac_orbit": 0,
        "stac_composite": 0, "stac_to_db": True, "stac_max_scenes": 5,
        "cache_dir": "copernicus_cache", "fetch": 1,
    })
    wc_shares = _lulc_summary(wc_out)
    print("  Mangroves (class 95) %:", wc_shares.get(95, 0.0))
    print("  classes_present:", wc_shares)
    cv2.imwrite(str(OUT / "panel_2_esa_wc_2021.png"), wc_out["preview"])

    # 4. io-lulc 2017 — collection 7
    step("io-lulc 2017 (t₀)  (geo_copernicus, collection 7)")
    lc17_node = gc_mod.GeoCopernicusNode()
    lc17_out = _wait_async(lc17_node, {
        "bbox": BBOX, "collection": 7,
        "date_start": "2017-01-01", "date_end": "2017-12-31",
        "resolution": RES, "stac_polarization": 0, "stac_orbit": 0,
        "stac_composite": 0, "stac_to_db": True, "stac_max_scenes": 5,
        "cache_dir": "copernicus_cache", "fetch": 1,
    })
    print("  classes_present:", _lulc_summary(lc17_out))

    # 5. io-lulc 2024 — collection 7
    step("io-lulc 2024 (t₁)  (geo_copernicus, collection 7)")
    lc24_node = gc_mod.GeoCopernicusNode()
    lc24_out = _wait_async(lc24_node, {
        "bbox": BBOX, "collection": 7,
        "date_start": "2024-01-01", "date_end": "2024-12-31",
        "resolution": RES, "stac_polarization": 0, "stac_orbit": 0,
        "stac_composite": 0, "stac_to_db": True, "stac_max_scenes": 5,
        "cache_dir": "copernicus_cache", "fetch": 1,
    })
    print("  classes_present:", _lulc_summary(lc24_out))
    cv2.imwrite(str(OUT / "panel_3_iolulc_2024.png"), lc24_out["preview"])

    # 6. Time-align change detection
    step("Change detection 2017 → 2024")
    ta = ta_mod.GeoTimeAlignNode()
    ch_out = ta.process({
        "t0_geotiff": lc17_out["geotiff"],
        "t1_geotiff": lc24_out["geotiff"],
    }, {
        "resampling": 0,        # nearest (categorical)
        "change_threshold": 0.5,
        "preview_band": "lulc_class",
        "cache_dir": "copernicus_cache",
    })
    print("  change_pct:", ch_out["meta"]["change_pct"], "%")
    cv2.imwrite(str(OUT / "panel_4_change_2017_2024.png"), ch_out["preview"])
    cv2.imwrite(str(OUT / "panel_4_change_mask.png"), ch_out["change_mask"])

    # Composite quad-panel for the paper / README
    step("Composite 2×2 figure")
    def pad_to(img: np.ndarray, target: tuple[int, int]) -> np.ndarray:
        th, tw = target
        ih, iw = img.shape[:2]
        scale = min(th / ih, tw / iw)
        new_h, new_w = int(ih * scale), int(iw * scale)
        res = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        canvas = np.full((th, tw, 3), 22, dtype=np.uint8)
        y_off = (th - new_h) // 2
        x_off = (tw - new_w) // 2
        canvas[y_off:y_off+new_h, x_off:x_off+new_w] = res
        return canvas

    panel_size = (480, 640)
    titles = [
        ("S1 Pol RGB (RVI / NRPB / PDI)", pf_out["preview"]),
        (f"ESA WC 2021  Mangroves={wc_shares.get(95, 0):.2f}%",
         wc_out["preview"]),
        ("io-lulc 2024", lc24_out["preview"]),
        (f"Change 2017→2024  pct={ch_out['meta']['change_pct']:.2f}%",
         ch_out["preview"]),
    ]
    grid = np.full((panel_size[0]*2 + 60, panel_size[1]*2 + 30, 3), 22, dtype=np.uint8)
    for i, (title, img) in enumerate(titles):
        row = i // 2
        col = i % 2
        y0 = 30 + row * panel_size[0] + row * 30
        x0 = 10 + col * panel_size[1] + col * 10
        padded = pad_to(img, panel_size)
        grid[y0:y0+panel_size[0], x0:x0+panel_size[1]] = padded
        cv2.putText(grid, title, (x0 + 8, y0 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1, cv2.LINE_AA)
    cv2.imwrite(str(OUT / "sinnamary_panels_2x2.png"), grid)

    print(f"\n✓ All panels written to {OUT}")


if __name__ == "__main__":
    main()
