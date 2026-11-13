#!/usr/bin/env python3
"""Bundle the Python side of the RhizoFit web app (pure standard library, runs in CI).

The app runs the RhizoFit code in the browser with Pyodide. This script zips exactly what
`scripts/root_web_runner.py` needs, keeping the repository layout so the runner's relative
paths work unchanged:

  engine/registry.py
  engine/plugins/<the plugins listed in rhizofit_pipeline.PLUGINS>
  scripts/rhizofit_pipeline.py, scripts/radial_zoning_lib.py, scripts/cell_recovery_lib.py,
  scripts/cell_files_lib.py, scripts/photometry_lib.py, scripts/damaged_region_lib.py,
  scripts/anchor_choice_lib.py, scripts/census_lib.py, scripts/root_web_runner.py

Usage: python3 scripts/build_root_webapp.py [--out website/public/rhizofit/engine.zip]
"""
import argparse
import ast
import os
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE = os.path.join('scripts', 'rhizofit_pipeline.py')
STATIC_FILES = (
    os.path.join('engine', 'registry.py'),
    PIPELINE,
    os.path.join('scripts', 'radial_zoning_lib.py'),
    os.path.join('scripts', 'cell_recovery_lib.py'),
    os.path.join('scripts', 'cell_files_lib.py'),
    os.path.join('scripts', 'photometry_lib.py'),
    os.path.join('scripts', 'damaged_region_lib.py'),
    os.path.join('scripts', 'anchor_choice_lib.py'),
    os.path.join('scripts', 'census_lib.py'),
    os.path.join('scripts', 'root_web_runner.py'),
)
DEFAULT_OUT = os.path.join(REPO, 'website', 'public', 'rhizofit', 'engine.zip')


def pipeline_plugins():
    """{node type: plugin module} declared by rhizofit_pipeline.PLUGINS (read without importing it)."""
    with open(os.path.join(REPO, PIPELINE), encoding='utf-8') as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == 'PLUGINS' for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit(f'{PIPELINE} defines no PLUGINS table')


def plugin_files():
    """Plugin files of the pipeline; fail on a missing one."""
    files = sorted({os.path.join('engine', 'plugins', f'{m}.py') for m in pipeline_plugins().values()})
    missing = [f for f in files if not os.path.isfile(os.path.join(REPO, f))]
    if missing:
        raise SystemExit(f'missing plugin file(s): {", ".join(missing)}')
    return files


def build(out):
    files = list(STATIC_FILES) + plugin_files()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(os.path.join(REPO, rel), rel.replace(os.sep, '/'))
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=DEFAULT_OUT)
    args = ap.parse_args()
    files = build(args.out)
    print(f'wrote {args.out} ({len(files)} files, {os.path.getsize(args.out) / 1024:.0f} KiB)')


if __name__ == '__main__':
    sys.exit(main())
