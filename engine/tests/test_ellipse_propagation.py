import numpy as np
import cv2
import pytest
import sys
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'engine'))
sys.path.insert(0, os.path.join(REPO, 'engine', 'tests'))

import vn_headless as H
H.load_plugins()
from registry import NODE_CLASS_REGISTRY


def test_geom_ellipse_propagation_node_registered():
    assert 'geom_ellipse_propagation' in NODE_CLASS_REGISTRY


def test_geom_ellipse_propagation_synthetic():
    proc = NODE_CLASS_REGISTRY['geom_ellipse_propagation']()
    h, w = 400, 400
    
    # Create 6 synthetic metaxylem vessels arranged in an ellipse
    mx = np.zeros((h, w), dtype=np.uint8)
    cx, cy = 200, 200
    rx, ry = 60, 45
    for k in range(6):
        th = k * (2 * np.pi / 6)
        vx = int(cx + rx * np.cos(th))
        vy = int(cy + ry * np.sin(th))
        cv2.circle(mx, (vx, vy), 10, 255, -1)

    res = proc.process({'landmarks': mx}, {})
    
    assert res['main'] is not None
    assert res['zones'] is not None
    assert res['stele_mask'] is not None
    assert res['endodermis_mask'] is not None
    assert res['ellipse_box'] is not None
    
    rep = res['report']
    assert abs(rep['center_x'] - 200) < 5.0
    assert abs(rep['center_y'] - 200) < 5.0
    assert rep['aspect_ratio'] > 1.10
    print("Synthetic test passed. Ellipse Center:", rep['center_x'], rep['center_y'], "Aspect:", rep['aspect_ratio'])
