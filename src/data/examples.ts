export const EXAMPLES = [
  {
    name: "OCR Scanner (Tesseract)",
    description: "Detects text regions with EAST and reads them with Tesseract.",
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
    description: "Detects moving objects using background subtraction and identifies their contours.",
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
    description: "Detects corners in an image using the Harris operator.",
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
    description: "Real-time human pose estimation using MediaPipe.",
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
    description: "Detected objects with YOLOv8 and dynamic overlays.",
    nodes: [
      { id: "src-1", type: "input_webcam", position: { x: 50, y: 150 }, data: { label: "Webcam", params: {} } },
      { id: "yolo-1", type: "object_detection_yolo", position: { x: 300, y: 150 }, data: { label: "YOLOv8", params: { confidence: 0.25 } } },
      { id: "overlay-1", type: "draw_overlay", position: { x: 550, y: 150 }, data: { label: "Visual Overlay", params: {} } },
      { id: "disp-1", type: "output_display", position: { x: 800, y: 150 }, data: { label: "Final Out", params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1", target: "yolo-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e2", source: "src-1", target: "overlay-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e3", source: "yolo-1", target: "overlay-1", sourceHandle: "list__detections", targetHandle: "any__data" },
      { id: "e4", source: "overlay-1", target: "disp-1", sourceHandle: "image__main", targetHandle: "image__main" }
    ]
  },
  {
    name: "Scientific Cell Segmenter",
    description: "Multi-stage watershed segmentation for separating touching objects.",
    nodes: [
      { id: "src-1", type: "input_image", position: { x: 50, y: 150 }, data: { label: "Cells Image", params: {} } },
      { id: "gray-1", type: "filter_gray", position: { x: 250, y: 150 }, data: { label: "Grayscale", params: {} } },
      { id: "thresh-1", type: "feat_threshold_adv", position: { x: 450, y: 150 }, data: { label: "Otsu Threshold", params: { mode: 2 } } },
      { id: "morph-1", type: "feat_morphology_adv", position: { x: 650, y: 150 }, data: { label: "Cleaning (Closing)", params: { operation: 1, size: 5 } } },
      { id: "dist-1", type: "feat_distance_transform", position: { x: 250, y: 350 }, data: { label: "Distance Map", params: {} } },
      { id: "markers-1", type: "feat_connected_components", position: { x: 450, y: 350 }, data: { label: "Markers", params: {} } },
      { id: "wshed-1", type: "feat_watershed", position: { x: 650, y: 350 }, data: { label: "Watershed", params: {} } },
      { id: "disp-1", type: "output_display", position: { x: 850, y: 250 }, data: { label: "Final Segmentation", params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1", target: "gray-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e2", source: "gray-1", target: "thresh-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e3", source: "thresh-1", target: "morph-1", sourceHandle: "mask__mask", targetHandle: "any__mask" },
      { id: "e4", source: "morph-1", target: "dist-1", sourceHandle: "mask__mask", targetHandle: "any__mask" },
      { id: "e5", source: "dist-1", target: "markers-1", sourceHandle: "main__main", targetHandle: "any__mask" },
      { id: "e6", source: "src-1", target: "wshed-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e7", source: "markers-1", target: "wshed-1", sourceHandle: "any__markers", targetHandle: "any__markers" },
      { id: "e8", source: "wshed-1", target: "disp-1", sourceHandle: "image__main", targetHandle: "image__main" }
    ]
  },
  {
    name: "Interactive Magic Painter",
    description: "Draw on screen using your finger landmarks (Hand Tracker).",
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
    description: "Creates an artistic motion trail by blending background motion over time.",
    nodes: [
      { id: "src-1", type: "input_webcam", position: { x: 50, y: 150 }, data: { label: "Webcam", params: {} } },
      { id: "mog-1", type: "bg_sub_mog2", position: { x: 250, y: 150 }, data: { label: "Movement Mask", params: { history: 100 } } },
      { id: "blend-1", type: "plugin_blend_images", position: { x: 500, y: 150 }, data: { label: "Ghost Blend", params: { opacity: 0.3 } } },
      { id: "disp-1", type: "output_display", position: { x: 750, y: 150 }, data: { label: "Trail View", params: {} } }
    ],
    edges: [
      { id: "e1", source: "src-1", target: "mog-1", sourceHandle: "image__main", targetHandle: "image__image" },
      { id: "e2", source: "src-1", target: "blend-1", sourceHandle: "image__main", targetHandle: "image_a" },
      { id: "e3", source: "mog-1", target: "blend-1", sourceHandle: "mask__mask", targetHandle: "image_b" },
      { id: "e4", source: "blend-1", target: "disp-1", sourceHandle: "image__main", targetHandle: "image__main" }
    ]
  }
];
