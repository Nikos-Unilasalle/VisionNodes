"""
Smoke pipeline: GDINO (zero-shot detect) -> SAM2 (box-prompted segment) on a stone wall.
Iterates GDINO params to find the best stone recall, then segments with SAM2.
Not a pytest test — run directly:  python3 tests/smoke_stone_pipeline.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
import importlib.util

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_PATH = os.path.join(ENGINE, '..', 'samples', 'mixed_wall.png')
OUT_DIR = os.path.join(ENGINE, '..', 'graphify-out', 'stone_pipeline')
os.makedirs(OUT_DIR, exist_ok=True)


def load_plugin(name):
    path = os.path.join(ENGINE, 'plugins', f'{name}.py')
    spec = importlib.util.spec_from_file_location(f'plugins.{name}', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f'plugins.{name}'] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    from registry import NODE_CLASS_REGISTRY

    load_plugin('grounding_dino_detector')
    load_plugin('sam_segmenter')

    GDINO = NODE_CLASS_REGISTRY['grounding_dino_detector']
    SAM = NODE_CLASS_REGISTRY['sam_segmenter']

    image = cv2.imread(IMG_PATH)
    assert image is not None, f'cannot read {IMG_PATH}'
    h, w = image.shape[:2]
    print(f'[img] {w}x{h}')

    # Downscale for speed (keep aspect). GDINO/SAM run fine on ~1280px wide.
    target_w = 1408
    if w > target_w:
        scale = target_w / w
        image = cv2.resize(image, (target_w, int(h * scale)), interpolation=cv2.INTER_AREA)
        h, w = image.shape[:2]
        print(f'[img] resized -> {w}x{h}')

    # ── Load GDINO model synchronously ──
    gd = GDINO()
    print(f'[gdino] device={gd.device}  loading model…')
    t0 = time.time()
    gd._load_model_thread('Base')   # synchronous call (not a thread here)
    print(f'[gdino] model ready in {time.time()-t0:.1f}s  ({gd.current_model_name})')

    # ── Iterate GDINO params: prompt + tile + thresholds ──
    # Dark flint nodules score LOW in GDINO → push thresholds way down.
    configs = [
        # label, prompt, tile_idx, box_thr, text_thr, min_area%, max_area%
        ('flint_t3',   'flint.',          2, 0.10, 0.06, 0.02, 6.0),
        ('blackstn_t3','black stone.',    2, 0.10, 0.06, 0.02, 6.0),
        ('rock_t4',    'rock.',           3, 0.09, 0.05, 0.02, 5.0),
        ('darkstn_t4', 'dark round stone.',3, 0.08, 0.05, 0.02, 5.0),
    ]

    results = []
    for (lbl, prompt, tile_idx, box_thr, text_thr, min_a, max_a) in configs:
        params = {
            'detect': True, 'text_prompt': prompt, 'model': 1,
            'tile_mode': tile_idx, 'tile_overlap': 64,
            'box_threshold': box_thr, 'text_threshold': text_thr,
            'nms_threshold': 0.4, 'min_area': min_a, 'max_area': max_a,
            'label_mode': 3, 'max_boxes': 0,
        }
        t0 = time.time()
        out = gd.process({'image': image}, params)
        dt = time.time() - t0
        n = int(out['count'])
        scores = out.get('scores', [])
        mean_s = float(np.mean(scores)) if scores else 0.0
        print(f'[gdino] {lbl:12s} prompt={prompt!r:14s} tile={tile_idx} '
              f'-> {n:3d} boxes  mean_score={mean_s:.3f}  ({dt:.1f}s)')
        cv2.imwrite(os.path.join(OUT_DIR, f'gdino_{lbl}.png'), out['main'])
        results.append((lbl, prompt, params, out, n, mean_s))

    # Pick the flint-targeted config (best precision on the dark nodules).
    # Raw box count over-detects bricks → don't pick by count.
    by_label = {r[0]: r for r in results}
    best = by_label.get('flint_t3') or max(results, key=lambda r: r[4])
    lbl, prompt, gd_params, gd_out, n, mean_s = best
    print(f'\n[pick] GDINO = {lbl!r}  ({n} boxes, prompt={prompt!r})')

    boxes_list = gd_out['boxes_list']
    if not boxes_list:
        print('[abort] no boxes to segment')
        return

    # ── Load SAM model synchronously ──
    sam = SAM()
    print(f'[sam] device={sam.device}  loading model…')
    t0 = time.time()
    sam._load_model_thread('SAM2 Base+')
    print(f'[sam] model ready in {time.time()-t0:.1f}s  ({sam.current_model_name})')

    # ── SAM2 batch-segment all GDINO boxes ──
    sam_params = {
        'segment': True, 'model': 2, 'prompt_mode': 3,   # Base+, Boxes List (all)
        'overlay_opacity': 55, 'multimask': False,
    }
    t0 = time.time()
    sam_out = sam.process({'image': image, 'boxes': boxes_list}, sam_params)
    dt = time.time() - t0
    print(f'[sam] segmented {int(sam_out["count"])} objects in {dt:.1f}s')

    cv2.imwrite(os.path.join(OUT_DIR, 'sam_overlay.png'), sam_out['main'])
    if sam_out.get('mask') is not None:
        cv2.imwrite(os.path.join(OUT_DIR, 'sam_mask.png'), sam_out['mask'])

    areas = sam_out.get('areas', [])
    if areas:
        print(f'[sam] areas px²: min={min(areas):.0f} '
              f'median={np.median(areas):.0f} max={max(areas):.0f}')

    print(f'\n[done] outputs in {OUT_DIR}')
    print(f'  gdino_{lbl}.png  /  sam_overlay.png  /  sam_mask.png')


if __name__ == '__main__':
    main()
