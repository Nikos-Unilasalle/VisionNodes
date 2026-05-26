#!/usr/bin/env bash
# Build the preprint PDF.
#
# Requires a LaTeX distribution. Two install paths:
#
#   1. MacTeX (recommended on macOS):
#        brew install --cask mactex-no-gui
#        eval "$(/usr/libexec/path_helper)"   # add /Library/TeX/texbin to PATH
#
#   2. Tectonic (smaller, self-contained):
#        brew install tectonic
#        # then: tectonic main.tex
#
# Run from inside the paper/ directory.

set -euo pipefail
cd "$(dirname "$0")"

if command -v tectonic >/dev/null 2>&1; then
    echo "[build] Using tectonic..."
    tectonic main.tex
elif command -v pdflatex >/dev/null 2>&1; then
    echo "[build] Using pdflatex + bibtex (3-pass)..."
    pdflatex -interaction=nonstopmode main.tex
    bibtex main || true
    pdflatex -interaction=nonstopmode main.tex
    pdflatex -interaction=nonstopmode main.tex
else
    echo "ERROR: no LaTeX engine found." >&2
    echo "Install MacTeX:  brew install --cask mactex-no-gui" >&2
    echo "Or tectonic:     brew install tectonic" >&2
    exit 1
fi

echo "[build] Done. Output: $(pwd)/main.pdf"
