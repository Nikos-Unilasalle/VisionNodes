"""
VNStudio Master Node Template
=============================
This file documents all native options for creating a new node in VisionNodes Studio.
You can copy-paste this template and adjust the parameters to your needs.
"""

import cv2
import numpy as np
from registry import vision_node, NodeProcessor

# -----------------------------------------------------------------------------
# THE DECORATOR: Your Node's DNA
# -----------------------------------------------------------------------------
@vision_node(
    type_id='my_new_node',        # Unique identifier (lowercase, underscores)
    label='My Master Node',      # Display name in the UI
    category='cv',               # 'cv', 'math', 'logic', 'draw', 'sci', 'util', 'geo'
    icon='Zap',                  # Lucide icon name (Zap, Image, Search, Ghost, etc.)
    description="Full description shown in the tooltip.",
    
    # -- UI & BEHAVIOR FLAGS --
    resizable=True,              # Can the user resize the node manually?
    min_width=240,               # Default minimum width if resizable
    min_height=180,              # Default minimum height if resizable
    colorable=True,              # Can the user change the node's color from a palette?
    
    # -- DYNAMIC PORT OPTIONS --
    dynamic_inputs=False,        # Connection-driven: Add a new input port whenever a link is connected.
    dynamic_outputs=False,       # Connection-driven: Same for outputs.
    variable_inputs=True,        # UI-driven: Show [+] and [-] buttons to add scalar inputs (a, b, c...).
    
    # -- PORT DEFINITIONS --
    # Colors: 'image' (blue), 'mask' (gray), 'scalar' (yellow), 'string' (light blue), 
    #         'dict' (green), 'list' (purple), 'any' (white), 'flow' (red), 'audio' (indigo)
    inputs=[
        {'id': 'main_image', 'label': 'Input Frame', 'color': 'image'},
        {'id': 'threshold',  'label': 'Thresh',      'color': 'scalar'}
    ],
    outputs=[
        {'id': 'main',       'label': 'Result',      'color': 'image'},
        {'id': 'stats',      'label': 'Data Out',    'color': 'dict'}
    ],
    
    # -- PARAMETER DEFINITIONS --
    # Types: 'int', 'float', 'number', 'string', 'bool', 'toggle', 'enum', 'trigger', 'code', 'color'
    params=[
        {'id': 'mode', 'label': 'Algorithm', 'type': 'enum', 'options': ['Fast', 'Accurate'], 'default': 'Fast'},
        {'id': 'strength', 'label': 'Strength', 'type': 'float', 'min': 0.0, 'max': 1.0, 'default': 0.5},
        {'id': 'invert', 'label': 'Invert Result', 'type': 'bool', 'default': False},
        {'id': 'custom_script', 'label': 'Code', 'type': 'code', 'default': '# Python code here'}
    ]
)
class MyMasterNode(NodeProcessor):
    """
    The processor class where the logic happens.
    'inputs' is a dictionary containing the data from connected handles.
    'params' is a dictionary containing the current values from the UI controls.
    """

    def process(self, inputs, params):
        # 1. READ INPUTS
        # Always use .get() to avoid errors if nothing is connected
        img = inputs.get('main_image')
        thresh_val = float(inputs.get('threshold', 128))
        if img is None: return {'main': None}

        # 2. PROGRESS REPORTING (Optional)
        # /!\ CAUTION: Only use for very long tasks (> 500ms). 
        # In a streaming pipeline (30fps), calling this at every frame will flood the UI 
        # and make it look "stuck" at a percentage.
        # self.report_progress(0.5, "Processing heavy task...")
        # self.report_progress(1.0, "Done!") # 1.0 dismisses the bar.

        # 3. READ PARAMETERS
        mode = params.get('mode', 'Fast')
        strength = float(params.get('strength', 0.5))
        do_invert = bool(params.get('invert', False))
        
        # 4. IMPLEMENT YOUR LOGIC
        result_img = None
        if img is not None:
            # OpenCV example
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, result_img = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)
            
            if do_invert:
                result_img = cv2.bitwise_not(result_img)
        
        # 5. RETURN OUTPUTS
        # The keys MUST match the IDs declared in the 'outputs' list of the decorator.
        return {
            'main': result_img,
            'stats': {'max_val': 255, 'method': mode, 'strength': strength}
        }
