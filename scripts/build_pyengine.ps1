# build_pyengine.ps1 — Bundle a self-contained Python engine into the Tauri app (Windows).
#
# Produces a fully relocatable Python (python-build-standalone, via uv) with all
# engine dependencies installed, plus a copy of the engine source, under:
#     src-tauri/resources/pyengine/   (the interpreter + site-packages)
#     src-tauri/resources/engine/     (engine.py, plugins, registry…)
#
# These get bundled into VisionNodes.exe by `tauri build`
# (see tauri.conf.json -> bundle.resources). The app then launches:
#     Resources/pyengine/Scripts/python.exe  Resources/engine/engine.py
#
# Run once before `npm run tauri build` (or whenever requirements.txt changes).
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts/build_pyengine.ps1

$ErrorActionPreference = "Stop"

# $PSScriptRoot is <repo>/scripts, so one parent reaches the repo root.
$ROOT = Split-Path -Parent $PSScriptRoot
$PYVER = "3.12"
$RES = "$ROOT\src-tauri\resources"
$PYDEST = "$RES\pyengine"
$ENGDEST = "$RES\engine"

Write-Host "▶ VNStudio Python engine bundler (Windows)"
Write-Host "  root: $ROOT"

# ── 0. Require uv ──
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "✗ 'uv' not found. Install it: https://docs.astral.sh/uv/"
  Write-Host "  Windows installer: https://astral.sh/uv/install.ps1"
  Write-Host "  Or: powershell -ExecutionPolicy ByPass -c 'irm https://astral.sh/uv/install.ps1 | iex'"
  exit 1
}

# ── 1. Get a standalone CPython and copy it into resources ──
Write-Host "▶ Fetching standalone CPython $PYVER via uv…"
uv python install "$PYVER"
$PYBIN = uv python find "$PYVER"
$PYHOME = Split-Path -Parent (Split-Path -Parent $PYBIN)  # …\cpython-3.12.x-windows-x64\
Write-Host "  source interpreter: $PYHOME"

Write-Host "▶ Copying interpreter → $PYDEST"
if (Test-Path $PYDEST) {
  Remove-Item -Recurse -Force $PYDEST
}
New-Item -ItemType Directory -Path $PYDEST -Force > $null
Copy-Item -Recurse "$PYHOME\*" -Destination $PYDEST

$PY = "$PYDEST\Scripts\python.exe"
if (-not (Test-Path $PY)) {
  Write-Host "✗ bundled python missing at $PY"
  exit 1
}

# ── 2. Install engine dependencies into the bundled interpreter ──
Write-Host "▶ Installing dependencies (this is the slow part — torch/sam2/rasterio)…"
& $PY -m ensurepip --upgrade 2> $null
& $PY -m pip install --upgrade pip
& $PY -m pip install -r "$ROOT\engine\requirements.txt"

# ── 3. Copy engine source into resources (self-contained, no caches/tests) ──
Write-Host "▶ Copying engine source → $ENGDEST"
if (Test-Path $ENGDEST) {
  Remove-Item -Recurse -Force $ENGDEST
}
New-Item -ItemType Directory -Path $ENGDEST -Force > $null

Get-ChildItem -Path "$ROOT\engine" -Recurse -Force |
  Where-Object {
    $_.FullName -notmatch '__pycache__|\.pyc$|\\tests\\|\.pytest_cache|_cache'
  } |
  ForEach-Object {
    $RelPath = $_.FullName.Substring("$ROOT\engine".Length).TrimStart('\')
    if ($_.PSIsContainer) {
      New-Item -ItemType Directory -Path "$ENGDEST\$RelPath" -Force -ErrorAction SilentlyContinue > $null
    } else {
      Copy-Item -Path $_.FullName -Destination "$ENGDEST\$RelPath" -Force
    }
  }

# ── 4. Prune to shrink the bundle ──
Write-Host "▶ Pruning bundle…"
Get-ChildItem -Path $PYDEST -Recurse -Force -Directory -Filter '__pycache__' |
  ForEach-Object { Remove-Item -Recurse -Force $_.FullName }
Get-ChildItem -Path $PYDEST -Recurse -Force -Directory -Filter 'tests' |
  Where-Object { $_.FullName -match 'site-packages' } |
  ForEach-Object { Remove-Item -Recurse -Force $_.FullName }

$DirSize = (Get-ChildItem -Path $PYDEST -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "✓ Done. Bundled python: $([Math]::Round($DirSize, 1)) MB"
Write-Host "  Next: npm run tauri build"
