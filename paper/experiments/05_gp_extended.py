"""
05_gp_extended.py
==================

Push GP much further than `02_compare_models.py`:

  - population_size : 5 000
  - generations     : 300
  - n_ensemble      : 30 seeds
  - parsimony       : 0.0001 (let bigger trees survive)
  - init_depth      : (3, 8)
  - tournament_size : 50
  - function_set    : {+, -, *, /, log, sqrt, inv, pow2}
  - sample weighting: continuous, 1/density(y) via KDE
  - validation      : 5-fold × 2 repeats CV (10 folds total)
  - leak guard      : split by station_id (no station in both train & test)

Total budget: ~3h on a modern laptop. Outputs:

  out/gp_extended.csv            — per-seed and aggregated CV metrics
  out/gp_extended_progress.log   — per-generation best fitness snapshot
  out/gp_extended_formulas.txt   — top expression per seed
  out/scatter_GP_extended.png    — final scatter
"""

from __future__ import annotations

import json, time, sys, math, os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde, spearmanr
from sklearn.model_selection import GroupKFold
from sklearn.metrics import r2_score, mean_squared_error
from gplearn.genetic import SymbolicRegressor
from gplearn.functions import make_function

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
OUT  = HERE / "out"
OUT.mkdir(exist_ok=True)
LOG  = OUT / "gp_extended_progress.log"
CSV  = OUT / "gp_extended.csv"
FRM  = OUT / "gp_extended_formulas.txt"
PNG  = OUT / "scatter_GP_extended.png"

BANDS = ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]
FEATURES = BANDS + [
    "Red_Green", "Blue_Green", "Red_NIR", "NIR_SWIR1", "Red_SWIR1",
    "NDTI", "MNDWI", "log_Red", "log_SWIR1",
]

# ── Extended GP config ────────────────────────────────────────────────────
POPULATION   = 5000
GENERATIONS  = 300
N_ENSEMBLE   = 30
PARSIMONY    = 0.0001
TOURNAMENT   = 50
INIT_DEPTH   = (3, 8)
P_CROSSOVER  = 0.70
P_SUB_MUT    = 0.12
P_HOIST_MUT  = 0.05
P_POINT_MUT  = 0.08
MAX_SAMPLES  = 0.9
SEED_BASE    = 423
LOG_TARGET   = True

# Repeated K-fold by station_id (no station leak)
N_SPLITS     = 5
N_REPEATS    = 2


# ── Custom functions ──────────────────────────────────────────────────────
def _protected_inv(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(np.abs(x) > 1e-6, 1.0 / x, 0.0)
    return out


def _protected_pow2(x):
    return np.clip(x * x, -1e6, 1e6)


inv_fn  = make_function(function=_protected_inv,  name="inv",  arity=1)
pow2_fn = make_function(function=_protected_pow2, name="pow2", arity=1)

FUNCTION_SET = ("add", "sub", "mul", "div", "log", "sqrt", inv_fn, pow2_fn)


# ── Feature engineering (mirrors 02_compare_models) ───────────────────────
def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    eps = 1e-6
    df["Red_Green"]  = df["Red"]  / (df["Green"] + eps)
    df["Blue_Green"] = df["Blue"] / (df["Green"] + eps)
    df["Red_NIR"]    = df["Red"]  / (df["NIR"]   + eps)
    df["NIR_SWIR1"]  = df["NIR"]  / (df["SWIR1"] + eps)
    df["Red_SWIR1"]  = df["Red"]  / (df["SWIR1"] + eps)
    df["NDTI"]       = (df["Red"] - df["Green"]) / (df["Red"] + df["Green"] + eps)
    df["MNDWI"]      = (df["Green"] - df["SWIR1"]) / (df["Green"] + df["SWIR1"] + eps)
    df["log_Red"]    = np.log(df["Red"] + eps)
    df["log_SWIR1"]  = np.log(df["SWIR1"] + eps)
    return df


# ── Continuous sample weighting via KDE ───────────────────────────────────
def density_weights(y: np.ndarray, bandwidth: float = 0.3) -> np.ndarray:
    """w_i = 1 / kde(y_i) normalised to mean 1. Heavy weight on rare labels."""
    y_log = np.log1p(y)
    kde   = gaussian_kde(y_log, bw_method=bandwidth)
    dens  = kde(y_log) + 1e-6
    w     = 1.0 / dens
    w     = w * len(y) / w.sum()
    # Clip extreme weights to avoid pure-outlier optimisation
    w = np.clip(w, 0.05, 20.0)
    w     = w * len(y) / w.sum()
    return w.astype(np.float64)


# ── Single-seed GP fit ────────────────────────────────────────────────────
def fit_one_gp(X_tr, y_tr, weights, seed: int, log_path: Path):
    """Returns the trained regressor + final fitness."""
    yt = np.log1p(y_tr) if LOG_TARGET else y_tr.astype(np.float64)

    gp = SymbolicRegressor(
        population_size=POPULATION,
        generations=GENERATIONS,
        tournament_size=TOURNAMENT,
        init_depth=INIT_DEPTH,
        stopping_criteria=0.001,
        p_crossover=P_CROSSOVER,
        p_subtree_mutation=P_SUB_MUT,
        p_hoist_mutation=P_HOIST_MUT,
        p_point_mutation=P_POINT_MUT,
        max_samples=MAX_SAMPLES,
        parsimony_coefficient=PARSIMONY,
        function_set=FUNCTION_SET,
        random_state=seed,
        n_jobs=1,
        verbose=0,
    )
    t0 = time.time()
    gp.fit(X_tr.values, yt, sample_weight=weights)
    elapsed = time.time() - t0

    # Log generation-level fitness from gp.run_details_ (gplearn stores it)
    rd = gp.run_details_
    if rd and "generation" in rd:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n--- seed {seed}  ({elapsed:.0f}s)\n")
            for i, gen in enumerate(rd["generation"]):
                if i % 25 == 0 or i == len(rd["generation"]) - 1:
                    fit_best = rd.get("best_fitness", [None] * len(rd["generation"]))[i]
                    fit_mean = rd.get("average_fitness", [None] * len(rd["generation"]))[i]
                    f.write(f"  gen {gen:3d}  best={fit_best:.4f}  mean={fit_mean:.4f}\n")

    return gp


def predict_gp(gp, X):
    p = gp.predict(X.values)
    if LOG_TARGET:
        p = np.expm1(np.clip(p, -10, 20))
    return np.clip(p, 0, 1000)


def main():
    df = pd.read_pickle(OUT / "matchups.pkl")
    df = add_features(df)
    X  = df[FEATURES].astype(np.float32)
    y  = df["label"].to_numpy(dtype=np.float64)
    groups = df["station_id"].astype(str).to_numpy()

    n_stations = len(set(groups))
    print(f"Loaded {len(df)} matchups across {n_stations} stations")
    print(f"Configuration:")
    print(f"  population={POPULATION}  generations={GENERATIONS}  ensemble={N_ENSEMBLE}")
    print(f"  parsimony={PARSIMONY}  tournament={TOURNAMENT}  init_depth={INIT_DEPTH}")
    print(f"  function_set=add,sub,mul,div,log,sqrt,inv,pow2")
    print(f"  sample_weight=continuous KDE  log_target={LOG_TARGET}")
    print(f"  CV: GroupKFold n_splits={N_SPLITS} × n_repeats={N_REPEATS} (split by station_id)")

    LOG.write_text(f"Extended GP run — {time.strftime('%Y-%m-%d %H:%M:%S')}\n", encoding="utf-8")

    # Outer CV loop with station-level grouping
    all_results = []   # one row per (repeat, fold)
    scatter_yt, scatter_yp = [], []
    formulas_per_seed = {}

    seeds = list(range(SEED_BASE, SEED_BASE + N_ENSEMBLE))

    rng = np.random.default_rng(SEED_BASE)
    for repeat_idx in range(N_REPEATS):
        perm = rng.permutation(len(set(groups)))
        # Build a station permutation map so GroupKFold sees stations in random order
        station_list = np.array(sorted(set(groups)))
        rng.shuffle(station_list)
        station_to_perm = {s: i for i, s in enumerate(station_list)}
        groups_perm = np.array([station_to_perm[g] for g in groups])

        gkf = GroupKFold(n_splits=N_SPLITS)
        for fold_idx, (tr, te) in enumerate(gkf.split(X, y, groups_perm)):
            t0 = time.time()
            X_tr, X_te = X.iloc[tr], X.iloc[te]
            y_tr, y_te = y[tr], y[te]

            weights = density_weights(y_tr)
            print(f"\n[repeat {repeat_idx + 1}/{N_REPEATS}  fold {fold_idx + 1}/{N_SPLITS}]"
                  f"  train={len(tr)}  test={len(te)}  stations_test={len(set(groups[te]))}")
            print(f"  weights: min={weights.min():.2f}  max={weights.max():.2f}  mean={weights.mean():.2f}")

            preds_te = np.zeros((N_ENSEMBLE, len(te)), dtype=np.float32)
            for k, seed in enumerate(seeds):
                gp = fit_one_gp(X_tr, y_tr, weights, seed, LOG)
                preds_te[k] = predict_gp(gp, X_te)
                if repeat_idx == 0 and fold_idx == 0:
                    formulas_per_seed[seed] = str(gp._program)
                if (k + 1) % 5 == 0:
                    elapsed = time.time() - t0
                    print(f"    seed {k + 1}/{N_ENSEMBLE} fitted  (elapsed {elapsed:.0f}s)")

            mu = preds_te.mean(axis=0)
            sg = preds_te.std(axis=0)

            r2   = float(r2_score(y_te, mu))
            rmse = float(np.sqrt(mean_squared_error(y_te, mu)))
            rho  = spearmanr(y_te, mu).correlation or 0.0
            slope, intercept = np.polyfit(y_te, mu, 1)

            print(f"  fold result: R²={r2:.3f}  RMSE={rmse:.2f}  ρ={rho:.3f}  slope={slope:.3f}  σ̄={sg.mean():.2f}")
            all_results.append({
                "repeat": repeat_idx, "fold": fold_idx,
                "n_train": len(tr), "n_test": len(te),
                "R2": r2, "RMSE": rmse, "rho": rho,
                "slope": float(slope), "intercept": float(intercept),
                "sigma_mean": float(sg.mean()),
            })
            scatter_yt.extend(y_te); scatter_yp.extend(mu)

            # Incremental save
            pd.DataFrame(all_results).to_csv(CSV, index=False)
            with open(FRM, "w", encoding="utf-8") as f:
                for s, expr in formulas_per_seed.items():
                    f.write(f"seed {s}:\n  {expr}\n\n")

    # Aggregate
    res = pd.DataFrame(all_results)
    summary = {
        "R2_mean":    float(res["R2"].mean()),
        "R2_std":     float(res["R2"].std()),
        "RMSE_mean":  float(res["RMSE"].mean()),
        "RMSE_std":   float(res["RMSE"].std()),
        "rho_mean":   float(res["rho"].mean()),
        "slope_mean": float(res["slope"].mean()),
        "sigma_mean": float(res["sigma_mean"].mean()),
        "n_folds":    int(len(res)),
        "n_seeds":    N_ENSEMBLE,
    }
    print("\n=== AGGREGATE ===")
    print(json.dumps(summary, indent=2))
    pd.DataFrame([summary]).to_csv(OUT / "gp_extended_summary.csv", index=False)

    # Scatter
    yt = np.array(scatter_yt); yp = np.array(scatter_yp)
    fig, ax = plt.subplots(figsize=(5.5, 5.5), facecolor="#1a1a1a")
    ax.set_facecolor("#0d0d0d")
    ax.scatter(yt, yp, s=12, alpha=0.45, c="#4a7fc8", edgecolors="none")
    lo, hi = 0, max(yt.max(), yp.max(), 50) * 1.05
    ax.plot([lo, hi], [lo, hi], "--", color="#aaa", lw=0.8, label="1:1")
    slope, intercept = np.polyfit(yt, yp, 1)
    ax.plot([lo, hi], [slope * lo + intercept, slope * hi + intercept], "-",
            color="#ff7f0e", lw=1.2, label=f"y = {slope:.2f}x + {intercept:.1f}")
    ax.set_xlabel("Observed NTU", color="white")
    ax.set_ylabel("Predicted NTU", color="white")
    ax.tick_params(colors="white")
    for s in ax.spines.values(): s.set_color("#555")
    ax.set_title(
        f"GP_extended (30 seeds, 5k pop, 300 gen)\n"
        f"R²={summary['R2_mean']:.3f}  RMSE={summary['RMSE_mean']:.1f}  ρ={summary['rho_mean']:.3f}",
        color="white", fontsize=10,
    )
    ax.legend(loc="upper left", framealpha=0.7, facecolor="#2a2a2a",
              edgecolor="#555", labelcolor="white", fontsize=9)
    ax.grid(True, alpha=0.2, color="white")
    plt.tight_layout()
    plt.savefig(PNG, dpi=140, bbox_inches="tight", facecolor="#1a1a1a")
    plt.close()
    print(f"\nWrote {CSV}, {FRM}, {PNG}")


if __name__ == "__main__":
    main()
