import cv2
import numpy as np
from registry import vision_node, NodeProcessor

POLARITY = ['Bright Peaks (maxima)', 'Dark Pits (minima)']
MIN_SIGMA = 0.0
FLAT_EPS = 0.02


def _gray_float(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return g.astype(np.float32)


def _local_peaks(smooth, min_distance, allowed):
    """(row, col) of pixels equal to the max of their (2d+1)² neighbourhood, inside `allowed`."""
    size = 2 * int(min_distance) + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    dilated = cv2.dilate(smooth, kernel)
    eroded = cv2.erode(smooth, kernel)
    span = float(smooth.max() - smooth.min()) or 1.0
    # A peak must rise above its neighbourhood: flat plateaus (e.g. empty background) are not objects
    is_peak = (smooth >= dilated) & ((smooth - eroded) > FLAT_EPS * span) & allowed
    # Plateaus: keep one pixel per connected flat peak
    n, labels, _, centroids = cv2.connectedComponentsWithStats(is_peak.astype(np.uint8), connectivity=8)
    pts = np.round(centroids[1:]).astype(int)
    if len(pts) == 0:
        return pts.reshape(0, 2)
    pts[:, 0] = np.clip(pts[:, 0], 0, smooth.shape[1] - 1)
    pts[:, 1] = np.clip(pts[:, 1], 0, smooth.shape[0] - 1)
    return pts[:, ::-1]


def _suppress_close(points, smooth, min_distance):
    """Greedy non-maximum suppression: strongest peaks first, drop neighbours closer than min_distance."""
    if len(points) == 0:
        return points
    order = np.argsort(-smooth[points[:, 0], points[:, 1]])
    kept, taken = [], np.zeros(smooth.shape, bool)
    r = max(1, int(min_distance))
    for idx in order:
        y, x = points[idx]
        if taken[y, x]:
            continue
        kept.append((y, x))
        cv2.circle(taken.view(np.uint8), (int(x), int(y)), r, 1, -1)
    return np.array(kept, dtype=int)


@vision_node(
    type_id='feat_peak_markers',
    label='Local Maxima Markers',
    category='segmentation',
    icon='Crosshair',
    description=(
        "One marker per bright (or dark) object: local maxima of the smoothed image, at least "
        "'Min Distance' apart. Feed the markers to Watershed to split touching objects into "
        "whole regions (cells, nuclei, grains, stars). Sigma ≈ object radius / 2, Min Distance "
        "≈ object radius; both can be driven by a Number."
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'mask', 'color': 'mask', 'label': 'Region (opt.)'},
        {'id': 'sigma', 'color': 'scalar', 'label': 'Sigma'},
        {'id': 'min_distance', 'color': 'scalar', 'label': 'Min Distance'},
    ],
    outputs=[
        {'id': 'markers', 'color': 'markers'},
        {'id': 'points', 'color': 'mask', 'label': 'Marker Dots'},
        {'id': 'count', 'color': 'scalar'},
    ],
    params=[
        {'id': 'polarity', 'label': 'Find', 'type': 'enum', 'options': POLARITY, 'default': 0},
        {'id': 'sigma', 'label': 'Smoothing Sigma (px)', 'type': 'float', 'default': 3.0, 'min': MIN_SIGMA, 'max': 50, 'step': 0.1},
        {'id': 'min_distance', 'label': 'Min Distance (px)', 'type': 'float', 'default': 7.0, 'min': 1, 'max': 200, 'step': 0.5},
    ],
)
class PeakMarkersNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'markers': None, 'points': None, 'count': 0}

        g = _gray_float(img)
        if int(params.get('polarity', 0)) == 1:
            g = -g
        sigma = max(MIN_SIGMA, float(params.get('sigma', 3.0)))
        smooth = cv2.GaussianBlur(g, (0, 0), sigma) if sigma > 0 else g
        min_dist = max(1.0, float(params.get('min_distance', 7.0)))

        mask = inputs.get('mask')
        if mask is not None:
            m = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY) if mask.ndim == 3 else mask
            if m.shape != g.shape:
                m = cv2.resize(m, (g.shape[1], g.shape[0]), interpolation=cv2.INTER_NEAREST)
            allowed = m > 0
        else:
            allowed = np.ones(g.shape, bool)

        peaks = _suppress_close(_local_peaks(smooth, min_dist, allowed), smooth, min_dist)
        markers = np.zeros(g.shape, np.int32)
        dots = np.zeros(g.shape, np.uint8)
        if len(peaks):
            markers[peaks[:, 0], peaks[:, 1]] = np.arange(1, len(peaks) + 1, dtype=np.int32)
            for y, x in peaks:
                cv2.circle(dots, (int(x), int(y)), 2, 255, -1)
        return {'markers': markers, 'points': dots, 'count': int(len(peaks))}
