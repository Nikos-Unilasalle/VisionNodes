"""
geo_monte_carlo_propagation.py — Stochastic Monte Carlo simulation for predicting gold mining (orpaillage) propagation.

Models risk by simulating multiple paths of expansion from existing active sites,
taking into account terrain slopes and HAND (Height Above Nearest Drainage) as constraints.
"""
import numpy as np
import cv2
import base64

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'monte_carlo_prop'


def _reproject_onto(target_geo: dict, source_geo: dict) -> np.ndarray:
    """Reproject single-band source raster onto target grid.

    Uses rasterio bilinear warping if possible, or OpenCV bilinear resizing as a fallback.
    """
    src_bands = source_geo.get('bands')
    if src_bands is None:
        raise ValueError("Source geodict does not contain bands.")

    src_2d = src_bands[0] if src_bands.ndim == 3 else src_bands

    target_bands = target_geo.get('bands')
    if target_bands is None:
        raise ValueError("Target geodict does not contain bands.")
    _, tH, tW = target_bands.shape if target_bands.ndim == 3 else (1, *target_bands.shape)

    try:
        import rasterio
        from rasterio.warp import reproject, Resampling

        target_crs = target_geo.get('crs')
        src_crs = source_geo.get('crs')
        target_transform = target_geo.get('transform')
        src_transform = source_geo.get('transform')

        if target_crs is None or src_crs is None or target_transform is None or src_transform is None:
            # Fallback to OpenCV bilinear resizing if georeferencing is missing
            return cv2.resize(src_2d.astype(np.float32), (tW, tH), interpolation=cv2.INTER_LINEAR)

        out = np.zeros((tH, tW), dtype=np.float32)
        reproject(
            source=src_2d.astype(np.float32),
            destination=out,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=target_transform,
            dst_crs=target_crs,
            resampling=Resampling.bilinear,
        )
        return out
    except Exception as e:
        send_notification(
            f'Monte Carlo: error aligning grids ({e}) — using OpenCV fallback',
            level='warning',
            notif_id=_NOTIF
        )
        return cv2.resize(src_2d.astype(np.float32), (tW, tH), interpolation=cv2.INTER_LINEAR)


@vision_node(
    type_id='geo_monte_carlo_propagation',
    label='Monte Carlo Propagation',
    category='geography',
    icon='Activity',
    description=(
        "Simulates potential paths of gold mining (orpaillage) propagation stochastically. "
        "Inputs active sites as the starting seed and constrains propagation using slope and HAND. "
        "Outputs a risk map (0-100%), visual preview, and area statistics."
    ),
    inputs=[
        {'id': 'active', 'color': 'geotiff', 'label': 'Active sites (T0 mask)'},
        {'id': 'slope',  'color': 'geotiff', 'label': 'Slope map (degrees)'},
        {'id': 'hand',   'color': 'geotiff', 'label': 'HAND map (meters)'},
    ],
    outputs=[
        {'id': 'risk',    'color': 'geotiff', 'label': 'Risk map (percentage)'},
        {'id': 'preview', 'color': 'image',   'label': 'Risk preview (RGB)'},
        {'id': 'stats',   'color': 'dict',    'label': 'Risk stats (dict)'},
    ],
    params=[
        {'id': 'n_simulations', 'type': 'int', 'default': 100, 'min': 10, 'max': 1000,
         'label': 'Monte Carlo Simulations'},
        {'id': 'n_steps',       'type': 'int', 'default': 5, 'min': 1, 'max': 20,
         'label': 'Propagation Horizon (Steps)'},
        {'id': 'prob_threshold', 'type': 'float', 'default': 0.85, 'min': 0.0, 'max': 1.0,
         'label': 'Forest Resistance (0 = none, 1 = absolute)'},
        {'id': 'hand_max',      'type': 'float', 'default': 12.0, 'min': 1.0, 'max': 50.0,
         'label': 'Max HAND for mining (m)'},
        {'id': 'slope_max',     'type': 'float', 'default': 15.0, 'min': 1.0, 'max': 45.0,
         'label': 'Max slope for mining (°)'},
        {'id': 'node_note',     'type': 'string', 'default': '',
         'label': 'Note'},
    ],
)
class GeoMonteCarloPropagationNode(NodeProcessor):

    def process(self, inputs: dict, params: dict) -> dict:
        active_geo = inputs.get('active')
        slope_geo = inputs.get('slope')
        hand_geo = inputs.get('hand')

        if active_geo is None or slope_geo is None or hand_geo is None:
            send_notification(
                "Monte Carlo: waiting for all inputs (Active sites, Slope, HAND)...",
                notif_id=_NOTIF
            )
            return {'risk': None, 'preview': None, 'stats': None}

        # Extract parameters
        n_simulations = max(10, int(params.get('n_simulations', 100)))
        n_steps = max(1, int(params.get('n_steps', 5)))
        prob_threshold = np.clip(float(params.get('prob_threshold', 0.85)), 0.0, 1.0)
        hand_max = float(params.get('hand_max', 12.0))
        slope_max = float(params.get('slope_max', 15.0))

        # Retrieve and shape reference active sites map
        active_bands = active_geo['bands']
        active = active_bands[0] if active_bands.ndim == 3 else active_bands
        fH, fW = active.shape

        send_notification("Monte Carlo: Aligning grids...", progress=0.1, notif_id=_NOTIF)

        # Reproject and clean inputs to reference active site grid
        slope_2d = _reproject_onto(active_geo, slope_geo)
        hand_2d = _reproject_onto(active_geo, hand_geo)

        slope_2d = np.where(np.isfinite(slope_2d), slope_2d, slope_max + 1.0)
        hand_2d = np.where(np.isfinite(hand_2d), hand_2d, hand_max + 1.0)
        slope_2d = np.clip(slope_2d, 0.0, None)
        hand_2d = np.clip(hand_2d, 0.0, None)

        send_notification("Monte Carlo: Running simulation...", progress=0.3, notif_id=_NOTIF)

        # Calculate attractiveness based on geomorphological variables
        # Attraction exponentially drops as slopes and HAND heights increase
        attractiveness = np.exp(-slope_2d / 10.0) * np.exp(-hand_2d / 8.0)
        # Apply strict hard cutoffs
        attractiveness[hand_2d > hand_max] = 0.0
        attractiveness[slope_2d > slope_max] = 0.0

        # We use a 3x3 structuring element (8-neighbor dilation) to represent adjacent expansion
        kernel = np.ones((3, 3), dtype=np.uint8)

        accumulated_risk = np.zeros((fH, fW), dtype=np.float32)

        # Initialize random generator for reproducibility across steps
        rng = np.random.default_rng(42)

        # Run Monte Carlo loop
        for sim in range(n_simulations):
            current_state = (active > 0).astype(np.uint8)

            for step in range(n_steps):
                # Identify neighboring uninfected pixels
                dilated = cv2.dilate(current_state, kernel)
                border = (dilated == 1) & (current_state == 0)

                if not np.any(border):
                    break

                # Draw random numbers and check if they exceed resistance threshold
                random_noise = rng.random((fH, fW))
                infection = border & (random_noise < (attractiveness * (1.0 - prob_threshold)))
                current_state[infection] = 1

            accumulated_risk += current_state

            # Stream progress updates periodically
            if sim % max(1, n_simulations // 5) == 0:
                pct = 0.3 + 0.6 * (sim / n_simulations)
                send_notification(
                    f"Monte Carlo: Simulating {sim}/{n_simulations}...",
                    progress=pct,
                    notif_id=_NOTIF
                )

        # Calculate final risk percentages
        risk_map_pct = (accumulated_risk / n_simulations) * 100.0

        # Create colorized preview
        # Mask active pixels at T0 to color them separately
        risk_only = np.copy(risk_map_pct)
        risk_only[active > 0] = 0.0

        preview_rgb = np.zeros((fH, fW, 3), dtype=np.uint8)
        # Red: high risk (> 50%)
        preview_rgb[risk_only > 50.0] = [40, 40, 200]
        # Orange: medium risk (15% to 50%)
        preview_rgb[(risk_only >= 15.0) & (risk_only <= 50.0)] = [40, 140, 220]
        # Yellow: low risk (2% to 15%)
        preview_rgb[(risk_only >= 2.0) & (risk_only < 15.0)] = [40, 220, 220]
        # Cyan-Blue: active historical mining sites
        preview_rgb[active > 0] = [200, 100, 40]

        # Calculate statistics
        total_pixels = float(fH * fW)
        active_T0_pct = float((active > 0).sum() / total_pixels) * 100.0
        risk_high_pct = float((risk_only > 50.0).sum() / total_pixels) * 100.0
        risk_med_pct = float(((risk_only >= 15.0) & (risk_only <= 50.0)).sum() / total_pixels) * 100.0
        risk_low_pct = float(((risk_only >= 2.0) & (risk_only < 15.0)).sum() / total_pixels) * 100.0

        stats_dict = {
            'surface_active_T0_pct': round(active_T0_pct, 2),
            'surface_risk_high_pct': round(risk_high_pct, 2),
            'surface_risk_medium_pct': round(risk_med_pct, 2),
            'surface_risk_low_pct': round(risk_low_pct, 2),
            'simulations_run': n_simulations,
        }

        # Build output geodict
        risk_geo = {
            **active_geo,
            'bands': risk_map_pct[np.newaxis].astype(np.float32),
            'count': 1,
            'band_names': ['risk_percentage'],
            'dtype': 'float32',
            '_source': 'monte_carlo_propagation',
            '_bands': ['risk_percentage'],
            'preview': preview_rgb,
        }

        # Create thumbnail for display in UI node graph
        h, w = preview_rgb.shape[:2]
        sc = min(1.0, 120 / h)
        thumb = cv2.resize(preview_rgb, (max(1, int(w * sc)), max(1, int(h * sc))))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 60])
        thumb_b64 = base64.b64encode(buf).decode('utf-8')

        send_notification("Monte Carlo: Done ✓", progress=1.0, notif_id=_NOTIF)

        return {
            'risk': risk_geo,
            'preview': preview_rgb,
            'stats': stats_dict,
            '_thumb': thumb_b64
        }
