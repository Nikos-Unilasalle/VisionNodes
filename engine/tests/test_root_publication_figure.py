import pytest
import numpy as np
import cv2
import sys, os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'engine'))

from plugins.draw_root_publication import RootPublicationFigureNode


def test_draw_root_publication_metadata():
    node = RootPublicationFigureNode()
    assert hasattr(node, 'process')
    # Check registration
    from registry import NODE_CLASS_REGISTRY
    assert 'draw_root_publication' in NODE_CLASS_REGISTRY


def test_draw_root_publication_synthetic():
    node = RootPublicationFigureNode()

    # Create synthetic root cross-section
    h, w = 300, 300
    cy, cx = 150, 150
    y, x = np.ogrid[:h, :w]
    r = np.sqrt((x - cx)**2 + (y - cy)**2)

    # 4 synthetic cells
    labels = np.zeros((h, w), dtype=np.int32)
    labels[(r >= 0) & (r < 30)] = 1      # Pith
    labels[(r >= 30) & (r < 60)] = 2     # Endodermis
    labels[(r >= 60) & (r < 100)] = 3    # Inner cortex
    labels[(r >= 100) & (r < 130)] = 4   # Outer cortex
    labels[(r >= 130) & (r < 145)] = 5   # Rhizodermis

    section = (r <= 145).astype(np.uint8) * 255
    m_pith = (r < 30).astype(np.uint8) * 255
    m_endo = ((r >= 30) & (r < 60)).astype(np.uint8) * 255
    m_inner = ((r >= 60) & (r < 100)).astype(np.uint8) * 255
    m_outer = ((r >= 100) & (r < 130)).astype(np.uint8) * 255
    m_rhizo = ((r >= 130) & (r < 145)).astype(np.uint8) * 255

    inputs = {
        'labels': labels,
        'boundary': section,
        'pith_mask': m_pith,
        'endodermis_mask': m_endo,
        'inner_cortex_mask': m_inner,
        'outer_cortex_mask': m_outer,
        'rhizodermis_mask': m_rhizo,
        'ellipse_report': {
            'center_x': 150.0, 'center_y': 150.0,
            'major_axis': 80.0, 'minor_axis': 80.0,
            'tilt_angle_deg': 0.0, 'scale_pith': 0.5,
            'scale_endodermis': 1.2, 'scale_metaxylem': 1.0,
        }
    }

    params = {
        'canvas_mode': 'clean_white',
        'pt_to_px': 1.33,
        'complete_steles': True,
        'hatch_lacunae': True,
        'draw_legend': True,
        'draw_scale_bar': True,
    }

    res = node.process(inputs, params)
    assert 'main' in res
    assert 'figure_with_legend' in res
    assert 'predictive_report' in res
    assert res['main'].shape == (h, w, 3)
    assert res['figure_with_legend'].shape[0] == h
    assert res['figure_with_legend'].shape[1] > w  # Contains legend panel
    assert 'pith_cells_observed' in res['predictive_report']


def test_draw_root_publication_none_fallback():
    node = RootPublicationFigureNode()
    res = node.process({}, {})
    assert res['main'] is None
