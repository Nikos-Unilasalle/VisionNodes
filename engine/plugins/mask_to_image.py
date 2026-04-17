from __main__ import vision_node, NodeProcessor
import cv2

@vision_node(
    type_id='plugin_mask_to_image',
    label='Mask to Image',
    category='mask',
    icon='Layers',
    description="Converts a binary mask (1 channel) to a standard image (3 channels).",
    inputs=[{'id': 'mask', 'color': 'mask'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[]
)
class MaskToImageNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {'main': None}
        if len(mask.shape) == 2 or mask.shape[2] == 1:
            return {'main': cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)}
        return {'main': mask}
