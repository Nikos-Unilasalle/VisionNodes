import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from registry import NODE_SCHEMAS, NODE_CLASS_REGISTRY

# Force plugin registration
import importlib.util
_plugin_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins', 'ml_plot_nodes.py')
_spec = importlib.util.spec_from_file_location('plugins.ml_plot_nodes', _plugin_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ScatterNode = NODE_CLASS_REGISTRY['ml_scatter_plot']

_BASE = {'x_col': 'x', 'y_col': 'y', 'colormap': 0, 'alpha': 0.8,
         'dot_size': 40, 'regression': False, 'grid': True, 'max_points': 0}


def _df(n=200, classes=3):
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        'x': rng.random(n),
        'y': rng.random(n),
        'cls': rng.choice([f'c{i}' for i in range(classes)], n),
        'score': rng.random(n),
    })


def _plot(df, **overrides):
    return ScatterNode().process({'table': df}, {**_BASE, **overrides})


def test_exposes_columns_for_the_inspector_hints():
    res = _plot(_df())
    assert res['df_meta']['columns'] == ['x', 'y', 'cls', 'score']


def test_categorical_hue_changes_the_plot():
    df = _df()
    plain = _plot(df)['main']
    hued = _plot(df, hue_col='cls')['main']
    assert hued is not None
    assert plain.shape != hued.shape or not np.array_equal(plain, hued)


def test_hue_column_is_matched_case_insensitively():
    df = _df()
    exact = _plot(df, hue_col='cls')['main']
    loose = _plot(df, hue_col=' CLS ')['main']
    assert np.array_equal(exact, loose)


def test_high_cardinality_hue_keeps_every_point():
    """A hue with more classes than the legend cap used to plot only the first
    20 values and silently drop the rest of the points."""
    df = _df(n=300)
    df['many'] = np.arange(300)  # 300 distinct values

    res = _plot(df, hue_col='many')
    assert res['main'] is not None
    assert _mod._is_continuous(df['many']) is True


def test_low_cardinality_numeric_hue_stays_categorical():
    df = _df()
    df['label'] = (df['x'] > 0.5).astype(int)
    assert _mod._is_continuous(df['label']) is False
    assert _plot(df, hue_col='label')['main'] is not None


def test_unknown_hue_column_still_renders():
    res = _plot(_df(), hue_col='does_not_exist')
    assert res['main'] is not None


def test_regression_and_hue_render_together():
    assert _plot(_df(), hue_col='cls', regression=True)['main'] is not None


def test_class_colors_are_distinct():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    colors = _mod._class_colors(plt, 'tab10', 5)
    assert len(colors) == 5
    assert len({tuple(c) for c in colors}) == 5
