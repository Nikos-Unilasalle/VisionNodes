from registry import vision_node, NodeProcessor
import numpy as np

@vision_node(
    type_id='geo_statistics',
    label='Geo Statistics',
    category='geo',
    icon='BarChart',
    description="Calculate area and value statistics from a GeoTIFF and a binary mask. Outputs area in pixels and hectares.",
    inputs=[
        {'id': 'geotiff', 'color': 'geotiff'},
        {'id': 'mask',    'color': 'mask'},
    ],
    outputs=[
        {'id': 'area_ha',   'color': 'scalar', 'label': 'Area (ha)'},
        {'id': 'pixels',    'color': 'scalar', 'label': 'Pixels'},
        {'id': 'mean_val',  'color': 'scalar', 'label': 'Mean Value'},
        {'id': 'meta',      'color': 'text',   'label': 'Summary'},
    ],
    params=[]
)
class GeoStatsNode(NodeProcessor):
    def process(self, inputs, params):
        geo  = inputs.get('geotiff')
        mask = inputs.get('mask')

        if geo is None or mask is None:
            return {'area_ha': 0, 'pixels': 0, 'mean_val': 0, 'meta': 'No input data'}

        # Ensure mask is binary and 2D
        if mask.ndim == 3:
            mask = mask[:, :, 0]
        
        # Create binary mask (robust detection)
        binary = (mask > 0)
        px_count = int(np.count_nonzero(binary))

        # Calculate area in hectares
        # transform[0] is pixel width, transform[4] is pixel height
        res_x = 10.0 # Default fallback (Sentinel-2 10m)
        res_y = 10.0
        
        transform = geo.get('transform')
        has_transform = False
        
        if transform:
            try:
                # Handle both list/tuple and Affine objects
                t = transform
                rx, ry = abs(t[0]), abs(t[4])
                if rx > 0 and ry > 0:
                    res_x, res_y = rx, ry
                    has_transform = True
                    
                    # Heuristic for Degrees (WGS84)
                    if res_x < 0.1: 
                        res_x *= 111319.0
                        res_y *= 111319.0
            except:
                pass
        
        pixel_area = res_x * res_y
        area_ha = (px_count * pixel_area) / 10000.0
        
        # Calculate stats
        data = geo['bands'][0]
        if px_count > 0:
            masked_data = data[binary]
            mean_val = float(np.mean(masked_data))
            min_val  = float(np.min(masked_data))
            max_val  = float(np.max(masked_data))
        else:
            mean_val = min_val = max_val = 0

        summary = (
            f"Pixels: {px_count} | Res: {res_x:.1f}m\n"
            f"Transform: {'Yes' if has_transform else 'No (Fallback 10m)'}\n"
            f"Range: {min_val:.2f} to {max_val:.2f}"
        )

        return {
            'area_ha': round(area_ha, 6),
            'pixels': px_count,
            'mean_val': round(mean_val, 4),
            'min_val': round(min_val, 4),
            'max_val': round(max_val, 4),
            'meta': summary
        }
