import {
  Camera, Waves, Layers, Box, Move, Target, Eye, PenTool,
  Hash, Type, Zap, Maximize, Music
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface CategoryNode {
  type: string;
  label: string;
  description?: string;
  schema?: any;
}

interface Category {
  id: string;
  label: string;
  icon: LucideIcon;
  nodes: CategoryNode[];
}

export const CATEGORIES: Category[] = [
  { id: 'src', label: 'Sources', icon: Camera, nodes: [
    { type: 'input_webcam', label: 'Webcam', description: 'Captures live video feed from your system camera.' },
    { type: 'input_image', label: 'Image File', description: 'Loads a static image from your local drive.' },
    { type: 'input_movie', label: 'Movie File', description: 'Plays a video file with playback and scrubbing controls.' },
    { type: 'input_solid_color', label: 'Solid Color', description: 'Generates an image of a custom solid color.' },
    { type: 'plugin_audio_input', label: 'Audio File', description: 'Loads an audio file (.wav, .mp3, .flac…).' }
  ]},
  { id: 'cv', label: 'Filters', icon: Waves, nodes: [
    { type: 'filter_canny', label: 'Canny Edge', description: 'Detects edges using the Canny algorithm (line drawing effect).' },
    { type: 'filter_blur', label: 'Gaussian Blur', description: 'Applies a Gaussian blur to smooth the image and reduce noise.' },
    { type: 'filter_gray', label: 'Grayscale', description: 'Converts the image to grayscale (black and white).' },
    { type: 'filter_threshold', label: 'Threshold', description: 'Separates the image into black and white based on intensity threshold.' }
  ]},
  { id: 'mask', label: 'Masks', icon: Layers, nodes: [
    { type: 'filter_color_mask', label: 'Color Mask', description: 'Creates a mask by isolating a range of colors (HSV).' },
    { type: 'filter_morphology', label: 'Morphology', description: 'Dilation or erosion operations to clean up masks.' },
    { type: 'util_coord_to_mask', label: 'Coord To Mask', description: 'Transforms detection coordinates into a white mask.' }
  ]},
  { id: 'blend', label: 'Blending', icon: Box, nodes: [
    { type: 'util_mask_blend', label: 'Mask Blend', description: 'Blends two images using a mask as an alpha layer.' }
  ]},
  { id: 'geom', label: 'Geometric', icon: Move, nodes: [
    { type: 'geom_flip', label: 'Flip', description: 'Inverts the image horizontally or vertically.' },
    { type: 'geom_resize', label: 'Resize', description: 'Changes the image resolution (scaling).' },
    { type: 'geom_crop_rect', label: 'Crop', description: 'Interactive rectangular crop with drag handles.' },
    { type: 'util_roi_polygon', label: 'ROI Polygon', description: 'Interactive polygonal mask definition for ROIs.' },
    { type: 'geom_perspective', label: 'Perspective Warp', description: 'Straightens a distorted area into a flat rectangle via 4 points.' },
    { type: 'util_manual_points', label: 'Manual 4 Points', description: 'Manually defines 4 reference points for geometric calculations.' }
  ]},
  { id: 'detect', label: 'Detect', icon: Target, nodes: [
    { type: 'analysis_face_mp', label: 'Face Tracker', description: 'Detects and tracks faces and facial landmarks (MediaPipe).' },
    { type: 'analysis_hand_mp', label: 'Hand Tracker', description: 'Detects and tracks hands and joints (MediaPipe).' },
    { type: 'analysis_pose_mp', label: 'Pose Tracker', description: 'Analyzes and tracks human body posture (33 keypoints) via MediaPipe.' },
    { type: 'analysis_head_pose', label: 'Head Pose', description: 'Estimates 3D head orientation (yaw, pitch, roll) from facial landmarks via solvePnP.' },
    { type: 'transform_eye_crop', label: 'Eye Crop', description: 'Crops and aligns left/right eye regions from facial landmarks. Reusable for any eye classifier.' },
    { type: 'analysis_gaze', label: 'Gaze Estimator', description: 'Estimates gaze direction (yaw/pitch) via L2CS-Net. Requires pip install l2cs + weights.' },
    { type: 'analysis_flow', label: 'Optical Flow', description: 'Analyzes the movement of every pixel between two frames.' }
  ]},
  { id: 'features', label: 'Features', icon: Target, nodes: [
    { type: 'feat_find_contours', label: 'Find Contours', description: 'Detects and extracts isolated shapes from a binary mask.' },
    { type: 'feat_fill_contours',   label: 'Fill Contours',   description: 'Fills all contours from a list into a binary mask (union). Connect contours_list from Find Contours.' },
    { type: 'feat_filter_contours', label: 'Filter Contours', description: 'Filters a contour list by elongation ratio (long/short axis) and/or area range.' },
    { type: 'feat_hough_circles', label: 'Hough Circles', description: 'Identifies perfect circular shapes through mathematical calculation.' },
    { type: 'feat_hough_lines', label: 'Hough Lines', description: 'Detects straight line segments (walls, joints, etc.).' },
    { type: 'feat_clahe', label: 'CLAHE (Contrast)', description: 'Improves local image contrast adaptively.' },
    { type: 'feat_bilateral', label: 'Bilateral Filter', description: 'Smoothes the image while preserving edge sharpness.' }
  ] },
  { id: 'visualize', label: 'Visualizers', icon: Eye, nodes: [
    { type: 'data_inspector', label: 'Inspect Unit', description: 'Displays the raw data content flowing through a link.' },
    { type: 'analysis_monitor', label: 'Universal Monitor', description: 'Ultra-polyvalent measurement tool (Flux, Areas, Brightness, Counting).' },
    { type: 'analysis_flow_viz', label: 'Flow Viz', description: 'Colorized visualization of motion direction and strength.' },
    { type: 'sci_plotter', label: 'Plotter', description: 'Multi-series real-time graph. Outputs both raw data and a live rendered image (main).' },
    { type: 'plotter_pro', label: 'Plotter Pro', description: 'Dual-series graph with filtering, thresholding, normalization, and peak detection.' },
  ]},
  { id: 'draw', label: 'Drawing', icon: PenTool, nodes: [
    { type: 'draw_overlay', label: 'Visual Overlay', description: 'Draws shapes and text over the main video stream.' }
  ]},
  { id: 'util', label: 'Utilities', icon: Box, nodes: [
    { type: 'data_list_selector', label: 'List Selector', description: 'Extracts a specific item from a list of detections.' },
    { type: 'list_region_select', label: 'Region Selector', description: 'Filters, sorts and selects a detection region. Outputs canonical 4 corner pts (TL→TR→BR→BL) ready for perspective warp.' },
    { type: 'data_coord_splitter', label: 'Coord Splitter', description: 'Splits a coordinate dictionary into 4 scalar values.' },
    { type: 'data_coord_combine', label: 'Coord Combine', description: 'Combines 4 scalar values into a coordinate dictionary.' },
    { type: 'util_landmark_selector', label: 'Landmark Selector', description: 'Extracts specific points from a landmark list (e.g. torso from pose).' }
  ]},
  { id: 'math', label: 'Math', icon: Hash, nodes: [
    { type: 'math_vec_to_screen', label: 'Vec → Screen', description: 'Maps a yaw/pitch direction vector to normalized screen coordinates (x, y). Smoothing + calibration.' },
    { type: 'math_add', label: 'Add', description: 'Adds two values (a + b).' },
    { type: 'math_sub', label: 'Subtract', description: 'Subtracts b from a (a - b).' },
    { type: 'math_mul', label: 'Multiply', description: 'Multiplies two values (a * b).' },
    { type: 'math_div', label: 'Divide', description: 'Divides a by b (a / b).' },
    { type: 'math_mod', label: 'Modulo', description: 'Returns the remainder of a / b.' },
    { type: 'math_min', label: 'Min', description: 'Returns the smaller of two values.' },
    { type: 'math_max', label: 'Max', description: 'Returns the larger of two values.' },
    { type: 'math_pow', label: 'Power', description: 'Calculates a raised to the power of b.' },
    { type: 'math_abs', label: 'Absolute', description: 'Removes the negative sign from a value.' },
    { type: 'math_round', label: 'Round', description: 'Rounds to the nearest integer.' },
    { type: 'math_sin', label: 'Sin', description: 'Sine of an angle in radians.' },
    { type: 'math_cos', label: 'Cos', description: 'Cosine of an angle in radians.' },
    { type: 'math_clamp', label: 'Clamp', description: 'Constrains a value between min and max.' },
    { type: 'math_distance', label: 'Distance', description: 'Calculates the Euclidean distance between two points.' }
  ] },
  { id: 'strings', label: 'Strings', icon: Type, nodes: [
    { type: 'string_input', label: 'String Input', description: 'Manual text entry for logic and display.' },
    { type: 'string_concat', label: 'Concatenate', description: 'Joins two strings (or a list of strings) with a separator.' },
    { type: 'string_replace', label: 'Search & Replace', description: 'Finds and replaces text in a string. Supports regex.' },
    { type: 'string_split', label: 'Split', description: 'Splits a string into a list via a separator.' },
    { type: 'string_length', label: 'Length', description: 'Counts the number of characters.' },
    { type: 'string_case', label: 'Case Change', description: 'Converts to Upper or Lower case.' }
  ] },
  { id: 'logic', label: 'Logic', icon: Zap, nodes: [
    { type: 'logic_python', label: 'Python Node', description: 'Run custom Python scripts with dynamic inputs.' },
    { type: 'mask_point_query', label: 'Mask Point Query', description: 'Checks if a point (x, y) falls within a mask. Returns true or false.' }
  ] },
  { id: 'out', label: 'Output', icon: Maximize, nodes: [
    { type: 'output_display', label: 'Display', description: 'The output terminal displaying the final video stream.' },
    { type: 'output_movie', label: 'Movie Export', description: 'Records the pipeline to an MP4 file, or records webcam directly and creates a Movie node on stop.' },
    { type: 'util_compose', label: 'Compose', description: 'Combines two images: side-by-side, split view, blend, difference, or checkerboard.' }
  ] },
  { id: 'canvas', label: 'Canvas', icon: Type, nodes: [
    { type: 'canvas_note', label: 'Note', description: 'Annotation text block. Double-click to edit. Drag & resize freely.' },
    { type: 'canvas_frame', label: 'Frame', description: 'Wraps and labels a group of nodes. Drag to encapsulate nodes.' },
    { type: 'canvas_reroute', label: 'Reroute', description: 'Pass-through node to organize wires.' }
  ] },
  { id: 'audio', label: 'Audio Processing', icon: Music, nodes: [
    { type: 'plugin_audio_input',         label: 'Audio File',     description: 'Loads an audio file (.wav, .mp3, .flac…).' },
    { type: 'plugin_audio_waveform',      label: 'Waveform View',  description: 'Renders the audio waveform as an image.' },
    { type: 'plugin_audio_to_spectrogram',label: 'Audio to Spectro',description: 'Converts audio into a log-mel spectrogram image.' },
    { type: 'plugin_spectrogram_to_audio',label: 'Spectro to Audio',description: 'Reconstructs audio from a spectrogram via Griffin-Lim.' },
    { type: 'plugin_audio_freq_filter',   label: 'Freq Filter',    description: 'Low-pass / High-pass / Band-pass / Band-stop IIR filter.' },
    { type: 'plugin_audio_pitch_shift',   label: 'Pitch Shift',    description: 'Shifts pitch by N semitones without changing duration.' },
    { type: 'plugin_audio_time_stretch',  label: 'Time Stretch',   description: 'Stretches or compresses duration without changing pitch.' },
    { type: 'plugin_audio_info',          label: 'Audio Info',     description: 'Computes RMS, peak amplitude, zero-crossing rate.' },
    { type: 'plugin_audio_export',        label: 'Audio Export',   description: 'Saves audio to a .wav file on disk.' },
    { type: 'plugin_audio_playback',      label: 'Speaker Out',    description: 'Plays audio through system speakers (sounddevice).' }
  ] }
];
