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
    type_id='seg_graph_regularize',
    label='Graph Regularization (CRF)',
    category='segmentation',
    icon='GitMerge',
    description=(
        "Spatial regularization / Markov Random Field (CRF) smoothing on a cell network.\n\n"
        "Eliminates isolated 'confetti' misclassifications by enforcing spatial consistency on the "
        "cell adjacency graph. Each cell's class is updated via weighted voting based on shared wall "
        "lengths with adjacent neighbors.\n"
        "- Self Weight: balance between keeping the original class and yielding to majority neighbors.\n"
        "- Barrier Mask: optional physical boundary (e.g. stele outline) preventing classes from bleeding "
        "across tissues (e.g. stele classes never cross into cortex)."
    ),
    inputs=[
        {'id': 'labels', 'color': 'markers', 'label': 'Cell Labels'},
        {'id': 'zones', 'color': 'markers', 'label': 'Initial Zone Map'},
        {'id': 'graph', 'color': 'dict', 'label': 'Adjacency Graph (opt.)'},
        {'id': 'barrier', 'color': 'mask', 'label': 'Tissue Barrier (opt.)'},
    ],
    outputs=[
        {'id': 'main', 'color': 'image', 'label': 'Regularized Zones'},
        {'id': 'zones', 'color': 'markers', 'label': 'Regularized Map'},
        {'id': 'cleaned_mask', 'color': 'mask', 'label': 'Reassigned Cells'},
        {'id': 'changes_count', 'color': 'scalar', 'label': 'Reassigned Count'},
        {'id': 'mask_1', 'color': 'mask', 'label': 'Zone 1 Mask'},
        {'id': 'mask_2', 'color': 'mask', 'label': 'Zone 2 Mask'},
        {'id': 'mask_3', 'color': 'mask', 'label': 'Zone 3 Mask'},
        {'id': 'mask_4', 'color': 'mask', 'label': 'Zone 4 Mask'},
        {'id': 'mask_5', 'color': 'mask', 'label': 'Zone 5 Mask'},
        {'id': 'mask_6', 'color': 'mask', 'label': 'Zone 6 Mask'},
    ],
    params=[
        {'id': 'iterations', 'label': 'Iterations', 'type': 'int', 'default': 3, 'min': 1, 'max': 10},
        {'id': 'self_weight', 'label': 'Self Weight (prior)', 'type': 'float', 'default': 0.35, 'min': 0.0, 'max': 2.0, 'step': 0.05},
        {'id': 'preserve_class', 'label': 'Preserve Class (0 = none)', 'type': 'int', 'default': 0, 'min': 0, 'max': 20},
        {'id': 'min_agreement', 'label': 'Min Neighbor Agreement', 'type': 'float', 'default': 0.5, 'min': 0.1, 'max': 1.0, 'step': 0.05},
    ],
)
class GraphRegularizeNode(NodeProcessor):
    def process(self, inputs, params):
        empty = {
            'main': None, 'zones': None, 'cleaned_mask': None, 'changes_count': 0,
            **{f'mask_{k}': None for k in range(1, 7)}
        }
        labels = inputs.get('labels')
        zones = inputs.get('zones')
        if not isinstance(labels, np.ndarray) or not isinstance(zones, np.ndarray):
            return empty

        from scipy import ndimage as ndi
        from skimage import measure

        labels = labels.astype(np.int32)
        h, w = labels.shape
        if zones.shape != (h, w):
            zones = cv2.resize(zones, (w, h), interpolation=cv2.INTER_NEAREST)
        zones = zones.astype(np.int32)

        barrier_in = inputs.get('barrier')
        barrier = _binary(barrier_in, (h, w)) if barrier_in is not None else None

        props = measure.regionprops(labels)
        if not props:
            return empty

        cell_ids = [p.label for p in props]

        # 1. Determine dominant initial class per cell
        # Median / mode of zone values inside each cell
        cell_class = {}
        cell_barrier_side = {}

        barrier_region = None
        if barrier is not None:
            # If barrier is a thin contour (less than 5% non-zero pixels), fill holes to obtain the inside/outside partition
            if 0 < cv2.countNonZero(barrier.astype(np.uint8)) < 0.05 * h * w:
                from scipy import ndimage as ndi
                barrier_region = ndi.binary_fill_holes(barrier)
            else:
                barrier_region = barrier

        for p in props:
            cy, cx = int(min(max(p.centroid[0], 0), h - 1)), int(min(max(p.centroid[1], 0), w - 1))
            cid = p.label
            c_val = int(zones[cy, cx])
            cell_class[cid] = c_val
            if barrier_region is not None:
                cell_barrier_side[cid] = bool(barrier_region[cy, cx])

        # 2. Adjacency graph
        graph_in = inputs.get('graph')
        neighbors = {}
        weights = {}

        if isinstance(graph_in, dict) and 'neighbors' in graph_in:
            raw_adj = graph_in['neighbors']
            neighbors = {int(k): set(int(n) for n in v) for k, v in raw_adj.items()}
        else:
            # Build directly from shared wall pixels
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

            neighbors = {cid: set() for cid in cell_ids}
            if all_pairs.size > 0:
                unique_pairs, edge_lengths = np.unique(all_pairs, axis=0, return_counts=True)
                for (u, v), w_uv in zip(unique_pairs, edge_lengths):
                    if u in neighbors and v in neighbors:
                        neighbors[u].add(int(v))
                        neighbors[v].add(int(u))
                        weights[(int(min(u, v)), int(max(u, v)))] = int(w_uv)

        # 3. Regularization iterations
        iters = int(params.get('iterations', 3))
        self_w = float(params.get('self_weight', 0.35))
        preserve_c = int(params.get('preserve_class', 0))
        min_agree = float(params.get('min_agreement', 0.5))

        curr_class = dict(cell_class)
        reassigned_cells = set()

        for it in range(iters):
            nxt_class = dict(curr_class)
            for cid in cell_ids:
                orig_c = curr_class[cid]
                if orig_c == preserve_c or orig_c == 0:
                    continue

                nbrs = neighbors.get(cid, set())
                if not nbrs:
                    continue

                votes = {}
                total_nbr_weight = 0.0
                for n in nbrs:
                    if n not in curr_class:
                        continue
                    n_c = curr_class[n]
                    # Barrier constraint: cannot vote across barrier
                    if barrier is not None:
                        if cell_barrier_side.get(cid) != cell_barrier_side.get(n):
                            continue

                    w_edge = float(weights.get((min(cid, n), max(cid, n)), 1.0))
                    votes[n_c] = votes.get(n_c, 0.0) + w_edge
                    total_nbr_weight += w_edge

                if total_nbr_weight <= 0.0:
                    continue

                # Add self prior weight
                votes[orig_c] = votes.get(orig_c, 0.0) + self_w * total_nbr_weight

                best_c = max(votes, key=votes.get)
                # Check if majority agreement threshold is met
                nbr_agree = (votes[best_c] - (self_w * total_nbr_weight if best_c == orig_c else 0.0)) / total_nbr_weight
                if best_c != orig_c and nbr_agree >= min_agree:
                    nxt_class[cid] = best_c
                    reassigned_cells.add(cid)

            curr_class = nxt_class

        # 4. Reconstruct regularized zone image
        out_zones = np.zeros((h, w), np.int32)
        changed_mask = np.zeros((h, w), np.uint8)

        for cid, c_val in curr_class.items():
            mask_c = (labels == cid)
            out_zones[mask_c] = c_val
            if c_val != cell_class.get(cid):
                changed_mask[mask_c] = 255

        # Also copy non-cell regions from original zones if any
        uncovered = (labels == 0) & (zones > 0)
        out_zones[uncovered] = zones[uncovered]

        # Colormap visual
        max_val = max(int(out_zones.max()), 1)
        scaled = np.clip(out_zones * (255 // max_val), 0, 255).astype(np.uint8)
        vis = cv2.applyColorMap(scaled, cv2.COLORMAP_TURBO)
        vis[out_zones == 0] = 0

        res = {
            'main': vis,
            'zones': out_zones,
            'cleaned_mask': changed_mask,
            'changes_count': len(reassigned_cells),
        }
        for k in range(1, 7):
            res[f'mask_{k}'] = (out_zones == k).astype(np.uint8) * 255
        return res
