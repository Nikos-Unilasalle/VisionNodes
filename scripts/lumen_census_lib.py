"""Stele census by lumens: one cell per brightness maximum, without closing its walls.

In the stele the cells are a few pixels wide and their thin walls are often open in the image:
a segmentation that needs closed walls merges neighbours and sees only the largest cells. A lumen
is still a bright spot between its walls. The smoothed image is cut into basins, one per brightness
maximum deeper than LUMEN_DEPTH (watershed of the inverted image), and each basin is one cell.

Two lumens whose common wall is too faint share one basin. Such a basin is not convex: a basin
whose solidity is below CLUMP_SOLIDITY holds as many cells as its area holds typical cells, the
typical cell being the peak of the distribution of basin sizes in the zone (in log area, so that
neither merged basins, on its right, nor fragments, on its left, move it).
"""
import cv2
import numpy as np
from scipy import ndimage as ndi
from scipy.stats import gaussian_kde
from skimage.measure import regionprops
from skimage.morphology import h_maxima
from skimage.segmentation import watershed

LUMEN_SMOOTHING_PX = 1.2   # working px: removes sensor noise, keeps lumens a few px wide
LUMEN_DEPTH = 2.0          # grey levels a lumen stands above the wall separating it from its neighbour
CLUMP_SOLIDITY = 0.88      # a basin less convex than this holds several cells
MIN_BASINS = 8             # below this the size distribution has no readable peak
INSIDE_SHARE = 0.5         # a basin belongs to the zone that holds at least half of it


def lumen_basins(gray, region):
    """Label map of the basins of `region` (bool), one per lumen; 0 outside."""
    region = np.asarray(region, bool)
    smooth = cv2.GaussianBlur(np.asarray(gray, np.float32), (0, 0), LUMEN_SMOOTHING_PX)
    markers, _ = ndi.label(h_maxima(smooth, LUMEN_DEPTH) & region)
    return watershed(-smooth, markers, mask=region)


def typical_area(areas):
    """Peak of the distribution of basin sizes (px), read on the log of the areas."""
    log_a = np.log(np.asarray(areas, float))
    if np.ptp(log_a) == 0:
        return float(np.exp(log_a[0]))
    x = np.linspace(log_a.min(), log_a.max(), 400)
    return float(np.exp(x[int(np.argmax(gaussian_kde(log_a)(x)))]))


def basin_shapes(basins):
    """{label: (area, solidity)} of every basin."""
    return {p.label: (float(p.area), float(p.solidity)) for p in regionprops(np.asarray(basins))}


def zone_census(basins, zone, vessels, shapes=None, **_):
    """(basins of the zone, estimated cells, 0): same contract as census_lib.zone_census."""
    basins = np.asarray(basins)
    zone = np.asarray(zone, bool) & ~np.asarray(vessels, bool)
    shapes = basin_shapes(basins) if shapes is None else shapes
    ids, inside = np.unique(basins[zone], return_counts=True)
    own = [i for i, n in zip(ids, inside) if i > 0 and n >= INSIDE_SHARE * shapes[i][0]]
    if not own:
        return 0, 0, 0
    area = np.array([shapes[i][0] for i in own])
    solidity = np.array([shapes[i][1] for i in own])
    cells = np.ones(len(own))
    if len(own) >= MIN_BASINS:
        clump = solidity < CLUMP_SOLIDITY
        cells[clump] = np.maximum(1, np.round(area[clump] / typical_area(area)))
    return len(own), int(cells.sum()), 0
