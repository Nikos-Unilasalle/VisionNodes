import React, { useState, useCallback, useMemo, useEffect, useRef, memo } from 'react';
import ReactFlow, {
  addEdge, Background, Controls, applyEdgeChanges, applyNodeChanges,
  Node, Edge, Connection, EdgeChange, NodeChange, Panel, BackgroundVariant,
  NodeResizer
} from 'reactflow';
import 'reactflow/dist/style.css';
import { 
  Camera, Waves, Ghost, Maximize, Settings, Cpu, HardDrive, Info,
  Plus, Layers, Search, User, Scaling, Zap, Activity, ChevronRight,
  Hash, Eye, Layout, PenTool, Database, Wind, Target, Move, Palette, Box, Image, Film,
  Pause, Play, Save, FolderOpen, BookOpen, Type, Pipette, GitCommit,
  AlignHorizontalDistributeCenter, AlignVerticalDistributeCenter, Grid3x3, Crop,
  Undo2, Redo2, FolderSearch, RefreshCw
} from 'lucide-react';
import * as N from './components/Nodes';
import { useVisionEngine } from './hooks/useVisionEngine';
import { useHistory } from './hooks/useHistory';
import { NodesDataContext } from './context/NodesDataContext';
import { NodeInspectorPanel } from './components/NodeInspectorPanel';
import logo from './assets/logo.svg';
import { motion, AnimatePresence } from 'framer-motion';
import { save, open } from '@tauri-apps/plugin-dialog';
import { writeTextFile, readTextFile, mkdir, exists, BaseDirectory, writeFile, rename, readDir } from '@tauri-apps/plugin-fs';
// Removed documentDir and join to avoid Path plugin dependency
// Examples loaded dynamically from public/examples/
import { getCurrentWindow } from '@tauri-apps/api/window';

const initialNodes: Node[] = [
  { id: 'node-1', type: 'input_webcam', position: { x: 50, y: 150 }, data: { label: 'Webcam', params: { device_index: 1 } } },
  { id: 'node-4', type: 'output_display', position: { x: 450, y: 150 }, data: { label: 'Display Outlet', params: {} } },
];

const initialEdges: Edge[] = [
  { id: 'e1-4', source: 'node-1', target: 'node-4', sourceHandle: 'image__main', targetHandle: 'image__main' },
];

const withNodeResizer = (
  Component: React.ComponentType<any>,
  minWidth: number,
  minHeight: number,
  getColor?: (data: any) => string
) => memo(({ selected, data, ...props }: any) => {
  const color = getColor ? getColor(data) : 'var(--accent, #7c3aed)';
  return (
    <div className="w-full h-full" style={{ minWidth, minHeight, position: 'relative' }}>
      <NodeResizer
        isVisible={selected}
        minWidth={minWidth}
        minHeight={minHeight}
        color={color}
        handleStyle={{ width: 8, height: 8, borderRadius: 2, zIndex: 20 }}
        lineStyle={{ borderColor: color, borderWidth: 1, opacity: selected ? 0.4 : 0, zIndex: 20 }}
      />
      <Component selected={selected} data={data} {...props} />
    </div>
  );
});

const getNoteColor = (data: any) => {
  const cIdx = data?.params?.color_index;
  const palIdx = data?.activePaletteIndex ?? 6;
  const bg = cIdx !== undefined ? N.PALETTES[palIdx]?.colors[cIdx % 5]?.bg : (data?.params?.bg_color || '#ffd4b8');
  return bg + '99';
};
const getFrameColor = (data: any) => {
  const cIdx = data?.params?.color_index;
  const palIdx = data?.activePaletteIndex ?? 6;
  return cIdx !== undefined ? N.PALETTES[palIdx]?.colors[cIdx % 5]?.bg : (data?.params?.bg_color || '#333333');
};

const withNodeColor = (Component: React.ComponentType<any>) =>
  memo(({ selected, data, ...props }: any) => {
    const cIdx = data?.params?.color_index;
    const palIdx = data?.activePaletteIndex ?? 6;
    const customBg = cIdx !== undefined
      ? N.PALETTES[palIdx]?.colors[cIdx % 5]?.bg
      : data?.params?.bg_color;
    const customText = cIdx !== undefined
      ? N.PALETTES[palIdx]?.colors[cIdx % 5]?.dark
      : data?.params?.text_color;
    return (
      <N.NodeColorProvider value={{ customBg, customText }}>
        <Component selected={selected} data={data} {...props} />
      </N.NodeColorProvider>
    );
  });

// Stable wrapped component for dynamic plugin nodes
const ColoredGenericCustomNode = withNodeColor(N.GenericCustomNode);

const _nodeTypes = {
  input_webcam: N.InputWebcamNode,
  input_image: N.InputImageNode,
  input_movie: N.InputMovieNode,
  input_solid_color: N.SolidColorNode,
  filter_canny: N.FilterCannyNode,
  filter_blur: N.FilterBlurNode,
  filter_gray: N.FilterGrayNode,
  filter_threshold: N.FilterThresholdNode,
  filter_morphology: N.FilterMorphologyNode,
  filter_color_mask: N.FilterColorMaskNode,
  geom_flip: N.GeomFlipNode,
  geom_resize: N.GeomResizeNode,
  geom_crop_rect: N.CropRectNode,
  analysis_face_mp: N.AnalysisFaceMPNode,
  analysis_hand_mp: N.AnalysisHandMPNode,
  analysis_pose_mp: N.AnalysisPoseMPNode,
  analysis_head_pose: N.AnalysisHeadPoseNode,
  transform_eye_crop: N.TransformEyeCropNode,
  analysis_gaze: N.AnalysisGazeNode,
  math_vec_to_screen: N.MathVecToScreenNode,
  analysis_flow: N.AnalysisFlowNode,
  analysis_flow_viz: N.AnalysisFlowVizNode,
  analysis_monitor: N.AnalysisMonitorNode,
  util_roi_polygon: N.ROIPolygonNode,
  draw_overlay: N.DrawOverlayNode,
  draw_point: N.GenericCustomNode,
  draw_line: N.GenericCustomNode,
  draw_rect: N.GenericCustomNode,
  util_coord_to_mask: N.UtilCoordToMaskNode,
  util_mask_blend: N.UtilMaskBlendNode,
  data_list_selector: N.DataListSelectorNode,
  data_coord_splitter: N.DataCoordSplitterNode,
  data_coord_combine: N.DataCoordCombineNode,
  data_inspector: withNodeResizer(N.DataInspectorNode, 180, 120),
  output_display: N.OutputDisplayNode,
  logic_python: N.PythonNode,
  canvas_note: withNodeResizer(N.CanvasNoteNode, 120, 60, getNoteColor),
  canvas_reroute: N.CanvasRerouteNode,
  output_movie: N.OutputMovieNode,
  math_add: N.MathNode,
  math_sub: N.MathNode,
  math_mul: N.MathNode,
  math_div: N.MathNode,
  math_mod: N.MathNode,
  math_min: N.MathNode,
  math_max: N.MathNode,
  math_pow: N.MathNode,
  math_abs: N.MathNode,
  math_round: N.MathNode,
  math_sin: N.MathNode,
  math_cos: N.MathNode,
  math_clamp: N.MathNode,
  math_distance: N.MathNode,
  string_input: N.StringNode,
  string_concat: N.StringNode,
  string_split: N.StringNode,
  string_length: N.StringNode,
  string_case: N.StringNode,
  canvas_frame: withNodeResizer(N.CanvasFrameNode, 200, 150, getFrameColor),
  sci_plotter: withNodeResizer(N.ScientificPlotterNode, 240, 180),
};

const nodeTypes = Object.fromEntries(
  Object.entries(_nodeTypes).map(([k, v]) => [k, withNodeColor(v as any)])
) as typeof _nodeTypes;

const CATEGORIES = [
  { id: 'src', label: 'Sources', icon: Camera, nodes: [
    { type: 'input_webcam', label: 'Webcam', description: 'Captures live video feed from your system camera.' },
    { type: 'input_image', label: 'Image File', description: 'Loads a static image from your local drive.' },
    { type: 'input_movie', label: 'Movie File', description: 'Plays a video file with playback and scrubbing controls.' },
    { type: 'input_solid_color', label: 'Solid Color', description: 'Generates an image of a custom solid color.' }
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
  { id: 'track', label: 'Tracking', icon: User, nodes: [
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
    { type: 'sci_plotter', label: 'Plotter', description: 'Multi-series real-time graph. Connect up to 5 scalar or list inputs. Resizable.' },
  ]},
  { id: 'draw', label: 'Drawing', icon: PenTool, nodes: [
    { type: 'draw_overlay', label: 'Visual Overlay', description: 'Draws shapes and text over the main video stream.' }
  ]},
  { id: 'util', label: 'Utilities', icon: Box, nodes: [
    { type: 'data_list_selector', label: 'List Selector', description: 'Extracts a specific item from a list of detections.' },
    { type: 'data_coord_splitter', label: 'Coord Splitter', description: 'Splits a coordinate dictionary into 4 scalar values.' },
    { type: 'data_coord_combine', label: 'Coord Combine', description: 'Combines 4 scalar values into a coordinate dictionary.' }
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
    { type: 'string_concat', label: 'Concatenate', description: 'Joins two strings together.' },
    { type: 'string_split', label: 'Split', description: 'Splits a string into a list via a separator.' },
    { type: 'string_length', label: 'Length', description: 'Counts the number of characters.' },
    { type: 'string_case', label: 'Case Change', description: 'Converts to Upper or Lower case.' }
  ] },
  { id: 'logic', label: 'Logic', icon: Zap, nodes: [
    { type: 'logic_python', label: 'Python Node', description: 'Run custom Python scripts with dynamic inputs.' }
  ] },
  { id: 'out', label: 'Output', icon: Maximize, nodes: [
    { type: 'output_display', label: 'Final Display', description: 'The output terminal displaying the final video stream.' },
    { type: 'output_movie', label: 'Movie Export', description: 'Records the pipeline to an MP4 file, or records webcam directly and creates a Movie node on stop.' },
    { type: 'util_compose', label: 'Compose', description: 'Combines two images: side-by-side, split view, blend, difference, or checkerboard.' }
  ] },
  { id: 'canvas', label: 'Canvas', icon: Type, nodes: [
    { type: 'canvas_note', label: 'Note', description: 'Annotation text block. Double-click to edit. Drag & resize freely.' },
    { type: 'canvas_frame', label: 'Frame', description: 'Wraps and labels a group of nodes. Drag to encapsulate nodes.' },
    { type: 'canvas_reroute', label: 'Reroute', description: 'Pass-through node to organize wires.' }
  ] }
];

type Canvas = { id: string; name: string; nodes: Node[]; edges: Edge[]; filePath: string | null };
const CANVAS_IDS = ['c1', 'c2', 'c3', 'c4'];
const CANVAS_NAMES = ['Scene 1', 'Scene 2', 'Scene 3', 'Scene 4'];
const makeInitialCanvases = (): Canvas[] => CANVAS_IDS.map((id, i) => ({
  id,
  name: CANVAS_NAMES[i],
  nodes: i === 0 ? initialNodes : [],
  edges: i === 0 ? initialEdges : [],
  filePath: null,
}));

function App() {
  const [canvases, setCanvases] = useState<Canvas[]>(makeInitialCanvases);
  const [activeCanvasId, setActiveCanvasId] = useState('c1');
  const activeCanvasIdRef = useRef('c1');
  useEffect(() => { activeCanvasIdRef.current = activeCanvasId; }, [activeCanvasId]);

  const nodes = useMemo(
    () => canvases.find(c => c.id === activeCanvasId)?.nodes ?? [],
    [canvases, activeCanvasId]
  );
  const edges = useMemo(
    () => canvases.find(c => c.id === activeCanvasId)?.edges ?? [],
    [canvases, activeCanvasId]
  );
  const setNodes = useCallback((updater: Node[] | ((nds: Node[]) => Node[])) => {
    setCanvases(prev => prev.map(c => c.id === activeCanvasIdRef.current
      ? { ...c, nodes: typeof updater === 'function' ? updater(c.nodes) : updater }
      : c));
  }, []);
  const setEdges = useCallback((updater: Edge[] | ((eds: Edge[]) => Edge[])) => {
    setCanvases(prev => prev.map(c => c.id === activeCanvasIdRef.current
      ? { ...c, edges: typeof updater === 'function' ? updater(c.edges) : updater }
      : c));
  }, []);
  const activeFilePath = useMemo(
    () => canvases.find(c => c.id === activeCanvasId)?.filePath ?? null,
    [canvases, activeCanvasId]
  );
  const setActiveFilePath = useCallback((path: string | null) => {
    setCanvases(prev => prev.map(c => c.id === activeCanvasIdRef.current ? { ...c, filePath: path } : c));
  }, []);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false);
  const [pendingConnection, setPendingConnection] = useState<any>(null);
  const [activeCategoryId, setActiveCategoryId] = useState(CATEGORIES[1].id);
  const [rightPanelWidth, setRightPanelWidth] = useState(340);
  const [isExamplesOpen, setIsExamplesOpen] = useState(false);
  const [examples, setExamples] = useState<{name: string, description: string, file: string}[]>([]);
  const [isProjectsOpen, setIsProjectsOpen] = useState(false);
  const [workDir, setWorkDir] = useState<string | null>(() => localStorage.getItem('vn-work-dir'));
  const [workDirFiles, setWorkDirFiles] = useState<string[]>([]);
  const [snapEnabled, setSnapEnabled] = useState(false);
  const isResizing = useRef(false);
  const nodesRef = useRef<any[]>([]);
  const edgesRef = useRef<any[]>([]);
  const addNodeRef = useRef<any>(null);
  nodesRef.current = nodes;
  edgesRef.current = edges;

  const { push: histPush, undo: histUndo, redo: histRedo, canUndo, canRedo } = useHistory();
  const lastParamPushRef = useRef(0);
  const pushSnapshot = useCallback(() => {
    histPush(activeCanvasId, { nodes: nodesRef.current, edges: edgesRef.current });
  }, [histPush, activeCanvasId]);

  const [menu, setMenu] = useState<{ id: string, x: number, y: number } | null>(null);
  const [roiEditingId, setRoiEditingId] = useState<string | null>(null);
  const [cropEditingId, setCropEditingId] = useState<string | null>(null);
  const [visualizedNodeId, setVisualizedNodeId] = useState<string | null>(null);
  const [pickColorNodeId, setPickColorNodeId] = useState<string | null>(null);
  const [activePaletteIndex, setActivePaletteIndex] = useState(6); // 6 is Original VN
  const [isPaletteSelectOpen, setIsPaletteSelectOpen] = useState(false);
  const [previewSize, setPreviewSize] = useState({ w: 400, h: 225 });
  const [previewPos, setPreviewPos] = useState({ x: 0, y: 0 });
  const [previewZoom, setPreviewZoom] = useState(1);
  const previewZoomRef = useRef(1);
  const [previewPan, setPreviewPan] = useState({ x: 0, y: 0 });
  const isPanning = useRef(false);
  const panStart = useRef({ mx: 0, my: 0, px: 0, py: 0 });
  const previewResizing = useRef(false);
  const previewResizeStart = useRef({ x: 0, y: 0, w: 400, h: 225 });
  const previewAspect = useRef(16 / 9);
  const [instance, setInstance] = useState<any>(null);
  
  const handleCapture = useCallback(async (nodeId: string, base64: string) => {
    try {
      const path = await save({
        defaultPath: `capture_${nodeId}_${Date.now()}.png`,
        filters: [{
          name: 'Image',
          extensions: ['png']
        }]
      });

      if (path) {
        // Most robust way to convert base64 to Uint8Array in modern JS
        const res = await fetch(`data:image/png;base64,${base64}`);
        const arrayBuffer = await res.arrayBuffer();
        const bytes = new Uint8Array(arrayBuffer);
        
        await writeFile(path, bytes);
        console.log("Image saved successfully to:", path);
      }
    } catch (err) {
      console.error('Failed to save image:', err);
    }
  }, []);

  const capturePlotterAsImage = useCallback(async (nodeId: string) => {
    try {
      const svgEl = document.querySelector(`[data-id="${nodeId}"] .recharts-wrapper svg`) as SVGSVGElement | null;
      if (!svgEl) { console.error('Plotter SVG not found for node', nodeId); return; }

      const width = svgEl.clientWidth || 400;
      const height = svgEl.clientHeight || 300;
      const svgData = new XMLSerializer().serializeToString(svgEl);
      const url = URL.createObjectURL(new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' }));

      const img = document.createElement('img') as HTMLImageElement;
      img.onload = async () => {
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d')!;
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, width, height);
        ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(url);
        canvas.toBlob(async (blob) => {
          if (!blob) return;
          try {
            const path = await save({
              defaultPath: `plotter_${Date.now()}.png`,
              filters: [{ name: 'Image', extensions: ['png'] }]
            });
            if (path) await writeFile(path, new Uint8Array(await blob.arrayBuffer()));
          } catch (err) { console.error('Failed to save plotter image:', err); }
        }, 'image/png');
      };
      img.src = url;
    } catch (err) { console.error('Failed to capture plotter:', err); }
  }, []);

  const { frame, nodesData, pluginSchemas, isConnected, updateGraph, requestCapture, setPreviewNode, lastCommands, notifications, dismissNotification, pushNotification } = useVisionEngine(handleCapture);

  const handleSaveAsImage = useCallback((nodeId: string) => {
    const nodeType = nodes.find(n => n.id === nodeId)?.type;
    if (nodeType === 'sci_plotter') {
      capturePlotterAsImage(nodeId);
    } else {
      requestCapture(nodeId);
    }
  }, [nodes, capturePlotterAsImage, requestCapture]);

  const dynamicCategories = useMemo(() => {
    const cats = CATEGORIES.map(c => ({...c, nodes: [...c.nodes]}));
    // Collect all statically-defined node types to avoid duplicates
    const staticTypes = new Set(CATEGORIES.flatMap(c => c.nodes.map(n => n.type)));
    (pluginSchemas || []).forEach(schema => {
      if (staticTypes.has(schema.type)) return; // skip already registered
      let targetCat = cats.find((c: any) => c.id === schema.category);
      if (!targetCat) {
         targetCat = {
            id: schema.category,
            label: schema.category.charAt(0).toUpperCase() + schema.category.slice(1),
            icon: Layers,
            nodes: []
         } as any;
         cats.splice(cats.length - 1, 0, targetCat as any);
      }
      targetCat!.nodes.push({ type: schema.type, label: schema.label, schema: schema } as any);
    });
    return cats.sort((a, b) => a.label.localeCompare(b.label));
  }, [pluginSchemas]);

  const activeCategory: any = dynamicCategories.find(c => c.id === activeCategoryId) || dynamicCategories[0];

  const dynamicNodeTypes = useMemo(() => {
    const types: any = { ...nodeTypes };
    (pluginSchemas || []).forEach(schema => {
      if (!types[schema.type]) {
        types[schema.type] = ColoredGenericCustomNode;
      }
    });
    return types;
  }, [pluginSchemas]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing.current) return;
      const newWidth = Math.max(250, Math.min(800, document.body.clientWidth - e.clientX));
      setRightPanelWidth(newWidth);
    };
    const handleMouseUp = () => { isResizing.current = false; };
    
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  useEffect(() => {
    document.title = "Vision Nodes Studio";
  }, []);

  const STATIC_IMAGE_PRODUCERS = useMemo(() => new Set([
    'input_webcam', 'input_image', 'input_movie', 'input_solid_color',
    'filter_canny', 'filter_blur', 'filter_gray', 'filter_threshold',
    'filter_morphology', 'filter_color_mask', 'geom_flip', 'geom_resize',
    'analysis_face_mp', 'analysis_hand_mp', 'analysis_pose_mp',
    'analysis_flow', 'analysis_flow_viz', 'util_roi_polygon', 'draw_overlay',
    'util_coord_to_mask', 'util_mask_blend', 'logic_python', 'output_display',
  ]), []);

  const nodesWithData = useMemo(() => {
    return nodes.map(node => {
      let dynamicColor = null;
      if (node.type === 'logic_switch') {
        const edge = edges.find(e => e.target === node.id && (e.targetHandle?.endsWith('if_true') || e.targetHandle?.endsWith('if_false')));
        if (edge) dynamicColor = edge.sourceHandle?.split('__')[0];
      }

      const schema = (pluginSchemas || []).find(s => s.type === node.type);
      const staticNode = CATEGORIES.flatMap(c => c.nodes).find(n => n.type === node.type);
      const description = schema?.description || (staticNode as any)?.description;

      return {
        ...node,
        data: {
          ...node.data,
          params: node.data?.params || {},
          schema,
          description,
          dynamicColor,
          activePaletteIndex,
          isVisualized: node.id === visualizedNodeId,
          onOpenEditor: node.type === 'util_roi_polygon'
            ? () => setRoiEditingId(node.id)
            : node.type === 'geom_crop_rect'
            ? () => setCropEditingId(node.id)
            : undefined,
          onChangeParams: (p: any) => {
            setNodes(nds => nds.map(n => n.id === node.id ? { ...n, data: { ...n.data, params: { ...n.data.params, ...p } } } : n));
          }
        }
      };
    });
  }, [nodes, edges, pluginSchemas, visualizedNodeId, activePaletteIndex]);

  const canVisualize = useCallback((nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return false;
    if (node.type === 'output_display') return true;
    if (STATIC_IMAGE_PRODUCERS.has(node.type || '')) return true;
    const schema = (pluginSchemas || []).find(s => s.type === node.type);
    if (schema?.outputs?.some((o: any) => o.color === 'image' || o.color === 'mask')) return true;
    return false;
  }, [nodes, pluginSchemas, STATIC_IMAGE_PRODUCERS]);

  const handleVisualize = useCallback((nodeId: string) => {
    const newId = visualizedNodeId === nodeId ? null : nodeId;
    setVisualizedNodeId(newId);
    setPreviewNode(newId);
    setMenu(null);
  }, [visualizedNodeId, setPreviewNode]);

  const selectedNode = useMemo(() => nodesWithData.find((n) => n.id === selectedNodeId) || null, [nodesWithData, selectedNodeId]);
  const selectedNodeLiveData = useMemo(() => {
    if (!selectedNodeId) return {};
    const dataKeys = Object.keys(nodesData).filter(k => k.startsWith(`${selectedNodeId}:`));
    return dataKeys.length > 0
      ? Object.fromEntries(dataKeys.map(k => [k.split(':')[1], nodesData[k]]))
      : (nodesData[selectedNodeId] ?? {});
  }, [selectedNodeId, nodesData]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    if (changes.some(c => c.type === 'remove')) pushSnapshot();
    setNodes((nds) => applyNodeChanges(changes, nds));
  }, [pushSnapshot]);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    if (changes.some(c => c.type === 'remove')) pushSnapshot();
    setEdges((eds) => applyEdgeChanges(changes, eds));
  }, [pushSnapshot]);

  const onConnect = useCallback((params: Connection) => {
    pushSnapshot();
    setEdges((eds) => addEdge({ ...params, id: `e-${Date.now()}` }, eds));
  }, [pushSnapshot]);

  // Centralized graph synchronization to prevent loops
  useEffect(() => {
    const timer = setTimeout(() => {
      if (isConnected) updateGraph(nodes, edges);
    }, 100);
    return () => clearTimeout(timer);
  }, [nodes, edges, isConnected, updateGraph]);

  const onConnectEnd = useCallback((event: any, connectionState?: any) => {
    if (connectionState && connectionState.isValid === false) {
      const containerBounds = document.querySelector('.react-flow')?.getBoundingClientRect();
      const x = event.clientX - (containerBounds?.left || 0);
      const y = event.clientY - (containerBounds?.top || 0);
      setPendingConnection({
        sourceNode: connectionState.fromNode?.id,
        sourceHandle: connectionState.fromHandle?.id,
        type: connectionState.fromHandle?.type,
        x, y
      });
      setIsAddMenuOpen(true);
    }
  }, []);

  const isValidConnection = useCallback((connection: Connection) => {
    if (!connection.sourceHandle || !connection.targetHandle) return false;
    const sourceType = connection.sourceHandle.split('__')[0];
    const targetType = connection.targetHandle.split('__')[0];
    
    if (targetType === 'any' || sourceType === 'any') return true;
    
    const sourceColor = N.HANDLE_COLORS[sourceType as keyof typeof N.HANDLE_COLORS] || sourceType;
    const targetColor = N.HANDLE_COLORS[targetType as keyof typeof N.HANDLE_COLORS] || targetType;
    
    return sourceColor === targetColor;
  }, []);

  const onNodeDragStop = useCallback((_: any, node: Node) => {
    const distToSq = (p: any, v: any, w: any) => {
      const l2 = Math.pow(v.x - w.x, 2) + Math.pow(v.y - w.y, 2);
      if (l2 === 0) return Math.pow(p.x - v.x, 2) + Math.pow(p.y - v.y, 2);
      let t = ((p.x - v.x) * (w.x - v.x) + (p.y - v.y) * (w.y - v.y)) / l2;
      t = Math.max(0, Math.min(1, t));
      return Math.pow(p.x - (v.x + t * (w.x - v.x)), 2) + Math.pow(p.y - (v.y + t * (w.y - v.y)), 2);
    };

    const nodeCenter = { x: node.position.x + 100, y: node.position.y + 50 };
    
    const edgeToInsert = edges.find(edge => {
      const sourceNode = nodes.find(n => n.id === edge.source);
      const targetNode = nodes.find(n => n.id === edge.target);
      if (!sourceNode || !targetNode) return false;
      const sx = sourceNode.position.x + 200, sy = sourceNode.position.y + 50;
      const tx = targetNode.position.x, ty = targetNode.position.y + 50;
      return Math.sqrt(distToSq(nodeCenter, {x:sx, y:sy}, {x:tx, y:ty})) < 30;
    });

    if (edgeToInsert && edgeToInsert.source !== node.id && edgeToInsert.target !== node.id) {
      setEdges((eds) => {
        return eds.filter(e => e.id !== edgeToInsert.id).concat([
          { id: `e-${Date.now()}-1`, source: edgeToInsert.source, target: node.id, sourceHandle: edgeToInsert.sourceHandle, targetHandle: 'main' },
          { id: `e-${Date.now()}-2`, source: node.id, target: edgeToInsert.target, sourceHandle: 'main', targetHandle: edgeToInsert.targetHandle }
        ]);
      });
    }
  }, [nodes, edges]);

  const updateNodeParams = (id: string, params: Record<string, unknown>) => {
    const now = Date.now();
    if (now - lastParamPushRef.current > 500) {
      pushSnapshot();
      lastParamPushRef.current = now;
    }
    setNodes((nds) => nds.map((node) => {
        if (node.id === id) return { ...node, data: { ...node.data, params: { ...node.data.params, ...params } } };
        return node;
    }));
  };

  const handleUndo = useCallback(() => {
    const prev = histUndo(activeCanvasId, { nodes: nodesRef.current, edges: edgesRef.current });
    if (!prev) return;
    setNodes(prev.nodes);
    setEdges(prev.edges);
    if (isConnected) updateGraph(prev.nodes, prev.edges);
  }, [histUndo, activeCanvasId, setNodes, setEdges, isConnected, updateGraph]);

  const handleRedo = useCallback(() => {
    const next = histRedo(activeCanvasId, { nodes: nodesRef.current, edges: edgesRef.current });
    if (!next) return;
    setNodes(next.nodes);
    setEdges(next.edges);
    if (isConnected) updateGraph(next.nodes, next.edges);
  }, [histRedo, activeCanvasId, setNodes, setEdges, isConnected, updateGraph]);

  const copyNodes = useCallback(() => {
    const selectedNodes = nodes.filter(n => n.selected);
    if (selectedNodes.length === 0) return;
    const clipboardData = {
      nodes: selectedNodes.map(n => ({...n, id: `node-copy-${Date.now()}-${Math.random()}`})),
      edges: edges.filter(e => selectedNodes.some(n => n.id === e.source) && selectedNodes.some(n => n.id === e.target))
    };
    localStorage.setItem('vision-nodes-clipboard', JSON.stringify(clipboardData));
  }, [nodes, edges]);

  const pasteNodes = useCallback((mousePos?: {x: number, y: number}) => {
    const raw = localStorage.getItem('vision-nodes-clipboard');
    if (!raw) return;
    pushSnapshot();
    const { nodes: copiedNodes, edges: copiedEdges } = JSON.parse(raw);
    const idMap: Record<string, string> = {};
    const newNodes = copiedNodes.map((n: any) => {
      const newId = `node-${Date.now()}-${Math.random()}`;
      idMap[n.id] = newId;
      return { 
        ...n, 
        id: newId, 
        selected: true,
        position: mousePos ? { x: mousePos.x + (n.position.x - copiedNodes[0].position.x), y: mousePos.y + (n.position.y - copiedNodes[0].position.y) } : { x: n.position.x + 50, y: n.position.y + 50 }
      };
    });
    const newEdges = copiedEdges.map((e: any) => ({
      ...e,
      id: `e-${Date.now()}-${Math.random()}`,
      source: idMap[e.source],
      target: idMap[e.target]
    }));
    setNodes(nds => [...nds.map(n => ({...n, selected: false})), ...newNodes]);
    setEdges(eds => [...eds, ...newEdges]);
  }, []);

  const refreshWorkDir = useCallback(async (dir: string) => {
    try {
      const entries = await readDir(dir);
      const files = entries
        .filter(e => !e.isDirectory && e.name?.endsWith('.vn'))
        .map(e => e.name!)
        .sort();
      setWorkDirFiles(files);
    } catch {
      setWorkDirFiles([]);
    }
  }, []);

  useEffect(() => {
    if (workDir) refreshWorkDir(workDir);
  }, [workDir, refreshWorkDir]);

  const setWorkDirAndSave = async () => {
    const dir = await open({ directory: true, multiple: false });
    if (dir && typeof dir === 'string') {
      localStorage.setItem('vn-work-dir', dir);
      setWorkDir(dir);
    }
  };

  const confirmUnsaved = async (): Promise<boolean> => {
    if (!activeFilePath && nodes.length === 0) return true;
    const { ask } = await import('@tauri-apps/plugin-dialog');
    const save = await ask(
      activeFilePath
        ? `"${activeFilePath.split(/[\\/]/).pop()}" has unsaved changes. Save before continuing?`
        : 'Current scene has unsaved changes. Save before continuing?',
      { title: 'Unsaved Changes', kind: 'warning', okLabel: 'Save', cancelLabel: 'Discard' }
    );
    if (save) await saveProject();
    return true;
  };

  const buildProjectContent = () => {
    const ui = { previewSize, previewPos, activePaletteIndex, visualizedNodeId };
    return JSON.stringify({ nodes, edges, ui }, null, 2);
  };

  const saveProject = async () => {
    try {
      let path = activeFilePath;
      if (!path) {
        path = await save({
          defaultPath: 'project.vn',
          filters: [{ name: 'VisionNodes Project', extensions: ['vn'] }]
        });
      }
      if (path) {
        await writeTextFile(path, buildProjectContent());
        setActiveFilePath(path);
        pushNotification(`Saved → ${path.split(/[\\/]/).pop()}`, 'info');
        if (workDir && path.startsWith(workDir)) refreshWorkDir(workDir);
      }
    } catch (err) {
      console.error('Failed to save project:', err);
      pushNotification('Save failed — see console', 'error');
    }
  };

  const saveProjectIncremental = async () => {
    try {
      let basePath: string | null = activeFilePath;
      if (!basePath) {
        basePath = await save({
          defaultPath: 'project.vn',
          filters: [{ name: 'VisionNodes Project', extensions: ['vn'] }]
        });
        if (!basePath) return;
        await writeTextFile(basePath, buildProjectContent());
        setActiveFilePath(basePath);
        return;
      }

      // Parse: dir + stem (without .vn)
      const lastSlash = Math.max(basePath.lastIndexOf('/'), basePath.lastIndexOf('\\'));
      const dir = basePath.slice(0, lastSlash + 1);
      const filename = basePath.slice(lastSlash + 1).replace(/\.vn$/i, '');

      // Check if stem ends with " NN" (space + digits)
      const numMatch = filename.match(/^(.*?) (\d+)$/);
      if (numMatch) {
        const stem = numMatch[1];
        const nextN = parseInt(numMatch[2], 10) + 1;
        const nextPath = `${dir}${stem} ${String(nextN).padStart(2, '0')}.vn`;
        await writeTextFile(nextPath, buildProjectContent());
        setActiveFilePath(nextPath);
        pushNotification(`Saved → ${nextPath.split(/[\\/]/).pop()}`, 'info');
        if (workDir && nextPath.startsWith(workDir)) refreshWorkDir(workDir);
      } else {
        const path01 = `${dir}${filename} 01.vn`;
        const path02 = `${dir}${filename} 02.vn`;
        await rename(basePath, path01);
        await writeTextFile(path02, buildProjectContent());
        setActiveFilePath(path02);
        pushNotification(`Renamed → ${path01.split(/[\\/]/).pop()} · Saved → ${path02.split(/[\\/]/).pop()}`, 'info');
        if (workDir && path02.startsWith(workDir)) refreshWorkDir(workDir);
      }
    } catch (err) {
      console.error('Failed incremental save:', err);
      pushNotification('Incremental save failed — see console', 'error');
    }
  };

  const loadProjectFromPath = async (filePath: string) => {
    try {
      const content = await readTextFile(filePath);
      const { nodes: newNodes, edges: newEdges, ui } = JSON.parse(content);
      setNodes(newNodes); setEdges(newEdges); setActiveFilePath(filePath);
      if (ui) {
        if (ui.previewSize) setPreviewSize(ui.previewSize);
        if (ui.previewPos) setPreviewPos(ui.previewPos);
        if (ui.activePaletteIndex !== undefined) setActivePaletteIndex(ui.activePaletteIndex);
        if (ui.visualizedNodeId !== undefined) { setVisualizedNodeId(ui.visualizedNodeId); setPreviewNode(ui.visualizedNodeId); }
      }
      updateGraph(newNodes, newEdges);
      pushNotification(`Opened → ${filePath.split(/[\\/]/).pop()}`, 'info');
    } catch (err) {
      console.error('Failed to load project:', err);
      pushNotification('Open failed — see console', 'error');
    }
  };

  const loadProject = async () => {
    await confirmUnsaved();
    try {
      const path = await open({
        filters: [{ name: 'VisionNodes Project', extensions: ['vn'] }],
        multiple: false
      });

      if (path && typeof path === 'string') await loadProjectFromPath(path);
    } catch (err) {
      console.error('Failed to open dialog:', err);
    }
  };

  const applyExampleData = (data: any) => {
    const nodes = data.nodes || [];
    const edges = data.edges || [];
    setNodes(nodes);
    setEdges(edges);
    if (data.ui) {
        if (data.ui.previewSize) setPreviewSize(data.ui.previewSize);
        if (data.ui.previewPos) setPreviewPos(data.ui.previewPos);
        if (data.ui.activePaletteIndex !== undefined) setActivePaletteIndex(data.ui.activePaletteIndex);
        if (data.ui.visualizedNodeId !== undefined) {
           setVisualizedNodeId(data.ui.visualizedNodeId);
           setPreviewNode(data.ui.visualizedNodeId);
        }
    }
    updateGraph(nodes, edges);
    setIsExamplesOpen(false);
  };

  const loadExample = async (file: string) => {
    try {
      const data = await fetch(`/examples/${file}`).then(r => r.json());
      applyExampleData(data);
    } catch(e) {
      console.error('Failed to load example:', file, e);
    }
  };

  useEffect(() => {
    fetch('/examples/manifest.json')
      .then(r => r.json())
      .then(setExamples)
      .catch(e => console.error('Failed to load examples manifest:', e));
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const cmdKey = isMac ? e.metaKey : e.ctrlKey;

      if (cmdKey && e.key === 'c') copyNodes();
      if (cmdKey && e.key === 'v') pasteNodes();
      if (cmdKey && !e.shiftKey && e.key === 'z') { e.preventDefault(); handleUndo(); }
      if (cmdKey && e.shiftKey && e.key === 'z') { e.preventDefault(); handleRedo(); }
      
      if (cmdKey && e.key.toLowerCase() === 'm') { e.preventDefault(); setIsAddMenuOpen(prev => !prev); }
      if (cmdKey && e.key.toLowerCase() === 'a') {
        e.preventDefault();
        setNodes(nds => nds.map(n => ({ ...n, selected: true })));
      }
      if (cmdKey && e.key.toLowerCase() === 'o') { e.preventDefault(); loadProject(); }
      if (cmdKey && e.key.toLowerCase() === 's') { e.preventDefault(); saveProject(); }
      if (cmdKey && e.shiftKey && e.key.toLowerCase() === 'f') {
        e.preventDefault();
        getCurrentWindow().isFullscreen().then(is => getCurrentWindow().setFullscreen(!is));
      }
      if (cmdKey && !e.shiftKey && e.key.toLowerCase() === 'f') {
        e.preventDefault();
        instance?.fitView();
      }

      if (e.key === 'Escape') {
        setIsAddMenuOpen(false);
        setPendingConnection(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [copyNodes, pasteNodes, handleUndo, handleRedo, instance]);

  const addNode = (type: string, label: string, schema?: any, initialParams: any = {}) => {
    pushSnapshot();
    const id = `node-${Date.now()}`;
    const position = pendingConnection ? { x: pendingConnection.x, y: pendingConnection.y } : { x: 450, y: 450 };
    // Some nodes need a default style so NodeResizer works from the start
    const defaultStyle: Record<string, any> = {
      data_inspector: { width: 220, height: 200 },
      canvas_note: { width: 300, height: 180 },
      canvas_reroute: { width: 16, height: 16 },
      canvas_frame: { width: 500, height: 400, zIndex: -1 },
      sci_plotter: { width: 320, height: 220 },
    };
    const nodeStyle = defaultStyle[type] || {};
    setNodes((nds) => {
      const nextNodes = [...nds, { id, type, position, style: nodeStyle, data: { label, params: initialParams, schema } }];
      if (pendingConnection && pendingConnection.sourceNode) {
        setTimeout(() => {
          const newEl = document.querySelector(`[data-id="${id}"]`);
          if (!newEl) return;
          const expectedColor = pendingConnection.sourceHandle.split('__')[0];
          const targetClass = pendingConnection.type === 'source' ? 'target' : 'source';
          const handles = Array.from(newEl.querySelectorAll(`.react-flow__handle-${targetClass}`));
          const match = handles.find(h => h.getAttribute('data-handleid')?.startsWith(`${expectedColor}__`)) || handles[0];
          
          if (match) {
            const matchedHandleId = match.getAttribute('data-handleid');
            if (matchedHandleId) {
              setEdges(eds => {
                const newEdges = [...eds, {
                  id: `e-${Date.now()}`,
                  source: pendingConnection.type === 'source' ? pendingConnection.sourceNode : id,
                  target: pendingConnection.type === 'source' ? id : pendingConnection.sourceNode,
                  sourceHandle: pendingConnection.type === 'source' ? pendingConnection.sourceHandle : matchedHandleId,
                  targetHandle: pendingConnection.type === 'source' ? matchedHandleId : pendingConnection.sourceHandle
                }];
                updateGraph(nextNodes, newEdges);
                return newEdges;
              });
            }
          }
        }, 50);
      } else {
        updateGraph(nextNodes, edges);
      }
      return nextNodes;
    });
    setIsAddMenuOpen(false);
    setPendingConnection(null);
  };
  addNodeRef.current = addNode;

  useEffect(() => { if (isConnected) updateGraph(nodesRef.current, edgesRef.current); }, [isConnected, updateGraph]);
  useEffect(() => {
    setSelectedNodeId(null);
    if (isConnected) updateGraph(nodesRef.current, edgesRef.current);
  }, [activeCanvasId, isConnected, updateGraph]);


  const alignNodes = useCallback((direction: 'horizontal' | 'vertical') => {
    setNodes(nds => {
      const selectedIds = nds.filter(n => n.selected).map(n => n.id);
      if (selectedIds.length < 2) return nds;
      
      const selNodes = nds.filter(n => n.selected);
      const avgX = selNodes.reduce((acc, n) => acc + n.position.x, 0) / selNodes.length;
      const avgY = selNodes.reduce((acc, n) => acc + n.position.y, 0) / selNodes.length;
      
      return nds.map(n => {
        if (!n.selected) return n;
        return {
          ...n,
          position: {
            x: direction === 'vertical' ? avgX : n.position.x,
            y: direction === 'horizontal' ? avgY : n.position.y
          }
        };
      });
    });
  }, []);

  useEffect(() => {
    if (lastCommands && lastCommands.length > 0) {
      lastCommands.forEach(cmd => {
        if (cmd.type === 'add_node') {
          let label = "New Node";
          if (cmd.node_type === 'input_image') label = "Captured Frame";
          if (cmd.node_type === 'input_movie') label = "Recorded Video";
          addNodeRef.current?.(cmd.node_type, label, null, cmd.params);
        }
      });
    }
  }, [lastCommands]);

  const [searchQuery, setSearchQuery] = useState('');
  const filteredNodes = useMemo(() => {
    if (!searchQuery) return activeCategory.nodes;
    const all = dynamicCategories.flatMap(c => c.nodes);
    return all.filter(n => n.label.toLowerCase().includes(searchQuery.toLowerCase()));
  }, [searchQuery, activeCategory, dynamicCategories]);

  useEffect(() => {
    const handleRemoveEdge = (e: any) => {
      const { nodeId, handleId, type } = e.detail;
      setEdges((eds) => {
        const nextEdges = eds.filter(edge => {
          if (type === 'target') return !(edge.target === nodeId && edge.targetHandle === handleId);
          if (type === 'source') return !(edge.source === nodeId && edge.sourceHandle === handleId);
          return true;
        });
        if (nextEdges.length !== eds.length) setTimeout(() => updateGraph(nodes, nextEdges), 10);
        return nextEdges;
      });
    };
    window.addEventListener('remove-handle-edge', handleRemoveEdge);
    return () => window.removeEventListener('remove-handle-edge', handleRemoveEdge);
  }, []);

  const coloredEdges = useMemo(() => {
    const resolveColor = (edge: any, visited = new Set()): string => {
      if (!edge || visited.has(edge.id)) return '#555';
      visited.add(edge.id);
      
      const sourceNode = nodes.find(n => n.id === edge.source);
      if (sourceNode?.type === 'canvas_reroute') {
        const incomingEdge = edges.find(e => e.target === sourceNode.id);
        if (incomingEdge) {
          return resolveColor(incomingEdge, visited);
        }
      }
      
      if (edge.sourceHandle) {
        const sourceType = edge.sourceHandle.split('__')[0];
        return (N.HANDLE_COLORS as any)[sourceType] || '#555';
      }
      return '#555';
    };

    return edges.map((edge: any) => ({
      ...edge,
      style: {
        ...edge.style,
        stroke: resolveColor(edge),
        strokeWidth: 2,
      }
    }));
  }, [edges, nodes]);

  return (
    <div className="w-full h-screen bg-[#0a0a0a] flex flex-col text-white font-sans overflow-hidden select-none">
      <header className="h-10 bg-[#151515] border-b border-[#222] flex items-center justify-between px-4 z-50">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="h-8 flex items-center justify-center transition-transform hover:scale-110">
              <img src={logo} alt="Logo" className="h-full w-auto object-contain" />
            </div>
            <h1 className="text-[11px] font-black tracking-[0.3em] text-white uppercase ml-1">VNStudio</h1>
          </div>
          <div className={`px-2 py-0.5 rounded text-[8px] font-bold ${isConnected ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'} border border-current opacity-60`}>
            {isConnected ? 'RUNTIME_CONNECTED' : 'WAITING_FOR_WS'}
          </div>
          <div className="h-4 w-[1px] bg-[#222] mx-1" />
          
          <div className="flex items-center bg-[#1a1a1a] rounded-lg border border-[#333] p-0.5">
            <button
              onClick={async () => { await confirmUnsaved(); pushSnapshot(); const n: any[] = []; const e: any[] = []; setNodes(n); setEdges(e); setActiveFilePath(null); updateGraph(n, e); }}
              className="flex items-center gap-2 px-3 py-1 hover:bg-white/10 rounded-md text-[10px] font-bold text-gray-400 transition-all"
            >
              <Plus size={14} /> New
            </button>
            <div className="w-[1px] h-3 bg-[#333] mx-0.5" />
            <button
              onClick={loadProject}
              className="flex items-center gap-2 px-3 py-1 hover:bg-white/10 rounded-md text-[10px] font-bold text-gray-400 transition-all"
            >
              <FolderOpen size={14} /> Open
            </button>
            <div className="w-[1px] h-3 bg-[#333] mx-0.5" />
            <button
              onClick={saveProject}
              className="flex items-center gap-2 px-3 py-1 bg-accent/10 hover:bg-accent/20 rounded-md text-[10px] font-bold text-accent transition-all"
              title={activeFilePath ? `Save → ${activeFilePath.split(/[\\/]/).pop()}` : 'Save As…'}
            >
              <Save size={14} />
              {activeFilePath
                ? activeFilePath.split(/[\\/]/).pop()?.replace(/\.vn$/i, '') ?? 'Save'
                : 'Save .vn'}
            </button>
            {activeFilePath && (<>
              <div className="w-[1px] h-3 bg-[#333] mx-0.5" />
              <button
                onClick={saveProjectIncremental}
                title="Save incremental version (+01, +02…)"
                className="flex items-center justify-center w-7 h-7 hover:bg-accent/20 rounded-md text-[11px] font-black text-accent transition-all"
              >
                +
              </button>
            </>)}
          </div>

          <div className="h-4 w-[1px] bg-[#222] mx-1" />

          <div className="flex items-center bg-[#1a1a1a] rounded-lg border border-[#333] p-0.5">
            <button
              onClick={handleUndo}
              disabled={!canUndo(activeCanvasId)}
              title="Undo (⌘Z)"
              className="flex items-center gap-1.5 px-3 py-1 hover:bg-white/10 rounded-md text-[10px] font-bold text-gray-400 transition-all disabled:opacity-25 disabled:cursor-not-allowed"
            >
              <Undo2 size={13} /> Undo
            </button>
            <div className="w-[1px] h-3 bg-[#333] mx-0.5" />
            <button
              onClick={handleRedo}
              disabled={!canRedo(activeCanvasId)}
              title="Redo (⌘⇧Z)"
              className="flex items-center gap-1.5 px-3 py-1 hover:bg-white/10 rounded-md text-[10px] font-bold text-gray-400 transition-all disabled:opacity-25 disabled:cursor-not-allowed"
            >
              <Redo2 size={13} /> Redo
            </button>
          </div>

          <div className="h-4 w-[1px] bg-[#222] mx-1" />

          <div className="flex items-center gap-1 bg-[#1a1a1a] rounded-lg border border-[#333] p-0.5">
            <button
              onClick={() => alignNodes('horizontal')}
              title="Align Horizontally"
              className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors"
            >
              <AlignHorizontalDistributeCenter size={14} />
            </button>
            <button 
              onClick={() => alignNodes('vertical')}
              title="Align Vertically"
              className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors"
            >
              <AlignVerticalDistributeCenter size={14} />
            </button>
            <div className="w-[1px] h-3 bg-[#333] mx-1" />
            <button 
              onClick={() => setSnapEnabled(!snapEnabled)}
              title="Snap to Grid"
              className={`p-1 rounded transition-colors ${snapEnabled ? 'text-accent bg-accent/20' : 'text-gray-500 hover:text-white hover:bg-white/10'}`}
            >
              <Grid3x3 size={14} />
            </button>
          </div>

          <div className="h-4 w-[1px] bg-[#222] mx-1" />

          <div className="flex items-center gap-1 bg-[#1a1a1a] rounded-lg border border-[#333] p-0.5">
            <button 
              onClick={() => addNode('input_image', 'Image File')}
              title="Add Image Node"
              className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors"
            >
              <Image size={14} />
            </button>
            <button 
              onClick={() => addNode('input_movie', 'Movie File')}
              title="Add Movie Node"
              className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors"
            >
              <Film size={14} />
            </button>
            <button 
              onClick={() => addNode('input_webcam', 'Webcam')}
              title="Add Webcam Node"
              className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors"
            >
              <Camera size={14} />
            </button>
          </div>

          <div className="h-4 w-[1px] bg-[#222] mx-1" />

          <div className="flex items-center gap-1 bg-[#1a1a1a] rounded-lg border border-[#333] p-0.5">
            <button 
              onClick={() => addNode('canvas_note', 'Note')}
              title="Add Note Node"
              className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors"
            >
              <Type size={14} />
            </button>
            <button 
              onClick={() => addNode('canvas_frame', 'Frame')}
              title="Add Frame Node"
              className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors"
            >
              <Layout size={14} />
            </button>
            <button 
              onClick={() => addNode('canvas_reroute', 'Reroute')}
              title="Add Reroute Node"
              className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors"
            >
              <GitCommit size={14} />
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-0.5 bg-[#1a1a1a] rounded-lg border border-[#333] p-0.5">
            {canvases.map(c => (
              <button
                key={c.id}
                onClick={() => setActiveCanvasId(c.id)}
                className={`px-3 py-1 rounded-md text-[10px] font-bold transition-all ${
                  activeCanvasId === c.id
                    ? 'bg-accent/20 text-accent'
                    : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                }`}
              >
                {c.name}
              </button>
            ))}
          </div>
           <div className="relative">
              <button
                onClick={() => setIsPaletteSelectOpen(!isPaletteSelectOpen)}
                className="flex items-center gap-2 px-3 py-1 bg-white/5 hover:bg-white/10 rounded-lg text-[10px] font-bold text-gray-400 transition-all border border-white/5"
              >
                <Palette size={14} /> Palette
              </button>
              <AnimatePresence>
                {isPaletteSelectOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setIsPaletteSelectOpen(false)} />
                    <motion.div 
                      initial={{ opacity: 0, y: 10, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 10, scale: 0.95 }}
                      className="absolute right-0 mt-2 w-48 bg-[#1a1a1a] border border-[#333] rounded-xl shadow-2xl z-50 p-2 overflow-hidden"
                    >
                      {N.PALETTES.map((pal, i) => (
                        <button 
                          key={i}
                          onClick={() => { setActivePaletteIndex(i); setIsPaletteSelectOpen(false); }}
                          className={`w-full text-left p-2 rounded-lg group transition-all flex flex-col gap-1.5 ${i === activePaletteIndex ? 'bg-accent/20 border border-accent/30' : 'hover:bg-white/5 border border-transparent'}`}
                        >
                          <div className="text-[9px] font-bold text-gray-200 group-hover:text-accent uppercase tracking-tighter">{pal.name}</div>
                          <div className="flex h-3 w-full rounded overflow-hidden">
                             {pal.colors.map((c, ci) => (
                               <div key={ci} className="flex-1" style={{ backgroundColor: c.bg }} />
                             ))}
                          </div>
                        </button>
                      ))}
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
           </div>
           
           {/* My Projects panel */}
           <div className="relative">
              <button
                onClick={() => setIsProjectsOpen(!isProjectsOpen)}
                className="flex items-center gap-2 px-3 py-1 bg-white/5 hover:bg-white/10 rounded-lg text-[10px] font-bold text-gray-400 transition-all border border-white/5"
              >
                <FolderSearch size={14} /> My Projects
              </button>
              <AnimatePresence>
                {isProjectsOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setIsProjectsOpen(false)} />
                    <motion.div
                      initial={{ opacity: 0, y: 10, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 10, scale: 0.95 }}
                      className="absolute right-0 mt-2 w-72 bg-[#1a1a1a] border border-[#333] rounded-xl shadow-2xl z-50 p-2 overflow-y-auto max-h-[70vh]"
                    >
                      {/* Define directory */}
                      <button
                        onClick={async () => { await setWorkDirAndSave(); }}
                        className="w-full flex items-center gap-2 p-3 hover:bg-accent/10 rounded-lg group transition-all text-left"
                      >
                        <FolderSearch size={13} className="text-accent shrink-0" />
                        <div>
                          <div className="text-[10px] font-bold text-gray-200 group-hover:text-accent uppercase tracking-tighter">Set Work Directory</div>
                          {workDir && <div className="text-[8px] text-gray-600 mt-0.5 truncate max-w-[220px]">{workDir}</div>}
                        </div>
                      </button>

                      {workDir && (
                        <>
                          <div className="flex items-center justify-between px-3 py-1.5">
                            <div className="w-full h-[1px] bg-[#2a2a2a]" />
                            <button onClick={() => refreshWorkDir(workDir)} className="ml-2 text-gray-600 hover:text-accent transition-colors shrink-0">
                              <RefreshCw size={10} />
                            </button>
                          </div>
                          {workDirFiles.length === 0 ? (
                            <div className="text-[9px] text-gray-600 px-3 py-2 italic">No .vn files in this directory</div>
                          ) : (
                            workDirFiles.map(file => (
                              <button
                                key={file}
                                onClick={async () => {
                                  await confirmUnsaved();
                                  await loadProjectFromPath(`${workDir}/${file}`);
                                  setIsProjectsOpen(false);
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-accent/10 rounded-lg group transition-all text-left"
                              >
                                <Save size={11} className="text-gray-600 group-hover:text-accent shrink-0" />
                                <span className="text-[10px] font-bold text-gray-300 group-hover:text-accent truncate">
                                  {file.replace(/\.vn$/i, '')}
                                </span>
                                {activeFilePath === `${workDir}/${file}` && (
                                  <span className="ml-auto text-[8px] text-accent font-black uppercase tracking-wider">active</span>
                                )}
                              </button>
                            ))
                          )}
                        </>
                      )}
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
           </div>

           <div className="relative">
              <button
                onClick={() => setIsExamplesOpen(!isExamplesOpen)}
                className="flex items-center gap-2 px-3 py-1 bg-white/5 hover:bg-white/10 rounded-lg text-[10px] font-bold text-gray-400 transition-all border border-white/5"
              >
                <BookOpen size={14} /> Examples
              </button>
              <AnimatePresence>
                {isExamplesOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setIsExamplesOpen(false)} />
                    <motion.div 
                      initial={{ opacity: 0, y: 10, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 10, scale: 0.95 }}
                      className="absolute right-0 mt-2 w-64 bg-[#1a1a1a] border border-[#333] rounded-xl shadow-2xl z-50 p-2 overflow-y-auto max-h-[70vh]"
                    >
                      {examples.map((ex, i) => (
                        <button
                          key={i}
                          onClick={() => loadExample(ex.file)}
                          className="w-full text-left p-3 hover:bg-accent/10 rounded-lg group transition-all"
                        >
                          <div className="text-[10px] font-bold text-gray-200 group-hover:text-accent uppercase tracking-tighter">{ex.name}</div>
                          <div className="text-[8px] text-gray-500 mt-1 leading-tight">{ex.description}</div>
                        </button>
                      ))}
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
           </div>
        </div>
      </header>

      <div className="flex-1 flex w-full relative">
        <div className="flex-1 relative overflow-hidden bg-[#080808]" onContextMenu={e => e.preventDefault()}>
          <NodesDataContext.Provider value={nodesData}>
          <ReactFlow
            nodes={nodesWithData} edges={coloredEdges}
            onInit={setInstance}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} 
            onConnect={onConnect} onConnectEnd={onConnectEnd} isValidConnection={isValidConnection}
            onNodeDragStart={() => pushSnapshot()}
            onNodeDragStop={onNodeDragStop}
            onEdgeClick={(_, edge) => { pushSnapshot(); setEdges(eds => { const n = eds.filter(e => e.id !== edge.id); updateGraph(nodes, n); return n; }); }}
            nodeTypes={dynamicNodeTypes} onNodeClick={(_, node) => setSelectedNodeId(node.id)} onPaneClick={() => { setSelectedNodeId(null); setMenu(null); }}
            onNodeContextMenu={(e, node) => { 
              e.preventDefault(); 
              if (node.type !== 'canvas_reroute') setMenu({ id: node.id, x: e.clientX, y: e.clientY }); 
            }}
            panOnDrag={[1, 2]} panOnScroll={true} selectionOnDrag={true}
            snapToGrid={snapEnabled} snapGrid={[20, 20]}
            defaultViewport={{ x: 0, y: 0, zoom: 0.7 }}
            fitView
          >
            <Background color="#111" variant={BackgroundVariant.Lines} gap={40} size={1} />
            <Controls className="bg-[#1a1a1a] border-[#333] fill-white" />
            <Panel position="top-left">
              <button 
                onClick={() => setIsAddMenuOpen(!isAddMenuOpen)}
                className="bg-accent hover:bg-blue-600 text-white p-2 px-8 rounded-full shadow-2xl transition-all font-black text-[10px] tracking-widest uppercase flex items-center gap-2"
              >
                <Plus size={14} /> Add Node
              </button>
            </Panel>
          </ReactFlow>
          </NodesDataContext.Provider>

          {/* Engine notification bar */}
          {notifications.length > 0 && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[300] flex flex-col gap-2 w-[500px] max-w-[90vw]">
              {notifications.map(n => {
                const isError = n.level === 'error';
                const isDone  = n.progress !== null && n.progress >= 1;
                const isRunning = n.progress !== null && n.progress < 1;
                return (
                  <div key={n.id} className={`bg-[#111]/97 backdrop-blur border rounded-xl px-4 py-3 shadow-2xl ${isError ? 'border-red-500/40' : isDone ? 'border-green-500/30' : 'border-white/10'}`}>
                    <div className="flex items-center gap-2">
                      {isRunning && (
                        <svg className="animate-spin shrink-0" width="13" height="13" viewBox="0 0 24 24" fill="none">
                          <circle cx="12" cy="12" r="10" stroke="#333" strokeWidth="3"/>
                          <path d="M12 2a10 10 0 0 1 10 10" stroke="#3b82f6" strokeWidth="3" strokeLinecap="round"/>
                        </svg>
                      )}
                      {isError  && <span className="text-red-400 text-[12px] shrink-0">✕</span>}
                      {isDone   && <span className="text-green-400 text-[12px] shrink-0">✓</span>}
                      <span className={`text-[11px] font-mono flex-1 min-w-0 break-words ${isError ? 'text-red-300' : 'text-white/80'}`}>
                        {n.message}
                      </span>
                      {n.progress !== null && !isError && (
                        <span className="text-[10px] text-white/40 shrink-0 ml-1">{Math.round(n.progress * 100)}%</span>
                      )}
                      {(isError || isDone) && (
                        <button
                          onClick={() => dismissNotification(n.id)}
                          className="ml-2 text-white/30 hover:text-white/70 shrink-0 text-[14px] leading-none transition-colors"
                        >×</button>
                      )}
                    </div>
                    {n.progress !== null && (
                      <div className="mt-2 h-1 rounded-full bg-white/10 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${isError ? 'bg-red-500' : isDone ? 'bg-green-500' : 'bg-blue-500'}`}
                          style={{ width: `${Math.min(100, Math.round(n.progress * 100))}%` }}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <AnimatePresence>
            {roiEditingId && (
               <ROIEditorOverlay
                 nodeId={roiEditingId}
                 node={nodesWithData.find(n => n.id === roiEditingId)}
                 nodesData={nodesData}
                 onClose={() => setRoiEditingId(null)}
               />
            )}
            {cropEditingId && (
               <CropEditorOverlay
                 node={nodesWithData.find(n => n.id === cropEditingId)}
                 nodesData={nodesData}
                 onClose={() => setCropEditingId(null)}
               />
            )}
          </AnimatePresence>

          {menu && (
            <div
              className="absolute z-[200] bg-[#1a1a1a]/95 backdrop-blur-xl border border-white/10 shadow-2xl rounded-2xl p-1.5 min-w-[180px] animate-in zoom-in-95 duration-150 origin-top-left"
              style={{ top: menu.y, left: menu.x }}
              onClick={() => setMenu(null)}
            >
              {canVisualize(menu.id) && (
                <>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleVisualize(menu.id); }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-accent rounded-xl text-white text-[11px] font-bold transition-all group"
                  >
                    <Eye size={16} className={visualizedNodeId === menu.id ? "text-yellow-400 group-hover:text-white" : "text-accent group-hover:text-white"} />
                    <span>{visualizedNodeId === menu.id ? 'Stop Visualizing' : 'Visualiser'}</span>
                  </button>
                  <div className="h-px bg-white/5 my-1 mx-2" />
                </>
              )}
              <button
                onClick={() => handleSaveAsImage(menu.id)}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-accent rounded-xl text-white text-[11px] font-bold transition-all group"
              >
                <Save size={16} className="text-accent group-hover:text-white" />
                <span>Save as Image...</span>
              </button>
              <div className="h-px bg-white/5 my-1 mx-2" />
              
              <div className="px-3 py-2 flex items-center justify-center gap-1.5 flex-wrap">
                 {N.PALETTES[activePaletteIndex].colors.map((c: any, i: number) => (
                    <button 
                      key={i} 
                      onClick={(e) => {
                        e.stopPropagation();
                        setNodes(nds => nds.map(n => n.id === menu.id ? { ...n, data: { ...n.data, params: { ...n.data.params, color_index: i, bg_color: undefined, text_color: undefined } } } : n));
                      }} 
                      className="w-4 h-4 rounded-full border border-black/20 shadow-sm hover:scale-125 transition-transform" 
                      style={{ backgroundColor: c.bg }} 
                    />
                 ))}
                 <button 
                    onClick={(e) => {
                       e.stopPropagation();
                       setNodes(nds => nds.map(n => n.id === menu.id ? { ...n, data: { ...n.data, params: { ...n.data.params, color_index: undefined, bg_color: undefined, text_color: undefined } } } : n));
                    }} 
                    className="w-4 h-4 rounded-full border border-white/20 hover:bg-white/10 hover:text-white transition-all flex items-center justify-center text-[10px] text-gray-500 bg-transparent shrink-0"
                 >
                    ×
                 </button>
              </div>
              <div className="h-px bg-white/5 my-1 mx-2" />

              <button
                onClick={() => {
                  pushSnapshot();
                  if (menu.id === visualizedNodeId) { setVisualizedNodeId(null); setPreviewNode(null); }
                  setNodes(nds => nds.filter(n => n.id !== menu.id));
                }}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-red-500 rounded-xl text-white text-[11px] font-bold transition-all group"
              >
                <Plus size={16} className="text-red-500 group-hover:text-white rotate-45" />
                <span>Delete Node</span>
              </button>
            </div>
          )}

          {isAddMenuOpen && (
            <div className="absolute inset-0 bg-black/80 backdrop-blur-md z-[100] flex items-center justify-center p-20" onClick={() => { setIsAddMenuOpen(false); setPendingConnection(null); }}>
              <div 
                className="bg-[#181818] border border-[#333] w-full max-w-[700px] h-[85vh] rounded-3xl shadow-2xl flex overflow-hidden animate-in zoom-in-95 duration-200"
                onClick={e => e.stopPropagation()}
              >
                <div className="w-56 bg-[#111] border-r border-[#222] p-6 flex flex-col gap-2">
                  {dynamicCategories.map(cat => (
                    <button 
                      key={cat.id} onClick={() => setActiveCategoryId(cat.id)}
                      className={`flex items-center gap-4 px-4 py-3 rounded-2xl text-[11px] font-bold transition-all ${activeCategoryId === cat.id ? 'bg-accent text-white shadow-xl shadow-accent/20' : 'text-gray-500 hover:bg-white/5'}`}
                    >
                      <cat.icon size={18} /> {cat.label}
                    </button>
                  ))}
                </div>
                <div className="flex-1 p-12 overflow-y-auto overflow-x-hidden flex flex-col">
                  <div className="flex items-center justify-between mb-10 border-b border-[#222] pb-4">
                    <h3 className="text-[10px] font-black text-gray-400 uppercase tracking-widest">
                      {searchQuery ? 'Search Results' : `Category :: ${activeCategory.label}`}
                    </h3>
                    <div className="relative group">
                      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 group-focus-within:text-accent transition-colors" />
                      <input 
                        autoFocus
                        type="text" 
                        placeholder="Search modules..." 
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        className="bg-black/40 border border-[#222] rounded-xl pl-10 pr-4 py-2 text-[11px] text-white outline-none focus:border-accent/50 w-64 transition-all"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    {filteredNodes.map((node: any) => (
                      <button
                        key={node.type} onClick={() => { addNode(node.type, node.label, node.schema); setSearchQuery(''); }}
                        className="p-6 bg-[#222] hover:bg-accent/10 border border-[#333] hover:border-accent/40 rounded-3xl text-left transition-all active:scale-95 group"
                      >
                        <div className="text-[11px] font-bold text-gray-200 uppercase tracking-tighter group-hover:text-accent transition-colors">{node.label}</div>
                        <div className="text-[8px] text-gray-600 font-mono mt-1 italic">{node.schema ? 'cv::plugin' : 'cv::node'}</div>
                      </button>
                    ))}
                  </div>
                  {filteredNodes.length === 0 && (
                    <div className="flex-1 flex flex-col items-center justify-center text-gray-700 gap-4 opacity-50 italic py-20">
                      <Search size={48} strokeWidth={1} />
                      <div className="text-[11px] font-bold uppercase tracking-widest">No modules found matching "{searchQuery}"</div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          <motion.div
            drag
            dragMomentum={false}
            animate={{ x: previewPos.x, y: previewPos.y }}
            onDragEnd={(e, info) => setPreviewPos({ x: previewPos.x + info.offset.x, y: previewPos.y + info.offset.y })}
            whileHover={{ cursor: 'grab' }}
            whileDrag={{ cursor: 'grabbing', zIndex: 100 }}
            onDoubleClick={() => { previewZoomRef.current = 1; setPreviewZoom(1); setPreviewPan({ x: 0, y: 0 }); }}
            onWheel={(e) => {
              e.stopPropagation();
              const oldZoom = previewZoomRef.current;
              const newZoom = Math.max(0.25, Math.min(8, oldZoom * (e.deltaY < 0 ? 1.1 : 0.9)));
              previewZoomRef.current = newZoom;
              setPreviewZoom(newZoom);
              const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
              const mx = e.clientX - rect.left;
              const my = e.clientY - rect.top;
              const cx = rect.width / 2;
              const cy = rect.height / 2;
              setPreviewPan(p => ({
                x: p.x + (mx - cx) * (1 / newZoom - 1 / oldZoom),
                y: p.y + (my - cy) * (1 / newZoom - 1 / oldZoom),
              }));
            }}
            onMouseDown={(e) => {
              if (e.button !== 1) return;
              e.preventDefault();
              isPanning.current = true;
              panStart.current = { mx: e.clientX, my: e.clientY, px: previewPan.x, py: previewPan.y };
              const onMove = (ev: MouseEvent) => {
                if (!isPanning.current) return;
                document.body.style.cursor = 'grabbing';
                setPreviewPan({
                  x: panStart.current.px + (ev.clientX - panStart.current.mx),
                  y: panStart.current.py + (ev.clientY - panStart.current.my),
                });
              };
              const onUp = (ev: MouseEvent) => {
                if (ev.button !== 1) return;
                isPanning.current = false;
                document.body.style.cursor = '';
                window.removeEventListener('mousemove', onMove);
                window.removeEventListener('mouseup', onUp);
              };
              window.addEventListener('mousemove', onMove);
              window.addEventListener('mouseup', onUp);
            }}
            className="absolute bottom-6 left-[49px] bg-black border-2 border-[#222] rounded-3xl shadow-2xl overflow-hidden z-20 group hover:border-accent transition-colors duration-300"
            style={{ width: previewSize.w, height: previewSize.h }}
          >
            {frame && <img src={frame} alt="Vision"
              className="w-full h-full object-contain pointer-events-none"
              style={{ transform: `translate(${previewPan.x}px, ${previewPan.y}px) scale(${previewZoom})`, transformOrigin: 'center' }}
              onLoad={(e) => {
                const img = e.currentTarget;
                if (img.naturalWidth && img.naturalHeight) {
                  const newAspect = img.naturalWidth / img.naturalHeight;
                  if (Math.abs(newAspect - previewAspect.current) > 0.02) {
                    previewAspect.current = newAspect;
                    setPreviewSize(prev => ({ w: prev.w, h: Math.round(prev.w / newAspect) }));
                  }
                }
              }} />}
            {previewZoom !== 1 && (
              <div className="absolute top-2 right-2 bg-black/60 text-white text-[9px] font-black px-2 py-1 rounded-lg pointer-events-none">
                {Math.round(previewZoom * 100)}%
              </div>
            )}
            {pickColorNodeId && (
              <div
                className="absolute inset-0 z-30"
                style={{ cursor: 'crosshair' }}
                onClick={(e) => {
                  const container = e.currentTarget.parentElement!;
                  const imgEl = container.querySelector('img') as HTMLImageElement | null;
                  if (!imgEl || !frame) return;
                  const rect = imgEl.getBoundingClientRect();
                  const px = e.clientX - rect.left;
                  const py = e.clientY - rect.top;
                  // sample via canvas
                  const canvas = document.createElement('canvas');
                  canvas.width = imgEl.naturalWidth;
                  canvas.height = imgEl.naturalHeight;
                  const ctx = canvas.getContext('2d')!;
                  ctx.drawImage(imgEl, 0, 0);
                  const scaleX = imgEl.naturalWidth / rect.width;
                  const scaleY = imgEl.naturalHeight / rect.height;
                  const [r, g, b] = ctx.getImageData(Math.floor(px * scaleX), Math.floor(py * scaleY), 1, 1).data;
                  updateNodeParams(pickColorNodeId, { r, g, b });
                  setPickColorNodeId(null);
                }}
              />
            )}
            <div
              className="absolute bottom-0 right-0 w-5 h-5 cursor-se-resize z-10 flex items-end justify-end pb-1 pr-1 opacity-0 group-hover:opacity-100 transition-opacity"
              onMouseDown={(e) => {
                e.stopPropagation();
                previewResizing.current = true;
                previewResizeStart.current = { x: e.clientX, y: e.clientY, w: previewSize.w, h: previewSize.h };
                const onMove = (ev: MouseEvent) => {
                  if (!previewResizing.current) return;
                  const dw = ev.clientX - previewResizeStart.current.x;
                  const newW = Math.max(160, previewResizeStart.current.w + dw);
                  setPreviewSize({ w: newW, h: Math.round(newW / previewAspect.current) });
                };
                const onUp = () => {
                  previewResizing.current = false;
                  window.removeEventListener('mousemove', onMove);
                  window.removeEventListener('mouseup', onUp);
                };
                window.addEventListener('mousemove', onMove);
                window.addEventListener('mouseup', onUp);
              }}
            >
              <svg width="8" height="8" viewBox="0 0 8 8" className="text-white/30">
                <path d="M8 0 L8 8 L0 8" fill="none" stroke="currentColor" strokeWidth="1.5"/>
              </svg>
            </div>
          </motion.div>
        </div>

        {/* Right Panel — absolute overlay so canvas never resizes */}
        <div
          className="absolute right-0 top-0 bg-[#0a0a0a] border-l border-[#1a1a1a] flex flex-col transition-all duration-300 h-full overflow-hidden z-10"
          style={{ width: selectedNodeId ? rightPanelWidth : 0, opacity: selectedNodeId ? 1 : 0 }}
        >
          {/* Resize Handle */}
          <div 
            className="absolute left-0 top-0 bottom-0 w-1.5 -ml-[3px] cursor-col-resize hover:bg-accent/50 z-20 transition-colors duration-150"
            onMouseDown={() => isResizing.current = true}
          />

          <div className="h-full flex flex-col">
            <div className="h-10 border-b border-[#222] flex items-center px-4 bg-[#1a1a1a] shrink-0">
              <Settings size={14} className="text-gray-500 mr-2" />
              <span className="text-[10px] font-black tracking-widest text-gray-400 uppercase">Unit Inspector</span>
            </div>
            
            <div className="flex-1 overflow-y-auto p-10">
              {selectedNode ? (
                <div className="space-y-12 animate-in slide-in-from-right-10 duration-500">
                  <div className="flex items-center gap-5">
                     <div className="w-16 h-16 bg-accent/5 rounded-3xl border border-accent/20 flex items-center justify-center text-accent shadow-inner">
                        <Cpu size={32} />
                     </div>
                     <div>
                        <h2 className="text-[14px] font-black text-white uppercase tracking-wider">{selectedNode.data.label}</h2>
                        {selectedNode.data.description && (
                          <p className="text-[10px] text-gray-400 italic mt-1 leading-relaxed opacity-80">{selectedNode.data.description}</p>
                        )}
                        <span className="text-[9px] text-gray-600 font-mono italic opacity-40 leading-none">{selectedNode.id}</span>
                     </div>
                  </div>

                  <NodeInspectorPanel
                    node={selectedNode}
                    liveData={selectedNodeLiveData}
                    activePaletteIndex={activePaletteIndex}
                    pickColorNodeId={pickColorNodeId}
                    onUpdateParams={updateNodeParams}
                    onPickColorToggle={setPickColorNodeId}
                    onRequestCapture={requestCapture}
                  />
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center opacity-5 py-20 grayscale pointer-events-none">
                  <Layout size={120} />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


const CropEditorOverlay = ({ node, nodesData, onClose }: any) => {
  const nd = (() => {
    if (!node?.id || !nodesData) return {};
    const dataKeys = Object.keys(nodesData).filter((k: string) => k.startsWith(`${node.id}:`));
    return dataKeys.length > 0
      ? Object.fromEntries(dataKeys.map((k: string) => [k.split(':')[1], nodesData[k]]))
      : (nodesData[node.id] ?? {});
  })();
  const frame = nd?.main_preview || nd?.main;
  const containerRef = useRef<HTMLDivElement>(null);
  const [rect, setRect] = useState({ x: 0.1, y: 0.1, w: 0.8, h: 0.8 });
  const dragMode = useRef<string | null>(null);
  const dragStart = useRef({ mx: 0, my: 0, rect: { x: 0, y: 0, w: 0, h: 0 } });

  useEffect(() => {
    try {
      if (node?.data?.params?.rect) setRect(JSON.parse(node.data.params.rect));
    } catch(e) {}
  }, [node?.id]);

  const getRelPos = (e: MouseEvent | React.MouseEvent) => {
    const r = containerRef.current?.getBoundingClientRect();
    if (!r) return { x: 0, y: 0 };
    return { x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), y: Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)) };
  };

  const HANDLE = 0.025;
  const getMode = (mx: number, my: number, r: typeof rect) => {
    const corners = { nw: [r.x, r.y], ne: [r.x+r.w, r.y], sw: [r.x, r.y+r.h], se: [r.x+r.w, r.y+r.h] } as Record<string,[number,number]>;
    for (const [name, [cx, cy]] of Object.entries(corners))
      if (Math.abs(mx - cx) < HANDLE && Math.abs(my - cy) < HANDLE) return name;
    if (mx > r.x && mx < r.x+r.w && my > r.y && my < r.y+r.h) return 'move';
    return 'draw';
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const pos = getRelPos(e);
    dragMode.current = getMode(pos.x, pos.y, rect);
    dragStart.current = { mx: pos.x, my: pos.y, rect: { ...rect } };

    const onMove = (ev: MouseEvent) => {
      const p = getRelPos(ev);
      const dx = p.x - dragStart.current.mx;
      const dy = p.y - dragStart.current.my;
      const sr = dragStart.current.rect;
      setRect(() => {
        let { x, y, w, h } = sr;
        switch (dragMode.current) {
          case 'draw':
            x = Math.min(dragStart.current.mx, p.x); y = Math.min(dragStart.current.my, p.y);
            w = Math.abs(p.x - dragStart.current.mx); h = Math.abs(p.y - dragStart.current.my);
            break;
          case 'move':
            x = Math.max(0, Math.min(1 - w, sr.x + dx)); y = Math.max(0, Math.min(1 - h, sr.y + dy));
            break;
          case 'nw':
            x = Math.max(0, Math.min(sr.x+sr.w-0.01, sr.x+dx)); y = Math.max(0, Math.min(sr.y+sr.h-0.01, sr.y+dy));
            w = sr.x+sr.w-x; h = sr.y+sr.h-y; break;
          case 'ne':
            y = Math.max(0, Math.min(sr.y+sr.h-0.01, sr.y+dy));
            w = Math.max(0.01, Math.min(1-sr.x, sr.w+dx)); h = sr.y+sr.h-y; break;
          case 'sw':
            x = Math.max(0, Math.min(sr.x+sr.w-0.01, sr.x+dx));
            w = sr.x+sr.w-x; h = Math.max(0.01, Math.min(1-sr.y, sr.h+dy)); break;
          case 'se':
            w = Math.max(0.01, Math.min(1-sr.x, sr.w+dx)); h = Math.max(0.01, Math.min(1-sr.y, sr.h+dy)); break;
        }
        return { x: Math.max(0, x), y: Math.max(0, y), w: Math.max(0.01, Math.min(1-Math.max(0,x), w)), h: Math.max(0.01, Math.min(1-Math.max(0,y), h)) };
      });
    };
    const onUp = () => { dragMode.current = null; window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  const save = () => { node.data.onChangeParams({ rect: JSON.stringify(rect) }); onClose(); };

  const corners = [
    { id: 'nw', x: rect.x, y: rect.y, cursor: 'nwse-resize' },
    { id: 'ne', x: rect.x+rect.w, y: rect.y, cursor: 'nesw-resize' },
    { id: 'sw', x: rect.x, y: rect.y+rect.h, cursor: 'nesw-resize' },
    { id: 'se', x: rect.x+rect.w, y: rect.y+rect.h, cursor: 'nwse-resize' },
  ];

  return (
    <div className="fixed inset-0 z-[1000] bg-black/95 backdrop-blur-3xl flex flex-col items-center justify-center p-8 select-none nodrag" onContextMenu={e => e.preventDefault()}>
      <div className="absolute top-8 left-8 flex items-center gap-4">
        <div className="p-2 bg-accent/20 rounded-lg text-accent"><Crop size={24} /></div>
        <div>
          <h2 className="text-xl font-black uppercase tracking-widest text-white">CROP EDITOR</h2>
          <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest opacity-50">Drag to draw · Corners to resize · Interior to move</p>
        </div>
      </div>

      <div className="relative flex-1 w-full flex items-center justify-center p-4">
        <div ref={containerRef} className="relative inline-block shadow-2xl rounded-2xl overflow-hidden border border-white/10 bg-[#0c0c0c]" onMouseDown={handleMouseDown} style={{ cursor: 'crosshair' }}>
          {frame ? (
            <img src={`data:image/jpeg;base64,${frame}`} className="block w-auto h-auto max-w-[90vw] max-h-[70vh]" draggable={false} />
          ) : (
            <div className="w-[800px] h-[450px] flex items-center justify-center text-gray-700"><Image size={48} className="opacity-10" /></div>
          )}
          <svg className="absolute inset-0 w-full h-full" style={{ pointerEvents: 'none' }}>
            <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 w-full h-full overflow-visible">
              <rect x="0" y="0" width="1" height={rect.y} fill="rgba(0,0,0,0.55)" />
              <rect x="0" y={rect.y+rect.h} width="1" height={1-(rect.y+rect.h)} fill="rgba(0,0,0,0.55)" />
              <rect x="0" y={rect.y} width={rect.x} height={rect.h} fill="rgba(0,0,0,0.55)" />
              <rect x={rect.x+rect.w} y={rect.y} width={1-(rect.x+rect.w)} height={rect.h} fill="rgba(0,0,0,0.55)" />
              <rect x={rect.x} y={rect.y} width={rect.w} height={rect.h} fill="none" stroke="var(--color-accent)" style={{ strokeWidth: 0.004 }} />
              {[1/3, 2/3].flatMap(t => [
                <line key={`v${t}`} x1={rect.x+rect.w*t} y1={rect.y} x2={rect.x+rect.w*t} y2={rect.y+rect.h} stroke="rgba(255,255,255,0.2)" style={{ strokeWidth: 0.002 }} />,
                <line key={`h${t}`} x1={rect.x} y1={rect.y+rect.h*t} x2={rect.x+rect.w} y2={rect.y+rect.h*t} stroke="rgba(255,255,255,0.2)" style={{ strokeWidth: 0.002 }} />
              ])}
            </svg>
            {corners.map(c => (
              <circle key={c.id} cx={`${c.x*100}%`} cy={`${c.y*100}%`} r={7}
                fill="white" stroke="var(--color-accent)" strokeWidth="2" style={{ pointerEvents: 'auto', cursor: c.cursor }} />
            ))}
          </svg>
        </div>
      </div>

      <div className="flex flex-col items-center gap-4">
        <div className="text-[10px] font-mono text-gray-600">
          x:{(rect.x*100).toFixed(1)}%  y:{(rect.y*100).toFixed(1)}%  —  {(rect.w*100).toFixed(1)}% × {(rect.h*100).toFixed(1)}%
        </div>
        <div className="flex items-center gap-4">
          <button onClick={onClose} className="px-10 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all">Cancel</button>
          <button onClick={() => setRect({ x: 0, y: 0, w: 1, h: 1 })} className="px-10 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all">Reset</button>
          <button onClick={save} className="px-16 py-3 bg-accent hover:bg-blue-600 shadow-2xl shadow-accent/20 rounded-2xl text-[10px] font-black uppercase tracking-widest text-white transition-all scale-105 active:scale-95 border border-white/10">Apply Crop</button>
        </div>
      </div>
    </div>
  );
};

const ROIEditorOverlay = ({ nodeId, node, nodesData, onClose }: any) => {
  const [points, setPoints] = useState<any[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const viewportRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const isPanning = useRef(false);
  const panOrigin = useRef({ mx: 0, my: 0, px: 0, py: 0 });

  const nd = (() => {
    if (!nodeId || !nodesData) return {};
    const dataKeys = Object.keys(nodesData).filter((k: string) => k.startsWith(`${nodeId}:`));
    return dataKeys.length > 0
      ? Object.fromEntries(dataKeys.map((k: string) => [k.split(':')[1], nodesData[k]]))
      : (nodesData[nodeId] ?? {});
  })();
  const frame = nd?.main_preview || nd?.main;

  useEffect(() => {
    if (node.data.params?.points) {
      try {
        const p = JSON.parse(node.data.params.points);
        if (Array.isArray(p)) setPoints(p);
      } catch (e) {}
    }
  }, [node.id]);

  // Keyboard support
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return; }
      if (selectedIndex === null) return;
      const step = e.shiftKey ? 0.01 : 0.002;
      let dx = 0, dy = 0;
      if (e.key === 'ArrowLeft')  dx = -step;
      if (e.key === 'ArrowRight') dx =  step;
      if (e.key === 'ArrowUp')    dy = -step;
      if (e.key === 'ArrowDown')  dy =  step;
      if (dx || dy) {
        e.preventDefault();
        setPoints(prev => {
          const next = [...prev];
          next[selectedIndex] = {
            x: Math.max(0, Math.min(1, next[selectedIndex].x + dx)),
            y: Math.max(0, Math.min(1, next[selectedIndex].y + dy)),
          };
          return next;
        });
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        setPoints(prev => prev.filter((_, i) => i !== selectedIndex));
        setSelectedIndex(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedIndex, onClose]);

  // Zoom via scroll wheel — centered on cursor
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const vp = viewportRef.current?.getBoundingClientRect();
    if (!vp) return;
    const factor = e.deltaY > 0 ? 0.85 : 1.18;
    const newZoom = Math.max(0.5, Math.min(10, zoom * factor));
    const ox = (e.clientX - vp.left) - vp.width  / 2;
    const oy = (e.clientY - vp.top)  - vp.height / 2;
    setPan({ x: ox - (ox - pan.x) * (newZoom / zoom), y: oy - (oy - pan.y) * (newZoom / zoom) });
    setZoom(newZoom);
  };

  // Get normalized image coords from mouse event (works after any transform)
  const imgCoords = (clientX: number, clientY: number) => {
    const r = imgRef.current?.getBoundingClientRect();
    if (!r) return null;
    return {
      x: Math.max(0, Math.min(1, (clientX - r.left) / r.width)),
      y: Math.max(0, Math.min(1, (clientY - r.top)  / r.height)),
    };
  };

  const handleSvgMouseDown = (e: React.MouseEvent) => {
    if (e.button === 1) return; // middle = pan handled below
    if (e.button !== 0) return;
    if (e.shiftKey) {
      const c = imgCoords(e.clientX, e.clientY);
      if (!c) return;
      const newPoints = [...points, c];
      setPoints(newPoints);
      setSelectedIndex(newPoints.length - 1);
      return;
    }
    // Start pan on empty left-click
    isPanning.current = true;
    panOrigin.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y };
    setSelectedIndex(null);
  };

  // Pan via mousemove on viewport (when panning)
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isPanning.current) return;
      setPan({
        x: panOrigin.current.px + (e.clientX - panOrigin.current.mx),
        y: panOrigin.current.py + (e.clientY - panOrigin.current.my),
      });
    };
    const onUp = () => { isPanning.current = false; };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  const updatePoint = (index: number, x: number, y: number) => {
    setPoints(prev => { const next = [...prev]; if (!next[index]) return prev; next[index] = { x, y }; return next; });
  };

  const save = () => { node.data.onChangeParams({ points: JSON.stringify(points) }); onClose(); };

  return (
    <div className="fixed inset-0 z-[1000] bg-black/95 backdrop-blur-3xl flex flex-col items-center justify-center p-3 select-none nodrag" onContextMenu={e => e.preventDefault()}>
      <div className="absolute top-3 left-5 flex items-center gap-4">
        <div className="p-2 bg-accent/20 rounded-lg text-accent"><Scaling size={24} /></div>
        <div>
          <h2 className="text-xl font-black uppercase tracking-widest text-white">MASK POLYGON EDITOR</h2>
          <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest opacity-50">Scroll to zoom · Drag to pan · Shift+click to add</p>
        </div>
      </div>

      {/* Zoom indicator */}
      <div className="absolute top-4 right-5 text-[10px] font-black font-mono text-accent/60 bg-accent/5 border border-accent/10 px-2 py-1 rounded-lg">
        {Math.round(zoom * 100)}%
      </div>

      {/* Viewport */}
      <div
        ref={viewportRef}
        className="relative flex-1 w-full overflow-hidden cursor-crosshair"
        onWheel={handleWheel}
        onMouseDown={e => { if (e.button === 1) { isPanning.current = true; panOrigin.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y }; }}}
      >
        {/* Transformed content */}
        <div
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: 'center center' }}
        >
          <div className="relative inline-block shadow-2xl rounded-2xl overflow-hidden border border-white/10 bg-[#0c0c0c] pointer-events-auto">
            {frame ? (
              <img
                ref={imgRef}
                src={`data:image/jpeg;base64,${frame}`}
                className="block w-auto h-auto max-w-[90vw] max-h-[80vh]"
                draggable={false}
              />
            ) : (
              <div className="w-[800px] h-[450px] flex flex-col items-center justify-center text-gray-700">
                <Image size={48} className="opacity-10" />
              </div>
            )}

            <svg className="absolute inset-0 w-full h-full" onMouseDown={handleSvgMouseDown}>
              <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 w-full h-full overflow-visible">
                {points.length >= 3 && (
                  <polygon points={points.map(p => `${p.x},${p.y}`).join(' ')} className="fill-accent/20 stroke-accent" style={{ strokeWidth: 0.004, pointerEvents: 'none' }} />
                )}
                {points.length > 0 && (
                  <polyline points={points.map(p => `${p.x},${p.y}`).join(' ')} fill="none" stroke="var(--color-accent)" style={{ strokeWidth: 0.004, strokeDasharray: points.length >= 3 ? 'none' : '0.01 0.01', pointerEvents: 'none' }} />
                )}
              </svg>
              {points.map((p, i) => (
                <circle
                  key={i}
                  cx={`${p.x * 100}%`} cy={`${p.y * 100}%`}
                  r={(selectedIndex === i ? 8 : 6) / zoom}
                  fill={selectedIndex === i ? 'white' : 'var(--color-accent)'}
                  stroke={selectedIndex === i ? 'var(--color-accent)' : 'white'}
                  strokeWidth={2 / zoom}
                  className="cursor-move"
                  onMouseDown={e => {
                    e.stopPropagation();
                    if (e.button === 2) { setPoints(prev => prev.filter((_, idx) => idx !== i)); setSelectedIndex(null); return; }
                    setSelectedIndex(i);
                    const move = (me: MouseEvent) => {
                      const c = imgCoords(me.clientX, me.clientY);
                      if (c) updatePoint(i, c.x, c.y);
                    };
                    const up = () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
                    window.addEventListener('mousemove', move);
                    window.addEventListener('mouseup', up);
                  }}
                />
              ))}
            </svg>
          </div>
        </div>
      </div>

      <div className="mt-3 flex flex-col items-center gap-3">
        <div className="flex items-center gap-6 px-8 py-3 bg-white/5 rounded-3xl border border-white/5 shadow-inner backdrop-blur-md">
          <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-500">
            <span className="px-2 py-1 bg-accent/20 text-accent rounded-lg border border-accent/20">SHIFT+CLIC</span><span>ADD</span>
          </div>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-500">
            <span className="px-2 py-1 bg-white/10 text-white rounded-lg border border-white/10">DRAG</span><span>PAN</span>
          </div>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-500">
            <span className="px-2 py-1 bg-white/10 text-white rounded-lg border border-white/10">SCROLL</span><span>ZOOM</span>
          </div>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-500">
            <span className="px-2 py-1 bg-white/10 text-white rounded-lg border border-white/10">ARROWS</span><span>NUDGE</span>
          </div>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-500">
            <span className="px-2 py-1 bg-red-500/10 text-red-500 rounded-lg border border-red-500/20">R-CLIC</span><span>DELETE</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={onClose} className="px-10 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all">Cancel</button>
          <button onClick={() => setPoints([])} className="px-10 py-3 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-2xl text-[10px] font-black uppercase tracking-widest text-red-500 transition-all">Clear All</button>
          <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} className="px-6 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all">Reset View</button>
          <button onClick={save} className="px-16 py-3 bg-accent hover:bg-blue-600 shadow-2xl shadow-accent/20 rounded-2xl text-[10px] font-black uppercase tracking-widest text-white transition-all scale-105 active:scale-95 border border-white/10">Apply Mask</button>
        </div>
      </div>
    </div>
  );
};

export default App;
