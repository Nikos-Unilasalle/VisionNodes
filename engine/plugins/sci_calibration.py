from registry import vision_node, NodeProcessor
import numpy as np

@vision_node(
    type_id='sci_calibration',
    label='Unit Calibration',
    category=['analysis', 'math'],
    icon='Scaling',
    description="Converts pixel measurements (length or area) into real-world units based on a calibration factor.",
    inputs=[{'id': 'input', 'color': 'any'}],
    outputs=[{'id': 'output', 'color': 'any'}],
    params=[
        {'id': 'factor',     'label': 'Pixels per Unit', 'type': 'float', 'default': 100.0},
        {'id': 'dimension',  'label': 'Dimension',       'type': 'string', 'default': 'Area', 'options': ['Length', 'Area']},
        {'id': 'unit_name',  'label': 'Unit Name',       'type': 'string', 'default': 'cm'},
    ]
)
class CalibrationNode(NodeProcessor):
    def process(self, inputs, params):
        val = inputs.get('input')
        if val is None:
            return {'output': None, 'display_value': "---"}
            
        try:
            # Handle list input if necessary
            is_list = isinstance(val, (list, np.ndarray, tuple))
            data = np.array(val) if is_list else float(val)
                
            factor = float(params.get('factor', 100.0))
            dim = params.get('dimension', 'Area')
            
            if factor <= 0:
                res = data
            else:
                if dim == 'Length':
                    res = data / factor
                else:
                    res = data / (factor ** 2)
                
            unit = params.get('unit_name', 'cm') + ('²' if dim == 'Area' else '')
            
            # Formatted display for the node UI
            if is_list:
                display = f"{len(res)} items"
            else:
                display = f"{res:.3f} {unit}"

            return {
                'output': res.tolist() if is_list else float(res),
                'display_value': display,
                'unit': unit
            }
        except Exception as e:
            return {'output': None, 'display_value': "Error"}
