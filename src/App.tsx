import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import ReactFlow, {
  Background, Controls, ControlButton, applyEdgeChanges, applyNodeChanges,
  Node, Edge, Connection, EdgeChange, NodeChange, Panel, BackgroundVariant,
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  Plus, ChevronRight, Layers, Heart
} from 'lucide-react';
import * as N from './components/Nodes';
import { useVisionEngine } from './hooks/useVisionEngine';
import { useHistory } from './hooks/useHistory';
import { NodesDataContext } from './context/NodesDataContext';
import { ComputingNodeContext } from './context/ComputingNodeContext';
import { NodeInspectorPanel, AnalysisDataPanel } from './components/NodeInspectorPanel';
import type { ExposedParam } from './components/NodeInspectorPanel';
import { AnimatePresence } from 'framer-motion';
import { save, open } from '@tauri-apps/plugin-dialog';
import { writeTextFile, writeFile, readDir, readTextFile } from '@tauri-apps/plugin-fs';
import { ask } from '@tauri-apps/plugin-dialog';

import { listen } from '@tauri-apps/api/event';
import { nodeTypes, ColoredGenericCustomNode } from './data/nodeTypes';
import { CATEGORIES } from './data/categories';
import { getNestedSubGraph, updateNestedSubGraph } from './utils/groups';
import type { Canvas, GroupEntry } from './data/canvases';
import { CANVAS_IDS, CANVAS_NAMES, makeInitialCanvases } from './data/canvases';
import { useFileOperations } from './hooks/useFileOperations';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { useConnectionHandling } from './hooks/useConnectionHandling';
import { useGroupOperations } from './hooks/useGroupOperations';
import NotificationBar from './components/ui/NotificationBar';
import AboutModal from './components/ui/AboutModal';
import RerouteOverlay from './components/overlays/RerouteOverlay';
import CropEditorOverlay from './components/overlays/CropEditorOverlay';
import AnnotatorOverlay from './components/overlays/AnnotatorOverlay';
import ManualPointsEditorOverlay from './components/overlays/ManualPointsEditorOverlay';
import LineEditorOverlay from './components/overlays/LineEditorOverlay';
import ROIEditorOverlay from './components/overlays/ROIEditorOverlay';
import ContextMenu from './components/menus/ContextMenu';
import AddNodeMenu from './components/menus/AddNodeMenu';
import Header from './components/header/Header';
import PreviewWidget from './components/preview/PreviewWidget';
import RightPanel from './components/panels/RightPanel';
import logo from './assets/logo.svg';

function App() {
  const [canvases, setCanvases] = useState<Canvas[]>(makeInitialCanvases);
  const [activeCanvasId, setActiveCanvasId] = useState('c1');
  const activeCanvasIdRef = useRef('c1');
  useEffect(() => { activeCanvasIdRef.current = activeCanvasId; }, [activeCanvasId]);

  const [favoriteFiles, setFavoriteFiles] = useState<Record<string, string>>(() => {
    try { return JSON.parse(localStorage.getItem('vn-favorites') || '{}'); }
    catch { return {}; }
  });

  const canvasNodes = useMemo(
    () => canvases.find(c => c.id === activeCanvasId)?.nodes ?? [],
    [canvases, activeCanvasId]
  );
  const canvasEdges = useMemo(
    () => canvases.find(c => c.id === activeCanvasId)?.edges ?? [],
    [canvases, activeCanvasId]
  );
  const canvasNodesRef = useRef<Node[]>([]);
  const canvasEdgesRef = useRef<Edge[]>([]);
  canvasNodesRef.current = canvasNodes;
  canvasEdgesRef.current = canvasEdges;

  const [groupStack, setGroupStack] = useState<GroupEntry[]>([]);
  const groupStackRef = useRef<GroupEntry[]>([]);
  useEffect(() => { groupStackRef.current = groupStack; }, [groupStack]);

  const nodes = useMemo(() => {
    if (groupStack.length === 0) return canvasNodes;
    return getNestedSubGraph(canvasNodes, groupStack).nodes;
  }, [canvasNodes, groupStack]);
  const edges = useMemo(() => {
    if (groupStack.length === 0) return canvasEdges;
    return getNestedSubGraph(canvasNodes, groupStack).edges;
  }, [canvasNodes, canvasEdges, groupStack]);

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

  const setViewNodes = useCallback((updater: Node[] | ((nds: Node[]) => Node[])) => {
    const fn = typeof updater === 'function' ? updater : (_: Node[]) => updater as Node[];
    if (groupStackRef.current.length === 0) { setNodes(updater); return; }
    setCanvases(prev => prev.map(c => c.id === activeCanvasIdRef.current
      ? { ...c, nodes: updateNestedSubGraph(c.nodes, groupStackRef.current, 'nodes', fn) }
      : c));
  }, [setNodes]);
  const setViewEdges = useCallback((updater: Edge[] | ((eds: Edge[]) => Edge[])) => {
    const fn = typeof updater === 'function' ? updater : (_: Edge[]) => updater as Edge[];
    if (groupStackRef.current.length === 0) { setEdges(updater); return; }
    setCanvases(prev => prev.map(c => c.id === activeCanvasIdRef.current
      ? { ...c, nodes: updateNestedSubGraph(c.nodes, groupStackRef.current, 'edges', fn) }
      : c));
  }, [setEdges]);
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
  const [rightPanelWidth, setRightPanelWidth] = useState(480);
  const [isTemplatesOpen, setIsTemplatesOpen] = useState(false);
  const [templates, setTemplates] = useState<{name: string, description: string, file: string}[]>([]);
  const [isProjectsOpen, setIsProjectsOpen] = useState(false);
  const [workDir, setWorkDir] = useState<string | null>(() => localStorage.getItem('vn-work-dir'));
  const [workDirFiles, setWorkDirFiles] = useState<string[]>([]);
  const [snapEnabled, setSnapEnabled] = useState(true);
  const [cursorFlowPos, setCursorFlowPos] = useState({ x: 400, y: 300 });
  const cursorFlowPosRef = useRef(cursorFlowPos);
  cursorFlowPosRef.current = cursorFlowPos;
  const isResizing = useRef(false);
  const nodesRef = useRef<any[]>([]);
  const edgesRef = useRef<any[]>([]);
  const addNodeRef = useRef<any>(null);
  nodesRef.current = nodes;
  edgesRef.current = edges;

  const { push: histPush, undo: histUndo, redo: histRedo, canUndo, canRedo } = useHistory();
  const lastParamPushRef = useRef(0);
  const pushSnapshot = useCallback(() => {
    histPush(activeCanvasId, { nodes: canvasNodesRef.current, edges: canvasEdgesRef.current });
  }, [histPush, activeCanvasId]);

  const [menu, setMenu] = useState<{ id: string, x: number, y: number } | null>(null);
  const [paneMenu, setPaneMenu] = useState<{ x: number, y: number } | null>(null);
  const [roiEditingId, setRoiEditingId] = useState<string | null>(null);
  const [cropEditingId, setCropEditingId] = useState<string | null>(null);
  const [annotatorEditingId, setAnnotatorEditingId] = useState<string | null>(null);
  const [manualPointsEditingId, setManualPointsEditingId] = useState<string | null>(null);
  const [lineEditingId, setLineEditingId] = useState<string | null>(null);
  const [visualizedNodeId, setVisualizedNodeId] = useState<string | null>(null);
  const [pickColorNodeId, setPickColorNodeId] = useState<string | null>(null);
  const [activePaletteIndex, setActivePaletteIndex] = useState(6);
  const [isPaletteSelectOpen, setIsPaletteSelectOpen] = useState(false);
  const [previewSize, setPreviewSize] = useState({ w: 400, h: 225 });
  const [previewPos, setPreviewPos] = useState({ x: 0, y: 0 });
  const [previewPopped, setPreviewPopped] = useState(false);
  const popoutWinRef = useRef<any>(null);
  const popoutLabelRef = useRef(`preview-popout-0`);
  const [previewZoom, setPreviewZoom] = useState(1);
  const previewZoomRef = useRef(1);
  const [previewPan, setPreviewPan] = useState({ x: 0, y: 0 });

  const [showAbout, setShowAbout] = useState(false);
  const isPanning = useRef(false);
  const panStart = useRef({ mx: 0, my: 0, px: 0, py: 0 });
  const previewResizing = useRef(false);
  const previewResizeStart = useRef({ x: 0, y: 0, w: 400, h: 225 });
  const previewAspect = useRef(16 / 9);
  const previewSizeRef = useRef(previewSize);
  previewSizeRef.current = previewSize;
  const previewResizeRef = useRef<HTMLDivElement>(null);
  const [instance, setInstance] = useState<any>(null);
  const [isRerouting, setIsRerouting] = useState(false);
  const [reroutePos, setReroutePos] = useState({ x: 0, y: 0 });
  const reroutePosRef = useRef({ x: 0, y: 0 });
  const connectingRef = useRef<{ nodeId: string; handleId: string; handleType: string } | null>(null);
  const connectionMadeRef = useRef(false);
  const rerouteDragRef = useRef<{
    capturedEdges: Edge[];
    handleType: 'source' | 'target';
    freeEndpoints: { x: number; y: number }[];
  } | null>(null);

  const handleCapture = useCallback(async (nodeId: string, base64: string) => {
    try {
      const path = await save({
        defaultPath: `capture_${nodeId}_${Date.now()}.png`,
        filters: [{ name: 'Image', extensions: ['png'] }]
      });
      if (path) {
        const res = await fetch(`data:image/png;base64,${base64}`);
        const arrayBuffer = await res.arrayBuffer();
        const bytes = new Uint8Array(arrayBuffer);
        await writeFile(path, bytes);
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
        ctx.fillStyle = '#1a1f26';
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

  const { frame, nodesData, nodesDataStore, pluginSchemas, isConnected, updateGraph, requestCapture, requestSnapshotToNode, setPreviewNode, lastCommands, notifications, dismissNotification, pushNotification, requestPyExport, computingNodeId } = useVisionEngine(handleCapture);

  const handlePopout = useCallback(async () => {
    const { WebviewWindow } = await import('@tauri-apps/api/webviewWindow');
    if (popoutWinRef.current) {
      try { await popoutWinRef.current.show(); await popoutWinRef.current.setFocus(); setPreviewPopped(true); return; } catch { popoutWinRef.current = null; }
    }
    const label = `preview-popout-${Date.now()}`;
    popoutLabelRef.current = label;
    const win = new WebviewWindow(label, {
      url: `${window.location.origin}/?popout=1`,
      title: 'Preview — VNStudio',
      width: 800, height: 450, minWidth: 320, minHeight: 180,
    });
    popoutWinRef.current = win;
    win.once('tauri://created', () => setPreviewPopped(true));
    win.once('tauri://destroyed', () => { setPreviewPopped(false); popoutWinRef.current = null; });
    win.once('tauri://error', (e: any) => { console.error('Popout error:', e); setPreviewPopped(false); popoutWinRef.current = null; });
  }, []);

  const handleBringBack = useCallback(async () => {
    if (popoutWinRef.current) { try { await popoutWinRef.current.close(); } catch {} popoutWinRef.current = null; }
    setPreviewPopped(false);
  }, []);

  const handleRemovePlotterPort = useCallback((nodeId: string, portId: string) => {
    pushSnapshot();
    setViewNodes((nds: Node[]) => nds.map((n: Node) => n.id === nodeId
      ? { ...n, data: { ...n.data, ports: ((n.data as any)?.ports ?? []).filter((p: any) => p.id !== portId) } }
      : n));
    setViewEdges((eds: Edge[]) => eds.filter(e => !(e.target === nodeId && e.targetHandle === portId)));
  }, [pushSnapshot, setViewNodes, setViewEdges]);

  const handleExportPy = useCallback(async (nodeId: string) => {
    try {
      pushNotification('Generating script…');
      const code = await requestPyExport(canvasNodesRef.current, canvasEdgesRef.current, nodeId);
      const path = await save({
        filters: [{ name: 'Python', extensions: ['py'] }], defaultPath: 'pipeline.py',
      });
      if (!path) return;
      await writeTextFile(path, code);
      pushNotification('Script saved');
    } catch (err: any) {
      pushNotification(`Export failed: ${err?.message ?? err}`, 'error');
    }
  }, [requestPyExport, pushNotification]);

  const handleSaveAsImage = useCallback((nodeId: string) => {
    const nodeType = nodes.find(n => n.id === nodeId)?.type;
    if (nodeType === 'sci_plotter') capturePlotterAsImage(nodeId);
    else requestCapture(nodeId);
  }, [nodes, capturePlotterAsImage, requestCapture]);

  const dynamicCategories = useMemo(() => {
    const cats = CATEGORIES.map(c => ({...c, nodes: [...c.nodes]}));
    const staticTypes = new Set(CATEGORIES.flatMap(c => c.nodes.map(n => n.type)));
    (pluginSchemas || []).forEach(schema => {
      if (staticTypes.has(schema.type)) return;
      const catIds = Array.isArray(schema.category) ? schema.category : [schema.category];
      catIds.forEach(catId => {
        let targetCat = cats.find((c: any) => c.id === catId);
        if (!targetCat) {
          targetCat = { id: catId, label: catId.charAt(0).toUpperCase() + catId.slice(1), icon: Layers, nodes: [] } as any;
          cats.splice(cats.length - 1, 0, targetCat as any);
        }
        targetCat!.nodes.push({ type: schema.type, label: schema.label, schema: schema } as any);
      });
    });
    return cats.sort((a, b) => a.label.localeCompare(b.label));
  }, [pluginSchemas]);

  const dynamicNodeTypes = useMemo(() => {
    const types: any = { ...nodeTypes };
    (pluginSchemas || []).forEach(schema => {
      if (!types[schema.type]) types[schema.type] = ColoredGenericCustomNode;
    });
    return types;
  }, [pluginSchemas]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isResizing.current) {
        const newWidth = window.innerWidth - e.clientX;
        setRightPanelWidth(Math.max(300, Math.min(800, newWidth)));
      }
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
    const el = previewResizeRef.current;
    if (!el) return;
    const onDown = (e: PointerEvent) => {
      e.stopPropagation();
      previewResizing.current = true;
      previewResizeStart.current = { x: e.clientX, y: e.clientY, w: previewSizeRef.current.w, h: previewSizeRef.current.h };
      const onMove = (ev: PointerEvent) => {
        if (!previewResizing.current) return;
        const dw = ev.clientX - previewResizeStart.current.x;
        const newW = Math.max(160, previewResizeStart.current.w + dw);
        setPreviewSize({ w: newW, h: Math.round(newW / previewAspect.current) });
      };
      const onUp = () => {
        previewResizing.current = false;
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
      };
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp);
    };
    el.addEventListener('pointerdown', onDown);
    return () => el.removeEventListener('pointerdown', onDown);
  }, []);

  useEffect(() => { document.title = "Vision Nodes Studio"; }, []);

  useEffect(() => {
    setCanvases(prev => prev.map(c => ({
      ...c,
      nodes: c.nodes.map(n => n.type === 'canvas_reroute'
        ? { ...n, style: { ...n.style, width: 8, height: (typeof n.style?.height === 'number' && n.style.height >= 24) ? n.style.height : 48 } }
        : n
      )
    })));
  }, []);

  const STATIC_IMAGE_PRODUCERS = useMemo(() => new Set([
    'input_webcam', 'input_image', 'input_movie', 'input_solid_color',
    'filter_canny', 'filter_blur', 'filter_gray', 'filter_threshold',
    'filter_morphology', 'filter_color_mask', 'geom_flip', 'geom_resize',
    'analysis_face_mp', 'analysis_hand_mp', 'analysis_pose_mp',
    'analysis_flow', 'analysis_flow_viz', 'util_roi_polygon', 'draw_overlay',
    'util_coord_to_mask', 'util_mask_blend', 'logic_python', 'output_display',
    'group_input', 'group_output',
  ]), []);

  const nodesWithData = useMemo(() => {
    const mapped = nodes.map(node => {
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
          onOpenEditor: (node.type === 'util_roi_polygon' || node.type === 'sci_interactive_calibration')
            ? () => setRoiEditingId(node.id)
            : node.type === 'geom_crop_rect'
            ? () => setCropEditingId(node.id)
            : node.type === 'tool_annotator'
            ? () => setAnnotatorEditingId(node.id)
            : node.type === 'manual_points'
            ? () => setManualPointsEditingId(node.id)
            : (node.type === 'feat_visual_size_gate' || node.type === 'sci_visual_measure')
            ? () => setLineEditingId(node.id)
            : undefined,
          onChangeParams: (p: any) => {
            setViewNodes(nds => nds.map(n => n.id === node.id ? { ...n, data: { ...n.data, params: { ...n.data.params, ...p } } } : n));
          },
          onExportPy: node.type === 'export_py' ? () => handleExportPy(node.id) : undefined,
          onRemovePort: (node.type === 'sci_plotter' || node.type === 'plotter_pro') ? (portId: string) => handleRemovePlotterPort(node.id, portId) : undefined,
          onToggleCollapse: node.type === 'canvas_frame' ? () => {
            pushSnapshot();
            setViewNodes(nds => nds.map(n => {
              if (n.id !== node.id) return n;
              const collapsed = !!(n.data?.params?.collapsed);
              if (!collapsed) {
                return { ...n, style: { ...n.style, height: 34 }, data: { ...n.data, params: { ...n.data.params, collapsed: true, savedHeight: (n.style?.height as number) ?? 400 } } };
              } else {
                return { ...n, style: { ...n.style, height: (n.data?.params?.savedHeight as number) ?? 400 }, data: { ...n.data, params: { ...n.data.params, collapsed: false } } };
              }
            }));
          } : undefined,
        }
      };
    });
    return mapped;
  }, [nodes, edges, pluginSchemas, visualizedNodeId, activePaletteIndex, handleExportPy, handleRemovePlotterPort]);

  const canVisualize = useCallback((nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return false;
    if (node.type === 'output_display') return true;
    if (STATIC_IMAGE_PRODUCERS.has(node.type || '')) return true;
    // group_node: visualizable if it has any image/mask output port
    if (node.type === 'group_node') {
      const outs: {id:string;color:string}[] = (node.data as any)?.outputs ?? [];
      if (outs.some(o => { const c = o.id.split('__')[0]; return c === 'image' || c === 'mask'; })) return true;
    }
    const schema = (pluginSchemas || []).find(s => s.type === node.type);
    if (schema?.outputs?.some((o: any) => o.color === 'image' || o.color === 'mask')) return true;
    return false;
  }, [nodes, pluginSchemas, STATIC_IMAGE_PRODUCERS]);

  const canSaveAsImage = useCallback((nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return false;
    const schema = (pluginSchemas || []).find(s => s.type === node.type);
    return !!(schema?.inputs?.some((p: any) => p.color === 'image' || p.color === 'mask') ||
              schema?.outputs?.some((p: any) => p.color === 'image' || p.color === 'mask'));
  }, [nodes, pluginSchemas]);

  const canBypass = useCallback((nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return false;
    if (['canvas_frame', 'canvas_note', 'canvas_reroute'].includes(node.type || '')) return false;
    const inTypes = new Set(
      edges.filter(e => e.target === nodeId).map(e => e.targetHandle?.split('__')[0]).filter(Boolean)
    );
    const outTypes = new Set(
      edges.filter(e => e.source === nodeId).map(e => e.sourceHandle?.split('__')[0]).filter(Boolean)
    );
    for (const t of inTypes) { if (outTypes.has(t)) return true; }
    return false;
  }, [nodes, edges]);

  const handleVisualize = useCallback((nodeId: string) => {
    const newId = visualizedNodeId === nodeId ? null : nodeId;
    let resolvedId = newId;
    if (newId) {
      const node = nodes.find(n => n.id === newId);
      if (node?.type === 'group_node') {
        // Resolve to the inner node that feeds group_output inside the subgraph.
        // The engine sees it as groupId::innerNodeId in the flattened graph.
        const sub = (node.data as any)?.subGraph;
        if (sub) {
          const gout = (sub.nodes as any[])?.find((n: any) => n.type === 'group_output');
          if (gout) {
            const feedEdge = (sub.edges as any[])?.find((e: any) => e.target === gout.id);
            if (feedEdge) resolvedId = `${newId}::${feedEdge.source}`;
          }
        }
      } else if (node?.type === 'group_output') {
        // Inside a group: resolve to the node feeding this group_output
        const feedEdge = edges.find(e => e.target === newId);
        if (feedEdge) resolvedId = feedEdge.source;
      } else if (node?.type === 'group_input') {
        // Inside a group: resolve to the node receiving from this group_input
        const feedEdge = edges.find(e => e.source === newId);
        if (feedEdge) resolvedId = feedEdge.target;
      }
    }
    setVisualizedNodeId(newId);
    setPreviewNode(resolvedId);
    setMenu(null);
  }, [visualizedNodeId, setPreviewNode, nodes, edges]);

  const handleRotate = useCallback((nodeId?: string) => {
    pushSnapshot();
    setViewNodes((nds: any) => nds.map((n: any) => {
      if (nodeId ? n.id === nodeId : n.selected) {
        const uiTypes = ['canvas_frame', 'canvas_note', 'canvas_reroute'];
        if (uiTypes.includes(n.type || '')) return n;
        return { ...n, data: { ...n.data, rotated: !(n.data as any)?.rotated } };
      }
      return n;
    }));
    setMenu(null);
  }, [pushSnapshot, setViewNodes]);

  const handleTeleport = useCallback((nodeId?: string) => {
    const targetId = nodeId ?? nodes.find((n: any) => n.selected)?.id;
    if (!targetId) return;
    const src = nodes.find((n: any) => n.id === targetId);
    if (!src) return;
    const skipTypes = ['canvas_note', 'canvas_reroute', 'canvas_frame', 'canvas_teleport', 'group_input', 'group_output'];
    if (skipTypes.includes(src.type ?? '')) return;
    const schema = pluginSchemas.find((s: any) => s.type === src.type);
    const sourceOutputs = schema?.outputs ?? [];
    if (sourceOutputs.length === 0) return;
    pushSnapshot();
    const newNode = {
      id: `teleport_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      type: 'canvas_teleport',
      position: { x: src.position.x + ((src.width as number) || 208) + 48, y: src.position.y },
      data: {
        label: src.data?.label ?? schema?.label ?? src.type,
        params: {
          source_id: src.id,
          source_type: src.type,
          color_index: src.data?.params?.color_index,
          bg_color: src.data?.params?.bg_color,
          text_color: src.data?.params?.text_color,
        },
        source_outputs: sourceOutputs,
        activePaletteIndex: src.data?.activePaletteIndex,
      },
      width: Math.min((src.width as number) || 208, 200),
      selected: false,
    };
    setViewNodes((nds: any) => [...nds, newNode]);
    setMenu(null);
  }, [nodes, pluginSchemas, pushSnapshot, setViewNodes]);

  const selectedNode = useMemo(() => nodesWithData.find((n) => n.id === selectedNodeId) || null, [nodesWithData, selectedNodeId]);
  const [selectedNodeLiveData, setSelectedNodeLiveData] = useState<Record<string, any>>({});
  useEffect(() => {
    if (!selectedNodeId) { setSelectedNodeLiveData({}); return; }
    setSelectedNodeLiveData(nodesDataStore.getNode(selectedNodeId));
    return nodesDataStore.subscribe(selectedNodeId, () => {
      setSelectedNodeLiveData(nodesDataStore.getNode(selectedNodeId));
    });
  }, [selectedNodeId, nodesDataStore]);

  const exposedGroupParams = useMemo((): ExposedParam[] => {
    if (selectedNode?.type !== 'group_node') return [];
    const subNodes: any[] = (selectedNode.data as any).subGraph?.nodes ?? [];
    const result: ExposedParam[] = [];
    for (const child of subNodes) {
      const exposed: string[] = child.data?.exposedParams ?? [];
      if (exposed.length === 0) continue;
      const schema = (pluginSchemas || []).find((s: any) => s.type === child.type);
      for (const paramId of exposed) {
        const paramSpec = schema?.params?.find((ps: any) => ps.id === paramId);
        if (!paramSpec) continue;
        result.push({
          nodeId: child.id,
          nodeLabel: child.data?.label || child.type,
          paramId,
          paramSpec,
          currentValue: child.data?.params?.[paramId] ?? paramSpec.default,
          customLabel: (child.data?.exposedParamLabels as Record<string, string> | undefined)?.[paramId],
        });
      }
    }
    return result;
  }, [selectedNode, pluginSchemas]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    if (changes.some(c => c.type === 'remove')) pushSnapshot();
    setViewNodes((nds) => applyNodeChanges(changes, nds));
  }, [pushSnapshot, setViewNodes]);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    if (changes.some(c => c.type === 'remove')) pushSnapshot();
    setViewEdges((eds) => applyEdgeChanges(changes, eds));
  }, [pushSnapshot, setViewEdges]);

  const onConnectStart = useCallback((_: any, { nodeId, handleId, handleType }: any) => {
    connectingRef.current = { nodeId, handleId, handleType };
    connectionMadeRef.current = false;
  }, []);

  const { onConnect } = useConnectionHandling({
    setViewNodes, setViewEdges, pushSnapshot, nodesRef, edgesRef,
    groupStackRef, activeCanvasIdRef, setCanvases, connectionMadeRef,
    pluginSchemas,
  });

  useEffect(() => {
    const timer = setTimeout(() => {
      if (isConnected) updateGraph(canvasNodes, canvasEdges);
    }, 100);
    return () => clearTimeout(timer);
  }, [canvasNodes, canvasEdges, isConnected, updateGraph]);

  // Sync mainConnected flag on Display nodes from actual edges
  useEffect(() => {
    setViewNodes(nds => nds.map(n => {
      if (n.type !== 'output_display') return n;
      const hasMain = canvasEdges.some(e => e.target === n.id && e.targetHandle?.endsWith('__main'));
      const cur = !!(n.data as any)?.mainConnected;
      if (hasMain === cur) return n;
      return { ...n, data: { ...n.data, mainConnected: hasMain } };
    }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canvasEdges]);

  const onConnectEnd = useCallback((event: any) => {
    if (!connectionMadeRef.current && connectingRef.current) {
      const target = event.target as HTMLElement;
      if (target?.closest('.react-flow__handle')) {
        connectingRef.current = null;
        connectionMadeRef.current = false;
        return;
      }
      setPendingConnection({
        sourceNode: connectingRef.current.nodeId,
        sourceHandle: connectingRef.current.handleId,
        type: connectingRef.current.handleType,
        clientX: event.clientX,
        clientY: event.clientY,
      });
      setIsAddMenuOpen(true);
    }
    connectingRef.current = null;
    connectionMadeRef.current = false;
  }, []);

  const isValidConnection = useCallback((connection: Connection) => {
    if (!connection.sourceHandle || !connection.targetHandle) return false;
    const sourceType = connection.sourceHandle.split('__')[0];
    const targetType = connection.targetHandle.split('__')[0];
    if (targetType === 'any' || sourceType === 'any') return true;
    const sourceColor = N.HANDLE_COLORS[sourceType as keyof typeof N.HANDLE_COLORS] || sourceType;
    const targetColor = N.HANDLE_COLORS[targetType as keyof typeof N.HANDLE_COLORS] || targetType;
    if (sourceColor === targetColor) return true;
    // Typed lists compatible with generic list ports
    const LIST_COLOR = N.HANDLE_COLORS['list'];
    const listCompatible = new Set(['points', 'contours', 'regions', 'vectors']);
    if (targetColor === LIST_COLOR && listCompatible.has(sourceType)) return true;
    if (sourceColor === LIST_COLOR && listCompatible.has(targetType)) return true;
    // mask ↔ markers: both are label/binary maps, engine handles conversion
    const MASK_COLOR    = N.HANDLE_COLORS['mask'];
    const MARKERS_COLOR = N.HANDLE_COLORS['markers'];
    if ((sourceColor === MASK_COLOR && targetColor === MARKERS_COLOR) ||
        (sourceColor === MARKERS_COLOR && targetColor === MASK_COLOR)) return true;
    return false;
  }, []);

  const onNodeDragStop = useCallback((event: React.MouseEvent, node: Node) => {
    if (!event.shiftKey) return;
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
      setViewEdges((eds) => {
        return eds.filter(e => e.id !== edgeToInsert.id).concat([
          { id: `e-${Date.now()}-1`, source: edgeToInsert.source, target: node.id, sourceHandle: edgeToInsert.sourceHandle, targetHandle: 'main' },
          { id: `e-${Date.now()}-2`, source: node.id, target: edgeToInsert.target, sourceHandle: 'main', targetHandle: edgeToInsert.targetHandle }
        ]);
      });
    }
  }, [nodes, edges, setViewEdges]);

  const updateNodeParams = (id: string, params: Record<string, unknown>) => {
    const now = Date.now();
    if (now - lastParamPushRef.current > 500) {
      pushSnapshot();
      lastParamPushRef.current = now;
    }
    setViewNodes((nds) => nds.map((node) => {
        if (node.id === id) return { ...node, data: { ...node.data, params: { ...node.data.params, ...params } } };
        return node;
    }));
  };

  const toggleExposedParam = useCallback((nodeId: string, paramId: string) => {
    setViewNodes(nds => nds.map(n => {
      if (n.id !== nodeId) return n;
      const cur = (n.data.exposedParams as string[] | undefined) ?? [];
      const next = cur.includes(paramId) ? cur.filter(id => id !== paramId) : [...cur, paramId];
      return { ...n, data: { ...n.data, exposedParams: next } };
    }));
  }, [setViewNodes]);

  const updateGroupChildParams = useCallback((groupNodeId: string, childNodeId: string, params: Record<string, unknown>) => {
    const now = Date.now();
    if (now - lastParamPushRef.current > 500) {
      pushSnapshot();
      lastParamPushRef.current = now;
    }
    setViewNodes(nds => nds.map(n => {
      if (n.id !== groupNodeId) return n;
      const sub = (n.data as any)?.subGraph ?? { nodes: [], edges: [] };
      return {
        ...n, data: {
          ...n.data, subGraph: {
            ...sub, nodes: sub.nodes.map((cn: any) =>
              cn.id === childNodeId
                ? { ...cn, data: { ...cn.data, params: { ...cn.data.params, ...params } } }
                : cn
            )
          }
        }
      };
    }));
  }, [setViewNodes, pushSnapshot]);

  const renameExposedParam = useCallback((childNodeId: string, paramId: string, newLabel: string) => {
    if (!selectedNode || selectedNode.type !== 'group_node') return;
    setViewNodes(nds => nds.map(n => {
      if (n.id !== selectedNode.id) return n;
      const sub = (n.data as any)?.subGraph ?? { nodes: [], edges: [] };
      return {
        ...n, data: {
          ...n.data, subGraph: {
            ...sub, nodes: sub.nodes.map((cn: any) =>
              cn.id === childNodeId
                ? { ...cn, data: { ...cn.data, exposedParamLabels: { ...(cn.data.exposedParamLabels ?? {}), [paramId]: newLabel } } }
                : cn
            ),
          },
        },
      };
    }));
  }, [selectedNode, setViewNodes]);

  const handleUndo = useCallback(() => {
    const prev = histUndo(activeCanvasId, { nodes: canvasNodesRef.current, edges: canvasEdgesRef.current });
    if (!prev) return;
    setGroupStack([]); groupStackRef.current = [];
    setNodes(prev.nodes); setEdges(prev.edges);
    if (isConnected) updateGraph(prev.nodes, prev.edges);
  }, [histUndo, activeCanvasId, setNodes, setEdges, isConnected, updateGraph]);

  const handleRedo = useCallback(() => {
    const next = histRedo(activeCanvasId, { nodes: canvasNodesRef.current, edges: canvasEdgesRef.current });
    if (!next) return;
    setGroupStack([]); groupStackRef.current = [];
    setNodes(next.nodes); setEdges(next.edges);
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
        ...n, id: newId, selected: true,
        position: mousePos ? { x: mousePos.x + (n.position.x - copiedNodes[0].position.x), y: mousePos.y + (n.position.y - copiedNodes[0].position.y) } : { x: n.position.x + 50, y: n.position.y + 50 }
      };
    });
    const newEdges = copiedEdges.map((e: any) => ({
      ...e, id: `e-${Date.now()}-${Math.random()}`, source: idMap[e.source], target: idMap[e.target]
    }));
    setViewNodes(nds => [...nds.map(n => ({...n, selected: false})), ...newNodes]);
    setViewEdges(eds => [...eds, ...newEdges]);
  }, [setViewNodes, setViewEdges]);

  const duplicateNodes = useCallback(() => {
    const selected = nodes.filter(n => n.selected);
    if (selected.length === 0) return;
    pushSnapshot();
    const idMap: Record<string, string> = {};
    const newNodes = selected.map(n => {
      const newId = `node-${Date.now()}-${Math.random()}`;
      idMap[n.id] = newId;
      return { ...n, id: newId, selected: true, position: { x: n.position.x + 40, y: n.position.y + 40 } };
    });
    const selectedIds = new Set(selected.map(n => n.id));
    const newEdges = edges
      .filter(e => selectedIds.has(e.source) && selectedIds.has(e.target))
      .map(e => ({ ...e, id: `e-${Date.now()}-${Math.random()}`, source: idMap[e.source], target: idMap[e.target] }));
    setViewNodes(nds => [...nds.map(n => ({ ...n, selected: false })), ...newNodes]);
    setViewEdges(eds => [...eds, ...newEdges]);
  }, [nodes, edges, pushSnapshot, setViewNodes, setViewEdges]);

  const refreshWorkDir = useCallback(async (dir: string) => {
    try {
      const entries = await readDir(dir);
      const files = entries
        .filter(e => !e.isDirectory && e.name?.endsWith('.vn'))
        .map(e => e.name!)
        .sort();
      setWorkDirFiles(files);
    } catch { setWorkDirFiles([]); }
  }, []);

  useEffect(() => {
    if (workDir) refreshWorkDir(workDir);
  }, [workDir, refreshWorkDir]);

  // Auto-load favorite files for each canvas on startup
  useEffect(() => {
    const favorites = JSON.parse(localStorage.getItem('vn-favorites') || '{}') as Record<string, string>;
    if (Object.keys(favorites).length === 0) return;
    (async () => {
      for (const [canvasId, filePath] of Object.entries(favorites)) {
        try {
          const content = await readTextFile(filePath);
          const { nodes: rawNodes, edges: newEdges } = JSON.parse(content);
          const newNodes = rawNodes.map((n: any) =>
            n.type === 'canvas_reroute'
              ? { ...n, style: { ...n.style, width: 8, height: (typeof n.style?.height === 'number' && n.style.height >= 24) ? n.style.height : 48 } }
              : n
          );
          setCanvases(prev => prev.map(c =>
            c.id === canvasId ? { ...c, nodes: newNodes, edges: newEdges, filePath } : c
          ));
        } catch { /* file may have moved — silently skip */ }
      }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleFavorite = useCallback(() => {
    if (!activeFilePath) return;
    const next = { ...favoriteFiles };
    if (next[activeCanvasId] === activeFilePath) {
      delete next[activeCanvasId];
    } else {
      next[activeCanvasId] = activeFilePath;
    }
    setFavoriteFiles(next);
    localStorage.setItem('vn-favorites', JSON.stringify(next));
  }, [activeFilePath, activeCanvasId, favoriteFiles]);

  const setWorkDirAndSave = async () => {
    const dir = await open({ directory: true, multiple: false });
    if (dir && typeof dir === 'string') {
      localStorage.setItem('vn-work-dir', dir);
      setWorkDir(dir);
    }
  };

  const confirmUnsaved = async (): Promise<boolean> => {
    if (!activeFilePath && nodes.length === 0) return true;
    const saveQ = await ask(
      activeFilePath
        ? `"${activeFilePath.split(/[\\/]/).pop()}" has unsaved changes. Save before continuing?`
        : 'Current scene has unsaved changes. Save before continuing?',
      { title: 'Unsaved Changes', kind: 'warning', okLabel: 'Save', cancelLabel: 'Discard' }
    );
    if (saveQ) await saveProject();
    return true;
  };

  const {
    saveProject, saveProjectAs, saveProjectIncremental,
    loadProject, loadProjectFromPath, applyTemplateData, loadTemplate,
  } = useFileOperations({
    canvasNodes, canvasEdges, activeFilePath, setActiveFilePath, pushNotification,
    setNodes, setEdges, setGroupStack, groupStackRef,
    updateGraph, setPreviewSize, setPreviewPos, setActivePaletteIndex,
    setVisualizedNodeId, setPreviewNode,
    workDir, refreshWorkDir,
    previewSize, previewPos, activePaletteIndex, visualizedNodeId,
    confirmUnsaved,
  });

  useEffect(() => {
    fetch('/templates/manifest.json')
      .then(r => r.json())
      .then(setTemplates)
      .catch(e => console.error('Failed to load templates manifest:', e));
  }, []);

  const enterGroup = useCallback((groupNodeId: string) => {
    const newStack = [...groupStackRef.current, { groupNodeId }];
    setGroupStack(newStack);
    groupStackRef.current = newStack;
    setSelectedNodeId(null);
    instance?.fitView({ duration: 300 });
  }, [instance]);

  const exitGroup = useCallback(() => {
    if (groupStackRef.current.length === 0) return;
    const newStack = groupStackRef.current.slice(0, -1);
    setGroupStack(newStack);
    groupStackRef.current = newStack;
    setSelectedNodeId(null);
    instance?.fitView({ duration: 300 });
  }, [instance]);

  const { groupSelectedNodes, ungroupNode } = useGroupOperations({
    nodesRef, edgesRef, pushSnapshot, setViewNodes, setViewEdges, instance,
  });

  useEffect(() => { if (isConnected) updateGraph(canvasNodesRef.current, canvasEdgesRef.current); }, [isConnected, updateGraph]);
  useEffect(() => {
    setSelectedNodeId(null);
    setGroupStack([]);
    groupStackRef.current = [];
    if (isConnected) updateGraph(canvasNodesRef.current, canvasEdgesRef.current);
  }, [activeCanvasId, isConnected, updateGraph]);

  const alignNodes = useCallback((direction: 'horizontal' | 'vertical') => {
    setViewNodes(nds => {
      const selNodes = nds.filter(n => n.selected);
      if (selNodes.length < 2) return nds;
      const avgX = selNodes.reduce((acc, n) => acc + n.position.x, 0) / selNodes.length;
      const avgY = selNodes.reduce((acc, n) => acc + n.position.y, 0) / selNodes.length;
      return nds.map(n => {
        if (!n.selected) return n;
        return { ...n, position: { x: direction === 'vertical' ? avgX : n.position.x, y: direction === 'horizontal' ? avgY : n.position.y } };
      });
    });
  }, [setViewNodes]);

  const addNode = useCallback((type: string, label: string, schema?: any, initialParams: any = {}, dropPosition?: { x: number, y: number }, skipSnapshot = false) => {
    if (!skipSnapshot) pushSnapshot();
    const id = `node-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const defaultStyle: Record<string, any> = {
      data_inspector: { width: 220, height: 200 },
      canvas_note: { width: 300, height: 180 },
      canvas_reroute: { width: 8, height: 48 },
      canvas_frame: { width: 500, height: 400, zIndex: -1 },
      util_csv_export: { width: 240 },
      sci_plotter: { width: 320, height: 220 },
      plotter_pro: { width: 320, height: 220 },
    };
    const nodeStyle = defaultStyle[type] || {};
    const nw = (nodeStyle.width ?? 160) as number;
    const nh = (nodeStyle.height ?? 80) as number;
    
    let position = dropPosition;
    if (!position) {
      position = pendingConnection
        ? (instance?.screenToFlowPosition({ x: pendingConnection.clientX, y: pendingConnection.clientY }) ?? { x: pendingConnection.clientX, y: pendingConnection.clientY })
        : { x: cursorFlowPosRef.current.x - nw / 2, y: cursorFlowPosRef.current.y - nh / 2 };
    }
    setViewNodes((nds) => {
      const nextNodes = [...nds, { id, type, position, style: nodeStyle, data: { label, params: initialParams, schema } }];
      if (pendingConnection && pendingConnection.sourceNode) {
        setTimeout(() => {
          const newEl = document.querySelector(`[data-id="${id}"]`);
          if (!newEl) return;
          const expectedColor = pendingConnection.sourceHandle.split('__')[0];
          const targetClass = pendingConnection.type === 'source' ? 'target' : 'source';
          const handles = Array.from(newEl.querySelectorAll(`.react-flow__handle.${targetClass}`));
          const match = handles.find(h => h.getAttribute('data-handleid')?.startsWith(`${expectedColor}__`)) || handles[0];
          if (match) {
            const matchedHandleId = match.getAttribute('data-handleid');
            if (matchedHandleId) {
              setViewEdges(eds => {
                return [...eds, {
                  id: `e-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                  source: pendingConnection.type === 'source' ? pendingConnection.sourceNode : id,
                  target: pendingConnection.type === 'source' ? id : pendingConnection.sourceNode,
                  sourceHandle: pendingConnection.type === 'source' ? pendingConnection.sourceHandle : matchedHandleId,
                  targetHandle: pendingConnection.type === 'source' ? matchedHandleId : pendingConnection.sourceHandle
                }];
              });
            }
          }
        }, 50);
      }
      return nextNodes;
    });
    setIsAddMenuOpen(false);
    setPendingConnection(null);
  }, [pushSnapshot, pendingConnection, instance, setViewNodes, setViewEdges, setIsAddMenuOpen, setPendingConnection]);
  addNodeRef.current = addNode;

  useEffect(() => {
    if (lastCommands && lastCommands.length > 0) {
      console.log("[Engine Commands] Processing:", lastCommands);
      lastCommands.forEach(cmd => {
        if (cmd.type === 'add_node') {
          let label = "New Node";
          if (cmd.node_type === 'input_image') label = "Captured Frame";
          if (cmd.node_type === 'input_movie') label = "Recorded Video";
          console.log("[Engine Commands] addNode call:", cmd.node_type, label, cmd.params);
          addNode(cmd.node_type, label, null, cmd.params);
        } else if (cmd.type === 'set_param') {
          setViewNodes(nds => nds.map(n =>
            n.id === cmd.node_id
              ? { ...n, data: { ...n.data, params: { ...n.data.params, ...cmd.params } } }
              : n
          ));
        }
      });
    }
  }, [lastCommands, addNode]);

  // Listen for snapshot-to-node events from the inspector panel
  useEffect(() => {
    const handler = (e: Event) => {
      const nodeId = (e as CustomEvent).detail?.nodeId;
      if (nodeId) {
        console.log('[Snapshot] Sending snapshot_to_node WS message for', nodeId);
        requestSnapshotToNode(nodeId);
      }
    };
    window.addEventListener('snapshot-to-node', handler);
    return () => window.removeEventListener('snapshot-to-node', handler);
  }, [requestSnapshotToNode]);


  const newProject = useCallback(async () => {
    await confirmUnsaved();
    pushSnapshot();
    const n: any[] = []; const e: any[] = [];
    setGroupStack([]); groupStackRef.current = [];
    setNodes(n); setEdges(e); setActiveFilePath(null);
    updateGraph(n, e);
  }, [confirmUnsaved, pushSnapshot, setNodes, setEdges, setActiveFilePath, updateGraph]);

  useKeyboardShortcuts({
    copyNodes, pasteNodes, duplicateNodes, handleUndo, handleRedo,
    pushSnapshot, setViewNodes, nodesRef, instance,
    groupSelectedNodes, exitGroup, groupStackRef, canBypass,
    setIsAddMenuOpen, saveProject, loadProject, setPendingConnection, handleRotate,
    handleVisualize, handleTeleport,
  });

  useEffect(() => {
    const handleRemoveEdge = (e: any) => {
      const { nodeId, handleId, type } = e.detail;
      setViewEdges((eds) => {
        return eds.filter(edge => {
          if (type === 'target') return !(edge.target === nodeId && edge.targetHandle === handleId);
          if (type === 'source') return !(edge.source === nodeId && edge.sourceHandle === handleId);
          return true;
        });
      });
    };
    window.addEventListener('remove-handle-edge', handleRemoveEdge);
    return () => window.removeEventListener('remove-handle-edge', handleRemoveEdge);
  }, [setViewEdges]);

  // Handle File Drag & Drop from Tauri
  useEffect(() => {
    if (!instance) return;
    const unlisten = listen('tauri://drag-drop', (event: any) => {
      const { paths, position } = event.payload as { paths: string[], position: { x: number, y: number } };
      if (!paths || paths.length === 0) return;

      // Push a single snapshot for the entire drop operation
      pushSnapshot();

      // Convert window position to flow position
      const flowPos = instance.screenToFlowPosition({ x: position.x, y: position.y });

      paths.forEach((p, index) => {
        const ext = p.split('.').pop()?.toLowerCase() || '';
        const fileName = p.split(/[\\/]/).pop() || 'File';
        
        // Offset multiple files slightly
        const finalPos = { x: flowPos.x + index * 20, y: flowPos.y + index * 20 };

        if (['jpg', 'jpeg', 'png', 'bmp', 'webp'].includes(ext)) {
          addNode('input_image', fileName, undefined, { path: p }, finalPos, true);
        } else if (['mp4', 'avi', 'mov', 'mkv', 'webm', 'm4v'].includes(ext)) {
          addNode('input_movie', fileName, undefined, { path: p }, finalPos, true);
        } else if (['wav', 'mp3', 'flac', 'ogg', 'm4a', 'aac'].includes(ext)) {
          addNode('plugin_audio_input', fileName, undefined, { path: p }, finalPos, true);
        } else if (['tif', 'tiff', 'jp2'].includes(ext)) {
          addNode('geo_geotiff_reader', fileName, undefined, { file_path: p }, finalPos, true);
        } else if (ext === 'vn') {
          confirmUnsaved().then(ok => { if (ok) loadProjectFromPath(p); });
        }
      });
    });
    return () => { unlisten.then(f => f()); };
  }, [instance, addNode, confirmUnsaved, loadProjectFromPath, pushSnapshot]);

  useEffect(() => {
    const onMouseDown = (e: MouseEvent) => {
      if (!e.shiftKey) return;
      const target = e.target as HTMLElement;
      if (!target.classList.contains('react-flow__handle')) return;
      const handleId = target.dataset.handleid;
      const nodeId = target.dataset.nodeid;
      if (!handleId || !nodeId) return;
      const sourceEdges = edgesRef.current.filter(e => e.source === nodeId && e.sourceHandle === handleId);
      const targetEdges = edgesRef.current.filter(e => e.target === nodeId && e.targetHandle === handleId);
      const handleType: 'source' | 'target' = sourceEdges.length > 0 ? 'source' : 'target';
      const connectedEdges = sourceEdges.length > 0 ? sourceEdges : targetEdges;
      if (connectedEdges.length === 0) return;
      e.stopImmediatePropagation(); e.preventDefault();
      const freeEndpoints = connectedEdges.map(edge => {
        const freeNodeId = handleType === 'source' ? edge.target : edge.source;
        const freeHandleId = handleType === 'source' ? edge.targetHandle : edge.sourceHandle;
        const el = freeHandleId
          ? document.querySelector(`[data-nodeid="${freeNodeId}"][data-handleid="${freeHandleId}"]`) as HTMLElement | null
          : null;
        const rect = el?.getBoundingClientRect();
        return { x: rect ? rect.left + rect.width / 2 : e.clientX, y: rect ? rect.top + rect.height / 2 : e.clientY };
      });
      rerouteDragRef.current = { capturedEdges: connectedEdges, handleType, freeEndpoints };
      reroutePosRef.current = { x: e.clientX, y: e.clientY };
      setReroutePos({ x: e.clientX, y: e.clientY });
      setIsRerouting(true);
    };
    document.addEventListener('mousedown', onMouseDown, { capture: true });
    return () => document.removeEventListener('mousedown', onMouseDown, { capture: true });
  }, []);

  useEffect(() => {
    if (!isRerouting) return;
    const onMove = (e: MouseEvent) => {
      reroutePosRef.current = { x: e.clientX, y: e.clientY };
      setReroutePos({ x: e.clientX, y: e.clientY });
    };
    const onUp = () => {
      const drag = rerouteDragRef.current;
      if (!drag || !instance) { setIsRerouting(false); return; }
      const { capturedEdges, handleType } = drag;
      const { x: mx, y: my } = reroutePosRef.current;
      const flowPos = instance.screenToFlowPosition({ x: mx, y: my });
      const rerouteId = `reroute-${Date.now()}`;
      const t = Date.now();
      const newEdges: Edge[] = [];
      const initialPorts: { id: string; color: string; label: string }[] = [];
      const mkPort = (i: number) => {
        const portId = `any__out_${i}_${Math.random().toString(36).substr(2, 6)}`;
        initialPorts.push({ id: portId, color: 'any', label: `out_${i}` });
        return portId;
      };
      if (handleType === 'source') {
        newEdges.push({ id: `rr-in-${t}`, source: capturedEdges[0].source, sourceHandle: capturedEdges[0].sourceHandle, target: rerouteId, targetHandle: 'any__in' });
        capturedEdges.forEach((edge, i) => {
          newEdges.push({ id: `rr-out-${t}-${i}`, source: rerouteId, sourceHandle: mkPort(i), target: edge.target, targetHandle: edge.targetHandle });
        });
      } else {
        newEdges.push({ id: `rr-in-${t}`, source: capturedEdges[0].source, sourceHandle: capturedEdges[0].sourceHandle, target: rerouteId, targetHandle: 'any__in' });
        newEdges.push({ id: `rr-out-${t}`, source: rerouteId, sourceHandle: mkPort(0), target: capturedEdges[0].target, targetHandle: capturedEdges[0].targetHandle });
      }
      const height = Math.max(48, 14 + initialPorts.length * 20 + 20);
      const rerouteNode: Node = {
        id: rerouteId, type: 'canvas_reroute',
        position: { x: flowPos.x - 4, y: flowPos.y - height / 2 },
        data: { label: 'Reroute', params: {}, ports: initialPorts },
        style: { width: 8, height },
      };
      pushSnapshot();
      setViewNodes(nds => [...nds, rerouteNode]);
      setViewEdges(eds => [...eds.filter(e => !capturedEdges.some(ce => ce.id === e.id)), ...newEdges]);
      document.body.style.cursor = '';
      rerouteDragRef.current = null;
      setIsRerouting(false);
    };
    document.body.style.cursor = 'crosshair';
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      document.body.style.cursor = '';
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [isRerouting, instance, pushSnapshot, setViewNodes, setViewEdges]);

  const coloredEdges = useMemo(() => {
    const resolveColor = (edge: any, visited = new Set()): string => {
      if (!edge || visited.has(edge.id)) return '#555';
      visited.add(edge.id);
      const sourceNode = nodes.find(n => n.id === edge.source);
      if (sourceNode?.type === 'canvas_reroute') {
        const incomingEdge = edges.find(e => e.target === sourceNode.id);
        if (incomingEdge) return resolveColor(incomingEdge, visited);
      }
      if (edge.sourceHandle) {
        const sourceType = edge.sourceHandle.split('__')[0];
        return (N.HANDLE_COLORS as any)[sourceType] || '#555';
      }
      return '#555';
    };
    const hiddenIds = isRerouting && rerouteDragRef.current
      ? new Set(rerouteDragRef.current.capturedEdges.map(e => e.id))
      : null;
    return edges
      .filter(edge => !hiddenIds || !hiddenIds.has(edge.id))
      .map((edge: any) => ({
        ...edge, style: { ...edge.style, stroke: resolveColor(edge), strokeWidth: 2 },
      }));
  }, [edges, nodes, isRerouting]);

  return (
    <div className="w-full h-screen bg-[#2c333f] flex flex-col text-white font-sans overflow-hidden select-none">
      <Header
        isConnected={isConnected}
        activeCanvasId={activeCanvasId}
        canvases={canvases}
        activeFilePath={activeFilePath}
        canUndo={canUndo(activeCanvasId)}
        canRedo={canRedo(activeCanvasId)}
        snapEnabled={snapEnabled}
        activePaletteIndex={activePaletteIndex}
        isPaletteSelectOpen={isPaletteSelectOpen}
        isProjectsOpen={isProjectsOpen}
        isTemplatesOpen={isTemplatesOpen}
        workDir={workDir}
        workDirFiles={workDirFiles}
        templates={templates}
        setActiveCanvasId={setActiveCanvasId}
        handleUndo={handleUndo}
        handleRedo={handleRedo}
        alignNodes={alignNodes}
        snapToggle={() => setSnapEnabled(!snapEnabled)}
        addNode={addNode}
        saveProject={saveProject}
        saveProjectAs={saveProjectAs}
        saveProjectIncremental={saveProjectIncremental}
        loadProject={loadProject}
        newProject={newProject}
        setIsPaletteSelectOpen={setIsPaletteSelectOpen}
        setActivePaletteIndex={setActivePaletteIndex}
        setIsProjectsOpen={setIsProjectsOpen}
        setIsTemplatesOpen={setIsTemplatesOpen}
        setWorkDirAndSave={setWorkDirAndSave}
        refreshWorkDir={refreshWorkDir}
        confirmUnsaved={confirmUnsaved}
        loadProjectFromPath={loadProjectFromPath}
        loadTemplate={loadTemplate}
        setShowAbout={setShowAbout}
      />

      <div className="flex-1 flex w-full relative">
        <div className="flex-1 relative overflow-hidden bg-[#1e2530]" onContextMenu={e => e.preventDefault()}>
          <NodesDataContext.Provider value={nodesDataStore}>
          <ComputingNodeContext.Provider value={computingNodeId}>
          <ReactFlow
            nodes={nodesWithData} edges={coloredEdges}
            onInit={setInstance}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} 
            onConnectStart={onConnectStart} onConnect={onConnect} onConnectEnd={onConnectEnd} isValidConnection={isValidConnection}
            onNodeDragStart={() => pushSnapshot()}
            onNodeDragStop={onNodeDragStop}
            onEdgeClick={(event, edge) => {
              if (event.shiftKey && instance) {
                pushSnapshot();
                const flowPos = instance.screenToFlowPosition({ x: event.clientX, y: event.clientY });
                const rerouteId = `reroute-${Date.now()}`;
                const portId = `any__out_0_${Math.random().toString(36).substr(2, 6)}`;
                const t = Date.now();
                setViewNodes(nds => [...nds, {
                  id: rerouteId, type: 'canvas_reroute',
                  position: { x: flowPos.x - 4, y: flowPos.y - 24 },
                  data: { label: 'Reroute', params: {}, ports: [{ id: portId, color: 'any', label: 'out_0' }] },
                  style: { width: 8, height: 48 },
                }]);
                setViewEdges(eds => [
                  ...eds.filter(e => e.id !== edge.id),
                  { id: `rr-in-${t}`, source: edge.source, sourceHandle: edge.sourceHandle, target: rerouteId, targetHandle: 'any__in' },
                  { id: `rr-out-${t}`, source: rerouteId, sourceHandle: portId, target: edge.target, targetHandle: edge.targetHandle },
                ]);
              } else {
                pushSnapshot();
                setViewEdges(eds => eds.filter(e => e.id !== edge.id));
              }
            }}
            nodeTypes={dynamicNodeTypes}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            onNodeDoubleClick={(_, node) => { if (node.type === 'group_node') enterGroup(node.id); }}
            onPaneClick={(e) => { setSelectedNodeId(null); setMenu(null); setPaneMenu(null); setIsAddMenuOpen(false); if (instance) { setCursorFlowPos(instance.screenToFlowPosition({ x: e.clientX, y: e.clientY })); } }}
            onDoubleClick={(e) => { if ((e.target as HTMLElement).classList.contains('react-flow__pane')) { instance?.fitView({ duration: 400 }); setTimeout(() => instance?.zoomOut({ duration: 300 }), 420); } }}
            onNodeContextMenu={(e, node) => {
              e.preventDefault(); setPaneMenu(null);
              if (node.type !== 'canvas_reroute') setMenu({ id: node.id, x: e.clientX, y: e.clientY });
            }}
            onPaneContextMenu={(e) => {
              e.preventDefault(); setMenu(null);
              if (instance) setCursorFlowPos(instance.screenToFlowPosition({ x: e.clientX, y: e.clientY }));
              const selectedCount = nodes.filter(n => n.selected).length;
              if (selectedCount > 1) { setPaneMenu({ x: (e as any).clientX, y: (e as any).clientY }); }
              else { setIsAddMenuOpen(true); }
            }}
            panOnDrag={[1, 2]} panOnScroll={false} zoomOnScroll={true} selectionOnDrag={true}
            snapToGrid={snapEnabled} snapGrid={[20, 20]}
            defaultViewport={{ x: 0, y: 0, zoom: 0.7 }}
            fitView
          >
            <Background color="rgba(255, 255, 255, 0.04)" variant={BackgroundVariant.Lines} gap={40} size={1} />
            <Controls className="bg-[#3d4452] border-[#4f5b6b] fill-white">
              {(() => {
                const isFav = !!activeFilePath && favoriteFiles[activeCanvasId] === activeFilePath;
                const noFile = !activeFilePath;
                return (
                  <ControlButton
                    onClick={toggleFavorite}
                    title={noFile ? 'Save the file first' : isFav ? 'Auto-load ON — click to disable' : 'Set as startup file for this canvas'}
                    style={{ opacity: noFile ? 0.3 : 1, cursor: noFile ? 'not-allowed' : 'pointer' }}
                  >
                    <Heart
                      size={12}
                      style={{
                        color: isFav ? '#4ade80' : '#9ca3af',
                        fill: isFav ? '#4ade80' : 'none',
                        transition: 'color 0.2s, fill 0.2s',
                      }}
                    />
                  </ControlButton>
                );
              })()}
            </Controls>
            <Panel position="top-left">
              <div className="flex flex-col gap-2">
                <button
                  onClick={() => setIsAddMenuOpen(!isAddMenuOpen)}
                  className="bg-[#007cf0] hover:bg-[#006cc0] text-white p-2 px-8 rounded-full shadow-2xl transition-all font-black text-[10px] tracking-widest uppercase flex items-center gap-2"
                >
                  <Plus size={14} /> Add Node
                </button>
                {groupStack.length > 0 && (
                  <div className="flex items-center gap-1 bg-[#1e2530]/90 backdrop-blur border border-accent/30 rounded-full px-3 py-1.5 text-[10px] font-bold shadow-lg">
                    <button onClick={() => { setGroupStack([]); groupStackRef.current = []; instance?.fitView({ duration: 300 }); }} className="text-gray-400 hover:text-white transition-colors">
                      Canvas
                    </button>
                    {groupStack.map((entry, i) => {
                      const parentNodes = i === 0 ? canvasNodes : getNestedSubGraph(canvasNodes, groupStack.slice(0, i)).nodes;
                      const gNode = parentNodes.find(n => n.id === entry.groupNodeId);
                      const label = (gNode?.data as any)?.params?.label || (gNode?.data as any)?.label || 'Group';
                      return (
                        <React.Fragment key={entry.groupNodeId}>
                          <ChevronRight size={10} className="text-gray-600" />
                          <button
                            onClick={() => {
                              const newStack = groupStack.slice(0, i + 1);
                              setGroupStack(newStack); groupStackRef.current = newStack;
                              instance?.fitView({ duration: 300 });
                            }}
                            className={`transition-colors ${i === groupStack.length - 1 ? 'text-accent' : 'text-gray-400 hover:text-white'}`}
                          >{label}</button>
                        </React.Fragment>
                      );
                    })}
                    <span className="ml-1 text-[8px] text-gray-600 font-mono">ESC to exit</span>
                  </div>
                )}
              </div>
            </Panel>
          </ReactFlow>
          </ComputingNodeContext.Provider>

          <RerouteOverlay isRerouting={isRerouting} rerouteDragRef={rerouteDragRef} reroutePos={reroutePos} />

          <NotificationBar notifications={notifications} dismissNotification={dismissNotification} />

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
                 onClose={() => setCropEditingId(null)}
               />
            )}
            {annotatorEditingId && (
               <AnnotatorOverlay
                 node={nodesWithData.find(n => n.id === annotatorEditingId)}
                 onClose={() => setAnnotatorEditingId(null)}
               />
            )}
            {manualPointsEditingId && (
               <ManualPointsEditorOverlay
                 node={nodesWithData.find(n => n.id === manualPointsEditingId)}
                 nodesData={nodesData}
                 onClose={() => setManualPointsEditingId(null)}
               />
            )}
            {lineEditingId && (
              <LineEditorOverlay
                node={nodesWithData.find(n => n.id === lineEditingId)}
                edges={edges}
                onClose={() => setLineEditingId(null)}
              />
            )}
          </AnimatePresence>
          </NodesDataContext.Provider>

          <ContextMenu
            menu={menu}
            paneMenu={paneMenu}
            nodes={nodes}
            canVisualize={canVisualize}
            canSaveAsImage={canSaveAsImage}
            canBypass={canBypass}
            visualizedNodeId={visualizedNodeId}
            activePaletteIndex={activePaletteIndex}
            handleVisualize={handleVisualize}
            handleSaveAsImage={handleSaveAsImage}
            pushSnapshot={pushSnapshot}
            setViewNodes={setViewNodes}
            enterGroup={enterGroup}
            ungroupNode={ungroupNode}
            groupSelectedNodes={groupSelectedNodes}
            handleRotate={handleRotate}
            handleTeleport={handleTeleport}
            setMenu={setMenu}
            setPaneMenu={setPaneMenu}
            setPreviewNode={setPreviewNode}
            setVisualizedNodeId={setVisualizedNodeId}
          />

          <AddNodeMenu
            isOpen={isAddMenuOpen}
            onClose={(e: any) => { setIsAddMenuOpen(false); setPendingConnection(null); if (instance) setCursorFlowPos(instance.screenToFlowPosition({ x: e.clientX, y: e.clientY })); }}
            dynamicCategories={dynamicCategories}
            activeCategoryId={activeCategoryId}
            setActiveCategoryId={setActiveCategoryId}
            addNode={addNode}
          />

          <PreviewWidget
            frame={frame}
            previewSize={previewSize}
            previewPos={previewPos}
            previewZoom={previewZoom}
            previewPan={previewPan}
            previewPopped={previewPopped}
            pickColorNodeId={pickColorNodeId}
            setPreviewPos={setPreviewPos}
            setPreviewZoom={setPreviewZoom}
            setPreviewPan={setPreviewPan}
            setPreviewSize={setPreviewSize}
            previewZoomRef={previewZoomRef}
            previewAspect={previewAspect}
            previewResizeRef={previewResizeRef as any}
            handlePopout={handlePopout}
            handleBringBack={handleBringBack}
            updateNodeParams={updateNodeParams}
            setPickColorNodeId={setPickColorNodeId}
            isPanning={isPanning}
            panStart={panStart}
          />
        </div>

        <RightPanel
          selectedNode={selectedNode}
          selectedNodeLiveData={selectedNodeLiveData}
          rightPanelWidth={rightPanelWidth}
          exposedGroupParams={exposedGroupParams}
          activePaletteIndex={activePaletteIndex}
          pickColorNodeId={pickColorNodeId}
          isInsideGroup={groupStack.length > 0}
          isResizing={isResizing}
          onUpdateParams={updateNodeParams}
          onPickColorToggle={setPickColorNodeId}
          onRequestCapture={requestCapture}
          onToggleExposed={toggleExposedParam}
          onUpdateGroupChildParams={selectedNode?.type === 'group_node'
            ? (childNodeId, params) => updateGroupChildParams(selectedNode.id, childNodeId, params)
            : undefined}
          onRenameExposedParam={selectedNode?.type === 'group_node' ? renameExposedParam : undefined}
        />
      </div>

      <AboutModal showAbout={showAbout} setShowAbout={setShowAbout} />
    </div>
  );
}

export default App;
