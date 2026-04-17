from __main__ import vision_node, NodeProcessor
import cv2
import numpy as np

@vision_node(
    type_id='plugin_blend_images',
    label='Simple Image Blend',
    category='blend',
    icon='Layers',
    description="Linearly blends two images based on a simple opacity factor.",
    inputs=[
        {'id': 'image_a', 'color': 'image'},
        {'id': 'image_b', 'color': 'image'}
    ],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'opacity', 'min': 0, 'max': 1, 'step': 0.05, 'default': 0.5}
    ]
)
class ImageBlendNode(NodeProcessor):
    def process(self, inputs, params):
        # On récupère les deux images
        img_a = inputs.get('image_a')
        img_b = inputs.get('image_b')
        
        # Si aucune ou une seule n'est connectée
        if img_a is None: return {'main': img_b}
        if img_b is None: return {'main': img_a}
        
        opacity = float(params.get('opacity', 0.5))
        
        # S'assurer que img_a est en couleur (3 canaux)
        if len(img_a.shape) == 2 or img_a.shape[2] == 1:
            img_a = cv2.cvtColor(img_a, cv2.COLOR_GRAY2BGR)
            
        # Redimensionnement de B pour coller exactement à la taille de A
        img_b_resized = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))
        
        # S'assurer que B est aussi en couleur
        if len(img_b_resized.shape) == 2 or img_b_resized.shape[2] == 1:
            img_b_resized = cv2.cvtColor(img_b_resized, cv2.COLOR_GRAY2BGR)
            
        # La magie OpenCV pour fusionner (A * (1-alpha) + B * alpha)
        blended = cv2.addWeighted(img_a, 1.0 - opacity, img_b_resized, opacity, 0)
        
        return {'main': blended}
