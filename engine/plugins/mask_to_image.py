from registry import vision_node, NodeProcessor
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
        import numpy as np
        mask = inputs.get('mask')
        if mask is None: return {'main': None}
        
        if mask.dtype != np.uint8:
            if mask.dtype in (np.float32, np.float64):
                mask = (np.clip(mask, 0.0, 1.0) * 255).astype(np.uint8) if float(mask.max()) <= 1.0 else np.clip(mask, 0, 255).astype(np.uint8)
            else:
                mask = np.clip(mask, 0, 255).astype(np.uint8)

        if len(mask.shape) == 2 or mask.shape[2] == 1:
            return {'main': cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)}
        return {'main': mask}
