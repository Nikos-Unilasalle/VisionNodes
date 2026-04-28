from registry import vision_node, NodeProcessor


@vision_node(
    type_id='geo_band_info',
    label='Band Info',
    category='geo',
    icon='List',
    description="Display GeoTIFF metadata: bands, dimensions, CRS. Pass-through on geotiff port.",
    inputs=[{'id': 'geotiff', 'color': 'geotiff'}],
    outputs=[{'id': 'geotiff', 'color': 'geotiff', 'label': 'Pass-through'}],
    params=[]
)
class BandInfoNode(NodeProcessor):
    def process(self, inputs, params):
        geo = inputs.get('geotiff')
        if geo is None:
            return {'geotiff': None}
        return {
            'geotiff':    geo,
            'band_names': geo.get('band_names', []),
            'count':      geo.get('count', 0),
            'width':      geo.get('width', 0),
            'height':     geo.get('height', 0),
            'crs':        geo.get('crs') or 'N/A',
            'dtype':      geo.get('dtype', 'N/A'),
        }
