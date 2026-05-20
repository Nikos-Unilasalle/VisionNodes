import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import json
from plugins.sci_index_painter import IndexPainterNode

def test_index_painter_basic():
    node = IndexPainterNode()
    params = {
        'width': 256,
        'height': 256,
        'bg_value': 0.5,
        'colormap': 0, # RdYlGn
        'classes': json.dumps([
            {"label": "Water",      "value": -0.50, "color": "#2196f3"},
            {"label": "Bare Soil",  "value":  0.10, "color": "#ff9800"},
        ]),
        'strokes': json.dumps([
            {"class_idx": 0, "pts": [[0.1, 0.2], [0.3, 0.4]], "radius": 0.05}
        ])
    }
    
    res = node.process({}, params)
    assert 'index' in res
    assert 'labels' in res
    assert 'main_preview' in res
    assert res['index'].shape == (256, 256)
    assert res['labels'].shape == (256, 256)
    assert isinstance(res['main_preview'], str)

def test_index_painter_colormap_string():
    node = IndexPainterNode()
    params = {
        'width': 128,
        'height': 128,
        'bg_value': 0.0,
        'colormap': 'Viridis', # String colormap option
        'classes': '[]',
        'strokes': '[]'
    }
    res = node.process({}, params)
    assert res['index'].shape == (128, 128)
