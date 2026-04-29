from registry import vision_node, NodeProcessor
import ee
import numpy as np
import cv2
import os

# Ensure GEE is initialized (shared with other GEE nodes)
def ensure_ee():
    try:
        # Just use standard initialization which picks up local credentials
        ee.Initialize()
    except Exception as e:
        print(f"[GEE] Initialization failed: {e}")
        pass

@vision_node(
    type_id='geo_land_cover',
    label='Geo Land Cover',
    category='geo',
    icon='Layers',
    description="Fetch ESA WorldCover 10m classification for the input region. Returns a binary mask for the selected class.",
    inputs=[{'id': 'geotiff', 'color': 'geotiff'}],
    outputs=[
        {'id': 'mask',    'color': 'mask', 'label': 'Class Mask'},
        {'id': 'overlay', 'color': 'image', 'label': 'Viz Overlay'},
        {'id': 'meta',    'color': 'string', 'label': 'Status'}
    ],
    params=[
        {
            'id': 'land_class', 
            'label': 'Land Class', 
            'type': 'int', 
            'default': 40, 
            'options': [
                {'label': '10 - Trees', 'value': 10},
                {'label': '20 - Shrubland', 'value': 20},
                {'label': '30 - Grassland', 'value': 30},
                {'label': '40 - Cropland', 'value': 40},
                {'label': '50 - Built-up', 'value': 50},
                {'label': '60 - Bare soil', 'value': 60},
                {'label': '80 - Water', 'value': 80},
                {'label': '90 - Wetland', 'value': 90},
            ]
        },
        {'id': 'gcp_project', 'label': 'Manual Project ID', 'type': 'string', 'default': ''},
        {'id': 'opacity', 'label': 'Overlay Opacity', 'type': 'float', 'default': 0.5, 'min': 0.0, 'max': 1.0}
    ]
)
class GeoLandCoverNode(NodeProcessor):
    def process(self, inputs, params):
        status = "Initializing..."
        
        geo = inputs.get('geotiff')
        
        # Determine Project ID (Priority: Input Image > Manual Param > Default)
        project_id = ""
        if geo and geo.get('_gcp_project'):
            project_id = geo.get('_gcp_project')
        if not project_id and params.get('gcp_project'):
            project_id = params.get('gcp_project')

        try:
            if project_id:
                ee.Initialize(project=project_id)
            else:
                ee.Initialize()
        except Exception as e:
            return {'mask': None, 'overlay': None, 'meta': f"GEE Init Error: {e}"}

        if geo is None:
            return {'mask': None, 'overlay': None, 'meta': "No GeoTIFF connected"}

        # Get spatial metadata
        transform = geo.get('transform')
        crs = geo.get('crs', 'EPSG:4326')
        width = geo['bands'][0].shape[1]
        height = geo['bands'][0].shape[0]
        
        try:
            x_min, y_max = transform[2], transform[5]
            x_max = x_min + (width * transform[0])
            y_min = y_max + (height * transform[4])

            # Ensure coordinates are in the right order [west, south, east, north]
            west, east = min(x_min, x_max), max(x_min, x_max)
            south, north = min(y_min, y_max), max(y_min, y_max)
            roi = ee.Geometry.Rectangle([west, south, east, north], crs, False)
            
            status = f"Fetching ESA WorldCover for {width}x{height} region..."
            
            # Try v200 then v100
            try:
                img = ee.ImageCollection('ESA/WorldCover/v200').first()
            except:
                img = ee.ImageCollection('ESA/WorldCover/v100').first()

            target_class = int(params.get('land_class', 40))
            # Clip the global image to our ROI to make it "bounded"
            class_mask = img.eq(target_class).clip(roi)
            
            # Use dimensions for absolute precision
            url = class_mask.getDownloadURL({
                'dimensions': [width, height],
                'crs': crs,
                'region': roi,
                'format': 'NPY'
            })
            
            import requests, io
            response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                # GEE often returns error messages as text even for NPY requests
                error_msg = response.text[:100]
                return {'mask': None, 'overlay': None, 'meta': f"GEE Error: {error_msg}"}

            data = np.load(io.BytesIO(response.content))
            
            # Handle structured arrays (e.g. data type = [('Map', 'u1')])
            if data.dtype.names:
                data = data[data.dtype.names[0]]

            if data is None or data.size == 0:
                return {'mask': None, 'overlay': None, 'meta': "Error: Received empty data"}

            if data.ndim == 3: data = data[0]
            
            # Final safety check on dimensions
            if data.shape[0] == 0 or data.shape[1] == 0:
                return {'mask': None, 'overlay': None, 'meta': "Error: Invalid data dimensions"}

            # Convert to float32 for OpenCV compatibility (fix for the 'resize' crash)
            data = data.astype(np.float32)
            
            data = cv2.resize(data, (width, height), interpolation=cv2.INTER_NEAREST)
            mask_out = (data * 255).astype(np.uint8)
            
            # Visualization
            bg = geo['bands'][0]
            bg_norm = cv2.normalize(bg, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            bg_color = cv2.cvtColor(bg_norm, cv2.COLOR_GRAY2BGR)
            
            colors = {10:(0,255,0), 20:(0,200,100), 30:(100,255,100), 40:(0,255,255), 50:(0,0,255), 60:(100,100,100), 80:(255,0,0)}
            color = colors.get(target_class, (255, 255, 255))
            
            overlay = bg_color.copy()
            overlay[mask_out > 0] = color
            viz = cv2.addWeighted(bg_color, 1-float(params.get('opacity',0.5)), overlay, float(params.get('opacity',0.5)), 0)
            
            return {
                'mask': mask_out,
                'overlay': viz,
                'meta': f"OK: {np.count_nonzero(mask_out)} px ({target_class})"
            }
            
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return {'mask': None, 'overlay': None, 'meta': f"Runtime Error: {str(e)[:50]}"}
