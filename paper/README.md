# Preprint: Interpretable Sentinel-2 Turbidity Mapping

LaTeX source for the manuscript.

## Build

```bash
# Option A — Tectonic (lightweight, single binary)
brew install tectonic
./build.sh

# Option B — MacTeX (full distro)
brew install --cask mactex-no-gui
eval "$(/usr/libexec/path_helper)"
./build.sh
```

Output: `main.pdf`.

## Required figures (drop into `figs/`)

Export each from VNStudio while the pipeline is running:

| Filename | Source node | How |
|---|---|---|
| `figs/mu_raster.png` | `raster_mean` (Mean NTU Raster μ) | Right-click → Export PNG |
| `figs/sigma_raster.png` | `raster_std` | Right-click → Export PNG |
| `figs/histograms.png` | `apply` (Ensemble Apply preview) | Screenshot the preview panel |
| `figs/wfd_distribution.png` | `geo_turbidity_stats` expanded view | Screenshot the WFD panel |

Optional extras for the preprint:

- `figs/pipeline_screenshot.png` — full canvas screenshot (Cmd+Shift+F + screenshot)
- `figs/training_scatter.png` — predicted vs. observed NTU on the held-out 20% split
- `figs/best_formula.png` — Inspector showing `BEST_FORMULA` text

## Editing

- `main.tex` — manuscript body
- `refs.bib` — bibliography
- Section/figure labels use `sec:` and `fig:` prefixes

Compile after any edit:

```bash
./build.sh
```
