import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

# Mock easyocr module since it might not be installed or would load heavy models
mock_easyocr = MagicMock()
sys.modules['easyocr'] = mock_easyocr

from plugins.easyocr_node import EasyOcrNode

@patch('plugins.easyocr_node.NodeProcessor.ensure_packages', return_value=True)
def test_easyocr_node_process(mock_ensure):
    node = EasyOcrNode()
    
    # Mock easyocr.Reader
    mock_reader_instance = MagicMock()
    # readtext returns a list of tuples: (box, text, confidence)
    mock_reader_instance.readtext.return_value = [
        ([[10, 10], [110, 10], [110, 50], [10, 50]], "HELLO WORLD", 0.95)
    ]
    mock_easyocr.Reader.return_value = mock_reader_instance
    
    # Since _load_reader runs in a background thread, we can call it synchronously for the test
    node._load_reader(0, False)
    
    # Verify Reader was initialized with English
    mock_easyocr.Reader.assert_called_with(['en'], gpu=False, verbose=False)
    
    # Process mock image
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    params = {
        'lang': 0,
        'gpu': False,
        'min_confidence': 0.4,
        'draw_text': True
    }
    
    res = node.process({'image': img}, params)
    
    assert 'main' in res
    assert 'text_regions' in res
    assert 'texts' in res
    assert res['texts'] == ["HELLO WORLD"]
    assert len(res['text_regions']) == 1
    assert res['text_regions'][0]['label'] == "HELLO WORLD"
