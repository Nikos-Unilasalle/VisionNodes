from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='plugin_mask_counter',
    label='Area Monitor',
    category='visualize',
    icon='Hash',
    description="Counts the number of white pixels in a mask to evaluate surface area.",
    inputs=[{'id': 'mask', 'color': 'mask'}],
    outputs=[
        {'id': 'main', 'color': 'mask'},
        {'id': 'count', 'color': 'scalar'}
    ],
    params=[]
)
class MaskCounterNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: 
            return {'main': None, 'display_text': '0 px'}
        
        # S'assurer que le mask est bien un masque binaire gris
        if len(mask.shape) == 3:
            mask_gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        else:
            mask_gray = mask
            
        # Comptage pur et dur des pixels non-noirs
        count = int(cv2.countNonZero(mask_gray))
        
        return {
            'main': mask,
            'count': count,
            'display_text': f"{count} px"
        }
