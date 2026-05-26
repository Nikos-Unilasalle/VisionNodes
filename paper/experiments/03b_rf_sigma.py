"""
03b_rf_sigma.py
================

Generate a per-pixel σ raster from the RandomForest by reading individual
tree predictions, then std across trees.

Outputs:
  out/rouen_sigma_rf.tif
  out/rouen_panel.png   — μ + σ side-by-side
"""
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from sklearn.ensemble import RandomForestRegressor
from scipy.ndimage import binary_erosion
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE  = Path(__file__).parent
OUT   = HERE / "out"
ROOT  = HERE.parents[1]
INFER = ROOT / "engine/plugins/copernicus_cache/165386a2bcd3d7.tif"
BANDS = ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]
FEATURES = BANDS + ["Red_Green", "Blue_Green", "Red_NIR", "NIR_SWIR1", "Red_SWIR1",
                    "NDTI", "MNDWI", "log_Red", "log_SWIR1"]


def dos1(b):
    b = b.astype(np.float32).copy()
    f = b[np.isfinite(b)]
    if f.size > 0 and float(np.percentile(f, 99)) > 10:
        b /= 10000
    for i in range(b.shape[0]):
        pos = b[i][b[i] > 0]
        if pos.size == 0: continue
        d = float(np.percentile(pos, 0.1))
        m = float(np.median(pos))
        if d > 0.5 * m: d = 0.0
        b[i] = np.clip(b[i] - d, 0, None)
    return b / np.pi


def add_features(df):
    eps = 1e-6
    df = df.copy()
    df["Red_Green"]  = df["Red"] / (df["Green"] + eps)
    df["Blue_Green"] = df["Blue"] / (df["Green"] + eps)
    df["Red_NIR"]    = df["Red"] / (df["NIR"] + eps)
    df["NIR_SWIR1"]  = df["NIR"] / (df["SWIR1"] + eps)
    df["Red_SWIR1"]  = df["Red"] / (df["SWIR1"] + eps)
    df["NDTI"]       = (df["Red"] - df["Green"]) / (df["Red"] + df["Green"] + eps)
    df["MNDWI"]      = (df["Green"] - df["SWIR1"]) / (df["Green"] + df["SWIR1"] + eps)
    df["log_Red"]    = np.log(df["Red"] + eps)
    df["log_SWIR1"]  = np.log(df["SWIR1"] + eps)
    return df


def add_feats_arr(arr):
    B, G, R, N, S1, S2 = arr
    eps = 1e-6
    return np.stack([B, G, R, N, S1, S2,
                     R / (G + eps), B / (G + eps), R / (N + eps),
                     N / (S1 + eps), R / (S1 + eps),
                     (R - G) / (R + G + eps),
                     (G - S1) / (G + S1 + eps),
                     np.log(R + eps), np.log(S1 + eps)], axis=0)


def main():
    df = pd.read_pickle(OUT / "matchups.pkl")
    df = add_features(df)
    X_tr = df[FEATURES].values
    y_tr = np.log1p(df["label"].values)

    print("Training 300-tree RF on all 563 matchups ...")
    rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=2,
                                random_state=42, n_jobs=-1)
    rf.fit(X_tr, y_tr)

    print(f"Loading {INFER} ...")
    with rasterio.open(INFER) as r:
        raw = r.read()
        meta = r.meta.copy()
    rrs = dos1(raw)

    G = rrs[1]; N = rrs[3]
    ndwi = (G - N) / (G + N + 1e-6)
    water = binary_erosion(ndwi > 0.1, iterations=2)
    H, W = water.shape

    feats = add_feats_arr(rrs)
    rows, cols = np.where(water)
    X_pix = feats[:, rows, cols].T

    print(f"Predicting μ+σ over {len(X_pix):,} water pixels (300 trees each) ...")
    # Each tree's prediction
    tree_preds = np.array([est.predict(X_pix) for est in rf.estimators_])  # (n_trees, N)
    tree_preds_lin = np.expm1(np.clip(tree_preds, -10, 20))
    mu_lin    = tree_preds_lin.mean(axis=0)
    sigma_lin = tree_preds_lin.std(axis=0)
    mu_lin    = np.clip(mu_lin, 0, 200)
    sigma_lin = np.clip(sigma_lin, 0, 200)

    mu_raster    = np.full((H, W), np.nan, dtype=np.float32)
    sigma_raster = np.full((H, W), np.nan, dtype=np.float32)
    mu_raster[rows, cols]    = mu_lin
    sigma_raster[rows, cols] = sigma_lin
    print(f"μ:  mean={np.nanmean(mu_raster):.2f}  med={np.nanmedian(mu_raster):.2f}  max={np.nanmax(mu_raster):.2f}")
    print(f"σ:  mean={np.nanmean(sigma_raster):.2f}  med={np.nanmedian(sigma_raster):.2f}  max={np.nanmax(sigma_raster):.2f}")

    meta.update(count=1, dtype="float32", nodata=np.nan)
    with rasterio.open(OUT / "rouen_mu_rf.tif", "w", **meta) as w: w.write(mu_raster, 1)
    with rasterio.open(OUT / "rouen_sigma_rf.tif", "w", **meta) as w: w.write(sigma_raster, 1)

    # Panel plot
    fig, axes = plt.subplots(1, 2, figsize=(13, 6), facecolor="#1a1a1a")
    im0 = axes[0].imshow(mu_raster, cmap="viridis", vmin=0, vmax=20)
    axes[0].set_title("Mean turbidity μ — RandomForest", color="white")
    cb0 = plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.02)
    cb0.set_label("NTU", color="white")
    cb0.ax.yaxis.set_tick_params(color="white")
    plt.setp(plt.getp(cb0.ax.axes, "yticklabels"), color="white")

    im1 = axes[1].imshow(sigma_raster, cmap="inferno", vmin=0, vmax=15)
    axes[1].set_title("Per-pixel σ — tree spread (300 trees)", color="white")
    cb1 = plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.02)
    cb1.set_label("NTU", color="white")
    cb1.ax.yaxis.set_tick_params(color="white")
    plt.setp(plt.getp(cb1.ax.axes, "yticklabels"), color="white")

    for ax in axes:
        ax.tick_params(colors="white"); ax.axis("off")

    plt.tight_layout()
    plt.savefig(OUT / "rouen_panel.png", dpi=140, bbox_inches="tight", facecolor="#1a1a1a")
    plt.close()
    print(f"Wrote {OUT/'rouen_panel.png'}, μ.tif, σ.tif")


if __name__ == "__main__":
    main()
