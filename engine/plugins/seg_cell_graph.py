import cv2
import numpy as np
from registry import vision_node, NodeProcessor


def _binary(m, shape=None):
    if m is None:
        return None
    m = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY) if m.ndim == 3 else m
    if shape is not None and m.shape != shape:
        m = cv2.resize(m, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return m > 0


@vision_node(
    type_id='seg_cell_graph',
    label='Cell Spatial Graph',
    category='segmentation',
    icon='Share2',
    description=(
        "Performs spatial, topological, and anatomical classification on a cell network:\n\n"
        "1. Adjacency Graph: builds the Region Adjacency Graph (RAG) from shared wall pixels, "
        "supplemented by Delaunay triangulation for micro-gaps.\n"
        "2. Endodermis Segmentation: identifies the continuous circular monolayer of cells wrapping the "
        "stele at the cortex/stele interface (uniform compact cells along the boundary, distinct from "
        "the giant cortical parenchyma cells).\n"
        "3. Large Peripheral Stele Cells: identifies the prominent cells situated in the outer/middle "
        "stele mantle, strictly inside the stele, flanking the metaxylem poles and distinct from the "
        "fine conductive phloem/procambium bundles (Z-score contrast vs local neighbors).\n"
        "4. Topological Layers: Breadth-First Search (BFS) assigns layer ranks from the boundary.\n"
        "5. Local Size Z-Score: relativizes cell area against adjacent neighbors (Z = (Area - mean) / std).\n"
        "6. Canonical Metaxylem Coordinates: computes distance and angular position relative to metaxylem poles."
    ),
    inputs=[
        {'id': 'labels', 'color': 'markers', 'label': 'Cell Labels'},
        {'id': 'boundary', 'color': 'mask', 'label': 'Boundary (e.g. Stele Outline)'},
        {'id': 'landmarks', 'color': 'mask', 'label': 'Landmarks (e.g. Metaxylem, opt.)'},
        {'id': 'stele', 'color': 'mask', 'label': 'Stele Region (opt.)'},
        {'id': 'cortex', 'color': 'mask', 'label': 'Cortex Region (opt.)'},
        {'id': 'section', 'color': 'mask', 'label': 'Section Region (opt.)'},
        {'id': 'section_boundary', 'color': 'mask', 'label': 'Section Boundary (opt.)'},
        {'id': 'center_mask', 'color': 'mask', 'label': 'Center (opt.)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image', 'label': 'Anatomy Overlay'},
        {'id': 'peripheral_mask', 'color': 'mask', 'label': 'Large Peripheral Cells'},
        {'id': 'endodermis_mask', 'color': 'mask', 'label': 'Endodermis Cells'},
        {'id': 'rhizodermis_mask', 'color': 'mask', 'label': 'Rhizodermis Cells'},
        {'id': 'layers_mask', 'color': 'mask', 'label': 'Topological Layers'},
        {'id': 'zscore_map', 'color': 'image', 'label': 'Local Z-Score Map'},
        {'id': 'features', 'color': 'list', 'label': 'Cell Features List'},
        {'id': 'graph', 'color': 'dict', 'label': 'Adjacency Graph'},
        {'id': 'peripheral_count', 'color': 'scalar', 'label': 'Peripheral Count'},
        {'id': 'endodermis_count', 'color': 'scalar', 'label': 'Endodermis Count'},
        {'id': 'rhizodermis_count', 'color': 'scalar', 'label': 'Rhizodermis Count'},
        {'id': 'count', 'color': 'scalar', 'label': 'Peripheral Count (alias)'},
    ],
    params=[
        {'id': 'layers_max', 'label': 'Max Layer Depth', 'type': 'int', 'default': 6, 'min': 1, 'max': 20},
        {'id': 'corridor_rhizo_dist', 'label': 'Rhizodermis Corridor Width (px)', 'type': 'float', 'default': 32.0, 'min': 5.0, 'max': 100.0, 'step': 1.0},
        {'id': 'corridor_endo_dist', 'label': 'Endodermis Corridor Width (px)', 'type': 'float', 'default': 21.0, 'min': 5.0, 'max': 80.0, 'step': 1.0},
        {'id': 'endo_max_area', 'label': 'Endodermis Max Area (px)', 'type': 'float', 'default': 550.0, 'min': 50.0, 'max': 1000.0, 'step': 10.0},
        {'id': 'lpsc_min_area_factor', 'label': 'LPSC Size Factor (× median)', 'type': 'float', 'default': 1.20, 'min': 0.5, 'max': 5.0, 'step': 0.05},
        {'id': 'lpsc_min_z', 'label': 'LPSC Min Local Z-Score', 'type': 'float', 'default': 0.20, 'min': -2.0, 'max': 5.0, 'step': 0.05},
        {'id': 'min_roundness', 'label': 'Min Roundness (0–1)', 'type': 'float', 'default': 0.35, 'min': 0.0, 'max': 1.0, 'step': 0.02},
        {'id': 'max_delaunay_dist', 'label': 'Delaunay Max Gap (px)', 'type': 'float', 'default': 35.0, 'min': 5.0, 'max': 200.0, 'step': 1.0},
    ],
)
class CellSpatialGraphNode(NodeProcessor):
    def process(self, inputs, params):
        empty = {
            'main': None, 'peripheral_mask': None, 'endodermis_mask': None, 'rhizodermis_mask': None,
            'layers_mask': None, 'zscore_map': None, 'features': [], 'graph': {},
            'peripheral_count': 0, 'endodermis_count': 0, 'rhizodermis_count': 0, 'count': 0
        }
        labels = inputs.get('labels')
        if not isinstance(labels, np.ndarray) or labels.ndim != 2:
            return empty

        from scipy.spatial import Delaunay
        from scipy.ndimage import distance_transform_edt
        from skimage import measure

        labels = labels.astype(np.int32)
        h, w = labels.shape

        stele_in = inputs.get('stele')
        stele = _binary(stele_in, (h, w)) if stele_in is not None else None

        cortex_in = inputs.get('cortex')
        cortex = _binary(cortex_in, (h, w)) if cortex_in is not None else None

        section_in = inputs.get('section')
        section = _binary(section_in, (h, w)) if section_in is not None else None

        sec_boundary_in = inputs.get('section_boundary')
        if sec_boundary_in is not None:
            sec_boundary_edge = _binary(sec_boundary_in, (h, w))
        elif section is not None:
            sec_u8 = section.astype(np.uint8) * 255
            sec_ero = cv2.erode(sec_u8, np.ones((3, 3), np.uint8))
            sec_boundary_edge = (sec_u8 > 0) & (sec_ero == 0)
        else:
            sec_boundary_edge = None

        dt_sec_boundary = distance_transform_edt(~sec_boundary_edge) if sec_boundary_edge is not None else None

        landmarks_in = inputs.get('landmarks')
        landmarks = _binary(landmarks_in, (h, w)) if landmarks_in is not None else np.zeros((h, w), bool)

        boundary_in = inputs.get('boundary')
        if boundary_in is not None:
            boundary_raw = _binary(boundary_in, (h, w))
            # If boundary is a filled region, extract outer edge
            if cv2.countNonZero(boundary_raw.astype(np.uint8)) > 0.05 * h * w:
                ero = cv2.erode(boundary_raw.astype(np.uint8), np.ones((3, 3), np.uint8))
                boundary_edge = (boundary_raw & (ero == 0))
            else:
                boundary_edge = boundary_raw
        elif stele is not None:
            stele_u8 = stele.astype(np.uint8) * 255
            ero = cv2.erode(stele_u8, np.ones((3, 3), np.uint8))
            boundary_edge = (stele_u8 > 0) & (ero == 0)
        else:
            boundary_edge = np.zeros((h, w), bool)
            boundary_edge[h // 2, :] = True

        # Distance transform to boundary edge (unsigned)
        dt_boundary = distance_transform_edt(~boundary_edge)

        # Signed inward distance transforms
        dt_stele_in = distance_transform_edt(stele) if stele is not None and np.any(stele) else dt_boundary
        dt_sec_in = distance_transform_edt(section) if section is not None and np.any(section) else dt_sec_boundary

        # Center determination & estimated stele radius
        center_in = inputs.get('center_mask')
        if center_in is not None and np.any(_binary(center_in, (h, w))):
            cm = _binary(center_in, (h, w))
            cy_c, cx_c = np.mean(np.where(cm), axis=1)
        elif stele is not None and np.any(stele):
            M = cv2.moments(stele.astype(np.uint8))
            cx_c = M['m10'] / (M['m00'] + 1e-9)
            cy_c = M['m01'] / (M['m00'] + 1e-9)
        else:
            cy_c, cx_c = h / 2.0, w / 2.0

        r_stele = float(np.sqrt(stele.sum() / np.pi)) if stele is not None and np.any(stele) else float(min(h, w) * 0.2)
        r_stele = max(r_stele, 10.0)

        # Landmark poles (metaxylem)
        lm_centroids = []
        if np.any(landmarks):
            lm_labels = measure.label(landmarks)
            for lm_prop in measure.regionprops(lm_labels):
                if lm_prop.area >= 20:
                    lm_centroids.append([float(lm_prop.centroid[1]), float(lm_prop.centroid[0])])
        lm_centroids = np.array(lm_centroids) if lm_centroids else np.empty((0, 2))

        if len(lm_centroids) > 0:
            cx_lm, cy_lm = lm_centroids.mean(axis=0)
            lm_angles = np.arctan2(lm_centroids[:, 1] - cy_lm, lm_centroids[:, 0] - cx_lm)
            lm_angles = np.sort(lm_angles)
        else:
            cx_lm, cy_lm = cx_c, cy_c
            lm_angles = np.array([])

        props = measure.regionprops(labels)
        if not props:
            return empty

        all_cids = [p.label for p in props]
        cell_dict = {p.label: p for p in props}

        # 1. Adjacency Graph from shared wall pixels
        left, right = labels[:, :-1], labels[:, 1:]
        m_h = (left != right) & (left > 0) & (right > 0)
        p_h = np.column_stack((left[m_h], right[m_h]))

        top, bot = labels[:-1, :], labels[1:, :]
        m_v = (top != bot) & (top > 0) & (bot > 0)
        p_v = np.column_stack((top[m_v], bot[m_v]))

        if p_h.size > 0 and p_v.size > 0:
            all_pairs = np.sort(np.vstack((p_h, p_v)), axis=1)
        elif p_h.size > 0:
            all_pairs = np.sort(p_h, axis=1)
        elif p_v.size > 0:
            all_pairs = np.sort(p_v, axis=1)
        else:
            all_pairs = np.empty((0, 2), dtype=np.int32)

        neighbors = {cid: set() for cid in all_cids}
        edge_weights = {}
        if all_pairs.size > 0:
            unique_pairs, edge_lengths = np.unique(all_pairs, axis=0, return_counts=True)
            for (u, v), w_uv in zip(unique_pairs, edge_lengths):
                neighbors[u].add(int(v))
                neighbors[v].add(int(u))
                edge_weights[(int(min(u, v)), int(max(u, v)))] = int(w_uv)

        # Delaunay for adjacent cells across micro-gaps
        max_d = float(params.get('max_delaunay_dist', 35.0))
        coords = np.array([[p.centroid[1], p.centroid[0]] for p in props])
        if len(coords) >= 4 and max_d > 0:
            tri = Delaunay(coords)
            cids_arr = np.array(all_cids)
            for simplex in tri.simplices:
                for i in range(3):
                    for j in range(i + 1, 3):
                        u_id, v_id = int(cids_arr[simplex[i]]), int(cids_arr[simplex[j]])
                        d = float(np.hypot(coords[simplex[i]][0] - coords[simplex[j]][0],
                                           coords[simplex[i]][1] - coords[simplex[j]][1]))
                        if d <= max_d:
                            neighbors[u_id].add(v_id)
                            neighbors[v_id].add(u_id)
                            edge_weights.setdefault((min(u_id, v_id), max(u_id, v_id)), 5)

        # 2. Local size stats & Z-Scores
        cell_areas = {p.label: float(p.area) for p in props}
        z_scores = {}
        mean_nbr_areas = {}
        for cid in all_cids:
            nbrs = neighbors.get(cid, set())
            if len(nbrs) >= 2:
                n_a = [cell_areas[n] for n in nbrs if n in cell_areas]
                m = float(np.mean(n_a))
                s = float(np.std(n_a))
                mean_nbr_areas[cid] = m
                z_scores[cid] = (cell_areas[cid] - m) / max(s, 1.0)
            elif len(nbrs) == 1:
                n_a = [cell_areas[n] for n in nbrs if n in cell_areas]
                m = float(n_a[0])
                mean_nbr_areas[cid] = m
                z_scores[cid] = (cell_areas[cid] - m) / max(m * 0.2, 1.0)
            else:
                mean_nbr_areas[cid] = cell_areas[cid]
                z_scores[cid] = 0.0

        # 3. Topological Layers: BFS starting from boundary contact
        boundary_dil = cv2.dilate(boundary_edge.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        layer1 = set()
        for p in props:
            cy, cx = int(min(max(p.centroid[0], 0), h - 1)), int(min(max(p.centroid[1], 0), w - 1))
            if dt_boundary[cy, cx] <= 14.0 or np.any(boundary_dil[labels == p.label]):
                layer1.add(p.label)

        layers = {cid: 1 for cid in layer1}
        curr = set(layer1)
        depth = 2
        max_depth = int(params.get('layers_max', 6))
        while curr and depth <= max_depth:
            nxt = set()
            for u in curr:
                for v in neighbors.get(u, []):
                    if v not in layers:
                        layers[v] = depth
                        nxt.add(v)
            curr = nxt
            depth += 1

        for cid in all_cids:
            layers.setdefault(cid, max_depth + 1)

        # 4. ANATOMICAL IDENTIFICATION (PARALLEL CORRIDORS & GATING):

        # A) RHIZODERMIS / EXODERMIS:
        # Zone defined by two extrapolated parallel curves:
        # - Outer curve: section boundary
        # - Inner parallel curve: offset distance corridor_rhizo_dist inward
        # Gating: only cells strictly inside this corridor AND belonging to the contiguous layer are classified.
        d_rhizo = float(params.get('corridor_rhizo_dist', 32.0))
        rhizo_raw_cids = set()
        dt_sec_active = dt_sec_in if dt_sec_in is not None else dt_sec_boundary
        if dt_sec_active is not None:
            for p in props:
                cy, cx = int(min(max(p.centroid[0], 0), h - 1)), int(min(max(p.centroid[1], 0), w - 1))
                d_out = float(dt_sec_active[cy, cx])
                cell_mask = (labels == p.label)
                touches_out = np.any(cell_mask & sec_boundary_edge) if sec_boundary_edge is not None else False
                if section is not None:
                    touches_out = touches_out or np.any(cell_mask & (~section))
                if touches_out or d_out <= d_rhizo:
                    rhizo_raw_cids.add(p.label)

            # Contiguity filtering: keep the largest connected component of contiguous cells
            visited = set()
            components = []
            for cid in rhizo_raw_cids:
                if cid not in visited:
                    comp = set()
                    q = [cid]
                    visited.add(cid)
                    while q:
                        curr = q.pop()
                        comp.add(curr)
                        for n in neighbors.get(curr, set()):
                            if n in rhizo_raw_cids and n not in visited:
                                visited.add(n)
                                q.append(n)
                    components.append(comp)
            rhizo_cids = max(components, key=len) if components else set()
        else:
            rhizo_cids = set()

        # B) ENDODERMIS:
        # Zone defined by two extrapolated parallel curves inside the stele:
        # - Outer curve: stele boundary contour (boundary_edge / ol_st)
        # - Inner parallel curve: offset distance corridor_endo_dist inward into the stele.
        # Strict signed gating:
        # 1. Centroid MUST be strictly inside stele (stele[cy, cx] == True), strictly preventing cortical cells.
        # 2. Inward distance to stele perimeter dt_stele_in <= corridor_endo_dist.
        # 3. Compact area (monolayer endodermal morphology: area <= endo_max_area).
        # 4. Graph contiguity: keep the connected components forming the perimeter ring.
        d_endo = float(params.get('corridor_endo_dist', 21.0))
        endo_max_a = float(params.get('endo_max_area', 550.0))

        endo_candidates = set()
        for p in props:
            cid = p.label
            if cid in rhizo_cids:
                continue
            cy, cx = int(min(max(p.centroid[0], 0), h - 1)), int(min(max(p.centroid[1], 0), w - 1))
            if landmarks[cy, cx]:
                continue

            # Strict signed gating: cell centroid must be inside the stele
            if stele is not None and not stele[cy, cx]:
                continue

            d_in = float(dt_stele_in[cy, cx]) if dt_stele_in is not None else float(dt_boundary[cy, cx])
            if d_in <= d_endo and (p.area <= endo_max_a):
                endo_candidates.add(cid)

        # Contiguity filtering on the adjacency graph: keep significant ring components
        visited = set()
        components = []
        for cid in endo_candidates:
            if cid not in visited:
                comp = set()
                q = [cid]
                visited.add(cid)
                while q:
                    curr = q.pop()
                    comp.add(curr)
                    for n in neighbors.get(curr, set()):
                        if n in endo_candidates and n not in visited:
                            visited.add(n)
                            q.append(n)
                components.append(comp)

        endo_cids = set()
        if components:
            max_len = max(len(c) for c in components)
            for c in components:
                # Keep main ring and any coherent ring segments
                if len(c) >= max(2, int(max_len * 0.1)):
                    endo_cids.update(c)

        # C) LARGE PERIPHERAL STELE CELLS:
        # Located strictly inside stele, not endo, not rhizo, not landmarks.
        lpsc_area_fac = float(params.get('lpsc_min_area_factor', 1.20))
        lpsc_min_z = float(params.get('lpsc_min_z', 0.20))
        min_round = float(params.get('min_roundness', 0.35))

        stele_props = [
            p for p in props
            if stele is not None and stele[int(min(max(p.centroid[0], 0), h - 1)), int(min(max(p.centroid[1], 0), w - 1))]
            and not landmarks[int(min(max(p.centroid[0], 0), h - 1)), int(min(max(p.centroid[1], 0), w - 1))]
            and p.label not in endo_cids
            and p.label not in rhizo_cids
        ]
        stele_areas = [float(p.area) for p in stele_props]
        med_stele = float(np.median(stele_areas)) if stele_areas else 100.0
        q65_stele = float(np.percentile(stele_areas, 65)) if stele_areas else 200.0

        lpsc_cids = set()
        for p in stele_props:
            cid = p.label
            cy, cx = int(min(max(p.centroid[0], 0), h - 1)), int(min(max(p.centroid[1], 0), w - 1))
            r = np.hypot(p.centroid[1] - cx_c, p.centroid[0] - cy_c)
            rel_r = r / r_stele

            # Stele peripheral mantle
            if 0.50 <= rel_r <= 0.98:
                a = float(p.area)
                z = float(z_scores.get(cid, 0.0))
                perim = float(max(p.perimeter, 1.0))
                circ = float(4.0 * np.pi * a / (perim ** 2))

                if (a >= med_stele * lpsc_area_fac and z >= lpsc_min_z) or (a >= q65_stele):
                    if circ >= min_round:
                        lpsc_cids.add(cid)

        # 5. Extract Feature Vector per Cell
        features = []
        for p in props:
            cid = int(p.label)
            cx, cy = float(p.centroid[1]), float(p.centroid[0])
            area = float(p.area)
            perim = float(max(p.perimeter, 1.0))
            circ = float(4.0 * np.pi * area / (perim ** 2))
            maj = p.axis_major_length if hasattr(p, 'axis_major_length') else getattr(p, 'major_axis_length', 1.0)
            min_ = p.axis_minor_length if hasattr(p, 'axis_minor_length') else getattr(p, 'minor_axis_length', 1.0)
            aspect = float(maj / max(min_, 1.0))
            dist_b = float(dt_boundary[int(min(max(cy, 0), h - 1)), int(min(max(cx, 0), w - 1))])
            r_rel = float(dist_b / r_stele)
            dist_c = float(np.hypot(cx - cx_c, cy - cy_c))

            if len(lm_centroids) > 0:
                dist_lm = float(np.min(np.hypot(lm_centroids[:, 0] - cx, lm_centroids[:, 1] - cy)))
                th = np.arctan2(cy - cy_lm, cx - cx_lm)
                diffs = np.abs(np.arctan2(np.sin(th - lm_angles), np.cos(th - lm_angles)))
                angle_pole = float(np.min(diffs))
            else:
                dist_lm = 0.0
                angle_pole = 0.0

            lay = int(layers.get(cid, max_depth + 1))
            z = float(z_scores.get(cid, 0.0))
            m_nbr = float(mean_nbr_areas.get(cid, area))

            features.append({
                'cell_id': cid,
                'cx': cx, 'cy': cy,
                'area': area,
                'perimeter': perim,
                'circularity': circ,
                'aspect_ratio': aspect,
                'dist_to_boundary': dist_b,
                'r_rel': r_rel,
                'dist_to_center': dist_c,
                'dist_to_nearest_landmark': dist_lm,
                'angle_to_pole': angle_pole,
                'mean_neighbor_area': m_nbr,
                'local_zscore': z,
                'topological_layer': lay,
                'is_endodermis': bool(cid in endo_cids),
                'is_large_peripheral': bool(cid in lpsc_cids),
                'is_rhizodermis': bool(cid in rhizo_cids),
            })

        # 6. Output Masks & Images
        periph_mask = np.isin(labels, list(lpsc_cids)).astype(np.uint8) * 255
        endo_mask = np.isin(labels, list(endo_cids)).astype(np.uint8) * 255
        rhizo_mask = np.isin(labels, list(rhizo_cids)).astype(np.uint8) * 255

        layers_map = np.zeros((h, w), np.uint8)
        for cid, lay in layers.items():
            if lay <= max_depth:
                layers_map[labels == cid] = int(lay)

        zscore_map = np.zeros((h, w), np.float32)
        for cid, z in z_scores.items():
            zscore_map[labels == cid] = np.clip(z, -3.0, 3.0)
        z_norm = ((np.clip(zscore_map, -2.5, 2.5) + 2.5) / 5.0 * 255).astype(np.uint8)
        z_vis = cv2.applyColorMap(z_norm, cv2.COLORMAP_JET)
        z_vis[labels == 0] = 0

        # Anatomy visualization overlay:
        # Background: dark gray cells
        vis = np.zeros((h, w, 3), np.uint8)
        vis[labels > 0] = (70, 70, 70)
        # Rhizodermis in blue (BGR: 214, 120, 42)
        vis[rhizo_mask > 0] = (214, 120, 42)
        # Endodermis in bright purple (BGR: 194, 87, 126)
        vis[endo_mask > 0] = (194, 87, 126)
        # Large peripheral in warm amber/orange (BGR: 6, 119, 217)
        vis[periph_mask > 0] = (6, 119, 217)
        # Metaxylem in green (BGR: 0, 131, 0)
        vis[landmarks > 0] = (0, 131, 0)

        adj_serializable = {int(k): [int(n) for n in v] for k, v in neighbors.items()}

        return {
            'main': vis,
            'peripheral_mask': periph_mask,
            'endodermis_mask': endo_mask,
            'rhizodermis_mask': rhizo_mask,
            'layers_mask': layers_map,
            'zscore_map': z_vis,
            'features': features,
            'graph': {'neighbors': adj_serializable},
            'peripheral_count': len(lpsc_cids),
            'endodermis_count': len(endo_cids),
            'rhizodermis_count': len(rhizo_cids),
            'count': len(lpsc_cids),
        }
