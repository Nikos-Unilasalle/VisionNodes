"""
util_monte_carlo_propagation.py — Generic Monte Carlo simulation node for propagating signals or states across arbitrary 2D grids (images/masks).
"""
import numpy as np
import cv2
import base64

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'gen_monte_carlo'


@vision_node(
    type_id='util_monte_carlo_propagation',
    label='Monte Carlo Propagation (Generic)',
    category='utility',
    icon='Activity',
    description=(
        "Simulates stochastic propagation/expansion of a state from a seed mask. "
        "An optional attractiveness/weight image can be connected to modulate propagation speed locally. "
        "Works on standard images (drawing, webcam, static files) in any context."
    ),
    inputs=[
        {'id': 'seed',           'color': 'mask',  'label': 'Seed mask'},
        {'id': 'attractiveness', 'color': 'image', 'label': 'Attractiveness map (optional)'},
    ],
    outputs=[
        {'id': 'probability',    'color': 'mask',  'label': 'Probability map'},
        {'id': 'preview',        'color': 'image', 'label': 'Visual preview (RGB)'},
        {'id': 'stats',          'color': 'dict',  'label': 'Stats (dict)'},
    ],
    params=[
        {'id': 'n_simulations', 'type': 'int', 'default': 100, 'min': 10, 'max': 1000,
         'label': 'Simulations'},
        {'id': 'n_steps',       'type': 'int', 'default': 10, 'min': 1, 'max': 100,
         'label': 'Propagation Steps'},
        {'id': 'resistance',    'type': 'float', 'default': 0.5, 'min': 0.0, 'max': 1.0,
         'label': 'Base Resistance'},
        {'id': 'neighborhood',  'type': 'enum', 'default': '8-connected',
         'options': ['8-connected', '4-connected'], 'label': 'Neighborhood'},
        {'id': 'node_note',     'type': 'string', 'default': '',
         'label': 'Note'},
    ],
)
class UtilMonteCarloPropagationNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        seed_img = inputs.get('seed')
        if seed_img is None:
            return {'probability': None, 'preview': None, 'stats': None}

        # Handle geodict vs raw numpy array (automatic unpacking if fed from a geo node)
        if isinstance(seed_img, dict) and 'bands' in seed_img:
            seed_bands = seed_img['bands']
            seed_2d = seed_bands[0] if seed_bands.ndim == 3 else seed_bands
        else:
            seed_2d = seed_img

        # Convert seed to binary mask
        if seed_2d.ndim == 3:
            seed_gray = cv2.cvtColor(seed_2d, cv2.COLOR_BGR2GRAY)
        else:
            seed_gray = seed_2d
        seed_mask = (seed_gray > 0).astype(np.uint8)
        H, W = seed_mask.shape

        # Extract parameters
        n_simulations = max(10, int(params.get('n_simulations', 100)))
        n_steps = max(1, int(params.get('n_steps', 10)))
        resistance = np.clip(float(params.get('resistance', 0.5)), 0.0, 1.0)
        neighborhood = params.get('neighborhood', '8-connected')

        # Retrieve and normalize attractiveness map if available
        attr_in = inputs.get('attractiveness')
        if attr_in is not None:
            if isinstance(attr_in, dict) and 'bands' in attr_in:
                attr_bands = attr_in['bands']
                attr_2d = attr_bands[0] if attr_bands.ndim == 3 else attr_bands
            else:
                attr_2d = attr_in

            # Resize to match seed shape if necessary
            if attr_2d.shape[:2] != (H, W):
                attr_2d = cv2.resize(attr_2d, (W, H), interpolation=cv2.INTER_LINEAR)

            if attr_2d.ndim == 3:
                attr_gray = cv2.cvtColor(attr_2d, cv2.COLOR_BGR2GRAY)
            else:
                attr_gray = attr_2d
            attractiveness = attr_gray.astype(np.float32) / 255.0
        else:
            attractiveness = np.ones((H, W), dtype=np.float32)

        # Set up neighborhood kernel
        if neighborhood == '4-connected':
            kernel = np.array([[0, 1, 0],
                               [1, 1, 1],
                               [0, 1, 0]], dtype=np.uint8)
        else:
            kernel = np.ones((3, 3), dtype=np.uint8)

        accumulated = np.zeros((H, W), dtype=np.float32)
        rng = np.random.default_rng(42)

        # Run simulations
        for sim in range(n_simulations):
            state = np.copy(seed_mask)
            for step in range(n_steps):
                dilated = cv2.dilate(state, kernel)
                border = (dilated == 1) & (state == 0)
                if not np.any(border):
                    break
                rand = rng.random((H, W))
                infection = border & (rand < (attractiveness * (1.0 - resistance)))
                state[infection] = 1
            accumulated += state

            if sim % max(1, n_simulations // 5) == 0:
                self.report_progress(
                    0.1 + 0.8 * (sim / n_simulations),
                    f"Monte Carlo Generic: Simulating {sim}/{n_simulations}..."
                )

        # Probability map (0-255 grayscale representation)
        prob_map_pct = (accumulated / n_simulations) * 100.0
        prob_map_uint8 = (accumulated / n_simulations * 255.0).astype(np.uint8)

        # Apply false color mapping for preview (using COLORMAP_JET)
        preview_rgb = cv2.applyColorMap(prob_map_uint8, cv2.COLORMAP_JET)
        # Background/Zero-risk pixels set to black
        preview_rgb[prob_map_uint8 == 0] = [0, 0, 0]
        # Highlight original seeds in bright cyan/blue-cyan
        preview_rgb[seed_mask > 0] = [255, 255, 0]

        # Calculate statistics
        total_pixels = float(H * W)
        active_T0_pct = float(seed_mask.sum() / total_pixels) * 100.0
        prob_high_pct = float((prob_map_pct > 50.0).sum() / total_pixels) * 100.0
        prob_med_pct = float(((prob_map_pct >= 15.0) & (prob_map_pct <= 50.0)).sum() / total_pixels) * 100.0
        prob_low_pct = float(((prob_map_pct >= 2.0) & (prob_map_pct < 15.0)).sum() / total_pixels) * 100.0

        stats_dict = {
            'seed_surface_pct': round(active_T0_pct, 2),
            'risk_high_pct': round(prob_high_pct, 2),
            'risk_medium_pct': round(prob_med_pct, 2),
            'risk_low_pct': round(prob_low_pct, 2),
            'simulations_run': n_simulations,
        }

        # Create thumbnail for display in UI node graph
        h, w = preview_rgb.shape[:2]
        sc = min(1.0, 120 / h)
        thumb = cv2.resize(preview_rgb, (max(1, int(w * sc)), max(1, int(h * sc))))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        thumb_b64 = base64.b64encode(buf).decode('utf-8')

        return {
            'probability': prob_map_uint8,
            'preview': preview_rgb,
            'stats': stats_dict,
            '_thumb': thumb_b64
        }
