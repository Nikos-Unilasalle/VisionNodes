from registry import vision_node, NodeProcessor

@vision_node(
    type_id='geo_bbox',
    label='Bounding Box',
    category='geography',
    icon='Square',
    description="Defines a Region of Interest (ROI) bounding box to share across geography nodes.",
    inputs=[],
    outputs=[
        {'id': 'bbox', 'color': 'string', 'label': 'BBox (str)'},
    ],
    params=[
        {'id': 'lon_min', 'label': 'West (Lon Min)',  'type': 'float', 'default': -5.5},
        {'id': 'lat_min', 'label': 'South (Lat Min)', 'type': 'float', 'default': 41.0},
        {'id': 'lon_max', 'label': 'East (Lon Max)',  'type': 'float', 'default': 9.5},
        {'id': 'lat_max', 'label': 'North (Lat Max)', 'type': 'float', 'default': 51.5},
    ]
)
class GeoBBoxNode(NodeProcessor):
    def process(self, inputs, params):
        lon_min = float(params.get('lon_min', -5.5))
        lat_min = float(params.get('lat_min', 41.0))
        lon_max = float(params.get('lon_max', 9.5))
        lat_max = float(params.get('lat_max', 51.5))
        
        bbox_str = f"{lon_min},{lat_min},{lon_max},{lat_max}"
        
        return {'bbox': bbox_str}
