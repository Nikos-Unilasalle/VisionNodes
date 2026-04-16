from __main__ import vision_node, NodeProcessor

@vision_node(
    type_id='util_coord_center',
    label='Coord Center',
    category='util',
    icon='Target',
    inputs=[{'id': 'data', 'color': 'dict'}],
    outputs=[
        {'id': 'cx', 'color': 'scalar'},
        {'id': 'cy', 'color': 'scalar'},
        {'id': 'dict', 'color': 'dict'}
    ],
    params=[]
)
class CoordCenterNode(NodeProcessor):
    def process(self, inputs, params):
        d = inputs.get('data')
        if not isinstance(d, dict) or 'xmin' not in d:
            return {'cx': 0.0, 'cy': 0.0, 'dict': {'xmin': 0.0, 'ymin': 0.0, 'width': 0.0, 'height': 0.0}}
        
        cx = d['xmin'] + d.get('width', 0.0) / 2.0
        cy = d['ymin'] + d.get('height', 0.0) / 2.0
        
        return {
            'cx': float(cx), 
            'cy': float(cy), 
            'dict': {'xmin': float(cx), 'ymin': float(cy), 'width': 0.0, 'height': 0.0}
        }
