from registry import vision_node, NodeProcessor
import numpy as np

@vision_node(
    type_id='sci_calibration',
    label='Unit Calibration',
    category=['analysis', 'math'],
    icon='Scaling',
    description="Converts pixel measurements (length or area) into real-world units based on a calibration factor.",
    inputs=[{'id': 'pixel_value', 'color': 'scalar'}],
    outputs=[{'id': 'real_value', 'color': 'scalar'}],
    params=[
        {'id': 'factor',     'label': 'Pixels per Unit', 'type': 'float', 'default': 100.0},
        {'id': 'dimension',  'label': 'Dimension',       'type': 'string', 'default': 'Area', 'options': ['Length', 'Area']},
        {'id': 'unit_name',  'label': 'Unit Name',       'type': 'string', 'default': 'cm'},
    ]
)
class CalibrationNode(NodeProcessor):
    def process(self, inputs, params):
        val = inputs.get('pixel_value')
        if val is None:
            return {'real_value': None}
            
        # Handle list input if necessary
        is_list = isinstance(val, (list, np.ndarray))
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
            
        return {
            'real_value': res.tolist() if is_list else float(res),
            'unit': params.get('unit_name', 'cm') + ('²' if dim == 'Area' else '')
        }
