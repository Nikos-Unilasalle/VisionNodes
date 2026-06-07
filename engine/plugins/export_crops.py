"""
Export Crops — Save one image per detected object from boxes or contours.

Source: a boxes list (Grounding DINO / YOLO / BBox Transform) and/or a contours
list (SAM). Each object is cropped and written to disk. Optionally classify the
output into per-class subfolders by connecting a labels list (DINOv2) — ideal for
building an ImageFolder reference set.

Cut modes:
  • Rect      : tight rectangular crop, opaque background.
  • Masked    : pixels outside the polygon are transparent (RGBA PNG, contours only).

Naming:
  • By id    : <out_dir>/<prefix>_<ts>_<id>.png
  • By class : <out_dir>/<label>/<label>_<ts>_<id>.png   (needs labels list)
"""
from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import os
import time


@vision_node(
    type_id='export_crops',
    label='Export Crops',
    category='output',
    icon='DownloadCloud',
    description=(
        "Export one image per object from a boxes list (GDINO/YOLO) and/or a "
        "contours list (SAM). Rect or masked (transparent) crops. Optionally sort "
        "into per-class subfolders via a connected labels list (DINOv2) — perfect "
        "for building an ImageFolder reference set. Press 'Export Now' to write."
    ),
    inputs=[
        {'id': 'image',       'color': 'image', 'label': 'Source Image'},
        {'id': 'boxes_list',  'color': 'list',  'label': 'Boxes List'},
        {'id': 'contours',    'color': 'list',  'label': 'Contours'},
        {'id': 'labels_list', 'color': 'list',  'label': 'Labels List (optional)'},
    ],
    outputs=[
        {'id': 'count', 'color': 'scalar', 'label': 'Exported Count'},
    ],
    params=[
        {'id': 'export_trigger', 'label': 'Export Now', 'type': 'trigger', 'default': 0},
        {'id': 'out_dir', 'label': 'Output Folder', 'type': 'string', 'default': 'exports/crops'},
        {'id': 'prefix',  'label': 'Prefix', 'type': 'string', 'default': 'crop'},
        {'id': 'source',  'label': 'Source', 'type': 'enum',
         'options': ['Auto', 'Boxes', 'Contours'], 'default': 0},
        {'id': 'cut_mode', 'label': 'Cut Mode', 'type': 'enum',
         'options': ['Rect (opaque)', 'Masked (transparent)'], 'default': 0},
        {'id': 'naming', 'label': 'Naming', 'type': 'enum',
         'options': ['Auto (by class if labels)', 'By id', 'By class'], 'default': 0},
        {'id': 'pad', 'label': 'Padding (px)', 'type': 'int', 'default': 5, 'min': 0, 'max': 200},
        {'id': 'format', 'label': 'Format', 'type': 'enum',
         'options': ['PNG', 'JPG'], 'default': 0},
    ],
)
class ExportCropsNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self.is_exporting = False

    # ── input normalization ─────────────────────────────────────────────────
    def _box_to_xyxy(self, box: dict, w: int, h: int) -> tuple:
        """Normalized box dict → pixel (x1,y1,x2,y2)."""
        x1 = float(box.get('xmin', 0.0)) * w
        y1 = float(box.get('ymin', 0.0)) * h
        x2 = x1 + float(box.get('width', 0.0)) * w
        y2 = y1 + float(box.get('height', 0.0)) * h
        return int(x1), int(y1), int(x2), int(y2)

    def _contour_to_np(self, contour, w: int, h: int):
        """Contour (list of [x,y], normalized or pixel) → int32 (N,1,2) pixel array."""
        if not isinstance(contour, (list, tuple)) or len(contour) < 3:
            return None
        try:
            arr = np.array(contour, dtype=np.float32).reshape(-1, 2)
        except Exception:
            return None
        # Heuristic: values in [0,1] → normalized → scale to pixels
        if arr.size and float(arr.max()) <= 1.0:
            arr[:, 0] *= w
            arr[:, 1] *= h
        return arr.astype(np.int32).reshape(-1, 1, 2)

    def _id_label_map(self, labels_list) -> dict:
        """labels_list [{id,label,...}] → {id: label}."""
        out = {}
        if isinstance(labels_list, list):
            for item in labels_list:
                if isinstance(item, dict) and 'id' in item:
                    out[int(item['id'])] = str(item.get('label', 'object'))
        return out

    def _safe(self, name: str) -> str:
        keep = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in str(name))
        return keep or 'object'

    # ── main ─────────────────────────────────────────────────────────────────
    def process(self, inputs: dict, params: dict) -> dict:
        trigger = int(params.get('export_trigger', 0)) == 1
        if not trigger:
            self.is_exporting = False
            return {'count': 0.0}
        if self.is_exporting:
            return {'count': 0.0}
        self.is_exporting = True

        img = inputs.get('image')
        if img is None or not hasattr(img, 'shape'):
            send_notification('Export Crops: no image', level='error')
            return {'count': 0.0}

        out_dir   = params.get('out_dir', 'exports/crops') or 'exports/crops'
        prefix    = params.get('prefix', 'crop') or 'crop'
        source    = int(params.get('source', 0))
        cut_mode  = int(params.get('cut_mode', 0))      # 0 rect, 1 masked
        naming    = int(params.get('naming', 0))        # 0 auto, 1 id, 2 class
        pad       = int(params.get('pad', 5))
        fmt       = 'jpg' if int(params.get('format', 0)) == 1 else 'png'

        boxes    = inputs.get('boxes_list')
        contours = inputs.get('contours')
        labels   = self._id_label_map(inputs.get('labels_list'))

        # Pick source
        use_contours = (source == 2) or (source == 0 and isinstance(contours, list) and len(contours) > 0)
        if source == 1:
            use_contours = False
        if use_contours and not (isinstance(contours, list) and len(contours)):
            send_notification('Export Crops: no contours', level='error')
            return {'count': 0.0}
        if not use_contours and not (isinstance(boxes, list) and len(boxes)):
            send_notification('Export Crops: no boxes', level='error')
            return {'count': 0.0}

        h, w = img.shape[:2]
        # JPG can't hold alpha → force rect if masked+jpg
        masked = (cut_mode == 1) and fmt == 'png'

        # Resolve "by class" — needs labels; auto falls back to id when absent
        by_class = (naming == 2) or (naming == 0 and len(labels) > 0)

        notif_id = f'export_crops_{int(time.time())}'
        send_notification('Export Crops: starting…', progress=0, notif_id=notif_id)

        # Prepare BGRA source once if masking
        if masked:
            if len(img.shape) == 2:
                src = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
            elif img.shape[2] == 3:
                src = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            else:
                src = img.copy()
        else:
            src = img

        ts = int(time.time())
        exported = 0

        # Build a unified list of (obj_id, xyxy, contour_or_None)
        items = []
        if use_contours:
            for i, c in enumerate(contours):
                cnt = self._contour_to_np(c, w, h)
                if cnt is None:
                    continue
                x, y, bw, bh = cv2.boundingRect(cnt)
                items.append((i, (x, y, x + bw, y + bh), cnt))
        else:
            for b in boxes:
                if not isinstance(b, dict):
                    continue
                oid = int(b.get('id', len(items)))
                items.append((oid, self._box_to_xyxy(b, w, h), None))

        total = len(items)
        for i, (oid, (x1, y1, x2, y2), cnt) in enumerate(items):
            if i % 5 == 0 or i == total - 1:
                send_notification(f'Export Crops: {i + 1}/{total}…',
                                  progress=int(i / max(1, total) * 100), notif_id=notif_id)

            xs = max(0, x1 - pad); ys = max(0, y1 - pad)
            xe = min(w, x2 + pad); ye = min(h, y2 + pad)
            if xe <= xs or ye <= ys:
                continue

            crop = src[ys:ye, xs:xe].copy()
            if crop.size == 0:
                continue

            if masked and cnt is not None:
                mask = np.zeros((h, w), dtype=np.uint8)
                cv2.fillPoly(mask, [cnt], 255)
                mask_crop = mask[ys:ye, xs:xe]
                crop[:, :, 3] = mask_crop

            # Resolve output path
            label = labels.get(oid, prefix)
            if by_class:
                sub = os.path.join(out_dir, self._safe(label))
                base = self._safe(label)
            else:
                sub = out_dir
                base = self._safe(prefix)
            try:
                os.makedirs(sub, exist_ok=True)
            except Exception as e:
                print(f'[Export Crops] mkdir failed {sub}: {e}')
                continue

            fname = os.path.join(sub, f'{base}_{ts}_{oid:04d}.{fmt}')
            try:
                cv2.imwrite(fname, crop)
                exported += 1
            except Exception as e:
                print(f'[Export Crops] write failed {fname}: {e}')

        send_notification(f'Export Crops: {exported} saved → {out_dir}',
                          progress=100, level='success', notif_id=notif_id)
        print(f'[Export Crops] {exported} crops → {out_dir}')
        return {'count': float(exported)}
