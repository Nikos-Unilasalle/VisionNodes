import cv2
import numpy as np
from registry import vision_node, NodeProcessor

@vision_node(
    type_id='mask_operations',
    label='Mask Operations',
    category='mask',
    icon='Layers',
    description="Perform bitwise operations between two masks.",
    inputs=[
        {'id': 'mask_a', 'color': 'mask'},
        {'id': 'mask_b', 'color': 'mask'}
    ],
    outputs=[{'id': 'mask', 'color': 'mask'}],
    params=[
        {'id': 'operation', 'label': 'Operation', 'type': 'enum', 'options': ['Addition (OR)', 'Subtraction (A - B)', 'Intersection (AND)'], 'default': 0}
    ]
)
class MaskOperationsNode(NodeProcessor):
    def process(self, inputs, params):
        m1 = inputs.get('mask_a')
        m2 = inputs.get('mask_b')
        
        if m1 is None and m2 is None: return {'mask': None}
        
        # Determine shape from whichever is available
        ref = m1 if m1 is not None else m2
        h, w = ref.shape[:2]
        
        if m1 is None: m1 = np.zeros((h, w), dtype=np.uint8)
        if m2 is None: m2 = np.zeros((h, w), dtype=np.uint8)
        
        # Ensure 1-channel uint8
        if len(m1.shape) == 3: m1 = cv2.cvtColor(m1, cv2.COLOR_BGR2GRAY)
        if len(m2.shape) == 3: m2 = cv2.cvtColor(m2, cv2.COLOR_BGR2GRAY)
        m1 = m1.astype(np.uint8)
        m2 = m2.astype(np.uint8)
        
        # Ensure same size
        if m1.shape[:2] != m2.shape[:2]:
            m2 = cv2.resize(m2, (m1.shape[1], m1.shape[0]), interpolation=cv2.INTER_NEAREST)
            
        op = int(params.get('operation', 0))
        
        if op == 0: # Addition (OR)
            res = cv2.bitwise_or(m1, m2)
        elif op == 1: # Subtraction (A - B)
            res = cv2.bitwise_and(m1, cv2.bitwise_not(m2))
        elif op == 2: # Intersection (AND)
            res = cv2.bitwise_and(m1, m2)
        else:
            res = m1
            
        return {'mask': res}
