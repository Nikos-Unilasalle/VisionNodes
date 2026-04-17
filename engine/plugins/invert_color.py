from __main__ import vision_node, NodeProcessor
import cv2

@vision_node(
    type_id='plugin_invert',
    label='Invert Color',
    category='cv',
    icon='Palette',
    description="Inverts all colors in the image (negative effect).",
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[]
)
class InvertNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'main': None}
        return {'main': cv2.bitwise_not(img)}
