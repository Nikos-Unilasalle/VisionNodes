#!/usr/bin/env bash
#
# build_pyengine.sh — Bundle a self-contained Python engine into the Tauri app.
#
# Produces a fully relocatable Python (python-build-standalone, via uv) with all
# engine dependencies installed, plus a copy of the engine source, under:
#     src-tauri/resources/pyengine/   (the interpreter + site-packages)
#     src-tauri/resources/engine/     (engine.py, plugins, registry…)
#
# These get bundled into VisionNodes.app/Contents/Resources/ by `tauri build`
# (see tauri.conf.json -> bundle.resources). The app then launches:
#     Resources/pyengine/bin/python3  Resources/engine/engine.py
#
# Run once before `npm run tauri build` (or whenever requirements.txt changes).
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYVER="3.12"
RES="$ROOT/src-tauri/resources"
PYDEST="$RES/pyengine"
ENGDEST="$RES/engine"

echo "▶ VNStudio Python engine bundler"
echo "  root: $ROOT"

# ── 0. Require uv (ships python-build-standalone, which IS relocatable) ──
if ! command -v uv >/dev/null 2>&1; then
  echo "✗ 'uv' not found. Install it: https://docs.astral.sh/uv/  (curl -LsSf https://astral.sh/uv/install.sh | sh)"
  exit 1
fi

# ── 1. Get a standalone CPython and copy it into resources ──
echo "▶ Fetching standalone CPython $PYVER via uv…"
uv python install "$PYVER"
PYBIN="$(uv python find "$PYVER")"
PYHOME="$(cd "$(dirname "$PYBIN")/.." && pwd)"   # …/cpython-3.12.x-macos-<arch>/
echo "  source interpreter: $PYHOME"

echo "▶ Copying interpreter → $PYDEST"
rm -rf "$PYDEST"
mkdir -p "$PYDEST"
cp -R "$PYHOME/." "$PYDEST/"

PY="$PYDEST/bin/python3"
[ -x "$PY" ] || { echo "✗ bundled python missing at $PY"; exit 1; }

# ── 2. Install engine dependencies into the bundled interpreter ──
# On Linux the default torch wheel bundles ~2 GB of CUDA/NVIDIA libs, which
# blows up the AppImage (and risks the squashfs size limit). Install the
# CPU-only build first; the requirements.txt pass below then sees torch
# already satisfied and leaves it alone. macOS/Windows default wheels are
# already CPU-only, so this step is Linux-specific.
if [ "$(uname -s)" = "Linux" ]; then
  echo "▶ Installing CPU-only torch (Linux: excludes bundled CUDA)…"
  uv pip install --break-system-packages \
    --index-url https://download.pytorch.org/whl/cpu \
    torch torchvision --python "$PY"
fi

# Build-backend deps for compiling sdists without isolation (sam2 below).
uv pip install --break-system-packages setuptools wheel --python "$PY"

# SAM-2 is a git sdist whose build imports torch. Under pip's default build
# isolation the build env has no torch, so it re-downloads torch (~GBs) and
# usually fails/times out. Install everything *except* sam2 first, then sam2
# with --no-build-isolation so it reuses the torch we just installed.
SAM2_REQ="$(grep -i '^SAM-2' "$ROOT/engine/requirements.txt" || true)"
REQ_TMP="$(mktemp)"
grep -v -i '^SAM-2' "$ROOT/engine/requirements.txt" > "$REQ_TMP"

echo "▶ Installing dependencies (slow part — torch/rasterio/mediapipe…)…"
uv pip install --break-system-packages -r "$REQ_TMP" --python "$PY"

if [ -n "$SAM2_REQ" ]; then
  echo "▶ Installing SAM-2 (--no-build-isolation, reuses installed torch)…"
  uv pip install --break-system-packages --no-build-isolation "$SAM2_REQ" --python "$PY"
fi
rm -f "$REQ_TMP"

# ── 3. Copy engine source into resources (self-contained, no caches/tests) ──
echo "▶ Copying engine source → $ENGDEST"
rm -rf "$ENGDEST"
mkdir -p "$ENGDEST"
rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'tests' \
  --exclude '.pytest_cache' \
  --exclude '*_cache' \
  "$ROOT/engine/" "$ENGDEST/"

# ── 4. Prune to shrink the bundle (tests, caches inside site-packages) ──
echo "▶ Pruning bundle…"
find "$PYDEST" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$PYDEST" -type d -name 'tests' -path '*/site-packages/*' -prune -exec rm -rf {} + 2>/dev/null || true

SIZE="$(du -sh "$PYDEST" 2>/dev/null | cut -f1)"
echo "✓ Done. Bundled python: $SIZE"
echo "  Next: npm run tauri build"
