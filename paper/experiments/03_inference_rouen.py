"""
03_inference_rouen.py
=====================

Apply the best model found in 02_compare_models.py to the Rouen inference tile.
Picks the model with the highest R², refits on the full matchup table, then
predicts NTU on every water pixel of the Rouen scene.

Outputs:
  out/rouen_mu.tif      — predicted NTU raster (single band, float32, with CRS)
  out/rouen_sigma.tif   — per-pixel ensemble std-dev (when applicable)
  out/rouen_overview.png — color-mapped preview for the paper
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_bounds

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import warnings
warnings.filterwarnings("ignore")

HERE   = Path(__file__).parent
OUT    = HERE / "out"
ROOT   = HERE.parents[1]
INFER  = ROOT / "engine/plugins/copernicus_cache/165386a2bcd3d7.tif"
SUMMARY = OUT / "model_compare.csv"

BANDS  = ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]


def dos1(bands):
    bands = bands.astype(np.float32).copy()
    finite = bands[np.isfinite(bands)]
    if finite.size > 0:
        p99 = float(np.percentile(finite, 99))
        if p99 > 10.0:
            bands /= 10000.0
    for i in range(bands.shape[0]):
        pos = bands[i][bands[i] > 0]
        if pos.size == 0:
            continue
        dark = float(np.percentile(pos, 0.1))
        med  = float(np.median(pos))
        if dark > 0.5 * med:
            dark = 0.0
        bands[i] = np.clip(bands[i] - dark, 0, None)
    return bands / np.pi


def add_features_arr(arr: np.ndarray) -> np.ndarray:
    """arr shape (6, H, W) -> features (Nfeat, H, W)."""
    B, G, R, N, S1, S2 = arr
    eps = 1e-6
    feats = [
        B, G, R, N, S1, S2,
        R / (G + eps),
        B / (G + eps),
        R / (N + eps),
        N / (S1 + eps),
        R / (S1 + eps),
        (R - G) / (R + G + eps),
        (G - S1) / (G + S1 + eps),
        np.log(R + eps),
        np.log(S1 + eps),
    ]
    return np.stack(feats, axis=0)


FEATURES = BANDS + [
    "Red_Green", "Blue_Green", "Red_NIR", "NIR_SWIR1", "Red_SWIR1",
    "NDTI", "MNDWI", "log_Red", "log_SWIR1",
]


def main():
    # 1. Pick best model from summary
    summary = pd.read_csv(SUMMARY)
    best = summary.sort_values("R2", ascending=False).iloc[0]
    print(f"Best model: {best['name']}  R²={best['R2']:.3f}  slope={best['slope']:.3f}")

    # 2. Load full matchup table, refit chosen model on ALL rows
    df_match = pd.read_pickle(OUT / "matchups.pkl")
    # re-derive features
    from importlib import import_module
    import sys; sys.path.insert(0, str(HERE))
    cmp_mod = import_module("02_compare_models")  # safe — same dir
    df_match = cmp_mod.add_features(df_match)
    X_train  = df_match[FEATURES]
    y_train  = df_match["label"].to_numpy(dtype=np.float64)

    name = best["name"]
    if name == "RandomForest":
        from sklearn.ensemble import RandomForestRegressor
        m = RandomForestRegressor(n_estimators=300, min_samples_leaf=2,
                                   random_state=42, n_jobs=-1)
        m.fit(X_train, np.log1p(y_train))
        predict = lambda X: np.expm1(np.clip(m.predict(X), -10, 20))
    elif name == "HistGradientBoosting":
        from sklearn.ensemble import HistGradientBoostingRegressor
        m = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05,
                                          max_depth=6, min_samples_leaf=10,
                                          random_state=42)
        m.fit(X_train, np.log1p(y_train))
        predict = lambda X: np.expm1(np.clip(m.predict(X), -10, 20))
    else:
        # GP ensemble (5 seeds), reuse helper from comparison module
        from gplearn.genetic import SymbolicRegressor
        if name == "GP_sample_weight":
            w = np.ones_like(y_train, dtype=np.float64)
            n_c = float((y_train < 5).sum()); n_t = float((y_train >= 5).sum())
            w[y_train < 5]  = 1.0 / n_c
            w[y_train >= 5] = 1.0 / n_t
            w *= len(y_train) / w.sum()
        else:
            w = None
        if name.startswith("GP_subsample"):
            frac = float(name.split("_")[-1])
            rng = np.random.default_rng(42)
            ci = np.where(y_train < 5)[0]
            ti = np.where(y_train >= 5)[0]
            kc = rng.choice(ci, size=max(20, int(len(ci) * frac)), replace=False)
            keep = np.concatenate([kc, ti])
            X_train = X_train.iloc[keep]
            y_train = y_train[keep]
            w = None
        models = []
        for s in range(423, 428):
            gp = SymbolicRegressor(
                population_size=1000, generations=50, stopping_criteria=0.01,
                p_crossover=0.7, p_subtree_mutation=0.1, p_hoist_mutation=0.05,
                p_point_mutation=0.1, max_samples=0.9, verbose=0,
                parsimony_coefficient=0.001, random_state=s,
                function_set=("add", "sub", "mul", "div", "log", "sqrt"),
            )
            if w is not None:
                gp.fit(X_train.values, np.log1p(y_train), sample_weight=w)
            else:
                gp.fit(X_train.values, np.log1p(y_train))
            models.append(gp)
        def predict(X):
            ps = np.array([np.expm1(np.clip(m.predict(X.values if hasattr(X, "values") else X), -10, 20))
                            for m in models])
            return ps.mean(axis=0), ps.std(axis=0)

    # 3. Load Rouen tile + DOS-1
    print(f"Loading {INFER} ...")
    with rasterio.open(INFER) as r:
        raw = r.read()
        meta = r.meta.copy()
        transform = r.transform
        crs = r.crs
    rrs = dos1(raw)
    print(f"Rrs range: [{np.nanmin(rrs):.5f}, {np.nanmax(rrs):.5f}]  shape={rrs.shape}")

    # 4. NDWI water mask
    G = rrs[1]; N = rrs[3]
    ndwi = (G - N) / (G + N + 1e-6)
    water = ndwi > 0.1
    # quick erosion: kernel 3x3 binary erode via shifts
    from scipy.ndimage import binary_erosion
    water = binary_erosion(water, iterations=2)
    print(f"Water pixels: {int(water.sum()):,}")

    # 5. Compute features only over water (saves a lot of memory)
    feats = add_features_arr(rrs)
    H, W  = water.shape
    rows, cols = np.where(water)
    X_pix = feats[:, rows, cols].T  # (N, 15)
    X_pix_df = pd.DataFrame(X_pix, columns=FEATURES)
    print(f"Predicting on {len(X_pix_df):,} water pixels ...")

    has_sigma = False
    if name.startswith("GP"):
        mu_flat, sigma_flat = predict(X_pix_df)
        has_sigma = True
    else:
        mu_flat = predict(X_pix_df)

    # Cap at 200 NTU for stats sanity
    mu_flat = np.clip(mu_flat, 0, 200)

    mu_raster = np.full((H, W), np.nan, dtype=np.float32)
    mu_raster[rows, cols] = mu_flat
    print(f"μ stats: mean={np.nanmean(mu_raster):.2f}  median={np.nanmedian(mu_raster):.2f}  "
          f"min={np.nanmin(mu_raster):.2f}  max={np.nanmax(mu_raster):.2f}")

    # 6. Save raster (GTiff)
    out_meta = meta.copy()
    out_meta.update(count=1, dtype="float32", nodata=np.nan)
    with rasterio.open(OUT / "rouen_mu.tif", "w", **out_meta) as w:
        w.write(mu_raster, 1)
    print(f"Wrote {OUT / 'rouen_mu.tif'}")

    if has_sigma:
        sigma_raster = np.full((H, W), np.nan, dtype=np.float32)
        sigma_raster[rows, cols] = sigma_flat
        with rasterio.open(OUT / "rouen_sigma.tif", "w", **out_meta) as w:
            w.write(sigma_raster, 1)
        print(f"Wrote {OUT / 'rouen_sigma.tif'}")

    # 7. Overview plot
    fig, ax = plt.subplots(figsize=(8, 6), facecolor="#1a1a1a")
    im = ax.imshow(mu_raster, cmap="viridis", vmin=0, vmax=20)
    cbar = plt.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
    cbar.set_label("Predicted NTU", color="white")
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color="white")
    ax.set_title(f"Rouen inference — best model: {name}",
                 color="white", fontsize=11)
    ax.tick_params(colors="white")
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(OUT / "rouen_overview.png", dpi=150,
                bbox_inches="tight", facecolor="#1a1a1a")
    plt.close()
    print(f"Wrote {OUT / 'rouen_overview.png'}")


if __name__ == "__main__":
    main()
