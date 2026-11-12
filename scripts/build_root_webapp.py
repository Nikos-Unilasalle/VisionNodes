#!/usr/bin/env python3
"""Bundle the Python side of the RhizoFit web app (pure standard library, runs in CI).

The app runs the real VNStudio code in the browser with Pyodide. This script zips exactly
what `scripts/root_web_runner.py` needs, keeping the repository layout so the runner's
relative paths work unchanged:

  engine/registry.py, engine/tests/vn_headless.py
  engine/plugins/<the plugins that declare the template's node types>
  scripts/radial_zoning_lib.py, scripts/cell_recovery_lib.py, scripts/cell_files_lib.py,
  scripts/photometry_lib.py, scripts/damaged_region_lib.py, scripts/census_lib.py, scripts/root_web_runner.py
  public/templates/root_predictive_ellipse_zoning.vn

Usage: python3 scripts/build_root_webapp.py [--out website/public/rhizofit/engine.zip]
"""
import argparse
import json
import os
import re
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join('public', 'templates', 'root_predictive_ellipse_zoning.vn')
STATIC_FILES = (
    os.path.join('engine', 'registry.py'),
    os.path.join('engine', 'tests', 'vn_headless.py'),
    os.path.join('scripts', 'radial_zoning_lib.py'),
    os.path.join('scripts', 'cell_recovery_lib.py'),
    os.path.join('scripts', 'cell_files_lib.py'),
    os.path.join('scripts', 'photometry_lib.py'),
    os.path.join('scripts', 'damaged_region_lib.py'),
    os.path.join('scripts', 'census_lib.py'),
    os.path.join('scripts', 'root_web_runner.py'),
    TEMPLATE,
)
EXTRA_TYPES = ('draw_root_publication',)  # instantiated directly by the runner
CANVAS_ONLY = {'canvas_frame', 'canvas_note', 'canvas_reroute'}
TYPE_ID = re.compile(r"""type_id\s*=\s*['"]([\w\-]+)['"]""")
DEFAULT_OUT = os.path.join(REPO, 'website', 'public', 'rhizofit', 'engine.zip')


def template_types():
    with open(os.path.join(REPO, TEMPLATE)) as f:
        vn = json.load(f)
    return {n['type'] for n in vn['nodes'] if n['type'] not in CANVAS_ONLY} | set(EXTRA_TYPES)


def plugin_files_for(types):
    """Map every node type to the plugin file that declares it; fail on a missing type."""
    plugin_dir = os.path.join(REPO, 'engine', 'plugins')
    owner = {}
    for name in sorted(os.listdir(plugin_dir)):
        if name.endswith('.py') and not name.startswith('_'):
            with open(os.path.join(plugin_dir, name), encoding='utf-8') as f:
                for t in TYPE_ID.findall(f.read()):
                    owner.setdefault(t, name)
    missing = sorted(t for t in types if t not in owner)
    if missing:
        raise SystemExit(f'no plugin declares node type(s): {", ".join(missing)}')
    return sorted({os.path.join('engine', 'plugins', owner[t]) for t in types})


def build(out):
    files = list(STATIC_FILES) + plugin_files_for(template_types())
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
