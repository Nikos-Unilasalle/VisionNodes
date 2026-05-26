"""
01_build_matchups.py
====================

Build the satellite-station matchup table that the GP pipeline ingests.
Pure Python, no VNStudio. Outputs `matchups.parquet`.

Steps:
  1. Load training mosaic GeoTIFF (6 bands: Blue, Green, Red, NIR, SWIR1, SWIR2).
  2. Load Naïades CSV.
  3. DOS-1 correction (per-band 0.1-percentile dark subtraction, safety cap).
  4. For each station within bbox: 5x5 nanmean pixel patch.
  5. Filter to ±30 days around 2023-07-04.
  6. Save Parquet ready for model training.
"""

from __future__ import annotations
import os, sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

# ─── Paths (relative to project root) ──────────────────────────────────────
ROOT          = Path(__file__).resolve().parents[2]
CACHE_DIR     = ROOT / "engine/plugins/copernicus_cache"
NAIADES_CSV   = ROOT / "engine/plugins/naiade.csv"
TRAINING_MOSAIC = CACHE_DIR / "d4e256b64eb562_mosaic.tif"
INFER_TIF       = CACHE_DIR / "165386a2bcd3d7.tif"   # Rouen 10m tile
OUT_DIR       = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

IMAGE_DATE   = "2023-07-04"
DATE_WINDOW  = 30   # days
SAMPLE_W     = 5    # 5x5 nanmean
BAND_NAMES   = ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]


# ─── DOS-1 correction ──────────────────────────────────────────────────────
def dos1(bands: np.ndarray) -> np.ndarray:
    """Same DOS-1 logic as engine/plugins/geo_acolite_full.py."""
    bands = bands.astype(np.float32).copy()
    finite = bands[np.isfinite(bands)]
    if finite.size > 0:
        p99 = float(np.percentile(finite, 99))
        if p99 > 10.0:
            bands = bands / 10000.0
    for i in range(bands.shape[0]):
        pos = bands[i][bands[i] > 0]
        if pos.size == 0:
            continue
        dark = float(np.percentile(pos, 0.1))
        med  = float(np.median(pos))
        if dark > 0.5 * med:
            dark = 0.0
        bands[i] = np.clip(bands[i] - dark, 0, None)
    return bands / np.pi  # BOA/pi -> Rrs


def lonlat_to_rc(lon: float, lat: float, transform) -> tuple[int, int]:
    """Convert lon/lat to (row, col) given a rasterio affine transform."""
    col, row = ~transform * (lon, lat)
    return int(round(row)), int(round(col))


def sample_window(bands: np.ndarray, r: int, c: int, w: int = 5) -> np.ndarray:
    """Return mean Rrs over a wxw window centered on (r, c), per band."""
    half = w // 2
    h, wcol = bands.shape[1], bands.shape[2]
    r0, r1 = max(0, r - half), min(h, r + half + 1)
    c0, c1 = max(0, c - half), min(wcol, c + half + 1)
    if r0 >= r1 or c0 >= c1:
        return np.full(bands.shape[0], np.nan, dtype=np.float32)
    patch = bands[:, r0:r1, c0:c1]
    out = np.full(patch.shape[0], np.nan, dtype=np.float32)
    for i in range(patch.shape[0]):
        m = np.isfinite(patch[i]) & (patch[i] > 0)
        if m.any():
            out[i] = float(patch[i][m].mean())
    return out


def main() -> None:
    print(f"[1/6] Reading mosaic: {TRAINING_MOSAIC}")
    with rasterio.open(TRAINING_MOSAIC) as r:
        bands_raw = r.read()
        transform = r.transform
        bounds    = r.bounds
        H, W      = r.height, r.width
    print(f"      shape={bands_raw.shape}, bounds={bounds}")

    print(f"[2/6] DOS-1 correction on {bands_raw.shape[0]} bands ...")
    rrs = dos1(bands_raw)
    print(f"      Rrs range: [{np.nanmin(rrs):.5f}, {np.nanmax(rrs):.5f}]")

    print(f"[3/6] Reading Naïades CSV ({NAIADES_CSV.stat().st_size//1024} KB)")
    df = pd.read_csv(NAIADES_CSV)
    print(f"      raw rows: {len(df)}, unique stations: {df['station_id'].nunique()}")

    # Filter inside mosaic bbox
    in_bbox = ((df['lon'] >= bounds.left) & (df['lon'] <= bounds.right)
               & (df['lat'] >= bounds.bottom) & (df['lat'] <= bounds.top))
    df = df[in_bbox].copy()
    print(f"      in-bbox rows: {len(df)}")

    # Temporal window
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    img_dt = pd.to_datetime(IMAGE_DATE)
    dt = (df['date'] - img_dt).abs()
    df = df[dt <= pd.Timedelta(days=DATE_WINDOW)].copy()
    print(f"      ±{DATE_WINDOW}d of {IMAGE_DATE}: {len(df)} rows")

    print(f"[4/6] Sampling {SAMPLE_W}×{SAMPLE_W} patches ...")
    out_rows = []
    for _, row in df.iterrows():
        rr, cc = lonlat_to_rc(row['lon'], row['lat'], transform)
        if not (0 <= rr < H and 0 <= cc < W):
            continue
        vals = sample_window(rrs, rr, cc, SAMPLE_W)
        if np.any(np.isnan(vals)):
            continue
        rec = {
            'station_id': row['station_id'],
            'lat': row['lat'], 'lon': row['lon'],
            'date': row['date'],
            'label': row['label'],
        }
        for n, v in zip(BAND_NAMES, vals):
            rec[n] = float(v)
        out_rows.append(rec)

    out = pd.DataFrame(out_rows)
    print(f"[5/6] Matchup table built: {len(out)} rows")
    print(out[['label'] + BAND_NAMES].describe().round(4))

    out.to_pickle(OUT_DIR / "matchups.pkl")
    out.to_csv(OUT_DIR / "matchups.csv", index=False)
    print(f"[6/6] Wrote {OUT_DIR / 'matchups.pkl'} + matchups.csv")


if __name__ == "__main__":
    main()
