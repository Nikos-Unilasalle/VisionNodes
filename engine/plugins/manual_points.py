"""
Manual Points — Interactive point placement on an image for SAM prompting.
Points are stored as a JSON param and output as a list for downstream use.
Each point has {x, y} in normalized [0-1] coordinates and a label (1=foreground, 0=background).
"""
from registry import vision_node, NodeProcessor
import cv2
import numpy as np
import json
import base64


@vision_node(
    type_id='manual_points',
    label='Manual Points',
    category='analysis',
    icon='MousePointer',
    description=(
        "Interactive point placement tool. Click on the preview to place foreground points, "
        "right-click to place background points. Use as input prompt for the SAM Segmenter. "
        "Points are stored in normalized [0-1] coordinates."
    ),
    inputs=[
        {'id': 'image', 'color': 'image'},
    ],
    outputs=[
        {'id': 'main',   'color': 'image',  'label': 'Annotated'},
        {'id': 'points', 'color': 'points', 'label': 'Points List'},
        {'id': 'count',  'color': 'scalar', 'label': 'Count'},
    ],
    params=[
        # Points storage (JSON array of {x, y, label})
        {'id': 'points', 'label': 'Points', 'type': 'string',
         'default': '[]'},

        # Visualization
        {'id': 'point_radius', 'label': 'Point Radius', 'type': 'number',
         'default': 8, 'min': 2, 'max': 30},
        {'id': 'show_labels', 'label': 'Show Labels', 'type': 'boolean',
         'default': True},
    ],
    colorable=True,
)
class ManualPointsNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._frame_count = 0
        self._last_preview = None

    def process(self, inputs, params):
        image = inputs.get('image')
        if image is None:
            return {'main': None, 'points': [], 'count': 0}

        # Parse points from JSON param
        try:
            points_raw = json.loads(params.get('points', '[]'))
            if not isinstance(points_raw, list):
                points_raw = []
        except (json.JSONDecodeError, TypeError):
            points_raw = []

        h, w = image.shape[:2]
        radius = int(params.get('point_radius', 8))
        show_labels = bool(params.get('show_labels', True))

        # Draw points on image
        annotated = image.copy()

        for i, pt in enumerate(points_raw):
            if not isinstance(pt, dict):
                continue
            px = float(pt.get('x', 0))
            py = float(pt.get('y', 0))
            label = int(pt.get('label', 1))  # 1=foreground, 0=background

            # Convert normalized → pixel
            cx = int(px * w)
            cy = int(py * h)

            # Colors: green for foreground, red for background
            if label == 1:
                color = (0, 220, 80)       # Green (BGR)
                outline = (255, 255, 255)
                text = 'FG'
            else:
                color = (60, 60, 255)      # Red (BGR)
                outline = (200, 200, 200)
                text = 'BG'

            # Draw filled circle with outline
            cv2.circle(annotated, (cx, cy), radius, color, -1)
            cv2.circle(annotated, (cx, cy), radius + 1, outline, 2)

            # Draw index number
            if show_labels:
                cv2.putText(
                    annotated, f'{i+1}',
                    (cx + radius + 4, cy + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    outline, 1, cv2.LINE_AA
                )

        # Draw legend
        if len(points_raw) > 0:
            fg_count = sum(1 for p in points_raw if isinstance(p, dict) and p.get('label', 1) == 1)
            bg_count = len(points_raw) - fg_count
            legend = f'FG:{fg_count}  BG:{bg_count}'
            cv2.putText(
                annotated, legend,
                (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA
            )

        # Generate preview for frontend (periodic, like Crop node)
        self._frame_count += 1
        if self._frame_count % 6 == 0:
            try:
                ph = 360
                pw = int(360 * w / h)
                pimg = cv2.resize(image, (pw, ph))
                _, buf = cv2.imencode('.jpg', pimg, [cv2.IMWRITE_JPEG_QUALITY, 60])
                self._last_preview = base64.b64encode(buf).decode('utf-8')
            except Exception:
                pass

        # Build output list (compatible with SAM Segmenter and Points to Mask)
        output_points = []
        for pt in points_raw:
            if isinstance(pt, dict) and 'x' in pt and 'y' in pt:
                output_points.append({
                    'x': float(pt['x']),
                    'y': float(pt['y']),
                    'label': int(pt.get('label', 1)),
                })

        return {
            'main': annotated,
            'main_preview': self._last_preview,
            'points': output_points,
            'count': len(output_points),
        }
