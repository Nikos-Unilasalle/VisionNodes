from __main__ import vision_node, NodeProcessor
import cv2

@vision_node(
    type_id='plugin_image_to_mask',
    label='Image to Mask',
    category='mask',
    icon='Layers',
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'mask', 'color': 'mask'}],
    params=[]
)
class ImageToMaskNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'mask': None}
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return {'mask': img}
