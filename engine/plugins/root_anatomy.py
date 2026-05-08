import cv2
import numpy as np
import os
import base64
from registry import NodeProcessor, vision_node
from skimage import measure


# --- Anatomy State ---
class RootAnatomyState:
    def __init__(self, image, px_per_mm=1.0):
        self.original = image
        self.px_per_mm = float(px_per_mm)
        self.masks = {
            'section': None,
            'stele': None,
            'cortex': None,
            'aerenchyma': None,
            'xylem': None,
            'protoxylem': None,
            'endodermis': None,
            'exodermis': None,
        }
        self.stats = {}

    def to_dict(self):
        """Returns a JSON-serializable summary of the state."""
        return {
            'px_per_mm': self.px_per_mm,
            'stats': self._clean_stats(),
            'has_section': self.masks['section'] is not None,
            'has_stele': self.masks['stele'] is not None,
        }

    def _clean_stats(self):
        """Converts stats to plain Python types for JSON compatibility."""
        clean = {}
        for k, v in self.stats.items():
            if v is None:
                clean[k] = None
            elif isinstance(v, (np.integer, np.floating)):
                clean[k] = float(v)
            elif isinstance(v, (tuple, list, np.ndarray)):
                if k == 'centroid' and len(v) >= 2:
                    clean[k] = [float(v[0]), float(v[1])]
                else:
                    clean[k] = str(v)
            else:
                clean[k] = v
        return clean

    def sync(self, data):
        """Syncs the state back into the data dictionary."""
        if not isinstance(data, dict):
            return
        summary = self.to_dict()
        data.update(summary)
        data['_state'] = self


# --- Helpers ---
def _state(data):
    """Extract state from data dict. Returns None if invalid."""
    if not isinstance(data, dict):
        return None
    st = data.get('_state')
    if isinstance(st, RootAnatomyState):
        return st
    return None


def _encode_preview(img, quality=50):
    """Encodes a numpy BGR image to base64 JPEG string for UI thumbnails."""
    if img is None:
        return None
    try:
        # Resize for thumbnail if too large
        h, w = img.shape[:2]
        if h > 180:
            sc = 180 / h
            img = cv2.resize(img, (int(w * sc), 180))
        _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return base64.b64encode(buf).decode('utf-8')
    except Exception:
        return None


def _otsu_masked(gray: np.ndarray, mask: np.ndarray):
    """Otsu threshold on masked pixels only.
    Computes threshold via numpy histogram to avoid cv2.threshold requiring
    a 2D input array when we only have a 1D masked pixel array."""
    pixels = gray[mask > 0].ravel().astype(np.uint8)
    if len(pixels) == 0:
        return 127, np.zeros_like(gray)

    hist = np.bincount(pixels, minlength=256).astype(np.float64)
    total = hist.sum()
    sum_total = float(np.dot(np.arange(256, dtype=np.float64), hist))

    best_var, thresh = 0.0, 0
    sum_b, w_b = 0.0, 0.0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_total - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > best_var:
            best_var = var
            thresh = t

    _, result = cv2.threshold(gray, thresh, 255, cv2.THRESH_BINARY)
    return thresh, result


def _to_gray(img):
    """Safely converts an image to grayscale, handling (H,W), (H,W,1), and (H,W,C)."""
    if img is None:
        return None
    if len(img.shape) == 2:
        return img.copy()
    if len(img.shape) == 3:
        if img.shape[2] >= 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img[:, :, 0].copy()
    return img.copy()


# --- Nodes ---

@vision_node(
    type_id="root_calibrate",
    label="Root Calibrate",
    category="root_anatomy",
    icon="Scaling",
    description="Sets the calibration factor (µm/pixel or px/mm) for root anatomy measurements.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "data", "color": "root_data", "label": "Anatomy Data"}],
    params=[
        {"id": "px_per_mm", "label": "Pixels per mm", "type": "float", "default": 204.0},
        {"id": "um_per_px", "label": "µm per pixel (alt)", "type": "float", "default": 0.0},
    ]
)
class RootCalibrateNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {"data": None}

        px_per_mm = params.get('px_per_mm', 204.0)
        um_per_px = params.get('um_per_px', 0.0)
        if um_per_px > 0:
            px_per_mm = 1000.0 / um_per_px

        state = RootAnatomyState(img, px_per_mm)
        data = {}
        state.sync(data)
        return {"data": data}


@vision_node(
    type_id="root_isolate_section",
    label="Isolate Section",
    category="root_anatomy",
    icon="Target",
    description="Isolates the root cross-section from the background and calculates RXSA.",
    inputs=[{"id": "data", "color": "root_data"}],
    outputs=[
        {"id": "data", "color": "root_data"},
        {"id": "preview", "color": "image", "label": "Section Mask"}
    ],
    params=[
        {"id": "invert", "label": "Invert (bright bg)", "type": "bool", "default": False},
        {"id": "blur", "label": "Gaussian Blur", "type": "int", "default": 5, "min": 0, "max": 21},
        {"id": "dilation", "label": "Dilation (cleanup)", "type": "int", "default": 2, "min": 0, "max": 10},
    ]
)
class RootIsolateNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        st = _state(data)
        if st is None:
            return {"data": None, "preview": None}

        img = st.original
        gray = _to_gray(img)
        h, w = gray.shape[:2]

        if params.get('invert', False):
            gray = cv2.bitwise_not(gray)

        blur_val = params.get('blur', 5)
        if blur_val > 0:
            k = blur_val if blur_val % 2 == 1 else blur_val + 1
            gray = cv2.GaussianBlur(gray, (k, k), 0)

        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Auto-orient: ensure background=0 regardless of image polarity
        # (corner pixels are almost always background)
        corners = [mask[0, 0], mask[0, w - 1], mask[h - 1, 0], mask[h - 1, w - 1]]
        if sum(v > 128 for v in corners) >= 3:
            mask = cv2.bitwise_not(mask)

        kernel = np.ones((3, 3), np.uint8)
        dil = params.get('dilation', 2)
        if dil > 0:
            mask = cv2.dilate(mask, kernel, iterations=dil)

        # Robust hole fill: flood background from all 4 corners with sentinel 128
        mask_ff = mask.copy()
        fm = np.zeros((h + 2, w + 2), np.uint8)
        for r, c in [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]:
            if mask_ff[r, c] == 0:
                cv2.floodFill(mask_ff, fm, (c, r), 128)
        # Pixels still 0 after flood = interior holes → fill them
        mask_ff[mask_ff == 0] = 255
        # Restore background (sentinel 128 → 0)
        mask_ff[mask_ff == 128] = 0
        mask = mask_ff

        if dil > 0:
            mask = cv2.erode(mask, kernel, iterations=dil)

        labels = measure.label(mask)
        props = measure.regionprops(labels)
        if props:
            largest = max(props, key=lambda x: x.area)
            mask = (labels == largest.label).astype(np.uint8) * 255
            st.stats['RXSA'] = round(largest.area / (st.px_per_mm ** 2), 4)
            st.masks['section'] = mask
            st.stats['centroid'] = largest.centroid

        st.sync(data)
        preview = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        return {"data": data, "preview": preview, "preview_b64": _encode_preview(preview)}


@vision_node(
    type_id="root_segment_stele",
    label="Segment Stele",
    category="root_anatomy",
    icon="Layers",
    description="Segments the stele using radial spatial weighting and local density analysis. Calculates TSA and SCWA.",
    inputs=[{"id": "data", "color": "root_data"}],
    outputs=[
        {"id": "data", "color": "root_data"},
        {"id": "preview", "color": "image", "label": "Stele Mask"},
        {"id": "density", "color": "image", "label": "Density Map (Debug)"}
    ],
    params=[
        {"id": "window_size", "label": "Density Window", "type": "int", "default": 20, "min": 5, "max": 100},
        {"id": "radial_weight", "label": "Radial Attenuation", "type": "float", "default": 2.0, "min": 0.0, "max": 10.0},
        {"id": "threshold_adj", "label": "Threshold Adj.", "type": "float", "default": 1.0, "min": 0.5, "max": 1.5},
        {"id": "invert", "label": "Invert (force)", "type": "bool", "default": False},
        {"id": "auto_invert", "label": "Auto-Polarity", "type": "bool", "default": True},
    ]
)
class RootSegmentSteleNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        st = _state(data)
        if st is None:
            return {"data": None, "preview": None, "density": None}

        section_mask = st.masks['section']
        if section_mask is None:
            return {"data": data, "preview": None, "density": None}

        img = st.original
        h, w = img.shape[:2]
        gray = _to_gray(img)
        
        # Auto-polarity: root should be bright for weighting to work
        do_invert = params.get('invert', False)
        if params.get('auto_invert', True):
            dt_ap = cv2.distanceTransform(section_mask, cv2.DIST_L2, 5)
            dt_norm_ap = cv2.normalize(dt_ap, None, 0, 1.0, cv2.NORM_MINMAX)
            m_inner = np.mean(gray[dt_norm_ap > 0.8]) if np.any(dt_norm_ap > 0.8) else 0
            m_outer = np.mean(gray[(dt_norm_ap < 0.3) & (section_mask > 0)]) if np.any((dt_norm_ap < 0.3) & (section_mask > 0)) else 255
            if m_inner < m_outer: # Stele is darker than cortex
                do_invert = not do_invert

        if do_invert:
            gray = cv2.bitwise_not(gray)

        # Radial spatial weighting via distance transform
        dt = cv2.distanceTransform(section_mask, cv2.DIST_L2, 5)
        dt_norm = cv2.normalize(dt, None, 0, 1.0, cv2.NORM_MINMAX)
        radial_weight = params.get('radial_weight', 2.0)
        weight_matrix = np.power(dt_norm, radial_weight)
        
        weighted_float = gray.astype(float) * weight_matrix
        if np.max(weighted_float) > 0:
            weighted = cv2.normalize(weighted_float, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        else:
            weighted = np.zeros_like(gray)

        # Local density map
        win = params.get('window_size', 20)
        density_map = cv2.GaussianBlur(weighted, (win | 1, win | 1), 0)
        density_map = cv2.bitwise_and(density_map, density_map, mask=section_mask)

        # Threshold with manual adjustment
        thresh, _ = _otsu_masked(density_map, section_mask)
        adj = params.get('threshold_adj', 1.0)
        _, stele_mask = cv2.threshold(density_map, int(thresh * adj), 255, cv2.THRESH_BINARY)
        stele_mask = cv2.bitwise_and(stele_mask, stele_mask, mask=section_mask)

        kernel = np.ones((5, 5), np.uint8)
        stele_mask = cv2.morphologyEx(stele_mask, cv2.MORPH_CLOSE, kernel)

        # Fill holes
        sf = stele_mask.copy()
        fm = np.zeros((h + 2, w + 2), np.uint8)
        cv2.floodFill(sf, fm, (0, 0), 255)
        stele_mask = stele_mask | cv2.bitwise_not(sf)

        labels = measure.label(stele_mask)
        props = measure.regionprops(labels)
        if props:
            largest = max(props, key=lambda x: x.area)
            stele_mask = (labels == largest.label).astype(np.uint8) * 255
            st.stats['TSA'] = round(largest.area / (st.px_per_mm ** 2), 4)

            # SCWA: Otsu on stele pixels only
            stele_gray = cv2.bitwise_and(gray, gray, mask=stele_mask)
            _, scwa_mask = _otsu_masked(stele_gray, stele_mask)
            st.stats['SCWA'] = round(float(np.sum(scwa_mask > 0)) / (st.px_per_mm ** 2), 4)
            st.masks['stele'] = stele_mask

        st.sync(data)
        preview = cv2.cvtColor(stele_mask, cv2.COLOR_GRAY2BGR)
        density_preview = cv2.applyColorMap(density_map, cv2.COLORMAP_VIRIDIS)
        return {
            "data": data, 
            "preview": preview, 
            "preview_b64": _encode_preview(preview),
            "density": density_preview,
            "density_b64": _encode_preview(density_preview)
        }


@vision_node(
    type_id="root_cortex_areas",
    label="Cortex Analysis",
    category="root_anatomy",
    icon="Box",
    description="Calculates cortical areas: TCA, CCWA, XSCWA.",
    inputs=[{"id": "data", "color": "root_data"}],
    outputs=[
        {"id": "data", "color": "root_data"},
        {"id": "preview", "color": "image", "label": "Cortex Mask"}
    ],
    params=[]
)
class RootCortexAreasNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        st = _state(data)
        if st is None:
            return {"data": None, "preview_b64": None, "stats": {}}

        section_mask = st.masks['section']
        stele_mask = st.masks['stele']
        if section_mask is None or stele_mask is None:
            return {"data": data, "preview": None}

        cortex_mask = cv2.subtract(section_mask, stele_mask)
        st.masks['cortex'] = cortex_mask

        px_per_mm = st.px_per_mm
        img = st.original
        gray = _to_gray(img)

        # TCA
        tca_mm2 = st.stats['RXSA'] - st.stats['TSA']
        st.stats['TCA'] = round(tca_mm2, 4)

        # CCWA: Otsu on cortex pixels only
        cortex_gray = cv2.bitwise_and(gray, gray, mask=cortex_mask)
        _, wall_mask_c = _otsu_masked(cortex_gray, cortex_mask)
        st.stats['CCWA'] = round(float(np.sum(wall_mask_c > 0)) / (px_per_mm ** 2), 4)

        # XSCWA: cross-section cell wall area (Table 1)
        section_gray = cv2.bitwise_and(gray, gray, mask=section_mask)
        _, xscwa_mask = _otsu_masked(section_gray, section_mask)
        st.stats['XSCWA'] = round(float(np.sum(xscwa_mask > 0)) / (px_per_mm ** 2), 4)

        # CCA and %CCA computed in RootAerenchymaNode (CCA = TCA - AA, Table 1)

        st.sync(data)
        preview = cv2.cvtColor(cortex_mask, cv2.COLOR_GRAY2BGR)
        return {"data": data, "preview": preview, "preview_b64": _encode_preview(preview)}


@vision_node(
    type_id="root_exclude_lateral",
    label="Exclude Lateral",
    category="root_anatomy",
    icon="Scissors",
    description="Excludes lateral roots using a polygon mask. Calculates LA. Must run before stele segmentation.",
    inputs=[
        {"id": "data", "color": "root_data"},
        {"id": "mask", "color": "mask", "label": "Exclusion Mask"}
    ],
    outputs=[{"id": "data", "color": "root_data"}],
    params=[]
)
class RootExcludeLateralNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        st = _state(data)
        if st is None:
            return {"data": None, "stats": {}}

        excl_mask = inputs.get('mask')
        if st.masks['section'] is not None and excl_mask is not None:
            if excl_mask.shape[:2] != st.masks['section'].shape[:2]:
                excl_mask = cv2.resize(excl_mask, (st.masks['section'].shape[1], st.masks['section'].shape[0]))
            excl_mask = _to_gray(excl_mask)

            la_px = float(np.sum(cv2.bitwise_and(excl_mask, excl_mask, mask=st.masks['section']) > 0))
            st.stats['LA'] = round(la_px / (st.px_per_mm ** 2), 4)

            st.masks['section'] = cv2.subtract(st.masks['section'], excl_mask)
            area_px = float(np.sum(st.masks['section'] > 0))
            st.stats['RXSA'] = round(area_px / (st.px_per_mm ** 2), 4)
        else:
            st.stats['LA'] = 0.0

        return {"data": data, "stats": dict(st.stats)}


@vision_node(
    type_id="root_aerenchyma_detect",
    label="Aerenchyma Detect",
    category="root_anatomy",
    icon="Wind",
    description="Detects aerenchyma lacunae (paper: major_axis > median + N×SD, excludes inner/outer 20% cortex). Computes AA, CCA, %CCA.",
    inputs=[{"id": "data", "color": "root_data"}],
    outputs=[
        {"id": "data", "color": "root_data"},
        {"id": "preview", "color": "image", "label": "Aerenchyma Mask"}
    ],
    params=[
        {"id": "min_area", "label": "Min Lacuna Area (px)", "type": "int", "default": 100},
        {"id": "sd_multiplier", "label": "Size Threshold (×SD)", "type": "float", "default": 1.0, "min": 0.5, "max": 6.0},
    ]
)
class RootAerenchymaNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        st = _state(data)
        if st is None:
            return {"data": None, "preview_b64": None, "stats": {}}

        cortex_mask = st.masks['cortex']
        if cortex_mask is None:
            return {"data": data, "preview": None}

        img = st.original
        gray = _to_gray(img)

        cortex_gray = cv2.bitwise_and(gray, gray, mask=cortex_mask)
        _, binary = _otsu_masked(cortex_gray, cortex_mask)

        spaces = cv2.bitwise_and(cv2.bitwise_not(binary), cv2.bitwise_not(binary), mask=cortex_mask)
        labels = measure.label(spaces)
        props = measure.regionprops(labels)

        min_area = params.get('min_area', 100)
        sd_mult = params.get('sd_multiplier', 1.0)

        # Paper criterion: major_axis > median + N×SD
        eligible = [p for p in props if p.area >= min_area]
        if eligible:
            major_axes = [p.major_axis_length for p in eligible]
            size_thresh = float(np.median(major_axes)) + sd_mult * float(np.std(major_axes))
        else:
            size_thresh = 0

        # Exclude inner/outer 20% of cortex depth (paper §Part IV)
        stele_mask = st.masks.get('stele')
        if stele_mask is not None:
            dist_from_stele = cv2.distanceTransform(cv2.bitwise_not(stele_mask), cv2.DIST_L2, 5)
            max_depth = float(np.max(dist_from_stele * (cortex_mask > 0)) + 1e-6)
        else:
            dist_from_stele = None
            max_depth = 1.0

        aerenchyma_mask = np.zeros_like(cortex_mask)
        lac_count = 0
        total_aa_px = 0

        for p in eligible:
            if p.major_axis_length <= size_thresh:
                continue
            if dist_from_stele is not None:
                cy, cx = int(p.centroid[0]), int(p.centroid[1])
                rel_d = dist_from_stele[cy, cx] / max_depth
                if rel_d < 0.2 or rel_d > 0.8:
                    continue
            aerenchyma_mask[labels == p.label] = 255
            lac_count += 1
            total_aa_px += p.area

        st.masks['aerenchyma'] = aerenchyma_mask
        st.stats['#Lac'] = lac_count
        aa_mm2 = total_aa_px / (st.px_per_mm ** 2)
        st.stats['AA'] = round(aa_mm2, 4)

        tca = st.stats.get('TCA', 0)
        if tca > 0:
            st.stats['%A'] = round((aa_mm2 / tca) * 100, 2)

        # CCA = TCA - AA (Table 1, not TCA - CCWA)
        cca_mm2 = tca - aa_mm2
        st.stats['CCA'] = round(cca_mm2, 4)
        # %CCA = CCA / RXSA (Table 1, denominator RXSA not TCA)
        rxsa = st.stats.get('RXSA', 0)
        if rxsa > 0:
            st.stats['%CCA'] = round((cca_mm2 / rxsa) * 100, 2)

        st.sync(data)
        preview = cv2.cvtColor(aerenchyma_mask, cv2.COLOR_GRAY2BGR)
        return {"data": data, "preview": preview, "preview_b64": _encode_preview(preview)}


@vision_node(
    type_id="root_cortical_cells",
    label="Cortical Cells",
    category="root_anatomy",
    icon="Calculator",
    description="Counts cortical cells across 3 radial bands (inner/mid/outer). Computes #CC, #CF, CSic/mc/oc.",
    inputs=[{"id": "data", "color": "root_data"}],
    outputs=[
        {"id": "data", "color": "root_data"},
        {"id": "preview", "color": "image", "label": "Cell Bands"}
    ],
    params=[
        {"id": "min_cell_area", "label": "Min Cell Area (px)", "type": "int", "default": 20, "min": 0, "max": 4000},
        {"id": "max_cell_area", "label": "Max Cell Area (px)", "type": "int", "default": 1000, "min": 0, "max": 4000},
    ]
)
class RootCorticalCellsNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        st = _state(data)
        if st is None:
            return {"data": None, "preview_b64": None, "stats": {}}

        cortex_mask = st.masks['cortex']
        stele_mask = st.masks['stele']
        if cortex_mask is None or stele_mask is None:
            return {"data": data, "preview": None}

        img = st.original
        gray = _to_gray(img)

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        inv_in_cortex = cv2.bitwise_and(cv2.bitwise_not(binary), cv2.bitwise_not(binary), mask=cortex_mask)
        labels = measure.label(inv_in_cortex)
        props = measure.regionprops(labels)

        dist_stele = cv2.distanceTransform(cv2.bitwise_not(stele_mask), cv2.DIST_L2, 5)
        max_cortex_width = float(np.max(dist_stele * (cortex_mask > 0)) + 1e-6)

        min_area = params.get('min_cell_area', 20)
        max_area = params.get('max_cell_area', 1000)
        px_per_mm = st.px_per_mm

        bands = np.zeros_like(cortex_mask)
        cell_counts = [0, 0, 0]
        cell_areas = [[], [], []]

        for p in props:
            if p.area < min_area or p.area > max_area:
                continue
            d = dist_stele[int(p.centroid[0]), int(p.centroid[1])]
            rel_d = d / max_cortex_width
            area_mm2 = p.area / (px_per_mm ** 2)
            if rel_d < 0.33:
                idx, val = 0, 80
            elif rel_d < 0.66:
                idx, val = 1, 160
            else:
                idx, val = 2, 255
            cell_counts[idx] += 1
            cell_areas[idx].append(area_mm2)
            bands[labels == p.label] = val

        st.stats['#CC'] = sum(cell_counts)
        st.stats['CSic'] = round(float(np.mean(cell_areas[0])), 6) if cell_areas[0] else 0
        st.stats['CSmc'] = round(float(np.mean(cell_areas[1])), 6) if cell_areas[1] else 0
        st.stats['CSoc'] = round(float(np.mean(cell_areas[2])), 6) if cell_areas[2] else 0

        # #CF = cortex radial thickness / mean cell linear size (Table 1)
        all_areas = cell_areas[0] + cell_areas[1] + cell_areas[2]
        if all_areas:
            mean_linear_mm = float(np.sqrt(np.mean(all_areas)))
            cortex_thickness_mm = max_cortex_width / px_per_mm
            st.stats['#CF'] = round(cortex_thickness_mm / (mean_linear_mm + 1e-9), 1)
        else:
            st.stats['#CF'] = 0

        preview = cv2.applyColorMap(bands, cv2.COLORMAP_JET)
        preview = cv2.bitwise_and(preview, preview, mask=cortex_mask)
        b64_preview = _encode_preview(preview)
        return {"data": data, "preview": preview, "preview_b64": b64_preview, "stats": dict(st.stats)}


@vision_node(
    type_id="root_xylem_detect",
    label="Xylem Detect",
    category="root_anatomy",
    icon="Zap",
    description="Detects metaxylem vessels using the Max Jump area algorithm (paper §Part V).",
    inputs=[{"id": "data", "color": "root_data"}],
    outputs=[
        {"id": "data", "color": "root_data"},
        {"id": "preview", "color": "image", "label": "Xylem Mask"}
    ],
    params=[
        {"id": "min_jump_ratio", "label": "Min Jump Ratio", "type": "float", "default": 2.0, "min": 1.1, "max": 20.0},
    ]
)
class RootXylemNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        st = _state(data)
        if st is None:
            return {"data": None, "preview_b64": None, "stats": {}}

        stele_mask = st.masks['stele']
        if stele_mask is None:
            return {"data": data, "preview_b64": None, "stats": dict(st.stats)}

        img = st.original
        gray = _to_gray(img)

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        vessels_raw = cv2.bitwise_and(cv2.bitwise_not(binary), cv2.bitwise_not(binary), mask=stele_mask)

        labels = measure.label(vessels_raw)
        props = measure.regionprops(labels)
        if not props:
            return {"data": data, "preview": None}

        props_sorted = sorted(props, key=lambda x: x.area)
        areas = [p.area for p in props_sorted]

        # Max Jump: maximum absolute area difference (paper §Part V)
        jump_idx = len(areas)
        max_diff = 0
        for i in range(len(areas) - 1):
            diff = areas[i + 1] - areas[i]
            if diff > max_diff:
                max_diff = diff
                jump_idx = i + 1

        # Accept only if jump exceeds min_jump_ratio × mean inter-object gap
        mean_diff = (areas[-1] - areas[0]) / max(len(areas) - 1, 1)
        if max_diff < params.get('min_jump_ratio', 2.0) * mean_diff:
            jump_idx = len(areas)

        xylem_mask = np.zeros_like(stele_mask)
        total_xva_px = 0
        for p in props_sorted[jump_idx:]:
            xylem_mask[labels == p.label] = 255
            total_xva_px += p.area

        st.masks['xylem'] = xylem_mask
        st.stats['XVA'] = round(total_xva_px / (st.px_per_mm ** 2), 4)

        st.sync(data)
        preview = cv2.cvtColor(xylem_mask, cv2.COLOR_GRAY2BGR)
        return {"data": data, "preview": preview, "preview_b64": _encode_preview(preview)}


@vision_node(
    type_id="root_protoxylem_detect",
    label="Protoxylem Detect",
    category="root_anatomy",
    icon="ZapOff",
    description="Detects protoxylem vessels (smaller than metaxylem) from remaining stele objects. Run after Xylem Detect.",
    inputs=[{"id": "data", "color": "root_data"}],
    outputs=[
        {"id": "data", "color": "root_data"},
        {"id": "preview", "color": "image", "label": "Protoxylem Mask"}
    ],
    params=[
        {"id": "min_area", "label": "Min Vessel Area (px)", "type": "int", "default": 10, "min": 1, "max": 500},
        {"id": "max_area", "label": "Max Vessel Area (px)", "type": "int", "default": 300, "min": 10, "max": 5000},
    ]
)
class RootProtoxylemNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        st = _state(data)
        if st is None:
            return {"data": None, "preview_b64": None, "stats": {}}

        stele_mask = st.masks.get('stele')
        if stele_mask is None:
            return {"data": data, "preview_b64": None, "stats": dict(st.stats)}

        img = st.original
        gray = _to_gray(img)

        # Detect outer periphery to avoid pith (central cells)
        dt_root = cv2.distanceTransform(st.masks['section'], cv2.DIST_L2, 5)
        # Average distance of stele to root edge. Anything further is likely pith in monocots.
        dist_avg = np.mean(dt_root[stele_mask > 0]) if np.any(stele_mask > 0) else 0
        outer_mask = (dt_root <= dist_avg) & (stele_mask > 0)

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Identify small vessels in the outer zone
        vessels_raw = cv2.bitwise_and(cv2.bitwise_not(binary), cv2.bitwise_not(binary), mask=outer_mask.astype(np.uint8)*255)

        # Exclude already-classified metaxylem
        xylem_mask = st.masks.get('xylem')
        if xylem_mask is not None:
            vessels_raw = cv2.bitwise_and(vessels_raw, cv2.bitwise_not(xylem_mask))

        labels = measure.label(vessels_raw)
        props = measure.regionprops(labels)

        min_area = params.get('min_area', 5)
        max_area = params.get('max_area', 400)

        proto_mask = np.zeros_like(stele_mask)
        total_px = 0
        count = 0
        for p in props:
            if min_area <= p.area <= max_area:
                proto_mask[labels == p.label] = 255
                total_px += p.area
                count += 1

        st.masks['protoxylem'] = proto_mask
        st.stats['#PX'] = count
        st.stats['PXA'] = round(total_px / (st.px_per_mm ** 2), 4)

        st.sync(data)
        preview = cv2.cvtColor(proto_mask, cv2.COLOR_GRAY2BGR)
        return {"data": data, "preview": preview, "preview_b64": _encode_preview(preview)}


@vision_node(
    type_id="root_layers",
    label="Endo/Exodermis",
    category="root_anatomy",
    icon="Layers",
    description="Segments endodermis (inner cortex layer) and exodermis (outer cortex layer). Run after Cortex Analysis.",
    inputs=[{"id": "data", "color": "root_data"}],
    outputs=[
        {"id": "data", "color": "root_data"},
        {"id": "preview", "color": "image", "label": "Layers Preview"}
    ],
    params=[
        {"id": "layer_width", "label": "Layer Width (px)", "type": "int", "default": 15, "min": 3, "max": 80},
    ]
)
class RootLayersNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        st = _state(data)
        if st is None:
            return {"data": None, "preview_b64": None, "stats": {}}

        cortex_mask  = st.masks.get('cortex')
        stele_mask   = st.masks.get('stele')
        section_mask = st.masks.get('section')
        if cortex_mask is None or stele_mask is None or section_mask is None:
            return {"data": data, "preview": None}

        px_per_mm = st.px_per_mm
        img = st.original
        gray = _to_gray(img)
        layer_w = params.get('layer_width', 15)

        # Endodermis: cortex cells within layer_w px of the stele boundary
        dist_from_stele = cv2.distanceTransform(cv2.bitwise_not(stele_mask), cv2.DIST_L2, 5)
        endo_band = ((dist_from_stele > 0) & (dist_from_stele <= layer_w)).astype(np.uint8) * 255
        endo_mask = cv2.bitwise_and(endo_band, endo_band, mask=cortex_mask)

        # Exodermis: cortex cells within layer_w px of the section outer boundary
        dist_from_outer = cv2.distanceTransform(section_mask, cv2.DIST_L2, 5)
        exo_band = ((dist_from_outer > 0) & (dist_from_outer <= layer_w)).astype(np.uint8) * 255
        exo_mask = cv2.bitwise_and(exo_band, exo_band, mask=cortex_mask)

        st.masks['endodermis'] = endo_mask
        st.masks['exodermis']  = exo_mask

        st.stats['EA']   = round(float(np.sum(endo_mask > 0)) / (px_per_mm ** 2), 4)
        st.stats['ExA']  = round(float(np.sum(exo_mask > 0))  / (px_per_mm ** 2), 4)

        endo_gray = cv2.bitwise_and(gray, gray, mask=endo_mask)
        _, endo_wall = _otsu_masked(endo_gray, endo_mask)
        st.stats['ECWA']  = round(float(np.sum(endo_wall > 0)) / (px_per_mm ** 2), 4)

        exo_gray = cv2.bitwise_and(gray, gray, mask=exo_mask)
        _, exo_wall = _otsu_masked(exo_gray, exo_mask)
        st.stats['ExCWA'] = round(float(np.sum(exo_wall > 0)) / (px_per_mm ** 2), 4)

        # Preview: gray cortex, cyan endodermis, magenta exodermis
        preview = np.zeros((*cortex_mask.shape, 3), dtype=np.uint8)
        preview[cortex_mask > 0] = (60, 60, 60)
        preview[endo_mask > 0]   = (255, 255, 0)
        preview[exo_mask > 0]    = (255, 0, 255)

        b64_preview = _encode_preview(preview)
        return {"data": data, "preview": preview, "preview_b64": b64_preview, "stats": dict(st.stats)}


def hex_to_bgr(hex_color, default=(0, 255, 0)):
    if not hex_color or not isinstance(hex_color, str):
        return default
    hex_color = hex_color.lstrip('#')
    try:
        if len(hex_color) == 6:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        elif len(hex_color) == 3:
            r, g, b = int(hex_color[0] * 2, 16), int(hex_color[1] * 2, 16), int(hex_color[2] * 2, 16)
        else:
            return default
        return (b, g, r)
    except Exception:
        return default


@vision_node(
    type_id="root_anatomy_overlay",
    label="Anatomy Overlay",
    category="root_anatomy",
    icon="Palette",
    description="Generates a colorized overlay of all anatomy layers.",
    inputs=[{"id": "data", "color": "root_data"}],
    outputs=[
        {"id": "image", "color": "image", "label": "Overlay Image"},
        {"id": "data", "color": "root_data"}
    ],
    params=[
        {"id": "opacity",          "label": "Fill Opacity",       "type": "float", "default": 0.4,  "min": 0.0, "max": 1.0},
        {"id": "show_outlines",    "label": "Show Outlines",      "type": "bool",  "default": True},
        {"id": "thickness",        "label": "Line Thickness",     "type": "int",   "default": 2,    "min": 1, "max": 10},
        {"id": "color_outline",    "label": "Color: Outline",     "type": "color", "default": "#ffffff"},
        {"id": "color_section",    "label": "Color: Section",     "type": "color", "default": "#ff8c00"},
        {"id": "color_stele",      "label": "Color: Stele",       "type": "color", "default": "#00ff00"},
        {"id": "color_aerenchyma", "label": "Color: Aerenchyma",  "type": "color", "default": "#ff0000"},
        {"id": "color_xylem",      "label": "Color: Metaxylem",   "type": "color", "default": "#ffff00"},
        {"id": "color_protoxylem", "label": "Color: Protoxylem",  "type": "color", "default": "#ffa500"},
        {"id": "color_endodermis", "label": "Color: Endodermis",  "type": "color", "default": "#00ffff"},
        {"id": "color_exodermis",  "label": "Color: Exodermis",   "type": "color", "default": "#ff00ff"},
    ]
)
class RootAnatomyOverlayNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        st = _state(data)
        if st is None:
            return {"image": None, "data": data}

        img = st.original
        overlay = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if len(img.shape) == 2 else img.copy()

        opacity       = params.get('opacity', 0.4)
        show_outlines = params.get('show_outlines', True)
        thickness     = params.get('thickness', 2)
        outline_color = hex_to_bgr(params.get('color_outline', '#ffffff'))
        colors = {
            'section':    hex_to_bgr(params.get('color_section',    '#ff8c00')),
            'stele':      hex_to_bgr(params.get('color_stele',      '#00ff00')),
            'aerenchyma': hex_to_bgr(params.get('color_aerenchyma', '#ff0000')),
            'xylem':      hex_to_bgr(params.get('color_xylem',      '#ffff00')),
            'protoxylem': hex_to_bgr(params.get('color_protoxylem', '#ffa500')),
            'endodermis': hex_to_bgr(params.get('color_endodermis', '#00ffff')),
            'exodermis':  hex_to_bgr(params.get('color_exodermis',  '#ff00ff')),
        }

        for key, color in colors.items():
            mask = st.masks.get(key)
            if mask is None:
                continue
            if opacity > 0:
                colored = np.zeros_like(overlay)
                colored[mask > 0] = color
                cv2.addWeighted(colored, opacity, overlay, 1.0, 0, overlay)
            if show_outlines:
                cnts = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                contours = cnts[-2]
                cv2.drawContours(overlay, contours, -1, outline_color, thickness)

        return {"image": overlay, "data": data, "preview_b64": _encode_preview(overlay)}


_REPORT_ORDER = [
    'RXSA', 'XSCWA',
    'TCA', 'CCWA', 'CCA', '%CCA', 'AA', '%A', '#Lac', '#CF', '#CC',
    'CSic', 'CSmc', 'CSoc', 'LA',
    'TSA', 'SCWA', 'XVA', 'PXA', '#PX',
    'EA', 'ECWA', 'ExA', 'ExCWA',
    'TSA:RXSA', 'TSA:TCA',
    'quality_score', 'focus_score', 'comments',
]

@vision_node(
    type_id="root_anatomy_report",
    label="Anatomy Report",
    category="root_anatomy",
    icon="BarChart2",
    description="Aggregates all anatomical variables. Output: flat dict of plain Python floats, ordered per RootScan Table 1.",
    inputs=[{"id": "data", "color": "root_data"}],
    outputs=[{"id": "report", "color": "dict"}],
    params=[
        {"id": "order", "label": "Key Order", "type": "enum", "default": "paper", "options": ["paper", "alpha"]},
    ]
)
class RootAnatomyReportNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        if not data:
            return {"report": {}}

        raw = data.get('stats', {})

        rxsa = raw.get('RXSA', 0) or 0
        tsa  = raw.get('TSA',  0) or 0
        tca  = raw.get('TCA',  0) or 0
        extra = {}
        if rxsa > 0:
            extra['TSA:RXSA'] = round(tsa / rxsa, 4)
        if tca > 0:
            extra['TSA:TCA'] = round(tsa / tca, 4)

        combined = {**raw, **extra}
        combined.pop('centroid', None)

        def _scalar(v):
            if v is None: return None
            if isinstance(v, str): return v
            try: return float(v)
            except Exception: return str(v)

        converted = {k: _scalar(v) for k, v in combined.items()}

        if params.get('order', 'paper') == 'paper':
            ordered = {k: converted[k] for k in _REPORT_ORDER if k in converted}
            ordered.update({k: v for k, v in converted.items() if k not in ordered})
        else:
            ordered = dict(sorted(converted.items()))

        return {"report": ordered}


@vision_node(
    type_id="root_quality_score",
    label="Quality Score",
    category="root_anatomy",
    icon="Activity",
    description="Manual quality scoring interface for the analysis.",
    inputs=[{"id": "data", "color": "root_data"}],
    outputs=[{"id": "data", "color": "root_data"}],
    params=[
        {"id": "score",    "label": "Overall Quality (1-5)", "type": "int",    "default": 5, "min": 1, "max": 5},
        {"id": "focus",    "label": "Focus Quality",         "type": "int",    "default": 5, "min": 1, "max": 5},
        {"id": "comments", "label": "Comments",              "type": "string", "default": ""},
    ]
)
class RootQualityScoreNode(NodeProcessor):
    def process(self, inputs, params):
        data = inputs.get('data')
        st = _state(data)
        if st is None:
            return {"data": None, "stats": {}}
        st.stats['quality_score'] = params.get('score', 5)
        st.stats['focus_score']   = params.get('focus', 5)
        st.stats['comments']      = params.get('comments', "")
        st.sync(data)
        return {"data": data}
