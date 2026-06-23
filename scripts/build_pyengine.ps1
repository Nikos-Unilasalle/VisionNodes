# build_pyengine.ps1 - Bundle a self-contained Python engine into the Tauri app (Windows).
#
# Produces a fully relocatable Python (python-build-standalone, via uv) with all
# engine dependencies installed, plus a copy of the engine source, under:
#     src-tauri/resources/pyengine/   (the interpreter + site-packages)
#     src-tauri/resources/engine/     (engine.py, plugins, registry...)
#
# These get bundled into VisionNodes.exe by `tauri build`
# (see tauri.conf.json -> bundle.resources). The app then launches:
#     Resources/pyengine/python.exe  Resources/engine/engine.py
#
# Run once before `npm run tauri build` (or whenever requirements.txt changes).
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts/build_pyengine.ps1
#
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads .ps1 as the
# system ANSI codepage; non-ASCII bytes (arrows, em dashes) become mojibake and
# break string parsing.

$ErrorActionPreference = "Stop"

# $PSScriptRoot is <repo>/scripts, so one parent reaches the repo root.
$ROOT = Split-Path -Parent $PSScriptRoot
$PYVER = "3.12"
$RES = "$ROOT\src-tauri\resources"
$PYDEST = "$RES\pyengine"
$ENGDEST = "$RES\engine"

Write-Host "> VNStudio Python engine bundler (Windows)"
Write-Host "  root: $ROOT"

# -- 0. Require uv --
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "[X] 'uv' not found. Install it: https://docs.astral.sh/uv/"
  Write-Host "  Windows installer: https://astral.sh/uv/install.ps1"
  Write-Host "  Or: powershell -ExecutionPolicy ByPass -c 'irm https://astral.sh/uv/install.ps1 | iex'"
  exit 1
}

# -- 1. Get a standalone CPython and copy it into resources --
Write-Host "> Fetching standalone CPython $PYVER via uv..."
uv python install "$PYVER"
$PYBIN = uv python find "$PYVER"
# On Windows the standalone python.exe sits at the root of the cpython dir
# (no bin/ subdir), so a single parent gives the interpreter home.
$PYHOME = Split-Path -Parent $PYBIN
Write-Host "  source interpreter: $PYHOME"

Write-Host "> Copying interpreter -> $PYDEST"
if (Test-Path $PYDEST) {
  Remove-Item -Recurse -Force $PYDEST
}
New-Item -ItemType Directory -Path $PYDEST -Force > $null
Copy-Item -Recurse "$PYHOME\*" -Destination $PYDEST

# python.exe is at the bundle root; fall back to Scripts\ just in case.
$PY = "$PYDEST\python.exe"
if (-not (Test-Path $PY)) {
  $PY = "$PYDEST\Scripts\python.exe"
}
if (-not (Test-Path $PY)) {
  Write-Host "[X] bundled python missing under $PYDEST"
  exit 1
}

# -- 2. Install engine dependencies into the bundled interpreter --
& $PY -m ensurepip --upgrade 2> $null
& $PY -m pip install --break-system-packages --upgrade pip setuptools wheel

# SAM-2 is a git sdist whose build imports torch. Under pip's default build
# isolation the build env has no torch, so it re-downloads torch (GBs) and
# usually fails. Install everything except sam2 first, then sam2 with
# --no-build-isolation so it reuses the torch just installed.
$reqLines = Get-Content "$ROOT\engine\requirements.txt"
$sam2 = ($reqLines | Where-Object { $_ -match '^(?i)SAM-2' } | Select-Object -First 1)
$reqNoSam2 = Join-Path $env:TEMP "vn_reqs_no_sam2.txt"
$reqLines | Where-Object { $_ -notmatch '^(?i)SAM-2' } | Set-Content $reqNoSam2

Write-Host "> Installing dependencies (slow part - torch/rasterio...)"
& $PY -m pip install --break-system-packages -r $reqNoSam2

if ($sam2) {
  Write-Host "> Installing SAM-2 (no build isolation, reuses installed torch)"
  & $PY -m pip install --break-system-packages --no-build-isolation $sam2
}
Remove-Item $reqNoSam2 -ErrorAction SilentlyContinue

# -- 3. Copy engine source into resources (self-contained, no caches/tests) --
Write-Host "> Copying engine source -> $ENGDEST"
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

# -- 4. Prune to shrink the bundle --
Write-Host "> Pruning bundle..."
Get-ChildItem -Path $PYDEST -Recurse -Force -Directory -Filter '__pycache__' |
  ForEach-Object { Remove-Item -Recurse -Force $_.FullName }
Get-ChildItem -Path $PYDEST -Recurse -Force -Directory -Filter 'tests' |
  Where-Object { $_.FullName -match 'site-packages' } |
  ForEach-Object { Remove-Item -Recurse -Force $_.FullName }

$DirSize = (Get-ChildItem -Path $PYDEST -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "[OK] Done. Bundled python: $([Math]::Round($DirSize, 1)) MB"
Write-Host "  Next: npm run tauri build"
