import cv2
import numpy as np
import os
import urllib.request
from __main__ import NodeProcessor, vision_node

# EAST Model path
EAST_MODEL_URL = "https://github.com/oyyd/frozen_east_text_detection.pb/raw/master/frozen_east_text_detection.pb"
EAST_MODEL_PATH = "frozen_east_text_detection.pb"

def download_east_model():
    if not os.path.exists(EAST_MODEL_PATH):
        print(f"[OCR] Downloading EAST model from {EAST_MODEL_URL}...")
        try:
            # Use curl if possible or urllib
            import subprocess
            subprocess.run(["curl", "-L", "-o", EAST_MODEL_PATH, EAST_MODEL_URL], check=True)
            print("[OCR] EAST model downloaded successfully.")
        except Exception as e:
            print(f"[OCR] Failed to download EAST model: {e}")

@vision_node(
    type_id="ocr_east_detect",
    label="Text Detector (EAST)",
    category="ocr",
    icon="Type",
    description="Locates text regions in images using the EAST Deep Learning model.",
    inputs=[{"id": "image", "color": "image"}],
    outputs=[{"id": "text_regions", "color": "list"}, {"id": "main", "color": "image"}],
    params=[
        {"id": "min_confidence", "label": "Min Conf", "type": "scalar", "min": 0, "max": 1.0, "step": 0.01, "default": 0.5},
        {"id": "width", "label": "Input W", "type": "scalar", "min": 32, "max": 6400, "step": 32, "default": 320},
        {"id": "height", "label": "Input H", "type": "scalar", "min": 32, "max": 6400, "step": 32, "default": 320}
    ]
)
class EastDetectorNode(NodeProcessor):
    def __init__(self):
        self.net = None
        download_east_model()

    def load_net(self):
        if self.net is None:
            if os.path.exists(EAST_MODEL_PATH):
                try:
                    self.net = cv2.dnn.readNet(EAST_MODEL_PATH)
                    print("[OCR] EAST model loaded successfully.")
                except Exception as e:
                    print(f"[OCR] Error loading EAST net: {e}")
            else:
                download_east_model()

    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None: return {"text_regions": [], "main": None}
        
        self.load_net()
        if self.net is None: return {"text_regions": [], "main": img}
        
        orig = img.copy()
        (H, W) = img.shape[:2]
        
        # EAST requires input multiple of 32
        newW = int(params.get('width', 320))
        newH = int(params.get('height', 320))
        newW = (newW // 32) * 32
        newH = (newH // 32) * 32
        
        rW = W / float(newW)
        rH = H / float(newH)
        
        blob = cv2.dnn.blobFromImage(img, 1.0, (newW, newH), (123.68, 116.78, 103.94), swapRB=True, crop=False)
        self.net.setInput(blob)
        # layerNames for EAST
        layerNames = ["feature_fusion/Conv_7/Sigmoid", "feature_fusion/concat_3"]
        (scores, geometry) = self.net.forward(layerNames)
        
        (numRows, numCols) = scores.shape[2:4]
        rects = []
        confidences = []
        
        min_conf = float(params.get('min_confidence', 0.5))
        
        for y in range(0, numRows):
            scoresData = scores[0, 0, y]
            x0 = geometry[0, 0, y]
            x1 = geometry[0, 1, y]
            x2 = geometry[0, 2, y]
            x3 = geometry[0, 3, y]
            anglesData = geometry[0, 4, y]
            
            for x in range(0, numCols):
                if scoresData[x] < min_conf: continue
                
                (offsetX, offsetY) = (x * 4.0, y * 4.0)
                angle = anglesData[x]
                cos = np.cos(angle)
                sin = np.sin(angle)
                h = x0[x] + x2[x]
                w = x1[x] + x3[x]
                
                endX = int(offsetX + (cos * x1[x]) + (sin * x2[x]))
                endY = int(offsetY - (sin * x1[x]) + (cos * x2[x]))
                startX = int(endX - w)
                startY = int(endY - h)
                
                rects.append((startX, startY, endX, endY))
                confidences.append(scoresData[x])
        
        # NMS
        from cv2 import dnn
        indices = dnn.NMSBoxes(rects, confidences, min_conf, 0.4)
        
        results = []
        if len(indices) > 0:
            for i in indices.flatten():
                (startX, startY, endX, endY) = rects[i]
                
                # Scale back to original
                sX = int(startX * rW)
                sY = int(startY * rH)
                eX = int(endX * rW)
                eY = int(endY * rH)
                
                results.append({
                    "xmin": max(0, sX/W), "ymin": max(0, sY/H), 
                    "width": min(1.0, (eX-sX)/W), "height": min(1.0, (eY-sY)/H),
                    "label": "text", "_type": "graphics", "shape": "rect",
                    "pts": [[max(0, sX/W), max(0, sY/H)], [min(1.0, eX/W), min(1.0, eY/H)]],
                    "color": "#ffff00", "relative": True
                })
                cv2.rectangle(orig, (sX, sY), (eX, eY), (0, 255, 0), 2)
                
        return {"text_regions": results, "main": orig}

@vision_node(
    type_id="ocr_tesseract",
    label="OCR (Tesseract)",
    category="ocr",
    icon="Type",
    description="Extracts text from an image region using Tesseract OCR.",
    inputs=[{"id": "image", "color": "image"}, {"id": "box", "color": "dict"}],
    outputs=[{"id": "text", "color": "any"}, {"id": "main", "color": "image"}],
    params=[
        {"id": "lang", "label": "Language", "type": "enum", "options": ["eng", "fra"], "default": 0}
    ]
)
class TesseractOcrNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.tesseract_available = False
        try:
            import pytesseract
            # Check if binary is available
            # pytesseract.get_tesseract_version()
            self.tesseract_available = True
        except:
            pass

    def process(self, inputs, params):
        img = inputs.get('image')
        box = inputs.get('box')
        if img is None: return {"text": "", "main": None}
        
        if not self.tesseract_available:
            return {"text": "Tesseract Error: lib not installed", "main": img}
        
        import pytesseract
        
        crop = img
        if box and isinstance(box, dict) and 'xmin' in box:
            (H, W) = img.shape[:2]
            x, y, w, h = int(box['xmin']*W), int(box['ymin']*H), int(box['width']*W), int(box['height']*H)
            crop = img[max(0, y):min(H, y+h), max(0, x):min(W, x+w)]
            
        if crop.size == 0: return {"text": "", "main": img}
        
        langs = ["eng", "fra"]
        lang = langs[int(params.get('lang', 0))]
        
        try:
            text = pytesseract.image_to_string(crop, lang=lang)
            return {"text": text.strip(), "main": crop}
        except Exception as e:
            return {"text": f"Error: {e}", "main": crop}
