from __main__ import vision_node, NodeProcessor
import cv2

@vision_node(
    type_id='plugin_invert_mask',
    label='Invert Mask',
    category='mask',
    icon='Layers',
    inputs=[{'id': 'mask', 'color': 'mask'}],
    outputs=[{'id': 'main', 'color': 'mask'}],
    params=[]
)
class InvertMaskNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {'main': None}
        return {'main': cv2.bitwise_not(mask)}
