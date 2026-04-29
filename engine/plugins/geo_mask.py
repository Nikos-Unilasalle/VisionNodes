from registry import vision_node, NodeProcessor
import numpy as np

@vision_node(
    type_id='geo_mask',
    label='Geo Mask',
    category='geo',
    icon='Scissors',
    description="Apply a binary mask to a GeoTIFF. Pixels outside the mask are set to zero (nodata). Equivalent to Bitwise AND.",
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff'},
        {'id': 'mask',    'color': 'mask'},
    ],
    outputs=[
        {'id': 'geotiff', 'color': 'geotiff', 'label': 'Masked GeoTIFF'},
    ],
    params=[
        {'id': 'invert', 'label': 'Invert Mask', 'type': 'boolean', 'default': False},
    ]
)
class GeoMaskNode(NodeProcessor):
    def process(self, inputs, params):
        geo  = inputs.get('geotiff')
        mask = inputs.get('mask')

        if geo is None or mask is None:
            return {'geotiff': None}

        # Prepare mask
        if mask.ndim == 3:
            mask = mask[:, :, 0]
        
        binary = (mask > 127)
        if params.get('invert', False):
            binary = ~binary

        # Apply to all bands
        bands = geo['bands'].copy()
        for i in range(geo['count']):
            bands[i][~binary] = 0
            
        out_geo = {**geo, 'bands': bands}
        return {'geotiff': out_geo}
