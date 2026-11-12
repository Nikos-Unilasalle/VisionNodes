"""Photometric normalisation of an upload: uneven illumination and flattened contrast are undone.

Downstream steps threshold grey levels (the section threshold has an absolute offset, wall
detection compares local levels), so a micrograph with a lighting gradient or a weak exposure is
first brought back to the photometry of a correct one. The rule is to restore, never degrade:
a correct micrograph passes through unchanged.

  backdrop      untextured pixels connected to the image border (the slide around the root);
                lumens are untextured too but enclosed by tissue, so they are not taken
  illumination  a quadratic surface fitted to the backdrop (robustly, outliers trimmed); when it
                varies by more than MAX_FLAT_VARIATION under the root, the image is divided by it
                (rescaled to its median, so the backdrop keeps its level)
  contrast      backdrop minus the darkest walls (2nd percentile of the tissue); below
                MIN_CONTRAST it is stretched back to MIN_CONTRAST around the backdrop level
"""
import cv2
import numpy as np

TEXTURE_SCALE = 1 / 80          # fraction of the image's longer side: window of the texture measure
MIN_BACKDROP_SHARE = 0.05       # less backdrop than this: the illumination is not estimated
MAX_FLAT_VARIATION = 0.12       # peak-to-peak / median of the fitted illumination under the root
MIN_CONTRAST = 120.0            # grey levels from the backdrop to the darkest walls (clean images: 130-170)
WALL_PERCENTILE = 2
TISSUE_MARGIN = 15              # grey levels under the backdrop: tissue
MAX_STRETCH = 6.0
FIT_SAMPLES = 20000
TRIM_MADS = 2.5


def _texture(gray):
    """Local mean gradient magnitude, smoothed over a window proportional to the image size."""
    g = cv2.GaussianBlur(gray, (0, 0), 1.0)
    mag = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    k = max(3, int(round(max(gray.shape) * TEXTURE_SCALE)) | 1)
    return cv2.blur(mag, (k, k))


def backdrop_mask(gray):
    """Untextured region connected to the image border (bool)."""
    tex = np.log1p(_texture(gray))
    t8 = cv2.normalize(tex, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, smooth = cv2.threshold(t8, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, lab = cv2.connectedComponents(smooth.astype(np.uint8))
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    return np.isin(lab, border[border > 0])


def _design(xx, yy, shape):
    h, w = shape
    x, y = xx / w - 0.5, yy / h - 0.5
    return np.column_stack([np.ones_like(x), x, y, x * x, x * y, y * y])


def fit_illumination(gray, backdrop, rng=None):
    """Quadratic illumination surface fitted to the backdrop, outliers trimmed; None if too little backdrop."""
    if backdrop.mean() < MIN_BACKDROP_SHARE:
        return None
    rng = rng if rng is not None else np.random.default_rng(0)
    ys, xs = np.nonzero(backdrop)
    pick = rng.choice(len(xs), min(FIT_SAMPLES, len(xs)), replace=False)
    A = _design(xs[pick].astype(float), ys[pick].astype(float), gray.shape)
    v = gray[ys[pick], xs[pick]].astype(float)
    keep = np.ones(len(v), bool)
    for _ in range(3):
        coef, *_ = np.linalg.lstsq(A[keep], v[keep], rcond=None)
        res = v - A @ coef
        mad = np.median(np.abs(res[keep] - np.median(res[keep]))) + 1e-6
        keep = np.abs(res) <= TRIM_MADS * 1.4826 * mad
    yy, xx = np.indices(gray.shape)
    return (_design(xx.ravel().astype(float), yy.ravel().astype(float), gray.shape) @ coef).reshape(gray.shape)


def normalise(img):
    """(normalised BGR uint8 image, report dict). The input is not modified."""
    f = img.astype(np.float32)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    backdrop = backdrop_mask(gray)
    report = {'backdrop_share': float(backdrop.mean()), 'flat_field': False, 'stretch': 1.0,
              'illumination_variation': None}
    surface = fit_illumination(gray, backdrop)
    if surface is not None:
        under = ~backdrop
        level = float(np.median(surface[backdrop]))
        span = surface[under] if under.any() else surface
        variation = float((np.percentile(span, 99) - np.percentile(span, 1)) / max(level, 1.0))
        report['illumination_variation'] = variation
        if variation > MAX_FLAT_VARIATION:
            gain = level / np.clip(surface, 1.0, None)
            f = f * gain[..., None]
            gray = gray * gain
            report['flat_field'] = True
    if backdrop.any():
        bg = float(np.median(gray[backdrop]))
        tissue = gray[~backdrop & (gray < bg - TISSUE_MARGIN)]
        if tissue.size:
            contrast = bg - float(np.percentile(tissue, WALL_PERCENTILE))
            report['contrast'] = contrast
            if 0 < contrast < MIN_CONTRAST:
                s = min(MIN_CONTRAST / contrast, MAX_STRETCH)
                bg_bgr = np.median(f[backdrop], axis=0)       # each channel around its own backdrop: no tint
                f = bg_bgr + s * (f - bg_bgr)
                report['stretch'] = float(s)
    out = np.clip(f, 0, 255).astype(np.uint8)
    return out, report
