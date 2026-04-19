import cv2
import numpy as np
from __main__ import vision_node, NodeProcessor

@vision_node(
    type_id='draw_text',
    label='Draw Text',
    category='draw',
    icon='Type',
    description="Draws text on an image or creates a graphic element. Connect text to the 'text' input and optionally an 'image'.",
    inputs=[
        {'id': 'text', 'color': 'string'},
        {'id': 'image', 'color': 'image'},
        {'id': 'x', 'color': 'scalar'},
        {'id': 'y', 'color': 'scalar'}
    ],
    outputs=[{'id': 'main', 'color': 'image'}, {'id': 'graphic', 'color': 'dict'}],
    params=[
        {'id': 'text', 'label': 'Text', 'type': 'string', 'default': 'Hello'},
        {'id': 'x', 'label': 'X Pos', 'type': 'scalar', 'min': 0, 'max': 1, 'step': 0.01, 'default': 0.5},
        {'id': 'y', 'label': 'Y Pos', 'type': 'scalar', 'min': 0, 'max': 1, 'step': 0.01, 'default': 0.5},
        {'id': 'font_scale', 'label': 'Size', 'type': 'scalar', 'min': 0.1, 'max': 5, 'step': 0.1, 'default': 1.0},
        {'id': 'thickness', 'label': 'Thickness', 'type': 'scalar', 'min': 1, 'max': 10, 'step': 1, 'default': 2},
        {'id': 'r', 'label': 'Red', 'type': 'scalar', 'min': 0, 'max': 255, 'default': 255},
        {'id': 'g', 'label': 'Green', 'type': 'scalar', 'min': 0, 'max': 255, 'default': 255},
        {'id': 'b', 'label': 'Blue', 'type': 'scalar', 'min': 0, 'max': 255, 'default': 255}
    ]
)
class DrawTextNode(NodeProcessor):
    def process(self, inputs, params):
        # 1. Determine the base template (Input socket has priority over Param)
        input_text = inputs.get('text')
        if input_text is not None and str(input_text).strip() != "":
            template = str(input_text)
        else:
            template = str(params.get('text', 'Hello'))
            
        # 2. Prepare formatting context (variables a-z)
        context = {}
        for i in range(26):
            char = chr(97 + i)
            val = inputs.get(char)
            # Format numbers nicely
            if isinstance(val, (int, float)):
                context[char] = f"{val:.2f}" if isinstance(val, float) else str(val)
            elif val is not None:
                context[char] = str(val)
            else:
                context[char] = "---"
        
        # 3. Try to format the template
        try:
            if "{" in template and "}" in template:
                text = template.format(**context)
            else:
                text = template
        except Exception:
            # Fallback if formatting fails (e.g. missing variable in braces)
            text = template
            
        # 4. Position Logic
        x = float(inputs.get('x', params.get('x', 0.5)))
        y = float(inputs.get('y', params.get('y', 0.5)))
        
        scale = float(params.get('font_scale', 1.0))
        thick = int(params.get('thickness', 2))
        r, g, b = int(params.get('r', 255)), int(params.get('g', 255)), int(params.get('b', 255))
        
        hex_color = '#%02x%02x%02x' % (r, g, b)
        
        graphic = {
            '_type': 'graphics',
            'shape': 'text',
            'text': text,
            'pts': [[x, y]],
            'relative': True,
            'font_scale': scale,
            'thickness': thick,
            'color': hex_color
        }
        
        img = inputs.get('image')
        if img is not None:
            # Direct drawing fallback
            img = img.copy()
            if len(img.shape) == 2: img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            h, w = img.shape[:2]
            scaled_x, scaled_y = int(x * w), int(y * h)
            # Use BGR for OpenCV drawing
            bgr_col = (b, g, r) 
            cv2.putText(img, text, (scaled_x, scaled_y), cv2.FONT_HERSHEY_SIMPLEX, scale, bgr_col, thick)
            
        return {"main": img, "graphic": graphic}
