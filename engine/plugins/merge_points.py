import numpy as np
from registry import vision_node, NodeProcessor


@vision_node(
    type_id='merge_points',
    label='Merge Points',
    category='detect',
    icon='Target',
    inputs=[{'id': 'points', 'color': 'list'}],
    outputs=[
        {'id': 'points', 'color': 'list'},
        {'id': 'keypoints', 'color': 'list'},
        {'id': 'count', 'color': 'scalar'},
    ],
    params=[
        {'id': 'threshold', 'type': 'number', 'default': 20, 'min': 1, 'max': 200, 'label': 'Merge Radius (px)'},
        {'id': 'image_width', 'type': 'number', 'default': 640, 'min': 1, 'max': 4000, 'label': 'Image Width'},
        {'id': 'image_height', 'type': 'number', 'default': 480, 'min': 1, 'max': 4000, 'label': 'Image Height'},
    ]
)
class MergePointsNode(NodeProcessor):
    def process(self, inputs, params):
        raw = inputs.get('points')

        if not raw:
            return {'points': [], 'keypoints': [], 'count': 0}

        iw = float(params.get('image_width', 640))
        ih = float(params.get('image_height', 480))
        threshold = float(params.get('threshold', 20))

        # Normalize input: accept list of dicts with x/y
        norm_pts = []
        for p in raw:
            if isinstance(p, dict) and 'x' in p and 'y' in p:
                norm_pts.append((float(p['x']), float(p['y'])))

        if not norm_pts:
            return {'points': [], 'keypoints': [], 'count': 0}

        # Convert normalized -> pixel coords
        px_pts = [(nx * iw, ny * ih) for nx, ny in norm_pts]

        # Greedy cluster merge
        assigned = [False] * len(px_pts)
        merged_px = []

        for i, (xi, yi) in enumerate(px_pts):
            if assigned[i]:
                continue
            cluster = [(xi, yi)]
            assigned[i] = True
            for j in range(i + 1, len(px_pts)):
                if assigned[j]:
                    continue
                xj, yj = px_pts[j]
                dist = ((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5
                if dist <= threshold:
                    cluster.append((xj, yj))
                    assigned[j] = True
            cx = sum(p[0] for p in cluster) / len(cluster)
            cy = sum(p[1] for p in cluster) / len(cluster)
            merged_px.append((cx, cy))

        # Convert back to normalized coords
        merged_norm = [
            {'x': cx / iw, 'y': cy / ih}
            for cx, cy in merged_px
        ]

        # Graphics format for visualization
        keypoints = [
            {
                '_type': 'graphics',
                'shape': 'point',
                'pts': [[p['x'], p['y']]],
                'relative': True,
                'color': '#00ff88',
            }
            for p in merged_norm
        ]

        return {
            'points': merged_norm,
            'keypoints': keypoints,
            'count': len(merged_norm),
        }
