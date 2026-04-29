from registry import vision_node, NodeProcessor
import numpy as np

@vision_node(
    type_id='filter_float_threshold',
    label='Float Threshold',
    category='mask',
    icon='Sliders',
    description="Thresholds a raw float32 array (e.g. NDVI, elevation) directly without 8-bit quantization loss. Connect the 'raw' output of Float Image. Water: -0.5→0.0, Vegetation: 0.2→1.0.",
    inputs=[{'id': 'raw', 'color': 'any'}],
    outputs=[
        {'id': 'mask',  'color': 'mask'},
        {'id': 'count', 'color': 'scalar'},
    ],
    params=[
        {'id': 'low',    'label': 'Min Value', 'type': 'float', 'default':  0.3, 'min': -1.0, 'max': 1.0, 'step': 0.01},
        {'id': 'high',   'label': 'Max Value', 'type': 'float', 'default':  1.0, 'min': -1.0, 'max': 1.0, 'step': 0.01},
        {'id': 'invert', 'label': 'Invert',    'type': 'boolean', 'default': False},
    ],
    colorable=True,
)
class FloatThresholdNode(NodeProcessor):
    def process(self, inputs, params):
        raw = inputs.get('raw')
        if raw is None:
            return {'mask': None, 'count': 0}

        # Handle GeoTIFF dictionary or raw numpy array
        if isinstance(raw, dict) and 'bands' in raw:
            data = raw['bands'][0].astype(np.float32)
        elif isinstance(raw, np.ndarray):
            data = raw.astype(np.float32)
            if data.ndim == 3:
                data = data[:, :, 0]
        else:
            return {'mask': None, 'count': 0}

        low  = float(params.get('low',  -1.0))
        high = float(params.get('high',  0.0))

        # Create binary mask
        mask = np.zeros(data.shape, dtype=np.uint8)
        valid_mask = (data >= low) & (data <= high)
        mask[valid_mask] = 255

        if params.get('invert', False):
            mask = 255 - mask

        # VisionNodes display nodes often expect 3 channels for mask visualization
        # We return a single channel but ensure it's clean
        count = int(np.count_nonzero(mask))
        return {'mask': mask, 'count': count}
