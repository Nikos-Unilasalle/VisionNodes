export const EXAMPLES = [
  {
    name: "OCR Scanner (Tesseract)",
    description: "Détecte des zones de texte avec EAST et les lit avec Tesseract.",
    nodes: [
      { id: "src-1", type: "input_image", position: { x: 50, y: 200 }, data: { label: "Sample Image", params: {} } },
      { id: "east-1", type: "ocr_east_detect", position: { x: 300, y: 200 }, data: { label: "Text Detector (EAST)", params: { min_confidence: 0.5 } } },
      { id: "selector-1", type: "data_list_selector", position: { x: 550, y: 200 }, data: { label: "Select First Region", params: { index: 0 } } },
      { id: "tess-1", type: "ocr_tesseract", position: { x: 800, y: 200 }, data: { label: "OCR (Tesseract)", params: { lang: 0 } } },
      { id: "ins-1", type: "data_inspector", position: { x: 1050, y: 200 }, data: { label: "Text Inspector", params: {} } },
      { id: "disp-1", type: "output_display", position: { x: 800, y: 400 }, data: { label: "Final Display", params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1", target: "east-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e2", source: "east-1", target: "selector-1", sourceHandle: "list__text_regions", targetHandle: "list__list_in" },
      { id: "e3", source: "src-1", target: "tess-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e4", source: "selector-1", target: "tess-1", sourceHandle: "dict__item_out", targetHandle: "dict__box" },
      { id: "e5", source: "tess-1", target: "ins-1", sourceHandle: "any__text", targetHandle: "any__data" },
      { id: "e6", source: "east-1", target: "disp-1", sourceHandle: "image__main", targetHandle: "image__main" }
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
    name: "Body Pose Tracking",
    description: "Estimation de pose humaine en temps réel avec MediaPipe.",
    nodes: [
      { id: "src-1", type: "input_webcam", position: { x: 50, y: 150 }, data: { label: "Webcam", params: {} } },
      { id: "pose-1", type: "analysis_pose_mp", position: { x: 300, y: 150 }, data: { label: "Pose Tracker", params: { model_complexity: 1 } } },
      { id: "disp-1", type: "output_display", position: { x: 550, y: 150 }, data: { label: "Pose View", params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1", target: "pose-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e2", source: "pose-1", target: "disp-1", sourceHandle: "image__main", targetHandle: "image__main" }
    ]
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
    name: "Stone Wall Segmenter",
    description: "Segmente chaque pierre d'un mur avec watershed : seuillage Otsu inversé, nettoyage morphologique, transform distance, filtrage des marqueurs par aire et analyse.",
    nodes: [
      { id: "src-1",         type: "input_image",              position: { x: 50,   y: 200 }, data: { label: "Stone Wall (stonewall.png)", params: { path: "samples/stonewall.png" } } },
      { id: "gray-1",        type: "filter_gray",               position: { x: 260,  y: 200 }, data: { label: "Grayscale",                  params: {} } },
      { id: "thresh-1",      type: "feat_threshold_adv",        position: { x: 470,  y: 200 }, data: { label: "Otsu Inv (stones = white)",  params: { mode: 3 } } },
      { id: "morph-open-1",  type: "feat_morphology_adv",       position: { x: 680,  y: 200 }, data: { label: "Opening (Remove Noise)",     params: { operation: 0, shape: 2, size: 5 } } },
      { id: "morph-close-1", type: "feat_morphology_adv",       position: { x: 890,  y: 200 }, data: { label: "Closing (Fill Stone Holes)", params: { operation: 1, shape: 2, size: 15 } } },
      { id: "dist-1",        type: "feat_distance_transform",   position: { x: 470,  y: 430 }, data: { label: "Distance Transform",         params: { dist_type: 0, mask_size: 1 } } },
      { id: "thresh-dist-1", type: "feat_threshold_adv",        position: { x: 680,  y: 430 }, data: { label: "Peak Threshold (70%)",       params: { mode: 4 } } },
      { id: "markers-1",     type: "feat_connected_components", position: { x: 890,  y: 430 }, data: { label: "Seed Markers",               params: {} } },
      { id: "filter-1",      type: "feat_marker_filter",        position: { x: 1100, y: 430 }, data: { label: "Filter Small Fragments",     params: { min_area: 800, max_area: 500000, area_unit: 0, remap_ids: 1 } } },
      { id: "wshed-1",       type: "feat_watershed",            position: { x: 1100, y: 200 }, data: { label: "Watershed",                  params: { visualization: 2, boundary_color: 1, boundary_thickness: 2, region_alpha: 0.5 } } },
      { id: "analysis-1",    type: "sci_marker_analysis",       position: { x: 1310, y: 430 }, data: { label: "Stone Analysis",             params: { show_labels: 1, show_points: 1, font_scale: 0.8, thickness: 2, coord_type: 0 } } },
      { id: "count-ins-1",   type: "data_inspector",            position: { x: 1310, y: 640 }, data: { label: "Stone Count",                params: {} } },
      { id: "disp-1",        type: "output_display",            position: { x: 1310, y: 200 }, data: { label: "Segmentation View",          params: {} } },
      { id: "disp-2",        type: "output_display",            position: { x: 1520, y: 430 }, data: { label: "Stone Analysis View",        params: {} } }
    ],
    edges: [
      { id: "e1",  source: "src-1",         target: "gray-1",        sourceHandle: "image__main",      targetHandle: "image__image" },
      { id: "e2",  source: "gray-1",        target: "thresh-1",      sourceHandle: "image__main",      targetHandle: "image__image" },
      { id: "e3",  source: "thresh-1",      target: "morph-open-1",  sourceHandle: "mask__mask",       targetHandle: "any__mask" },
      { id: "e4",  source: "morph-open-1",  target: "morph-close-1", sourceHandle: "mask__mask",       targetHandle: "any__mask" },
      { id: "e5",  source: "morph-close-1", target: "dist-1",        sourceHandle: "mask__mask",       targetHandle: "any__mask" },
      { id: "e6",  source: "dist-1",        target: "thresh-dist-1", sourceHandle: "image__main",      targetHandle: "image__image" },
      { id: "e7",  source: "thresh-dist-1", target: "markers-1",     sourceHandle: "mask__mask",       targetHandle: "any__mask" },
      { id: "e8",  source: "markers-1",     target: "filter-1",      sourceHandle: "any__markers",     targetHandle: "any__markers" },
      { id: "e9",  source: "src-1",         target: "wshed-1",       sourceHandle: "image__main",      targetHandle: "image__image" },
      { id: "e10", source: "filter-1",      target: "wshed-1",       sourceHandle: "any__markers_out", targetHandle: "any__markers" },
      { id: "e11", source: "wshed-1",       target: "disp-1",        sourceHandle: "image__main",      targetHandle: "image__main" },
      { id: "e12", source: "wshed-1",       target: "analysis-1",    sourceHandle: "any__markers_out", targetHandle: "any__markers" },
      { id: "e13", source: "src-1",         target: "analysis-1",    sourceHandle: "image__main",      targetHandle: "image__image" },
      { id: "e14", source: "analysis-1",    target: "disp-2",        sourceHandle: "image__main",      targetHandle: "image__main" },
      { id: "e15", source: "wshed-1",       target: "count-ins-1",   sourceHandle: "scalar__count",    targetHandle: "any__data" }
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
  }
];

