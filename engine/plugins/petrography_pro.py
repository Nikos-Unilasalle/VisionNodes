import cv2
import numpy as np
import math
from registry import vision_node, NodeProcessor

def get_angle(p1, p2, p3):
    """Calculates the interior angle at p2 between p1-p2 and p2-p3."""
    v1 = (float(p1[0] - p2[0]), float(p1[1] - p2[1]))
    v2 = (float(p3[0] - p2[0]), float(p3[1] - p2[1]))
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    det = v1[0]*v2[1] - v1[1]*v2[0]
    angle = math.atan2(det, dot)
    if angle < 0: angle += 2 * math.pi
    return math.degrees(angle)

def remove_binding_pixels(mask):
    """Removes 1px bridges (binding pixels)."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

@vision_node(
    type_id="petro_grain_separator",
    label="Petro Grain Separator (SRC)",
    category='geology',
    icon="Scissors",
    description=(
        "Separates connected grains by linking their concavities (SRC Algorithm).\n\n"
        "GUIDE:\n"
        "- Epsilon: Boundary simplification (in Units). Small = high fidelity (noisy), Large = robust.\n"
        "- Angle: Concavity threshold (180-300°). Typically 195° to detect 'pits' between grains.\n"
        "- Max Cut Dist: Maximum allowed length for a separation line. Should be close to the average grain diameter."
    ),
    inputs=[
        {"id": "mask", "color": "mask", "label": "Binary Grain Mask"},
        {"id": "scale", "color": "scalar", "label": "Px/Unit"}
    ],
    outputs=[
        {"id": "mask",  "color": "mask"},
        {"id": "count", "color": "scalar", "label": "Grain Count"},
        {"id": "frac",  "color": "scalar", "label": "Area Fraction (%)"},
    ],
    params=[
        {"id": "mode", "label": "Target Grains", "type": "enum", "options": ["White (on black)", "Black (on white)"], "default": 0},
        {"id": "epsilon", "label": "Polygonal Approx (Units)", "type": "float", "default": 0.02, "min": 0.0, "max": 100.0},
        {"id": "angle_thresh", "label": "Concavity Angle (°)", "type": "float", "default": 195.0, "min": 180.0, "max": 300.0},
        {"id": "max_dist", "label": "Max Cut Distance (Units)", "type": "float", "default": 1.0, "min": 0.0, "max": 1000.0}
    ]
)
class PetroGrainSeparatorNode(NodeProcessor):
    def process(self, inputs, params):
        mask = inputs.get('mask')
        if mask is None: return {"mask": None}
        scale = float(inputs.get('scale') or 1.0)
        if len(mask.shape) == 3: mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
        mode = int(params.get('mode', 0))
        if mode == 1: binary = cv2.bitwise_not(binary)
        epsilon_units = float(params.get('epsilon', 0.02))
        angle_thresh = float(params.get('angle_thresh', 195.0))
        max_dist_units = float(params.get('max_dist', 1.0))
        epsilon_px = max(1.0, epsilon_units * scale)
        max_dist_px = max_dist_units * scale
        binary = remove_binding_pixels(binary)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        result_mask = binary.copy()
        for cnt in contours:
            if cv2.contourArea(cnt) < (10 * scale): continue
            poly = cv2.approxPolyDP(cnt, epsilon_px, True)
            n = len(poly)
            if n < 4: continue
            concave_points = []
            for i in range(n):
                p1, p2, p3 = poly[i-1][0], poly[i][0], poly[(i+1)%n][0]
                if get_angle(p1, p2, p3) > angle_thresh: concave_points.append({'pos': p2, 'idx': i})
            if len(concave_points) >= 2:
                positions = np.array([cp['pos'] for cp in concave_points], dtype=np.float32)
                diff = positions[:, np.newaxis, :] - positions[np.newaxis, :, :]
                dist_matrix = np.sqrt((diff ** 2).sum(axis=-1))
                np.fill_diagonal(dist_matrix, np.inf)
                used = set()
                for i, cp1 in enumerate(concave_points):
                    if i in used: continue
                    row = dist_matrix[i].copy()
                    if used: row[list(used)] = np.inf
                    candidates = np.where(row < max_dist_px)[0]
                    candidates = candidates[np.argsort(row[candidates])]
                    best_j = None
                    for j in candidates:
                        p1, p2 = concave_points[i]['pos'], concave_points[int(j)]['pos']
                        is_inside = all(
                            0 <= int(p1[1] + s * (p2[1] - p1[1])) < binary.shape[0]
                            and 0 <= int(p1[0] + s * (p2[0] - p1[0])) < binary.shape[1]
                            and binary[int(p1[1] + s * (p2[1] - p1[1])), int(p1[0] + s * (p2[0] - p1[0]))] != 0
                            for s in [0.2, 0.4, 0.5, 0.6, 0.8]
                        )
                        if is_inside:
                            best_j = int(j)
                            break
                    if best_j is not None:
                        cv2.line(result_mask, tuple(cp1['pos']), tuple(concave_points[best_j]['pos']), 0, 1)
                        used.add(i); used.add(best_j)
        n_labels, _ = cv2.connectedComponents(result_mask)
        grain_count = n_labels - 1
        grain_frac = round(float(np.count_nonzero(result_mask)) / result_mask.size * 100.0, 2)
        if mode == 1: result_mask = cv2.bitwise_not(result_mask)
        return {"mask": result_mask, "count": grain_count, "frac": grain_frac}

@vision_node(
    type_id="petro_point_counter",
    label="Petro Point Counter",
    category='geology',
    icon="LayoutGrid",
    description=(
        "Grid sampling for modal analysis. Points are spread edge-to-edge to cover the full image area.\n\n"
        "GUIDE:\n"
        "- Grid Size: Aim for 300 to 500 total points (e.g., 20x25).\n"
        "- Point Size: Defines both marker visibility and sampling robustness (majority vote in circle).\n"
        "- Show Markers: Toggle visibility of the sampling points."
    ),
    inputs=[{"id": "image", "color": "any"}, {"id": "mask", "color": "mask"}],
    outputs=[{"id": "main", "color": "image"}, {"id": "data", "color": "any"}],
    params=[
        {"id": "grid_rows", "label": "Rows", "type": "int", "default": 10, "min": 2, "max": 200},
        {"id": "grid_cols", "label": "Cols", "type": "int", "default": 10, "min": 2, "max": 200},
        {"id": "point_size", "label": "Point Size (Sampling Radius)", "type": "int", "default": 3, "min": 1, "max": 20},
        {"id": "show_labels", "label": "Show Markers", "type": "boolean", "default": True}
    ]
)
class PetroPointCounterNode(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        mask_in = inputs.get('mask')
        if img is None: return {"main": None}
        rows, cols, pt_size = int(params.get('grid_rows', 10)), int(params.get('grid_cols', 10)), int(params.get('point_size', 3))
        show_markers = params.get('show_labels', True)
        h, w = img.shape[:2]
        canvas = img.copy()
        mask = None
        is_labeled = False
        if mask_in is not None:
            mask = cv2.cvtColor(mask_in, cv2.COLOR_BGR2GRAY) if len(mask_in.shape) == 3 else mask_in.copy()
            is_labeled = not set(np.unique(mask)).issubset({0, 255})
        y_coords = np.linspace(0, h - 1, rows, dtype=int)
        x_coords = np.linspace(0, w - 1, cols, dtype=int)
        points_data, counts = [], {}
        for py in y_coords:
            for px in x_coords:
                class_id = 0
                if mask is not None:
                    y1, y2 = max(0, py - pt_size), min(h, py + pt_size + 1)
                    x1, x2 = max(0, px - pt_size), min(w, px + pt_size + 1)
                    roi = mask[y1:y2, x1:x2]
                    if roi.size > 0:
                        vals, v_counts = np.unique(roi, return_counts=True)
                        class_id = int(vals[np.argmax(v_counts)])
                if show_markers:
                    if is_labeled:
                        palette = [(128, 128, 128), (0, 255, 255), (0, 0, 255), (0, 255, 0), (255, 0, 0), (255, 0, 255), (0, 165, 255)]
                        color = palette[class_id % len(palette)]
                    else:
                        color = (0, 255, 255) if class_id == 0 else (0, 0, 255)
                    cv2.circle(canvas, (px, py), pt_size, color, -1)
                    cv2.circle(canvas, (px, py), pt_size + 1, (0,0,0), 1)
                points_data.append({"x": int(px), "y": int(py), "class": class_id})
                counts[class_id] = counts.get(class_id, 0) + 1
        total = len(points_data)
        stats = {}
        for k, v in sorted(counts.items()):
            if is_labeled:
                name = "Background" if k == 0 else f"Phase {k}"
            else:
                name = "Black Grains" if k == 0 else ("White Matrix" if k == 255 else f"Class {k}")
            stats[name] = f"{(v/total)*100:.1f}%"
        return {"main": canvas, "data": stats}

def _label_bboxes_from_sorted(markers: np.ndarray) -> dict:
    """Compute {lbl: (ymin,ymax,xmin,xmax)} for all non-zero labels in one vectorized pass."""
    h, w = markers.shape[:2]
    flat = markers.ravel()
    nz   = flat > 0
    if not np.any(nz):
        return {}
    nz_flat = flat[nz]
    nz_idx  = np.where(nz)[0]
    order   = np.argsort(nz_flat, kind='stable')
    s_lbl   = nz_flat[order]
    s_row   = nz_idx[order] // w
    s_col   = nz_idx[order] %  w
    uniq, starts = np.unique(s_lbl, return_index=True)
    ends = np.append(starts[1:], len(s_lbl))
    return {
        int(lbl): (int(s_row[s:e].min()), int(s_row[s:e].max()),
                   int(s_col[s:e].min()), int(s_col[s:e].max()))
        for lbl, s, e in zip(uniq, starts, ends)
    }


@vision_node(
    type_id="petro_neighbor_analysis",
    label="Petro Neighbor Analysis (Context)",
    category='geology',
    icon="Users",
    description=(
        "Analyzes grain contacts and neighborhood (Context). Works on both binary masks and labeled markers.\n\n"
        "GUIDE:\n"
        "- Target Grains: Choose if grains are black or white (only used if input is binary).\n"
        "- Search Radius: Distance to look for adjacent grains.\n"
        "- Min Contact: Minimum boundary length to consider grains as 'touching'."
    ),
    inputs=[
        {"id": "contours", "color": "list",   "label": "Contours (FastSAM / Grain Stats)"},
        {"id": "image",    "color": "image",   "label": "Image (required with Contours)"},
        {"id": "markers",  "color": "any",     "label": "Mask or Labeled Markers (alt.)"},
        {"id": "scale",    "color": "scalar",  "label": "Px/Unit"}
    ],
    outputs=[
        {"id": "main", "color": "image", "label": "Coordination Map"},
        {"id": "data", "color": "any",   "label": "Context Stats"}
    ],
    params=[
        {"id": "mode",             "label": "Target Grains (mask only)", "type": "enum",
         "options": ["White (on black)", "Black (on white)"], "default": 0},
        {"id": "dilate_units",     "label": "Search Radius (px / units)", "type": "float",
         "default": 5.0, "min": 1.0, "max": 200.0, "step": 1.0},
        {"id": "min_contact_units","label": "Min Contact (px / units)",   "type": "float",
         "default": 2.0, "min": 1.0, "max": 200.0, "step": 1.0},
    ]
)
class PetroNeighborAnalysisNode(NodeProcessor):
    def process(self, inputs, params):
        scale           = float(inputs.get('scale') or 1.0)
        contours_input  = inputs.get('contours')
        raw_markers     = inputs.get('markers')
        image           = inputs.get('image')

        markers    = None
        label_bbox = {}  # {lbl: (ymin, ymax, xmin, xmax)}

        # Path A: FastSAM contours → fillPoly → bboxes from contour points (free)
        if isinstance(contours_input, list) and len(contours_input) > 0:
            ref = image if image is not None else (
                  raw_markers if isinstance(raw_markers, np.ndarray) else None)
            if ref is None:
                return {"main": None, "data": "Connect Image input when using Contours"}
            h, w = ref.shape[:2]
            markers = np.zeros((h, w), dtype=np.int32)
            for i, cnt_pts in enumerate(contours_input, 1):
                pts = np.array(cnt_pts, dtype=np.int32).reshape(-1, 2)
                cv2.fillPoly(markers, [pts.reshape(-1, 1, 2)], i)
                label_bbox[i] = (int(pts[:, 1].min()), int(pts[:, 1].max()),
                                 int(pts[:, 0].min()), int(pts[:, 0].max()))

        # Path B: binary mask → connectedComponentsWithStats (bboxes free from OpenCV)
        elif isinstance(raw_markers, np.ndarray):
            m = raw_markers
            if m.ndim == 3:
                m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY)
            unique_vals = np.unique(m)
            if set(unique_vals.tolist()).issubset({0, 255}):
                _, binary = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
                if int(params.get('mode', 0)) == 1:
                    binary = cv2.bitwise_not(binary)
                num_lbl, markers, stats, _ = cv2.connectedComponentsWithStats(binary.astype(np.uint8))
                for lbl in range(1, num_lbl):
                    x  = stats[lbl, cv2.CC_STAT_LEFT]
                    y  = stats[lbl, cv2.CC_STAT_TOP]
                    bw = stats[lbl, cv2.CC_STAT_WIDTH]
                    bh = stats[lbl, cv2.CC_STAT_HEIGHT]
                    label_bbox[lbl] = (y, y + bh - 1, x, x + bw - 1)
            else:
                markers    = m.astype(np.int32)
                label_bbox = _label_bboxes_from_sorted(markers)

        if markers is None:
            return {"main": None}

        h, w = markers.shape[:2]
        dilate_px      = max(1, int(float(params.get('dilate_units',      5.0)) * scale))
        min_contact_px = max(1, int(float(params.get('min_contact_units', 2.0)) * scale))

        labels = np.unique(markers)
        labels = labels[labels > 0]
        if len(labels) == 0:
            return {"main": np.zeros((h, w, 3), dtype=np.uint8), "data": "No grains found"}

        adj    = {lbl: set() for lbl in labels}
        counts = {lbl: 0     for lbl in labels}
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (dilate_px*2+1, dilate_px*2+1))

        for lbl in labels:
            bbox = label_bbox.get(int(lbl))
            if bbox is None:
                ys, xs = np.where(markers == lbl)
                if ys.size == 0: continue
                bbox = (int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max()))
            ymin, ymax, xmin, xmax = bbox
            pad = dilate_px + 1
            y1, y2 = max(0, ymin - pad), min(h, ymax + pad + 1)
            x1, x2 = max(0, xmin - pad), min(w, xmax + pad + 1)
            roi_markers = markers[y1:y2, x1:x2]
            roi_grain   = (roi_markers == lbl).astype(np.uint8) * 255
            dilated_roi = cv2.dilate(roi_grain, kernel)
            overlap_zone = roi_markers[dilated_roi > 0]
            for n_lbl in np.unique(overlap_zone):
                if n_lbl > 0 and n_lbl != lbl:
                    if np.count_nonzero(overlap_zone == n_lbl) >= min_contact_px:
                        adj[lbl].add(int(n_lbl))

        max_neighbors = 0
        for lbl, neighbors in adj.items():
            n_count = len(neighbors)
            counts[lbl] = n_count
            if n_count > max_neighbors:
                max_neighbors = n_count

        # Vectorized coord_map: O(H×W) lookup instead of N × O(H×W) loop
        max_lbl   = int(labels.max())
        count_lut = np.zeros(max_lbl + 1, dtype=np.int32)
        for lbl, n in counts.items():
            count_lut[int(lbl)] = n
        clipped   = np.clip(markers, 0, max_lbl)
        coord_map = count_lut[clipped]
        coord_map[markers == 0] = 0

        if max_neighbors > 0:
            vis = cv2.applyColorMap(
                (coord_map.astype(np.float32) * 255 / max_neighbors).clip(0, 255).astype(np.uint8),
                cv2.COLORMAP_JET)
            vis[markers == 0] = 0
        else:
            vis = np.zeros((h, w, 3), dtype=np.uint8)
            
        summary = {
            "Total Grains": len(labels),
            "Max Neighbors": max_neighbors,
            "Mean Coordination": float(np.mean(list(counts.values()))) if counts else 0,
            "Isolated Grains": len([c for c in counts.values() if c == 0])
        }
        return {"main": vis, "data": summary}
