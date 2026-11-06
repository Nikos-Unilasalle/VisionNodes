import cv2
import numpy as np
from registry import vision_node, NodeProcessor

METHODS = ['Sato', 'Meijering', 'Frangi']
POLARITIES = ['Dark ridges (dark walls, bright lumens)', 'Bright ridges']


def _gray_float(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return g.astype(np.float32)


def _binary(m, shape):
    m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY) if m.ndim == 3 else m
    if m.shape != shape:
        m = cv2.resize(m, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return m > 0


def ridge_map(gray, method=0, dark=True, sigma_min=1.0, sigma_max=2.5, n_scales=3):
    from skimage.filters import frangi, meijering, sato
    sigmas = np.linspace(sigma_min, max(sigma_max, sigma_min), max(1, n_scales))
    f = (sato, meijering, frangi)[method]
    return f(gray, sigmas=sigmas, black_ridges=dark).astype(np.float32)


def normalize_local(r, radius, floor_pct, inside=None):
    """Ridge strength relative to its neighbourhood: 1 = a typical ridge nearby. Faint walls in a
    pale area count as much as strong walls in a dark one; the floor (a percentile of the local
    level) keeps flat, ridge-free areas from having their noise blown up."""
    loc = cv2.GaussianBlur(r, (0, 0), radius)
    ref = loc[inside] if inside is not None and inside.any() else loc
    floor = max(float(np.percentile(ref, floor_pct)), 1e-6)
    return r / np.maximum(loc, floor)


@vision_node(
    type_id='filter_ridge',
    label='Ridge Filter',
    category='image',
    icon='Waves',
    description=(
        "Enhances thin lines — cell walls, vessels, cracks, leaf veins, fibres — whatever their "
        "brightness, using the curvature of the image (Hessian matrix) at several scales "
        "(Sato, Meijering or Frangi filter). Width scales: σ ≈ half the line thickness in px.\n\n"
        "Local Normalisation divides the ridge strength by its average around each pixel, so "
        "that faint lines in a pale or blurred area come out as clearly as strong ones (1 = a "
        "typical ridge of the neighbourhood). Set the radius to a few object widths; 0 = off. "
        "The floor (percentile of the local level) stops flat areas from turning their noise "
        "into ridges.\n\n"
        "'main' is the map scaled to 0–255; 'ridge' keeps the float values (input of Cell "
        "Tessellation). The optional mask limits the statistics and the output to a region."
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
        {'id': 'mask', 'color': 'mask', 'label': 'Region (opt.)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image'},
        {'id': 'ridge', 'color': 'any', 'label': 'Ridge Map (float)'},
    ],
    params=[
        {'id': 'method', 'label': 'Method', 'type': 'enum', 'options': METHODS, 'default': 0},
        {'id': 'polarity', 'label': 'Lines Are', 'type': 'enum', 'options': POLARITIES, 'default': 0},
        {'id': 'sigma_min', 'label': 'Smallest Scale σ (px)', 'type': 'float', 'default': 1.0, 'min': 0.5, 'max': 20, 'step': 0.5},
        {'id': 'sigma_max', 'label': 'Largest Scale σ (px)', 'type': 'float', 'default': 2.5, 'min': 0.5, 'max': 20, 'step': 0.5},
        {'id': 'n_scales', 'label': 'Scales', 'type': 'int', 'default': 3, 'min': 1, 'max': 8},
        {'id': 'norm_radius', 'label': 'Local Normalisation Radius (px, 0 = off)', 'type': 'float', 'default': 15, 'min': 0, 'max': 200, 'step': 1},
        {'id': 'floor_pct', 'label': 'Normalisation Floor (percentile)', 'type': 'float', 'default': 40, 'min': 0, 'max': 95, 'step': 5},
    ],
)
class RidgeFilterNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None, 'ridge': None}
        gray = _gray_float(img)
        m_in = inputs.get('mask')
        inside = _binary(m_in, gray.shape) if m_in is not None else None
        r = ridge_map(gray, int(params.get('method', 0)), int(params.get('polarity', 0)) == 0,
                      float(params.get('sigma_min', 1.0)), float(params.get('sigma_max', 2.5)),
                      int(params.get('n_scales', 3)))
        radius = float(params.get('norm_radius', 15))
        if radius > 0:
            r = normalize_local(r, radius, float(params.get('floor_pct', 40)), inside)
        if inside is not None:
            r[~inside] = 0
        top = float(np.percentile(r[r > 0], 99)) if (r > 0).any() else 1.0
        vis = (np.clip(r / max(top, 1e-6), 0, 1) * 255).astype(np.uint8)
        return {'main': vis, 'ridge': r}
