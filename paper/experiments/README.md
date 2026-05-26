# Offline experiment scripts

Reproduce the model comparison without VNStudio. All paths relative to repo root.

## Requirements

```bash
pip install gplearn scikit-learn pandas numpy rasterio matplotlib scipy
```

## Run

```bash
python 01_build_matchups.py       # build matchups.pkl from CSV + mosaic
python 02_compare_models.py        # 5-fold × 3-repeat CV across 6 model strategies
python 03_inference_rouen.py       # apply best to Rouen tile -> GeoTIFF + PNG
```

## Outputs (`out/`)

- `matchups.pkl` / `matchups.csv` — 563 satellite-station rows
- `model_compare.csv` — R²/RMSE/slope per strategy
- `scatter_*.png` — predicted-vs-observed per model
- `rouen_mu.tif` — final NTU prediction raster (best model)
- `rouen_sigma.tif` — ensemble σ (if best is GP)
- `rouen_overview.png` — color preview for paper

## Strategies compared

| Name | Idea |
|---|---|
| GP_baseline | gplearn ensemble, no rebalance |
| GP_subsample_0.30 | Drop 70% of Clear (label<5) |
| GP_subsample_0.50 | Drop 50% of Clear |
| GP_sample_weight | Inverse-class-freq weights, no row drop |
| RandomForest | 200 trees, log-target |
| HistGradientBoosting | sklearn HGB, log-target |
