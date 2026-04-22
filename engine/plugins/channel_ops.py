"""
Channel split and merge nodes.
Split: image → individual R, G, B (and A if present) as grayscale images.
Merge: R, G, B (optional A) → composite BGR or BGRA image.
"""

import cv2
import numpy as np
from __main__ import vision_node, NodeProcessor

@vision_node(
    type_id='plugin_channel_split',
    label='Channel Split',
    category='cv',
    icon='Layers',
    description="Splits an image into individual R, G, B (and A) channel grayscale images.",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'r', 'color': 'image'},
        {'id': 'g', 'color': 'image'},
        {'id': 'b', 'color': 'image'},
        {'id': 'a', 'color': 'image'},
    ],
    params=[]
)
class ChannelSplitNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'r': None, 'g': None, 'b': None, 'a': None}

        if img.ndim == 2:
            gray = img
            return {'r': gray, 'g': gray, 'b': gray, 'a': None}

        if img.shape[2] == 4:
            b, g, r, a = cv2.split(img)
        else:
            b, g, r = cv2.split(img[:, :, :3])
            a = None

        def to_bgr(ch):
            return cv2.cvtColor(ch, cv2.COLOR_GRAY2BGR)

        return {
            'r': to_bgr(r),
            'g': to_bgr(g),
            'b': to_bgr(b),
            'a': to_bgr(a) if a is not None else None,
        }


@vision_node(
    type_id='plugin_channel_merge',
    label='Channel Merge',
    category='cv',
    icon='Layers',
    description="Merges R, G, B (and optional A) channel images into a single composite image.",
    inputs=[
        {'id': 'r', 'color': 'image'},
        {'id': 'g', 'color': 'image'},
        {'id': 'b', 'color': 'image'},
        {'id': 'a', 'color': 'image'},
    ],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[]
)
class ChannelMergeNode(NodeProcessor):
    @staticmethod
    def _to_gray(img):
        if img is None:
            return None
        if img.ndim == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def process(self, inputs, params):
        r = self._to_gray(inputs.get('r'))
        g = self._to_gray(inputs.get('g'))
        b = self._to_gray(inputs.get('b'))
        a = self._to_gray(inputs.get('a'))

        # Fill missing channels with zeros at the size of the first available
        ref = next((c for c in (r, g, b) if c is not None), None)
        if ref is None:
            return {'main': None}
        h, w = ref.shape[:2]
        blank = np.zeros((h, w), dtype=np.uint8)
        r = r if r is not None else blank
        g = g if g is not None else blank
        b = b if b is not None else blank

        # Resize channels to ref size if they differ
        def fit(ch):
            if ch.shape[:2] != (h, w):
                ch = cv2.resize(ch, (w, h))
            return ch
        r, g, b = fit(r), fit(g), fit(b)

        if a is not None:
            a = fit(a)
            return {'main': cv2.merge([b, g, r, a])}
        return {'main': cv2.merge([b, g, r])}
