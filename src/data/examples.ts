export const EXAMPLES = [
  {
    name: "OCR Scanner (Tesseract)",
    description: "Détecte les zones de texte, sélectionne la plus grande, la redresse par homographie, lit le texte et l'affiche sur l'image.",
    nodes: [
      { id: "src-1",  type: "input_image",     position: { x: 50,   y: 220 }, data: { label: "book.jpg",              params: { path: "samples/book.jpg" } } },
      { id: "east-1", type: "ocr_east_detect",  position: { x: 340,  y: 220 }, data: { label: "Text Detector (EAST)", params: { min_confidence: 0.3, width: 640, height: 640 } } },
      { id: "py-1",   type: "logic_python",     position: { x: 640,  y: 220 }, data: { label: "Largest Region",       params: { code: "items = a if isinstance(a, list) else []\nif not items:\n    out_dict = {}; out_list = []\nelse:\n    item = max(items, key=lambda x: x.get('width',0)*x.get('height',0))\n    out_dict = item\n    pts = item.get('pts',[])\n    if len(pts) == 4:\n        out_list = pts\n    else:\n        x0=item.get('xmin',0); y0=item.get('ymin',0)\n        x1=x0+item.get('width',1); y1=y0+item.get('height',1)\n        out_list = [[x1,y0],[x0,y0],[x0,y1],[x1,y1]]" } } },
      { id: "warp-1", type: "geom_perspective", position: { x: 960,  y: 60  }, data: { label: "Homography Warp",      params: { width: 500, height: 600 } } },
      { id: "tess-1", type: "ocr_tesseract",    position: { x: 1260, y: 60  }, data: { label: "OCR (Tesseract)",      params: { psm: 1, upscale: 3, padding: 8 } } },
      { id: "draw-1", type: "draw_text",        position: { x: 960,  y: 390 }, data: { label: "Text Overlay",         params: { x: 0.05, y: 0.93, font_scale: 1.2, thickness: 2, r: 255, g: 255, b: 0 } } },
      { id: "disp-1", type: "output_display",   position: { x: 1260, y: 390 }, data: { label: "Display",              params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1",  target: "east-1", sourceHandle: "image__main",     targetHandle: "image__image"   },
      { id: "e2", source: "east-1", target: "py-1",   sourceHandle: "list__text_regions", targetHandle: "any__a"      },
      { id: "e3", source: "src-1",  target: "warp-1", sourceHandle: "image__main",     targetHandle: "image__image"   },
      { id: "e4", source: "py-1",   target: "warp-1", sourceHandle: "list__out_list",  targetHandle: "list__src_pts"  },
      { id: "e5", source: "warp-1", target: "tess-1", sourceHandle: "image__main",     targetHandle: "image__image"   },
      { id: "e6", source: "east-1", target: "draw-1", sourceHandle: "image__main",     targetHandle: "image__image"   },
      { id: "e7", source: "tess-1", target: "draw-1", sourceHandle: "any__text",       targetHandle: "string__text"   },
      { id: "e8", source: "draw-1", target: "disp-1", sourceHandle: "image__main",     targetHandle: "image__main"    }
    ]
  },
  {
    name: "Movement Analysis (MOG2)",
    description: "Détecte les objets en mouvement par soustraction de fond et identifie leurs contours.",
    nodes: [
      { id: "src-1", type: "input_webcam", position: { x: 50, y: 200 }, data: { label: "Webcam", params: { device_index: 0 } } },
      { id: "mog-1", type: "bg_sub_mog2", position: { x: 300, y: 200 }, data: { label: "MOG2 Subtractor", params: { history: 500, threshold: 16 } } },
      { id: "gray-1", type: "filter_gray", position: { x: 300, y: 350 }, data: { label: "Grayscale", params: {} } },
      { id: "cont-1", type: "feat_find_contours", position: { x: 550, y: 200 }, data: { label: "Find Contours", params: {} } },
      { id: "disp-1", type: "output_display", position: { x: 800, y: 200 }, data: { label: "Movement Mask", params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1", target: "mog-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e2", source: "src-1", target: "gray-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e3", source: "mog-1", target: "cont-1", sourceHandle: "mask__mask", targetHandle: "image__main" },
      { id: "e4", source: "mog-1", target: "disp-1", sourceHandle: "mask__mask", targetHandle: "image__main" }
    ]
  },
  {
    name: "Harris Corner Detection",
    description: "Détecte les coins d'une image avec l'opérateur Harris.",
    nodes: [
      { id: "src-1", type: "input_image", position: { x: 50, y: 200 }, data: { label: "Sample Image", params: {} } },
      { id: "harris-1", type: "feat_harris", position: { x: 300, y: 200 }, data: { label: "Harris Corners", params: { threshold: 0.01 } } },
      { id: "disp-1", type: "output_display", position: { x: 600, y: 200 }, data: { label: "Corners Display", params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1", target: "harris-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e2", source: "harris-1", target: "disp-1", sourceHandle: "image__main", targetHandle: "image__main" }
    ]
  },
  {
    name: "Smile Detector",
    description: "Détecte les sourires via MediaPipe (distance coins de bouche), collecte les frames et exporte en CSV.",
    nodes: [
      { id: "node-4", type: "output_display", position: { x: 2636.800262045092, y: 87.36047870117721 }, data: { label: "Display Outlet", params: { color_index: 0 } } },
      { id: "node-1776927198621", type: "input_webcam", position: { x: 35.32945917319175, y: 106.78348756554338 }, data: { label: "Webcam", params: { device_index: 1, color_index: 0 } } },
      { id: "node-1776928209916", type: "analysis_face_mp", position: { x: 288.6877066970555, y: 106.78348756554338 }, data: { label: "Face Tracker", params: { color_index: 1, max_faces: 1 } } },
      { id: "node-1776928276513", type: "geom_track_point", position: { x: 560, y: 80 }, data: { label: "Track Point", params: { point_id: 61, color_index: 1 } } },
      { id: "node-1776928283867-0.6549439590251004", type: "geom_track_point", position: { x: 560, y: 240 }, data: { label: "Track Point", params: { point_id: 306, color_index: 1 } } },
      { id: "node-1776928339261", type: "data_group_dicts", position: { x: 1260, y: 260 }, data: { label: "Group Dicts", params: { color_index: 3 } } },
      { id: "node-1776928389320", type: "data_coord_combine", position: { x: 940, y: 260 }, data: { label: "Coord Combine", params: { color_index: 3 } } },
      { id: "node-1776928402570-0.6024858036260399", type: "data_coord_combine", position: { x: 940, y: 460 }, data: { label: "Coord Combine", params: { color_index: 3 } } },
      { id: "node-1776928521256", type: "tracker_visualize", position: { x: 1600, y: 80 }, data: { label: "Track Visualizer", params: { color_index: 2, show_trail: 0, trail_length: 2, show_id: 0, thickness: 1, fill_alpha: 0, font_scale: 100, show_point: 1, point_radius: 16, point_use_id_color: 1 } } },
      { id: "node-1776928674420", type: "math_distance", position: { x: 1260, y: 460 }, data: { label: "Distance", params: { color_index: 3 } } },
      { id: "node-1776928731663", type: "math_mul", position: { x: 1520, y: 260 }, data: { label: "Multiply", params: { value_b: 100, color_index: 3 } } },
      { id: "node-1776929645929", type: "logic_compare", position: { x: 1800, y: 260 }, data: { label: "Data Compare", params: { op: 2, color_index: 3 } } },
      { id: "node-1776929672831", type: "scalar_input", position: { x: 1520, y: 400 }, data: { label: "Number", params: { value: 10, color_index: 3 } } },
      { id: "node-1776929709350", type: "logic_collect", position: { x: 1800, y: 380 }, data: { label: "Collect", params: { color_index: 3 } } },
      { id: "node-1776929732297-0.7690993319587301", type: "data_inspector", position: { x: 2369.8097905135687, y: 660.3176748542672 }, data: { label: "Inspect Unit", params: { color_index: 4 } } },
      { id: "node-1776929810061", type: "util_csv_export", position: { x: 2640, y: 380 }, data: { label: "CSV Export", params: { path: "exports", filename: "smiles", record: false, color_index: 0 } } },
      { id: "node-1776930227099", type: "geom_cropper", position: { x: 1900, y: 80 }, data: { label: "Auto Cropper", params: { color_index: 2 } } },
      { id: "node-1776930311222", type: "draw_text", position: { x: 2200, y: 80 }, data: { label: "Draw Text", params: { text: "Smiles: {a}", var_count: 1, x: 0.04, y: 0.09, r: 0, g: 0, b: 0, color_index: 2 } } },
      { id: "node-1776931626188", type: "analysis_monitor", position: { x: 2366.9070725106203, y: 347.36198372108913 }, data: { label: "Universal Monitor", params: { color_index: 4 } } },
      { id: "node-1776931649789-0.5893530904765598", type: "analysis_monitor", position: { x: 2366.758602549143, y: 502.7354217759382 }, data: { label: "Universal Monitor", params: { color_index: 4 } } },
      { id: "node-1776931674836-0.31710932674867864", type: "analysis_monitor", position: { x: 2367.280401203558, y: 955.8418795912312 }, data: { label: "Universal Monitor", params: { color_index: 4 } } },
      { id: "node-1776931758362", type: "canvas_reroute", position: { x: 2100, y: 480 }, data: { label: "Reroute", params: {} } },
      { id: "node-1776931809942-0.0658277492703534", type: "canvas_reroute", position: { x: 2040, y: 280 }, data: { label: "Reroute", params: {} } }
    ],
    edges: [
      { id: "e-1776928281719", source: "node-1776928209916", sourceHandle: "dict__face_0", target: "node-1776928276513", targetHandle: "dict__data" },
      { id: "e-1776928288806", source: "node-1776928209916", sourceHandle: "dict__face_0", target: "node-1776928283867-0.6549439590251004", targetHandle: "dict__data" },
      { id: "e-1776928352583", source: "node-1776928339261", sourceHandle: "list__main", target: "node-1776928521256", targetHandle: "list__tracks" },
      { id: "e-1776928395813", source: "node-1776928276513", sourceHandle: "scalar__x", target: "node-1776928389320", targetHandle: "scalar__x" },
      { id: "e-1776928397186", source: "node-1776928276513", sourceHandle: "scalar__y", target: "node-1776928389320", targetHandle: "scalar__y" },
      { id: "e-1776928399316", source: "node-1776928389320", sourceHandle: "dict__dict_out", target: "node-1776928339261", targetHandle: "dict__dict1" },
      { id: "e-1776928406780", source: "node-1776928283867-0.6549439590251004", sourceHandle: "scalar__x", target: "node-1776928402570-0.6024858036260399", targetHandle: "scalar__x" },
      { id: "e-1776928411632", source: "node-1776928402570-0.6024858036260399", sourceHandle: "dict__dict_out", target: "node-1776928339261", targetHandle: "dict__dict2" },
      { id: "e-1776928451660", source: "node-1776928283867-0.6549439590251004", sourceHandle: "scalar__y", target: "node-1776928402570-0.6024858036260399", targetHandle: "scalar__y" },
      { id: "e-1776928547881", source: "node-1776928339261", sourceHandle: "list__main", target: "node-1776928521256", targetHandle: "list__tracks" },
      { id: "e-1776928679933", source: "node-1776928389320", sourceHandle: "dict__dict_out", target: "node-1776928674420", targetHandle: "dict__p1" },
      { id: "e-1776928682394", source: "node-1776928402570-0.6024858036260399", sourceHandle: "dict__dict_out", target: "node-1776928674420", targetHandle: "dict__p2" },
      { id: "e-1776928745440", source: "node-1776928674420", sourceHandle: "scalar__result", target: "node-1776928731663", targetHandle: "scalar__a" },
      { id: "e-1776929660410", source: "node-1776928731663", sourceHandle: "scalar__result", target: "node-1776929645929", targetHandle: "scalar__in_a" },
      { id: "e-1776929681236", source: "node-1776929672831", sourceHandle: "scalar__value", target: "node-1776929645929", targetHandle: "scalar__in_b" },
      { id: "e-1776929726531", source: "node-1776928731663", sourceHandle: "scalar__result", target: "node-1776929709350", targetHandle: "any__value" },
      { id: "e-1776929735704", source: "node-1776929709350", sourceHandle: "list__list", target: "node-1776929732297-0.7690993319587301", targetHandle: "any__data" },
      { id: "e-1776930259920", source: "node-1776928209916", sourceHandle: "image__main", target: "node-1776928521256", targetHandle: "image__image" },
      { id: "e-1776930275166", source: "node-1776928521256", sourceHandle: "image__main", target: "node-1776930227099", targetHandle: "image__image" },
      { id: "e-1776930412056", source: "node-1776930311222", sourceHandle: "image__main", target: "node-4", targetHandle: "image__main" },
      { id: "e-1776930414554", source: "node-1776930227099", sourceHandle: "image__main", target: "node-1776930311222", targetHandle: "image__image" },
      { id: "e-1776931020000", source: "node-1776928209916", sourceHandle: "dict__face_0", target: "node-1776930227099", targetHandle: "any__data" },
      { id: "e-1776931631020", source: "node-1776928731663", sourceHandle: "scalar__result", target: "node-1776931626188", targetHandle: "any__data" },
      { id: "e-1776931776629", source: "node-1776929709350", sourceHandle: "scalar__count", target: "node-1776931758362", targetHandle: "any__in" },
      { id: "e-1776931784323", source: "node-1776931758362", sourceHandle: "any__out", target: "node-1776929810061", targetHandle: "any__val_1" },
      { id: "e-1776931790693", source: "node-1776931758362", sourceHandle: "any__out", target: "node-1776931674836-0.31710932674867864", targetHandle: "any__data" },
      { id: "e-1776931797891", source: "node-1776931758362", sourceHandle: "any__out", target: "node-1776930311222", targetHandle: "scalar__a" },
      { id: "e-1776931834337", source: "node-1776929645929", sourceHandle: "boolean__result", target: "node-1776931809942-0.0658277492703534", targetHandle: "any__in" },
      { id: "e-1776931837035", source: "node-1776931809942-0.0658277492703534", sourceHandle: "any__out", target: "node-1776929709350", targetHandle: "boolean__condition" },
      { id: "e-1776931840002", source: "node-1776931809942-0.0658277492703534", sourceHandle: "any__out", target: "node-1776931649789-0.5893530904765598", targetHandle: "any__data" }
    ],
    ui: { previewSize: { w: 520, h: 501 }, previewPos: { x: 50.66015625, y: -23.50390625 }, activePaletteIndex: 5, visualizedNodeId: "node-4" }
  },
  {
    name: "YOLO Object Detection",
    description: "Détection d'objets sur une image statique avec YOLOv11. Affiche les boîtes englobantes, le compte total et la liste des objets détectés.",
    nodes: [
      { id: "src-1",     type: "input_image",           position: { x: 50,  y: 200 }, data: { label: "Things (things.jpg)", params: { path: "samples/things.jpg" } } },
      { id: "yolo-1",   type: "object_detection_yolo",  position: { x: 300, y: 200 }, data: { label: "YOLO Detector",       params: { confidence: 25, model_size: 0 } } },
      { id: "overlay-1", type: "draw_overlay",           position: { x: 570, y: 200 }, data: { label: "Bounding Boxes",      params: {} } },
      { id: "disp-1",   type: "output_display",         position: { x: 840, y: 200 }, data: { label: "Annotated View",      params: {} } },
      { id: "mon-1",    type: "analysis_monitor",       position: { x: 570, y: 420 }, data: { label: "Object Count",        params: { mode: 7 } } },
      { id: "ins-1",    type: "data_inspector",         position: { x: 840, y: 420 }, data: { label: "Detection List",      params: { filter_key: "label" } } }
    ],
    edges: [
      { id: "e1", source: "src-1",     target: "yolo-1",   sourceHandle: "image__main",        targetHandle: "image__image" },
      { id: "e2", source: "src-1",     target: "overlay-1", sourceHandle: "image__main",       targetHandle: "image__image" },
      { id: "e3", source: "yolo-1",   target: "overlay-1", sourceHandle: "list__objects_list", targetHandle: "any__data" },
      { id: "e4", source: "overlay-1", target: "disp-1",   sourceHandle: "image__main",        targetHandle: "image__main" },
      { id: "e5", source: "yolo-1",   target: "mon-1",     sourceHandle: "list__objects_list", targetHandle: "data__data" },
      { id: "e6", source: "yolo-1",   target: "ins-1",     sourceHandle: "list__objects_list", targetHandle: "any__data" }
    ]
  },
  {
    name: "SORT Multi-Object Tracking",
    description: "Suivi multi-objets en temps réel : YOLO détecte les objets, SORT leur assigne un ID persistant avec Kalman Filter + algorithme hongrois.",
    nodes: [
      { id: "src-1",   type: "input_webcam",         position: { x: 50,   y: 200 }, data: { label: "Webcam",        params: { device_index: 0 } } },
      { id: "yolo-1",  type: "object_detection_yolo", position: { x: 300,  y: 200 }, data: { label: "YOLO Detector", params: { confidence: 30, model_size: 0 } } },
      { id: "sort-1",  type: "tracker_sort",          position: { x: 560,  y: 200 }, data: { label: "SORT Tracker",  params: { max_age: 5, min_hits: 2, iou_threshold: 30 } } },
      { id: "viz-1",   type: "tracker_visualize",     position: { x: 820,  y: 200 }, data: { label: "Track Viz",     params: { show_trail: 1, trail_length: 30, show_id: 1, show_label: 1, thickness: 2 } } },
      { id: "disp-1",  type: "output_display",        position: { x: 1080, y: 200 }, data: { label: "Final Output",  params: {} } },
      { id: "count-1", type: "data_inspector",        position: { x: 560,  y: 380 }, data: { label: "Track Count",   params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1",  target: "yolo-1",  sourceHandle: "image__main",        targetHandle: "image__image" },
      { id: "e2", source: "yolo-1", target: "sort-1",  sourceHandle: "list__objects_list", targetHandle: "list__detections" },
      { id: "e3", source: "src-1",  target: "sort-1",  sourceHandle: "image__main",        targetHandle: "image__image" },
      { id: "e4", source: "sort-1", target: "viz-1",   sourceHandle: "list__tracks",       targetHandle: "list__tracks" },
      { id: "e5", source: "src-1",  target: "viz-1",   sourceHandle: "image__main",        targetHandle: "image__image" },
      { id: "e6", source: "viz-1",  target: "disp-1",  sourceHandle: "image__main",        targetHandle: "image__main" },
      { id: "e7", source: "sort-1", target: "count-1", sourceHandle: "scalar__count",      targetHandle: "any__data" }
    ]
  },
  {
    name: "DeepSORT Multi-Object Tracking",
    description: "Suivi multi-objets avec réidentification visuelle : YOLO + DeepSORT (Kalman + CNN embeddings) pour des IDs plus stables même après occultation.",
    nodes: [
      { id: "src-1",  type: "input_webcam",         position: { x: 50,   y: 200 }, data: { label: "Webcam",         params: { device_index: 0 } } },
      { id: "yolo-1", type: "object_detection_yolo", position: { x: 300,  y: 200 }, data: { label: "YOLO Detector",  params: { confidence: 30, model_size: 0 } } },
      { id: "ds-1",   type: "tracker_deepsort",      position: { x: 560,  y: 200 }, data: { label: "DeepSORT",       params: { max_age: 5, n_init: 2, embedder: 0, max_cosine_dist: 40 } } },
      { id: "viz-1",  type: "tracker_visualize",     position: { x: 820,  y: 200 }, data: { label: "Track Viz",      params: { show_trail: 1, trail_length: 40, show_id: 1, show_label: 1, thickness: 2, fill_alpha: 10 } } },
      { id: "disp-1", type: "output_display",        position: { x: 1080, y: 200 }, data: { label: "Final Output",   params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1",  target: "yolo-1", sourceHandle: "image__main",        targetHandle: "image__image" },
      { id: "e2", source: "yolo-1", target: "ds-1",   sourceHandle: "list__objects_list", targetHandle: "list__detections" },
      { id: "e3", source: "src-1",  target: "ds-1",   sourceHandle: "image__main",        targetHandle: "image__image" },
      { id: "e4", source: "ds-1",   target: "viz-1",  sourceHandle: "list__tracks",       targetHandle: "list__tracks" },
      { id: "e5", source: "src-1",  target: "viz-1",  sourceHandle: "image__main",        targetHandle: "image__image" },
      { id: "e6", source: "viz-1",  target: "disp-1", sourceHandle: "image__main",        targetHandle: "image__main" }
    ]
  },
  {
    name: "Galets Segmenter",
    description: "Segmente chaque galet avec watershed : seuillage Otsu, nettoyage morphologique, transform distance, filtrage des marqueurs par aire et analyse.",
    nodes: [
            {
                  "id": "src-1",
                  "type": "input_image",
                  "position": {
                        "x": -452.6105081459157,
                        "y": 291.31557941262685
                  },
                  "data": {
                        "label": "Billes (billes.jpg)",
                        "params": {
                              "path": "/Users/nikos/Desktop/VNStudio/samples/galets.jpg"
                        }
                  },
                  "width": 208,
                  "height": 211,
                  "selected": false,
                  "positionAbsolute": {
                        "x": -452.6105081459157,
                        "y": 291.31557941262685
                  },
                  "dragging": false
            },
            {
                  "id": "gray-1",
                  "type": "filter_gray",
                  "position": {
                        "x": 326.70004722854065,
                        "y": 374.9314573077128
                  },
                  "data": {
                        "label": "Grayscale",
                        "params": {}
                  },
                  "width": 208,
                  "height": 90,
                  "selected": false,
                  "positionAbsolute": {
                        "x": 326.70004722854065,
                        "y": 374.9314573077128
                  },
                  "dragging": false
            },
            {
                  "id": "thresh-1",
                  "type": "feat_threshold_adv",
                  "position": {
                        "x": 326.4929923659444,
                        "y": 248.93070091814639
                  },
                  "data": {
                        "label": "Otsu (billes = white)",
                        "params": {
                              "mode": 0,
                              "threshold": 95
                        }
                  },
                  "width": 208,
                  "height": 112,
                  "selected": false,
                  "positionAbsolute": {
                        "x": 326.4929923659444,
                        "y": 248.93070091814639
                  },
                  "dragging": false
            },
            {
                  "id": "morph-open-1",
                  "type": "feat_morphology_adv",
                  "position": {
                        "x": 583.6086638923651,
                        "y": 154.53159360564322
                  },
                  "data": {
                        "label": "Opening (Remove Noise)",
                        "params": {
                              "operation": 0,
                              "shape": 2,
                              "size": 9.96,
                              "iterations": 5
                        }
                  },
                  "width": 208,
                  "height": 90,
                  "selected": false,
                  "dragging": false,
                  "positionAbsolute": {
                        "x": 583.6086638923651,
                        "y": 154.53159360564322
                  }
            },
            {
                  "id": "morph-close-1",
                  "type": "feat_morphology_adv",
                  "position": {
                        "x": 583.1039550365978,
                        "y": 257.87617721394184
                  },
                  "data": {
                        "label": "Closing (Fill Holes)",
                        "params": {
                              "operation": 1,
                              "shape": 2,
                              "size": 2,
                              "iterations": 1
                        }
                  },
                  "width": 208,
                  "height": 90,
                  "selected": false,
                  "positionAbsolute": {
                        "x": 583.1039550365978,
                        "y": 257.87617721394184
                  },
                  "dragging": false
            },
            {
                  "id": "dist-1",
                  "type": "feat_distance_transform",
                  "position": {
                        "x": 585.7282002902997,
                        "y": 362.0705749001109
                  },
                  "data": {
                        "label": "Distance Transform",
                        "params": {
                              "dist_type": 2,
                              "mask_size": 0
                        }
                  },
                  "width": 208,
                  "height": 112,
                  "selected": false,
                  "positionAbsolute": {
                        "x": 585.7282002902997,
                        "y": 362.0705749001109
                  },
                  "dragging": false
            },
            {
                  "id": "thresh-dist-1",
                  "type": "feat_threshold_adv",
                  "position": {
                        "x": 585.9105749891987,
                        "y": 492.98035017791653
                  },
                  "data": {
                        "label": "Peak Threshold (70%)",
                        "params": {
                              "mode": 0,
                              "threshold": 53
                        }
                  },
                  "width": 208,
                  "height": 112,
                  "selected": false,
                  "dragging": false,
                  "positionAbsolute": {
                        "x": 585.9105749891987,
                        "y": 492.98035017791653
                  }
            },
            {
                  "id": "markers-1",
                  "type": "feat_connected_components",
                  "position": {
                        "x": 856.0514426467327,
                        "y": 295.4368938524096
                  },
                  "data": {
                        "label": "Seed Markers",
                        "params": {}
                  },
                  "width": 208,
                  "height": 144,
                  "selected": false,
                  "positionAbsolute": {
                        "x": 856.0514426467327,
                        "y": 295.4368938524096
                  },
                  "dragging": false
            },
            {
                  "id": "filter-1",
                  "type": "feat_marker_filter",
                  "position": {
                        "x": 859.5037017930877,
                        "y": 457.3552861793231
                  },
                  "data": {
                        "label": "Filter Small Fragments",
                        "params": {
                              "min_area": 200,
                              "max_area": 500000,
                              "area_unit": 0,
                              "remap_ids": 1
                        }
                  },
                  "width": 208,
                  "height": 144,
                  "selected": false,
                  "positionAbsolute": {
                        "x": 859.5037017930877,
                        "y": 457.3552861793231
                  },
                  "dragging": false
            },
            {
                  "id": "wshed-1",
                  "type": "feat_watershed",
                  "position": {
                        "x": 1235.8796638906722,
                        "y": 276.12875021945774
                  },
                  "data": {
                        "label": "Watershed",
                        "params": {
                              "visualization": 2,
                              "boundary_color": 0,
                              "boundary_thickness": 4,
                              "region_alpha": 0
                        }
                  },
                  "width": 208,
                  "height": 144,
                  "selected": true,
                  "dragging": false,
                  "positionAbsolute": {
                        "x": 1235.8796638906722,
                        "y": 276.12875021945774
                  }
            },
            {
                  "id": "analysis-1",
                  "type": "sci_marker_analysis",
                  "position": {
                        "x": 1236.1317211874689,
                        "y": 436.8537578279668
                  },
                  "data": {
                        "label": "Marker Analysis",
                        "params": {
                              "show_labels": 1,
                              "show_points": 1,
                              "font_scale": 0.8,
                              "thickness": 3,
                              "coord_type": 0
                        }
                  },
                  "width": 208,
                  "height": 144,
                  "selected": false,
                  "positionAbsolute": {
                        "x": 1236.1317211874689,
                        "y": 436.8537578279668
                  },
                  "dragging": false
            },
            {
                  "id": "count-ins-1",
                  "type": "data_inspector",
                  "position": {
                        "x": 1526.5686783462374,
                        "y": 599.7631963728302
                  },
                  "data": {
                        "label": "Marble Count",
                        "params": {}
                  },
                  "width": 202,
                  "height": 120,
                  "selected": false,
                  "positionAbsolute": {
                        "x": 1526.5686783462374,
                        "y": 599.7631963728302
                  },
                  "dragging": false,
                  "style": {
                        "width": 202,
                        "height": 120
                  },
                  "resizing": false
            },
            {
                  "id": "disp-1",
                  "type": "output_display",
                  "position": {
                        "x": 1511.167720522356,
                        "y": 250.88772223436183
                  },
                  "data": {
                        "label": "Segmentation View",
                        "params": {}
                  },
                  "width": 208,
                  "height": 144,
                  "selected": false,
                  "positionAbsolute": {
                        "x": 1511.167720522356,
                        "y": 250.88772223436183
                  },
                  "dragging": false
            },
            {
                  "id": "disp-2",
                  "type": "output_display",
                  "position": {
                        "x": 1520,
                        "y": 430
                  },
                  "data": {
                        "label": "Marble Analysis View",
                        "params": {}
                  },
                  "width": 208,
                  "height": 144
            },
            {
                  "id": "node-1776885243551",
                  "type": "util_roi_polygon",
                  "position": {
                        "x": -209.76359724519807,
                        "y": 274.56334133785657
                  },
                  "style": {},
                  "data": {
                        "label": "ROI Polygon",
                        "params": {
                              "points": "[{\"x\":0.045012165450121655,\"y\":0.0027624309392265192},{\"x\":0.049878345498783457,\"y\":0.988950276243094},{\"x\":0.9476885644768857,\"y\":0.988950276243094},{\"x\":0.9452554744525548,\"y\":0}]"
                        }
                  },
                  "width": 208,
                  "height": 242,
                  "selected": false,
                  "positionAbsolute": {
                        "x": -209.76359724519807,
                        "y": 274.56334133785657
                  },
                  "dragging": false
            },
            {
                  "id": "node-1776885277292",
                  "type": "geom_perspective",
                  "position": {
                        "x": 42.03643134904132,
                        "y": 299.6783473526284
                  },
                  "style": {},
                  "data": {
                        "label": "Perspective Warp",
                        "params": {}
                  },
                  "width": 208,
                  "height": 112,
                  "selected": false,
                  "positionAbsolute": {
                        "x": 42.03643134904132,
                        "y": 299.6783473526284
                  },
                  "dragging": false
            }
      ],
    edges: [
            {
                  "id": "e2",
                  "source": "gray-1",
                  "target": "thresh-1",
                  "sourceHandle": "image__main",
                  "targetHandle": "image__image"
            },
            {
                  "id": "e3",
                  "source": "thresh-1",
                  "target": "morph-open-1",
                  "sourceHandle": "mask__mask",
                  "targetHandle": "any__mask"
            },
            {
                  "id": "e4",
                  "source": "morph-open-1",
                  "target": "morph-close-1",
                  "sourceHandle": "mask__mask",
                  "targetHandle": "any__mask"
            },
            {
                  "id": "e5",
                  "source": "morph-close-1",
                  "target": "dist-1",
                  "sourceHandle": "mask__mask",
                  "targetHandle": "any__mask"
            },
            {
                  "id": "e8",
                  "source": "markers-1",
                  "target": "filter-1",
                  "sourceHandle": "any__markers",
                  "targetHandle": "any__markers",
                  "selected": false
            },
            {
                  "id": "e10",
                  "source": "filter-1",
                  "target": "wshed-1",
                  "sourceHandle": "any__markers_out",
                  "targetHandle": "any__markers",
                  "selected": false
            },
            {
                  "id": "e11",
                  "source": "wshed-1",
                  "target": "disp-1",
                  "sourceHandle": "image__main",
                  "targetHandle": "image__main"
            },
            {
                  "id": "e12",
                  "source": "wshed-1",
                  "target": "analysis-1",
                  "sourceHandle": "any__markers_out",
                  "targetHandle": "any__markers"
            },
            {
                  "id": "e14",
                  "source": "analysis-1",
                  "target": "disp-2",
                  "sourceHandle": "image__main",
                  "targetHandle": "image__main"
            },
            {
                  "id": "e-1776884759002-1",
                  "source": "wshed-1",
                  "target": "analysis-1",
                  "sourceHandle": "scalar__count",
                  "targetHandle": "main"
            },
            {
                  "id": "e-1776884759002-2",
                  "source": "analysis-1",
                  "target": "count-ins-1",
                  "sourceHandle": "main",
                  "targetHandle": "any__data"
            },
            {
                  "source": "dist-1",
                  "sourceHandle": "image__main",
                  "target": "thresh-dist-1",
                  "targetHandle": "image__image",
                  "id": "e-1776884794323"
            },
            {
                  "source": "thresh-dist-1",
                  "sourceHandle": "mask__mask",
                  "target": "markers-1",
                  "targetHandle": "any__mask",
                  "id": "e-1776884799928",
                  "selected": false
            },
            {
                  "source": "src-1",
                  "sourceHandle": "image__main",
                  "target": "node-1776885243551",
                  "targetHandle": "image__image",
                  "id": "e-1776885250809"
            },
            {
                  "source": "node-1776885243551",
                  "sourceHandle": "list__pts",
                  "target": "node-1776885277292",
                  "targetHandle": "list__src_pts",
                  "id": "e-1776885282244"
            },
            {
                  "source": "node-1776885243551",
                  "sourceHandle": "image__main",
                  "target": "node-1776885277292",
                  "targetHandle": "image__image",
                  "id": "e-1776885283524"
            },
            {
                  "source": "node-1776885277292",
                  "sourceHandle": "image__main",
                  "target": "gray-1",
                  "targetHandle": "image__image",
                  "id": "e-1776885285762"
            },
            {
                  "source": "wshed-1",
                  "sourceHandle": "image__main",
                  "target": "analysis-1",
                  "targetHandle": "image__image",
                  "id": "e-1776885477693"
            },
            {
                  "source": "analysis-1",
                  "sourceHandle": "scalar__count",
                  "target": "count-ins-1",
                  "targetHandle": "any__data",
                  "id": "e-1776885491418"
            },
            {
                  "id": "e-1776885831315-1",
                  "source": "thresh-1",
                  "target": "morph-close-1",
                  "sourceHandle": "main",
                  "targetHandle": "main"
            },
            {
                  "source": "node-1776885277292",
                  "sourceHandle": "image__main",
                  "target": "wshed-1",
                  "targetHandle": "image__image",
                  "id": "e-1776886059893"
            }
      ]
  },
  {
    name: "Interactive Magic Painter",
    description: "Dessine à l'écran avec les landmarks de la main (Hand Tracker).",
    nodes: [
      { id: "src-1", type: "input_webcam", position: { x: 50, y: 150 }, data: { label: "Webcam", params: {} } },
      { id: "hand-1", type: "analysis_hand_mp", position: { x: 250, y: 150 }, data: { label: "Hand Tracker", params: { max_hands: 1 } } },
      { id: "sel-1", type: "data_list_selector", position: { x: 450, y: 150 }, data: { label: "Tip of Index", params: { index: 8 } } },
      { id: "point-1", type: "draw_point", position: { x: 650, y: 150 }, data: { label: "Finger Point", params: { r: 0, g: 255, b: 255, thickness: 10 } } },
      { id: "overlay-1", type: "draw_overlay", position: { x: 850, y: 150 }, data: { label: "Draw Layer", params: {} } },
      { id: "disp-1", type: "output_display", position: { x: 1050, y: 150 }, data: { label: "Canvas View", params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1", target: "hand-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e2", source: "src-1", target: "overlay-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e3", source: "hand-1", target: "sel-1", sourceHandle: "data__hand_0", targetHandle: "list__list_in" },
      { id: "e4", source: "sel-1", target: "point-1", sourceHandle: "any__item_out", targetHandle: "scalar__x" },
      { id: "e5", source: "point-1", target: "overlay-1", sourceHandle: "dict__draw", targetHandle: "any__data" },
      { id: "e6", source: "overlay-1", target: "disp-1", sourceHandle: "image__main", targetHandle: "image__main" }
    ]
  },
  {
    name: "Ghost Motion Trail",
    description: "Crée un trail artistique en mélangeant le fond en mouvement dans le temps.",
    nodes: [
      { id: "src-1", type: "input_webcam", position: { x: 50, y: 150 }, data: { label: "Webcam", params: {} } },
      { id: "mog-1", type: "bg_sub_mog2", position: { x: 250, y: 150 }, data: { label: "Movement Mask", params: { history: 100 } } },
      { id: "blend-1", type: "plugin_blend_images", position: { x: 500, y: 150 }, data: { label: "Ghost Blend", params: { opacity: 0.3 } } },
      { id: "disp-1", type: "output_display", position: { x: 750, y: 150 }, data: { label: "Trail View", params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1", target: "mog-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e2", source: "src-1", target: "blend-1", sourceHandle: "image__main", targetHandle: "image__image_a" },
      { id: "e3", source: "mog-1", target: "blend-1", sourceHandle: "mask__mask", targetHandle: "image__image_b" },
      { id: "e4", source: "blend-1", target: "disp-1", sourceHandle: "image__main", targetHandle: "image__main" }
    ]
  },
  {
    name: "Feature Matching (ORB)",
    description: "Compare deux images et trouve des similitudes avec les keypoints ORB et un matcher Brute-Force.",
    nodes: [
      { id: "src-1", type: "input_image", position: { x: 50, y: 50 }, data: { label: "Template Image", params: {} } },
      { id: "src-2", type: "input_image", position: { x: 50, y: 300 }, data: { label: "Scene Image", params: {} } },
      { id: "orb-1", type: "feat_orb", position: { x: 300, y: 50 }, data: { label: "ORB A", params: { n_features: 500 } } },
      { id: "orb-2", type: "feat_orb", position: { x: 300, y: 300 }, data: { label: "ORB B", params: { n_features: 500 } } },
      { id: "match-1", type: "feat_matcher", position: { x: 550, y: 175 }, data: { label: "Feature Matcher", params: { method: 0, norm: 1, max_matches: 50 } } },
      { id: "disp-1", type: "output_display", position: { x: 850, y: 175 }, data: { label: "Matches View", params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1", target: "orb-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e2", source: "src-2", target: "orb-2", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e3", source: "orb-1", target: "match-1", sourceHandle: "any__descriptors", targetHandle: "any__des1" },
      { id: "e4", source: "orb-2", target: "match-1", sourceHandle: "any__descriptors", targetHandle: "any__des2" },
      { id: "e5", source: "orb-1", target: "match-1", sourceHandle: "list__keypoints", targetHandle: "list__kp1" },
      { id: "e6", source: "orb-2", target: "match-1", sourceHandle: "list__keypoints", targetHandle: "list__kp2" },
      { id: "e7", source: "src-1", target: "match-1", sourceHandle: "image__main", targetHandle: "image__img1" },
      { id: "e8", source: "src-2", target: "match-1", sourceHandle: "image__main", targetHandle: "image__img2" },
      { id: "e9", source: "match-1", target: "disp-1", sourceHandle: "image__main", targetHandle: "image__main" }
    ]
  },
  {
    name: "Warp Affine: Animated Transform",
    description: "Un Python Node calcule une matrice affine 2x3 animée (rotation + zoom oscillant). Warp Affine l'applique. Compose compare original et résultat côte à côte.",
    nodes: [
      { id: "src-1",     type: "input_image",     position: { x: 50,  y: 200 }, data: { label: "Portrait (portrait.jpeg)", params: { path: "samples/portrait.jpeg" } } },
      { id: "py-1",      type: "logic_python",    position: { x: 280, y: 360 }, data: { label: "Affine Matrix",   params: { code: "# Rotation + zoom oscillant\nif 'f' not in state: state['f'] = 0\nstate['f'] += 1\n\nangle = state['f'] * 0.8\nscale = 1.0 + 0.2 * np.sin(state['f'] * 0.04)\n\nif a is not None and isinstance(a, np.ndarray):\n    h, w = a.shape[:2]\n    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)\n    out_any = M.tolist()" } } },
      { id: "warp-1",    type: "geom_warp_affine", position: { x: 540, y: 200 }, data: { label: "Warp Affine",    params: {} } },
      { id: "compose-1", type: "util_compose",    position: { x: 770, y: 200 }, data: { label: "Checkerboard",   params: { mode: 6, split_pos: 10 } } },
      { id: "disp-1",    type: "output_display",  position: { x: 1010, y: 200 }, data: { label: "Final Output",  params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1",     target: "py-1",      sourceHandle: "image__main",    targetHandle: "any__a" },
      { id: "e2", source: "py-1",      target: "warp-1",    sourceHandle: "any__out_any",   targetHandle: "any__matrix" },
      { id: "e3", source: "src-1",     target: "warp-1",    sourceHandle: "image__main",    targetHandle: "image__image" },
      { id: "e4", source: "src-1",     target: "compose-1", sourceHandle: "image__main",    targetHandle: "image__image_a" },
      { id: "e5", source: "warp-1",    target: "compose-1", sourceHandle: "image__main",    targetHandle: "image__image_b" },
      { id: "e6", source: "compose-1", target: "disp-1",    sourceHandle: "image__main",    targetHandle: "image__main" }
    ]
  },
  {
    name: "Python: Image Stats",
    description: "Script Python personnalisé pour inverser l'image et calculer sa luminosité moyenne.",
    nodes: [
      { id: "src-1", type: "input_webcam", position: { x: 50, y: 150 }, data: { label: "Webcam", params: {} } },
      { id: "py-1", type: "logic_python", position: { x: 300, y: 150 }, data: { 
          label: "Custom Script", 
          params: { 
            code: "# Invert image and get mean\nout_main = 255 - a if a is not None else None\nif a is not None:\n    out_scalar = float(np.mean(a))\n    out_any = f'Avg Brightness: {out_scalar:.1f}'" 
          } 
      }},
      { id: "disp-1", type: "output_display", position: { x: 550, y: 150 }, data: { label: "Inverted View", params: {} } },
      { id: "ins-1", type: "data_inspector", position: { x: 550, y: 350 }, data: { label: "Stats View", params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1", target: "py-1", sourceHandle: "image__main", targetHandle: "any__a" },
      { id: "e2", source: "py-1", target: "disp-1", sourceHandle: "image__main", targetHandle: "image__main" },
      { id: "e3", source: "py-1", target: "ins-1", sourceHandle: "any__out_any", targetHandle: "any__data" }
    ]
  },
  {
    name: "Sprint Race Tracker",
    description: "Détecte et suit chaque coureur avec SORT sur une vidéo de sprint. Chaque athlète reçoit un ID unique persistant. Compte cumulatif des IDs vus affiché en temps réel.",
    nodes: [
      { id: "src-1",    type: "input_movie",           position: { x: 50,   y: 250 }, data: { label: "Movie File",        params: { path: "samples/sprint.mp4" } } },
      { id: "yolo-1",   type: "object_detection_yolo", position: { x: 300,  y: 250 }, data: { label: "YOLO Detector",     params: { confidence: 35, model_size: 0 } } },
      { id: "filter-1", type: "util_filter_label",     position: { x: 560,  y: 50  }, data: { label: "Label Filter",      params: { query: "person" } } },
      { id: "sort-1",   type: "tracker_sort",          position: { x: 820,  y: 250 }, data: { label: "SORT Tracker",      params: { max_age: 8, min_hits: 2, iou_threshold: 25 } } },
      { id: "py-1",     type: "logic_python",          position: { x: 960,  y: 460 }, data: {
          label: "Python Script",
          params: {
            code: "# Compte les IDs uniques vus depuis le lancement\n# 'a' = liste des tracks actifs | 'b' = count actuel\nif 'seen_ids' not in state:\n    state['seen_ids'] = set()\n\nif isinstance(a, list):\n    for t in a:\n        if isinstance(t, dict) and 'track_id' in t:\n            state['seen_ids'].add(t['track_id'])\n\nactive = int(b) if b is not None else 0\ntotal  = len(state['seen_ids'])\n\nout_scalar = float(total)\nout_any    = f'Active: {active}  |  Total seen: {total}'"
          }
      }},
      { id: "viz-1",    type: "tracker_visualize",     position: { x: 1080, y: 50  }, data: { label: "Track Visualizer", params: { show_trail: 1, trail_length: 25, show_id: 1, show_label: 1, thickness: 2, fill_alpha: 15 } } },
      { id: "disp-1",   type: "output_display",        position: { x: 1340, y: 50  }, data: { label: "Final Out",        params: {} } },
      { id: "mon-1",    type: "analysis_monitor",      position: { x: 1340, y: 280 }, data: { label: "Universal Monitor", params: { mode: 7 } } },
      { id: "ins-1",    type: "data_inspector",        position: { x: 1080, y: 460 }, data: { label: "Inspector",        params: {} } }
    ],
    edges: [
      { id: "e1",  source: "src-1",    target: "yolo-1",   sourceHandle: "image__main",        targetHandle: "image__image" },
      { id: "e2",  source: "yolo-1",   target: "filter-1", sourceHandle: "list__objects_list", targetHandle: "list__list_in" },
      { id: "e3",  source: "filter-1", target: "sort-1",   sourceHandle: "list__list_out",     targetHandle: "list__detections" },
      { id: "e4",  source: "src-1",    target: "sort-1",   sourceHandle: "image__main",        targetHandle: "image__image" },
      { id: "e5",  source: "sort-1",   target: "viz-1",    sourceHandle: "list__tracks",       targetHandle: "list__tracks" },
      { id: "e6",  source: "sort-1",   target: "viz-1",    sourceHandle: "image__main",        targetHandle: "image__image" },
      { id: "e7",  source: "viz-1",    target: "disp-1",   sourceHandle: "image__main",        targetHandle: "image__main" },
      { id: "e8",  source: "sort-1",   target: "py-1",     sourceHandle: "list__tracks",       targetHandle: "any__a" },
      { id: "e9",  source: "sort-1",   target: "py-1",     sourceHandle: "scalar__count",      targetHandle: "any__b" },
      { id: "e10", source: "py-1",     target: "ins-1",    sourceHandle: "any__out_any",       targetHandle: "any__data" },
      { id: "e11", source: "filter-1", target: "mon-1",    sourceHandle: "list__list_out",     targetHandle: "data__data" }
    ]
  },
  {
    name: "EVM Pulse Detector (Wu et al. 2012)",
    description: "Eulerian Video Magnification — détecte le pouls par amplification des variations de couleur (Cr/Cb) du visage. Paramètres conformes au papier original : alpha=120, bande 0.83–1.0 Hz (50–60 BPM). Le Plotter affiche la forme d'onde Cr en temps réel (oscillations = battements cardiaques).",
     nodes: [
      {
            "id": "src-1",
            "type": "input_movie",
            "position": {
                  "x": 50,
                  "y": 220
            },
            "data": {
                  "label": "Face Video",
                  "params": {
                        "path": "/Users/nikos/Desktop/VNStudio/samples/face.mp4",
                        "playing": true
                  }
            },
            "width": 208,
            "height": 377,
            "selected": false
      },
      {
            "id": "evm-1",
            "type": "plugin_evm_color",
            "position": {
                  "x": 310,
                  "y": 220
            },
            "data": {
                  "label": "EVM Color",
                  "params": {
                        "alpha": 200,
                        "low_cutoff": 830,
                        "high_cutoff": 1000,
                        "fps": 30,
                        "levels": 2,
                        "attenuation": 10
                  }
            },
            "width": 208,
            "height": 176,
            "selected": false
      },
      {
            "id": "disp-1",
            "type": "output_display",
            "position": {
                  "x": 580,
                  "y": 220
            },
            "data": {
                  "label": "Amplified View",
                  "params": {}
            },
            "width": 208,
            "height": 144,
            "selected": false
      },
      {
            "id": "mon-1",
            "type": "analysis_monitor",
            "position": {
                  "x": 310,
                  "y": 440
            },
            "data": {
                  "label": "Pulse Signal",
                  "params": {
                        "mode": 8,
                        "scale": 1,
                        "precision": 4
                  }
            },
            "width": 208,
            "height": 144,
            "selected": false
      },
      {
            "id": "plot-1",
            "type": "sci_plotter",
            "position": {
                  "x": 579.9489637558381,
                  "y": 608.7041208659688
            },
            "data": {
                  "label": "Cr Waveform",
                  "params": {
                        "buffer_size": 150,
                        "min_y": 30,
                        "max_y": 0
                  }
            },
            "width": 208,
            "height": 136,
            "selected": false,
            "positionAbsolute": {
                  "x": 579.9489637558381,
                  "y": 608.7041208659688
            },
            "dragging": false
      },
      {
            "id": "disp-2",
            "type": "output_display",
            "position": {
                  "x": 580,
                  "y": 440
            },
            "data": {
                  "label": "Color Delta Vis",
                  "params": {}
            },
            "width": 208,
            "height": 144,
            "selected": false
      },
      {
            "id": "node-1776920734460",
            "type": "plugin_filter_kalman",
            "position": {
                  "x": 310.4969130079495,
                  "y": 611.1532137526636
            },
            "style": {},
            "data": {
                  "label": "Kalman Filter",
                  "params": {},
                  "schema": {
                        "type": "plugin_filter_kalman",
                        "label": "Kalman Filter",
                        "category": "analysis",
                        "icon": "Activity",
                        "description": "1D Kalman filter. Q = process noise (dynamics), R = measurement noise.",
                        "inputs": [
                              {
                                    "id": "value",
                                    "color": "scalar"
                              }
                        ],
                        "outputs": [
                              {
                                    "id": "filtered",
                                    "color": "scalar"
                              },
                              {
                                    "id": "raw",
                                    "color": "scalar"
                              }
                        ],
                        "params": [
                              {
                                    "id": "q",
                                    "min": 0,
                                    "max": 100,
                                    "step": 1,
                                    "default": 1
                              },
                              {
                                    "id": "r",
                                    "min": 1,
                                    "max": 1000,
                                    "step": 1,
                                    "default": 100
                              }
                        ]
                  }
            },
            "width": 208,
            "height": 112,
            "selected": false,
            "positionAbsolute": {
                  "x": 310.4969130079495,
                  "y": 611.1532137526636
            },
            "dragging": false
      },
      {
            "id": "node-1776920751445-0.9541665721493834",
            "type": "sci_plotter",
            "position": {
                  "x": 577.5483179746593,
                  "y": 767.1957483532086
            },
            "data": {
                  "label": "Cr Waveform",
                  "params": {
                        "buffer_size": 150,
                        "min_y": 30,
                        "max_y": 0
                  }
            },
            "width": 208,
            "height": 136,
            "selected": true,
            "positionAbsolute": {
                  "x": 577.5483179746593,
                  "y": 767.1957483532086
            },
            "dragging": false
      }
],
      edges: [
      {
            "id": "e1",
            "source": "src-1",
            "target": "evm-1",
            "sourceHandle": "image__main",
            "targetHandle": "image__image"
      },
      {
            "id": "e2",
            "source": "evm-1",
            "target": "disp-1",
            "sourceHandle": "image__main",
            "targetHandle": "image__main"
      },
      {
            "id": "e3",
            "source": "evm-1",
            "target": "mon-1",
            "sourceHandle": "scalar__signal",
            "targetHandle": "any__data"
      },
      {
            "id": "e5",
            "source": "evm-1",
            "target": "disp-2",
            "sourceHandle": "image__filtered_vis",
            "targetHandle": "image__main"
      },
      {
            "source": "evm-1",
            "sourceHandle": "scalar__signal",
            "target": "node-1776920734460",
            "targetHandle": "scalar__value",
            "id": "e-1776920747911"
      },
      {
            "source": "node-1776920734460",
            "sourceHandle": "scalar__filtered",
            "target": "plot-1",
            "targetHandle": "scalar__value",
            "id": "e-1776920749652"
      },
      {
            "source": "node-1776920734460",
            "sourceHandle": "scalar__raw",
            "target": "node-1776920751445-0.9541665721493834",
            "targetHandle": "scalar__value",
            "id": "e-1776920754396"
      }
]
    }
];
