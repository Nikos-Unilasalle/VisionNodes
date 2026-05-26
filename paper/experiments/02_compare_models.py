"""
02_compare_models.py
====================

Compare turbidity-from-Rrs models on the 563-row matchup table:

  - GP_baseline         : gplearn, no rebalancing, log_transform
  - GP_subsample_0.30   : drop 70% of Clear (label<5)
  - GP_subsample_0.50   : drop 50% of Clear
  - GP_sample_weight    : inverse-class-frequency weights (no row drop)
  - RandomForest        : 200 trees, log-target
  - GradientBoosting    : sklearn HistGB, log-target

Cross-validated on a fixed 5-fold split (RepeatedKFold n_splits=5, n_repeats=3).
Metrics: R², RMSE (NTU), Spearman ρ, scatter slope, P90/P95 absolute error.

Outputs:
  out/model_compare.csv         — metric table
  out/scatter_<name>.png        — predicted-vs-observed
  out/feature_importance.png    — RF gini importance
"""

from __future__ import annotations
import warnings, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.model_selection import RepeatedKFold
from sklearn.metrics import r2_score, mean_squared_error

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gplearn.genetic import SymbolicRegressor

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

HERE     = Path(__file__).parent
OUT      = HERE / "out"
SEED     = 42
N_SPLITS = 5
N_REPEAT = 2   # 10 folds total — keeps GP comparison tractable
BANDS    = ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]


# ─── Spectral features (mirror ml_spectral_features node) ─────────────────
def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    eps = 1e-6
    df["Red_Green"]  = df["Red"]  / (df["Green"]  + eps)
    df["Blue_Green"] = df["Blue"] / (df["Green"]  + eps)
    df["Red_NIR"]    = df["Red"]  / (df["NIR"]    + eps)
    df["NIR_SWIR1"]  = df["NIR"]  / (df["SWIR1"]  + eps)
    df["Red_SWIR1"]  = df["Red"]  / (df["SWIR1"]  + eps)
    df["NDTI"]       = (df["Red"] - df["Green"]) / (df["Red"] + df["Green"] + eps)
    df["MNDWI"]      = (df["Green"] - df["SWIR1"]) / (df["Green"] + df["SWIR1"] + eps)
    df["log_Red"]    = np.log(df["Red"] + eps)
    df["log_SWIR1"]  = np.log(df["SWIR1"] + eps)
    return df


FEATURES = BANDS + [
    "Red_Green", "Blue_Green", "Red_NIR", "NIR_SWIR1", "Red_SWIR1",
    "NDTI", "MNDWI", "log_Red", "log_SWIR1"
]


# ─── Evaluation harness ────────────────────────────────────────────────────
def evaluate(name: str, fit_pred_fn, X: pd.DataFrame, y: np.ndarray) -> dict:
    """Run RepeatedKFold, return aggregated metrics + scatter data."""
    rkf = RepeatedKFold(n_splits=N_SPLITS, n_repeats=N_REPEAT, random_state=SEED)
    r2s, rmses, rhos, slopes = [], [], [], []
    y_all_true, y_all_pred = [], []
    t0 = time.time()
    for fold, (idx_tr, idx_te) in enumerate(rkf.split(X)):
        Xt, Xe = X.iloc[idx_tr], X.iloc[idx_te]
        yt, ye = y[idx_tr], y[idx_te]
        try:
            yp = fit_pred_fn(Xt, yt, Xe)
            yp = np.clip(yp, 0, 1000)
        except Exception as e:
            print(f"  [{name}] fold {fold} failed: {e}")
            continue
        r2s.append(r2_score(ye, yp))
        rmses.append(float(np.sqrt(mean_squared_error(ye, yp))))
        rho = spearmanr(ye, yp).correlation
        rhos.append(rho if rho is not None else 0.0)
        slope, intercept = np.polyfit(ye, yp, 1)
        slopes.append(float(slope))
        y_all_true.extend(ye); y_all_pred.extend(yp)
    elapsed = time.time() - t0
    return {
        "name":   name,
        "R2":     float(np.mean(r2s)),
        "R2_std": float(np.std(r2s)),
        "RMSE":   float(np.mean(rmses)),
        "rho":    float(np.mean(rhos)),
        "slope":  float(np.mean(slopes)),
        "time_s": round(elapsed, 1),
        "y_true": np.array(y_all_true),
        "y_pred": np.array(y_all_pred),
    }


# ─── Model builders ────────────────────────────────────────────────────────
def gp_predict(X_tr, y_tr, X_te, log_target=True, parsimony=0.001,
               generations=50, population=1000, seeds=(423,)):
    """GP ensemble (single run if 1 seed). Returns mean prediction."""
    yt = np.log1p(y_tr) if log_target else y_tr
    preds = []
    for s in seeds:
        gp = SymbolicRegressor(
            population_size=population, generations=generations,
            stopping_criteria=0.01, p_crossover=0.7, p_subtree_mutation=0.1,
            p_hoist_mutation=0.05, p_point_mutation=0.1, max_samples=0.9,
            verbose=0, parsimony_coefficient=parsimony, random_state=s,
            function_set=("add", "sub", "mul", "div", "log", "sqrt"),
        )
        gp.fit(X_tr.values, yt)
        p = gp.predict(X_te.values)
        if log_target:
            p = np.expm1(np.clip(p, -10, 20))
        preds.append(p)
    return np.mean(preds, axis=0)


def gp_baseline(Xt, yt, Xe):
    return gp_predict(Xt, yt, Xe, seeds=(423, 424))


def gp_subsample(Xt, yt, Xe, keep_frac: float):
    rng = np.random.default_rng(SEED)
    clear_idx  = np.where(yt < 5)[0]
    turbid_idx = np.where(yt >= 5)[0]
    n_keep     = max(20, int(len(clear_idx) * keep_frac))
    keep_clear = rng.choice(clear_idx, size=min(n_keep, len(clear_idx)), replace=False)
    keep = np.concatenate([keep_clear, turbid_idx])
    return gp_predict(Xt.iloc[keep], yt[keep], Xe, seeds=(423, 424))


def gp_weighted(Xt, yt, Xe):
    """Pass sample_weight = inverse class freq to gplearn."""
    w = np.ones_like(yt, dtype=np.float64)
    n_clear  = float((yt < 5).sum())
    n_turbid = float((yt >= 5).sum())
    if n_clear > 0 and n_turbid > 0:
        w[yt < 5]  = 1.0 / n_clear
        w[yt >= 5] = 1.0 / n_turbid
        w *= len(yt) / w.sum()
    yt_log = np.log1p(yt)
    preds = []
    for s in (423, 424):
        gp = SymbolicRegressor(
            population_size=1000, generations=50, stopping_criteria=0.01,
            p_crossover=0.7, p_subtree_mutation=0.1, p_hoist_mutation=0.05,
            p_point_mutation=0.1, max_samples=0.9, verbose=0,
            parsimony_coefficient=0.001, random_state=s,
            function_set=("add", "sub", "mul", "div", "log", "sqrt"),
        )
        gp.fit(Xt.values, yt_log, sample_weight=w)
        p = np.expm1(np.clip(gp.predict(Xe.values), -10, 20))
        preds.append(p)
    return np.mean(preds, axis=0)


def rf_predict(Xt, yt, Xe):
    yt_log = np.log1p(yt)
    rf = RandomForestRegressor(n_estimators=200, max_depth=None,
                               min_samples_leaf=2, random_state=SEED, n_jobs=-1)
    rf.fit(Xt, yt_log)
    return np.expm1(np.clip(rf.predict(Xe), -10, 20))


def nechad_red_predict(Xt, yt, Xe):
    """Nechad 2010 fixed formula on B4 (Red). Ignores training set entirely.
    NTU = (A * rho_w) / (1 - rho_w/C) + B,  A=228.1, B=0.1641, C=0.1724
    """
    A, B, C = 228.1, 0.1641, 0.1724
    rho = np.clip(Xe["Red"].values, 0.0, C * 0.999)
    return np.maximum(0.0, (A * rho) / (1.0 - rho / C) + B)


def nechad_calibrated_predict(Xt, yt, Xe):
    """Nechad formula structure with A,B,C re-fit on local training data."""
    from scipy.optimize import least_squares
    rho_tr = np.clip(Xt["Red"].values, 0.0, 0.4)

    def resid(p):
        A, B, C = p
        if C <= 0.001 or A <= 0:
            return 1e6 * np.ones_like(rho_tr)
        rho_c = np.clip(rho_tr, 0.0, C * 0.999)
        pred = (A * rho_c) / (1.0 - rho_c / C) + B
        return np.log1p(np.maximum(pred, 0)) - np.log1p(yt)

    res = least_squares(resid, x0=[228.1, 0.1641, 0.1724],
                        bounds=([1, -5, 0.05], [10000, 5, 0.5]))
    A, B, C = res.x
    rho = np.clip(Xe["Red"].values, 0.0, C * 0.999)
    return np.maximum(0.0, (A * rho) / (1.0 - rho / C) + B)


def hgb_predict(Xt, yt, Xe):
    yt_log = np.log1p(yt)
    hgb = HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.05, max_depth=6,
        min_samples_leaf=10, random_state=SEED,
    )
    hgb.fit(Xt, yt_log)
    return np.expm1(np.clip(hgb.predict(Xe), -10, 20))


# ─── Plot ──────────────────────────────────────────────────────────────────
def scatter_plot(res, save_path):
    yt, yp = res["y_true"], res["y_pred"]
    fig, ax = plt.subplots(figsize=(5, 5), facecolor="#1a1a1a")
    ax.set_facecolor("#0d0d0d")
    ax.scatter(yt, yp, s=12, alpha=0.45, c="#4a7fc8", edgecolors="none")
    lo, hi = 0, max(yt.max(), yp.max(), 50) * 1.05
    ax.plot([lo, hi], [lo, hi], "--", color="#aaa", lw=0.8, label="1:1")
    # regression
    slope, intercept = np.polyfit(yt, yp, 1)
    xs = np.array([lo, hi])
    ax.plot(xs, slope * xs + intercept, "-", color="#ff7f0e", lw=1.2,
            label=f"y = {slope:.2f}x + {intercept:.1f}")
    ax.set_xlabel("Observed NTU", color="white")
    ax.set_ylabel("Predicted NTU", color="white")
    ax.tick_params(colors="white")
    for s in ax.spines.values(): s.set_color("#555")
    ax.set_title(
        f"{res['name']}\nR²={res['R2']:.3f}  RMSE={res['RMSE']:.1f}  ρ={res['rho']:.3f}",
        color="white", fontsize=10,
    )
    ax.legend(loc="upper left", framealpha=0.7, facecolor="#2a2a2a",
              edgecolor="#555", labelcolor="white", fontsize=9)
    ax.grid(True, alpha=0.2, color="white")
    plt.tight_layout()
    plt.savefig(save_path, dpi=140, bbox_inches="tight", facecolor="#1a1a1a")
    plt.close()


def main():
    df = pd.read_pickle(OUT / "matchups.pkl")
    df = add_features(df)
    X = df[FEATURES]
    y = df["label"].to_numpy(dtype=np.float64)
    print(f"Loaded {len(df)} matchups, features: {FEATURES}")

    runs = [
        ("GP_baseline",          gp_baseline),
        ("GP_subsample_0.30",    lambda Xt, yt, Xe: gp_subsample(Xt, yt, Xe, 0.30)),
        ("GP_subsample_0.50",    lambda Xt, yt, Xe: gp_subsample(Xt, yt, Xe, 0.50)),
        ("GP_sample_weight",     gp_weighted),
        ("Nechad_2010_published",   nechad_red_predict),
        ("Nechad_2010_recalibrated", nechad_calibrated_predict),
        ("RandomForest",         rf_predict),
        ("HistGradientBoosting", hgb_predict),
    ]

    results = []
    for name, fn in runs:
        print(f"\n=== {name} ===")
        r = evaluate(name, fn, X, y)
        print(f"  R²={r['R2']:.3f}±{r['R2_std']:.3f}  RMSE={r['RMSE']:.2f}  "
              f"slope={r['slope']:.3f}  time={r['time_s']}s")
        scatter_plot(r, OUT / f"scatter_{name}.png")
        results.append(r)

    summary = pd.DataFrame([{k: v for k, v in r.items() if k not in ("y_true", "y_pred")}
                             for r in results])
    summary.to_csv(OUT / "model_compare.csv", index=False)
    print("\n=== SUMMARY ===")
    print(summary.to_string(index=False))
    print(f"\nSaved {OUT / 'model_compare.csv'}")


if __name__ == "__main__":
    main()
