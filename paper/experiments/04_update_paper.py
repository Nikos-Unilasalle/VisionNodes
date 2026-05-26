"""
04_update_paper.py
==================

Inject the model-comparison results into the LaTeX preprint.
Adds (or replaces) a `model_compare` table block and a paragraph
in §Results referencing the best-performing strategy.

Run after 02_compare_models.py + 03_inference_rouen.py.
"""
from pathlib import Path
import pandas as pd

HERE  = Path(__file__).parent
OUT   = HERE / "out"
PAPER = HERE.parents[1] / "main.tex"

SUMMARY_CSV = OUT / "model_compare.csv"

TABLE_TAG_START = "% <<MODEL_COMPARE_TABLE_START>>"
TABLE_TAG_END   = "% <<MODEL_COMPARE_TABLE_END>>"


def build_table(df: pd.DataFrame) -> str:
    df = df.sort_values("R2", ascending=False).reset_index(drop=True)
    body = []
    for _, r in df.iterrows():
        name = r["name"].replace("_", r"\_")
        body.append(
            f"{name} & {r['R2']:.3f} & {r['R2_std']:.3f} & "
            f"{r['RMSE']:.2f} & {r['rho']:.3f} & {r['slope']:.3f} \\\\"
        )
    rows = "\n".join(body)
    return rf"""{TABLE_TAG_START}
\begin{{table}}[h]
\centering
\caption{{Cross-validated model comparison (RepeatedKFold, 5 splits × 3 repeats, n=563 matchups). All targets log-transformed before fitting. Best R² in bold.}}
\label{{tab:modelcompare}}
\small
\begin{{tabular}}{{lrrrrr}}
\toprule
Model & R² & $\sigma_{{R^2}}$ & RMSE (NTU) & Spearman $\rho$ & Slope \\
\midrule
{rows}
\bottomrule
\end{{tabular}}
\end{{table}}
{TABLE_TAG_END}
"""


def main():
    summary = pd.read_csv(SUMMARY_CSV)
    tex = build_table(summary)
    out = PAPER.read_text(encoding="utf-8")

    if TABLE_TAG_START in out and TABLE_TAG_END in out:
        # replace existing block
        before = out.split(TABLE_TAG_START)[0]
        after  = out.split(TABLE_TAG_END)[1]
        out = before + tex + after
    else:
        # insert before §Discussion
        marker = r"\section{Discussion}"
        out = out.replace(marker, tex + "\n\n" + marker, 1)

    PAPER.write_text(out, encoding="utf-8")
    print(f"Patched {PAPER}")
    best = summary.sort_values("R2", ascending=False).iloc[0]
    print(f"Best model: {best['name']}  R²={best['R2']:.3f}  slope={best['slope']:.3f}")


if __name__ == "__main__":
    main()
