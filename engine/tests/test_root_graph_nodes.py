import os
import sys
import numpy as np
import pytest
import cv2

_ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ENGINE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vn_headless as H
H.load_plugins()

from registry import NODE_CLASS_REGISTRY


def _node(type_id):
    return NODE_CLASS_REGISTRY[type_id]()


def test_cell_spatial_graph_finds_topological_layers_and_zscore():
    # Synthetic grid of 5x5 cells
    h, w = 100, 100
    labels = np.zeros((h, w), np.int32)
    k = 1
    for r in range(5):
        for c in range(5):
            y1, y2 = r * 20, (r + 1) * 20
            x1, x2 = c * 20, (c + 1) * 20
            labels[y1:y2, x1:x2] = k
            k += 1

    # Outer boundary mask (top and left borders)
    boundary = np.zeros((h, w), np.uint8)
    boundary[0, :] = 255
    boundary[:, 0] = 255

    proc = _node('seg_cell_graph')
    out = proc.process({
        'labels': labels,
        'boundary': boundary,
    }, {
        'layers_max': 5,
    })

    assert out['main'] is not None
    assert out['layers_mask'] is not None
    assert out['endodermis_mask'] is not None
    assert out['peripheral_mask'] is not None
    assert out['rhizodermis_mask'] is not None
    assert 'rhizodermis_count' in out
    assert len(out['features']) == 25
    assert 'graph' in out and 'neighbors' in out['graph']

    # Cell 1 (top-left) should be Layer 1
    f1 = next(f for f in out['features'] if f['cell_id'] == 1)
    assert f1['topological_layer'] == 1

    # Cell 25 (bottom-right) should be higher layer
    f25 = next(f for f in out['features'] if f['cell_id'] == 25)
    assert f25['topological_layer'] > 1


def test_graph_regularize_cleans_confetti():
    # 3x3 cells where center cell has different zone from all surrounding neighbors
    h, w = 60, 60
    labels = np.zeros((h, w), np.int32)
    zones = np.zeros((h, w), np.int32)
    k = 1
    for r in range(3):
        for c in range(3):
            y1, y2 = r * 20, (r + 1) * 20
            x1, x2 = c * 20, (c + 1) * 20
            labels[y1:y2, x1:x2] = k
            # Zone 1 everywhere except center cell which is Zone 2 (confetti)
            zones[y1:y2, x1:x2] = 2 if (r == 1 and c == 1) else 1
            k += 1

    proc = _node('seg_graph_regularize')
    out = proc.process({
        'labels': labels,
        'zones': zones,
    }, {
        'iterations': 2,
        'self_weight': 0.1,
        'min_agreement': 0.5,
    })

    assert out['zones'] is not None
    assert out['changes_count'] == 1
    # Center cell should have been flipped to Zone 1
    assert out['zones'][30, 30] == 1
