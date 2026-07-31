from registry import vision_node, NodeProcessor
import numpy as np
import cv2

@vision_node(
    type_id='sci_calibration',
    label='Unit Calibration',
    category='measure',
    icon='Scaling',
    description="Converts pixel measurements (length or area) into real-world units based on a calibration factor.",
    inputs=[{'id': 'input', 'color': 'any'}],
    outputs=[{'id': 'output', 'color': 'any'}],
    params=[
        {'id': 'factor',     'label': 'Pixels per Unit', 'type': 'float', 'default': 100.0},
        {'id': 'dimension',  'label': 'Dimension',       'type': 'string', 'default': 'Area', 'options': ['Length', 'Area']},
        {'id': 'unit_name',  'label': 'Unit Name',       'type': 'string', 'default': 'cm'},
    ]
)
class CalibrationNode(NodeProcessor):
    def process(self, inputs, params):
        val = inputs.get('input')
        
        # Fallback for stale connections or mismatched IDs
        if val is None:
            relevant_inputs = [v for k, v in inputs.items() if k not in ['raw_frame', 'image']]
            if relevant_inputs:
                val = relevant_inputs[0]

        if val is None:
            return {'output': None, 'display_value': "---"}
            
        try:
            # Handle list input if necessary
            is_list = isinstance(val, (list, np.ndarray, tuple))
            data = np.array(val) if is_list else float(val)
                
            factor = float(params.get('factor', 100.0))
            dim = params.get('dimension', 'Area')
            
            if factor <= 0:
                res = data
            else:
                if dim == 'Length':
                    res = data / factor
                else:
                    res = data / (factor ** 2)
                
            unit = params.get('unit_name', 'cm') + ('²' if dim == 'Area' else '')
            
            # Formatted display for the node UI
            if is_list:
                display = f"{len(res)} items"
            else:
                display = f"{res:.3f} {unit}"

            return {
                'main': res.tolist() if is_list else float(res),
                'output': res.tolist() if is_list else float(res),
                'display_value': display,
                'unit': unit
            }
        except Exception as e:
            return {'output': None, 'display_value': "Error"}

@vision_node(
    type_id='sci_interactive_calibration',
    label='Visual Calibration',
    category='measure',
    icon='Scaling',
    description=(
        "Calculates a calibration factor by drawing a line of a known physical length on the image.\n\n"
        "Two ways to read the result, both always computed:\n"
        "• Px/Unit — pixels per unit of the length you typed (e.g. px/mm)\n"
        "• µm/px — microns per pixel, the convention Region Properties and Grain Stats expect\n\n"
        "Recognised units: µm, mm, cm, m, in. Any other unit name leaves µm/px unavailable."
    ),
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[
        {'id': 'factor',    'color': 'scalar', 'label': 'Px/Unit'},
        {'id': 'um_per_px', 'color': 'scalar', 'label': 'µm/px'},
        # NOTE: carries a string, but declared 'scalar' because Ruler's matching input
        # is declared 'scalar' too. Fixing the type means changing both nodes at once,
        # plus the handles stored in existing .vn files — not a one-sided change.
        {'id': 'unit',      'color': 'scalar', 'label': 'Unit Name'},
        {'id': 'main',      'color': 'image'}
    ],
    params=[
        {'id': 'points',   'label': 'Line Points', 'type': 'string', 'default': '[]'},
        {'id': 'real_len', 'label': 'Known Length', 'type': 'float', 'default': 10.0},
        {'id': 'unit',     'label': 'Unit Name',   'type': 'string', 'default': 'mm'},
        {'id': 'readout',  'label': 'Show',        'type': 'enum',
         'options': ['Both', 'Px / Unit', 'µm / Pixel'], 'default': 0},
    ]
)
class InteractiveCalibrationNode(NodeProcessor):
    # The preview is the backdrop the user draws on, in an overlay that zooms to 20x.
    # Too small and the calibration line cannot be placed on an edge; too large and the
    # base64 rides in nodes_data on every engine cycle (30 fps when a realtime node is
    # in the graph). 4 MP keeps a typical photo at native resolution, and the cache
    # below means an unchanged frame is never re-encoded.
    PREVIEW_MAX_PIXELS = 4_000_000
    # A live source (webcam, video) would ship a fresh multi-megapixel preview every
    # frame. Calibration is done on a still image, so when frames arrive faster than
    # this we fall back to a light preview instead of flooding the socket.
    LIVE_CALL_INTERVAL_S = 0.25
    PREVIEW_LIVE_MAX_PIXELS = 310_000   # matches the previous 640x480, so nothing regresses

    # µm per unit of length. The unit param stays free text for backward compatibility,
    # so it is matched leniently — anything unrecognised disables the µm/px output
    # rather than silently emitting a wrong scale.
    UM_PER_UNIT = {
        'um': 1.0, 'µm': 1.0, 'μm': 1.0, 'micron': 1.0, 'microns': 1.0,
        'mm': 1e3, 'millimeter': 1e3, 'millimetre': 1e3,
        'cm': 1e4, 'centimeter': 1e4, 'centimetre': 1e4,
        'm': 1e6, 'meter': 1e6, 'metre': 1e6,
        'in': 25400.0, 'inch': 25400.0, '"': 25400.0,
    }

    @classmethod
    def _um_per_unit(cls, unit_name):
        return cls.UM_PER_UNIT.get(str(unit_name).strip().lower().rstrip('s') or 'mm') \
            or cls.UM_PER_UNIT.get(str(unit_name).strip().lower())

    def __init__(self, engine=None):
        self._cache_key = None
        self._cache_b64 = None
        self._last_call_t = None

    @staticmethod
    def _fingerprint(img, pts_json, real_len):
        """Cheap change detector: shape + a strided sample. Avoids hashing 4 MP/frame."""
        sample = float(np.asarray(img[::64, ::64], dtype=np.float64).sum())
        return (img.shape, str(img.dtype), sample, pts_json, real_len)

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {'factor': 1.0, 'um_per_px': 0.0}

        h, w = img.shape[:2]
        import json
        try:
            pts = json.loads(params.get('points', '[]'))
        except: pts = []

        px_per_unit = 1.0
        um_per_px = 0.0
        display = "Draw Line"

        out_img = img.copy()
        if len(out_img.shape) == 2:
            out_img = cv2.cvtColor(out_img, cv2.COLOR_GRAY2BGR)

        if len(pts) >= 2:
            p1, p2 = pts[0], pts[1]
            dx = (p2['x'] - p1['x']) * w
            dy = (p2['y'] - p1['y']) * h
            px_dist = np.sqrt(dx**2 + dy**2)
            
            real_len = float(params.get('real_len', 10.0))
            unit = params.get('unit', 'mm')
            
            if px_dist > 0 and real_len > 0:
                px_per_unit = px_dist / real_len
                um_per_unit = self._um_per_unit(unit)
                if um_per_unit:
                    um_per_px = um_per_unit / px_per_unit

                readout = int(params.get('readout', 0) or 0)
                px_txt = f"{px_per_unit:.2f} px/{unit}"
                um_txt = f"{um_per_px:.1f} µm/px" if um_per_px else f"unknown unit '{unit}'"
                display = {1: px_txt, 2: um_txt}.get(readout, f"{px_txt}  ·  {um_txt}")
            
            # Draw line for visual feedback. Sizes scale with the image so the markers
            # stay visible on a 4000px photo without swallowing the edge being targeted
            # on a small one — and the endpoints are hollow so the exact point remains
            # readable underneath.
            a = (int(p1['x'] * w), int(p1['y'] * h))
            b = (int(p2['x'] * w), int(p2['y'] * h))
            thick = max(2, int(round(w / 800)))
            radius = max(4, int(round(w / 300)))
            cv2.line(out_img, a, b, (255, 0, 255), thick)
            for pt in (a, b):
                cv2.circle(out_img, pt, radius, (255, 255, 255), thick)

        # Encode preview to base64, reusing the last one when nothing changed.
        import base64
        key = None
        try:
            key = self._fingerprint(img, params.get('points', '[]'),
                                    float(params.get('real_len', 10.0)))
        except Exception:
            pass

        import time
        now = time.monotonic()
        is_live = (self._last_call_t is not None
                   and (now - self._last_call_t) < self.LIVE_CALL_INTERVAL_S
                   and key != self._cache_key)
        self._last_call_t = now
        budget = self.PREVIEW_LIVE_MAX_PIXELS if is_live else self.PREVIEW_MAX_PIXELS

        if key is not None and key == self._cache_key:
            preview_b64 = self._cache_b64
        else:
            preview_b64 = None
            try:
                # Never upscale; downscale only past the pixel budget, with INTER_AREA
                # so edges stay clean instead of aliasing — an aliased edge is exactly
                # what defeats precise placement.
                scale = min(1.0, (budget / float(w * h)) ** 0.5)
                if scale < 1.0:
                    pw, ph = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
                    pimg = cv2.resize(out_img, (pw, ph), interpolation=cv2.INTER_AREA)
                else:
                    pimg = out_img
                _, buf = cv2.imencode('.jpg', pimg, [cv2.IMWRITE_JPEG_QUALITY, 88])
                preview_b64 = base64.b64encode(buf).decode('utf-8')
            except Exception:
                pass
            self._cache_key, self._cache_b64 = key, preview_b64

        unit = params.get('unit', 'mm')
        return {
            'factor': float(px_per_unit),
            'um_per_px': float(um_per_px),
            'unit': unit,
            'main': out_img,
            'main_preview': preview_b64,
            'display_value': display
        }
