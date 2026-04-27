import cv2
import numpy as np
import os
from registry import NodeProcessor, vision_node


def canonical_corners(pts_raw):
    """Sort 4 corners into [TL, TR, BR, BL] via sum/diff method."""
    if not pts_raw or len(pts_raw) < 4:
        return pts_raw
    pts = []
    for p in pts_raw[:4]:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            pts.append([float(p[0]), float(p[1])])
        elif isinstance(p, dict):
            pts.append([float(p.get('x', 0)), float(p.get('y', 0))])
    if len(pts) < 4:
        return pts_raw
    import numpy as _np
    a = _np.array(pts)
    s = a.sum(axis=1);  d = _np.diff(a, axis=1).ravel()
    return [pts[int(_np.argmin(s))], pts[int(_np.argmin(d))],
            pts[int(_np.argmax(s))], pts[int(_np.argmax(d))]]

EAST_MODEL_URL = "https://github.com/oyyd/frozen_east_text_detection.pb/raw/master/frozen_east_text_detection.pb"
EAST_MODEL_PATH = "frozen_east_text_detection.pb"

def download_east_model():
    if not os.path.exists(EAST_MODEL_PATH):
        print(f"[OCR] Downloading EAST model...")
        try:
            import subprocess
            subprocess.run(["curl", "-L", "-o", EAST_MODEL_PATH, EAST_MODEL_URL], check=True)
            print("[OCR] EAST model downloaded.")
        except Exception as e:
            print(f"[OCR] Download failed: {e}")

@vision_node(
    type_id="ocr_east_detect",
    label="Text Detector (EAST)",
    category="ocr",
    icon="Type",
    description="Locates text regions in images using the EAST Deep Learning model. Supports rotated text.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "text_regions", "color": "list"}, {"id": "main", "color": "image"}],
    params=[
        {"id": "min_confidence", "label": "Min Confidence", "type": "scalar", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.3},
        {"id": "nms_threshold",  "label": "NMS Threshold",  "type": "scalar", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.4},
        {"id": "width",          "label": "Input W (×32)",  "type": "scalar", "min": 32,  "max": 1280, "step": 32,   "default": 640},
        {"id": "height",         "label": "Input H (×32)",  "type": "scalar", "min": 32,  "max": 1280, "step": 32,   "default": 640}
    ]
)
class EastDetectorNode(NodeProcessor):
    def __init__(self):
        self.net = None
        download_east_model()

    def load_net(self):
        if self.net is None and os.path.exists(EAST_MODEL_PATH):
            try:
                self.net = cv2.dnn.readNet(EAST_MODEL_PATH)
                print("[OCR] EAST model loaded.")
            except Exception as e:
                print(f"[OCR] Load error: {e}")
        elif self.net is None:
            download_east_model()

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"text_regions": [], "main": None}

        self.load_net()
        if self.net is None: return {"text_regions": [], "main": img}

        orig = img.copy()
        H, W = img.shape[:2]

        newW = max(32, (int(params.get('width',  640)) // 32) * 32)
        newH = max(32, (int(params.get('height', 640)) // 32) * 32)
        rW, rH = W / float(newW), H / float(newH)
        min_conf  = float(params.get('min_confidence', 0.3))
        nms_thresh = float(params.get('nms_threshold',  0.4))

        blob = cv2.dnn.blobFromImage(img, 1.0, (newW, newH),
                                     (123.68, 116.78, 103.94), swapRB=True, crop=False)
        self.net.setInput(blob)
        scores, geometry = self.net.forward(
            ["feature_fusion/Conv_7/Sigmoid", "feature_fusion/concat_3"])

        numRows, numCols = scores.shape[2], scores.shape[3]
        rects, confidences, rotated_boxes = [], [], []

        for y in range(numRows):
            sd = scores[0, 0, y]
            d0, d1, d2, d3 = geometry[0,0,y], geometry[0,1,y], geometry[0,2,y], geometry[0,3,y]
            ang = geometry[0, 4, y]

            for x in range(numCols):
                if sd[x] < min_conf: continue

                ox, oy = x * 4.0, y * 4.0
                ca, sa = np.cos(ang[x]), np.sin(ang[x])

                # Decode 4 rotated corners (EAST convention: TR, TL, BL, BR)
                pts = np.array([
                    [ox + ca*d1[x] + sa*d2[x],  oy - sa*d1[x] + ca*d2[x]],
                    [ox - ca*d3[x] + sa*d2[x],  oy + sa*d3[x] + ca*d2[x]],
                    [ox - ca*d3[x] - sa*d0[x],  oy + sa*d3[x] - ca*d0[x]],
                    [ox + ca*d1[x] - sa*d0[x],  oy - sa*d1[x] - ca*d0[x]],
                ], dtype=np.float32)

                xs, ys = pts[:, 0], pts[:, 1]
                rects.append((int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))
                confidences.append(float(sd[x]))
                rotated_boxes.append(pts)

        indices = cv2.dnn.NMSBoxes(rects, confidences, min_conf, nms_thresh)
        results = []

        if len(indices) > 0:
            for i in indices.flatten():
                scaled = (rotated_boxes[i] * np.array([rW, rH])).astype(np.int32)
                sX = int(np.clip(scaled[:, 0].min(), 0, W))
                sY = int(np.clip(scaled[:, 1].min(), 0, H))
                eX = int(np.clip(scaled[:, 0].max(), 0, W))
                eY = int(np.clip(scaled[:, 1].max(), 0, H))
                norm_pts = [[float(np.clip(p[0]/W,0,1)), float(np.clip(p[1]/H,0,1))] for p in scaled]

                results.append({
                    "xmin": sX/W, "ymin": sY/H,
                    "width": (eX-sX)/W, "height": (eY-sY)/H,
                    "label": "text", "_type": "graphics", "shape": "polygon",
                    "pts": norm_pts, "color": "#ffff00", "relative": True
                })
                cv2.polylines(orig, [scaled.reshape(-1, 1, 2)], True, (0, 255, 0), 2)

        return {"text_regions": results, "main": orig}


def _deskew_crop(img, box):
    """Extract and deskew a rotated text region using perspective transform."""
    H, W = img.shape[:2]
    pts_norm = box.get('pts')

    if pts_norm and len(pts_norm) == 4:
        # Canonical TL, TR, BR, BL order — fixes upside-down text
        ordered = canonical_corners(pts_norm)
        src = np.array([[p[0]*W, p[1]*H] for p in ordered], dtype=np.float32)

        w = int(max(np.linalg.norm(src[0]-src[1]), np.linalg.norm(src[3]-src[2])))
        h = int(max(np.linalg.norm(src[0]-src[3]), np.linalg.norm(src[1]-src[2])))
        if w < 2 or h < 2:
            return None

        dst = np.array([[0,0],[w-1,0],[w-1,h-1],[0,h-1]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(src, dst)
        return cv2.warpPerspective(img, M, (w, h))

    elif 'xmin' in box:
        x = int(box['xmin']*W); y = int(box['ymin']*H)
        w = int(box['width']*W); h = int(box['height']*H)
        crop = img[max(0,y):min(H,y+h), max(0,x):min(W,x+w)]
        return crop if crop.size > 0 else None

    return None


@vision_node(
    type_id="ocr_tesseract",
    label="OCR (Tesseract)",
    category="ocr",
    icon="Type",
    description="Extracts text from an image region using Tesseract OCR. Deskews rotated crops automatically.",
    inputs=[{"id": "image", "color": "image"}, {"id": "box", "color": "dict"}],
    outputs=[{"id": "text", "color": "any"}, {"id": "main", "color": "image"}],
    params=[
        {"id": "lang",    "label": "Language", "type": "enum",
         "options": ["eng", "fra"], "default": 0},
        {"id": "psm",     "label": "PSM Mode",  "type": "enum",
         "options": ["3 – Auto", "6 – Uniform block", "7 – Single line", "8 – Single word", "11 – Sparse text"],
         "default": 1},
        {"id": "padding", "label": "Padding px", "type": "scalar", "min": 0, "max": 40, "default": 4},
        {"id": "upscale", "label": "Upscale ×",  "type": "scalar", "min": 1, "max": 8,  "default": 2}
    ]
)
class TesseractOcrNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.tesseract_available = False
        try:
            import pytesseract
            self.tesseract_available = True
        except:
            pass

    def process(self, inputs, params):
        img  = inputs.get('image')
        box  = inputs.get('box')
        if img is None: return {"text": "", "main": None}

        if not self.tesseract_available:
            return {"text": "Tesseract not installed", "main": img}

        import pytesseract

        # Deskew/crop
        crop = _deskew_crop(img, box) if box else img.copy()
        if crop is None or crop.size == 0:
            return {"text": "", "main": img}

        # Padding
        pad = int(params.get('padding', 4))
        if pad > 0:
            crop = cv2.copyMakeBorder(crop, pad, pad, pad, pad,
                                      cv2.BORDER_CONSTANT, value=(255,255,255))

        # Upscale for better accuracy on small crops
        scale = int(params.get('upscale', 2))
        if scale > 1:
            crop = cv2.resize(crop, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_CUBIC)

        # Convert to grayscale + threshold
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape)==3 else crop
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        langs   = ["eng", "fra"]
        psm_map = [3, 6, 7, 8, 11]
        lang = langs[int(params.get('lang', 0))]
        psm  = psm_map[int(params.get('psm',  1))]
        cfg  = f"--psm {psm}"

        try:
            text = pytesseract.image_to_string(bw, lang=lang, config=cfg)
            return {"text": text.strip(), "main": crop}
        except Exception as e:
            return {"text": f"Error: {e}", "main": crop}
