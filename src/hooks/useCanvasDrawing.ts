import { useCallback, useEffect, useRef, useState } from 'react';
import type { Node } from 'reactflow';
import {
  addStroke,
  distance,
  readInkParams,
  screenToFlowPoint,
  simplifyPath,
  smoothPath,
  MIN_POINT_DISTANCE,
  SIMPLIFY_TOLERANCE,
  type InkPoint,
  type InkStroke,
} from '../utils/inkGeometry';

export const INK_NODE_TYPE = 'canvas_ink';

/** Ink sits just behind the nodes, like frames: annotations never cover a node. */
const INK_Z_INDEX = -1;

/** Body class driving the crosshair cursor over every element (see App.css). */
const DRAWING_CLASS = 'vn-drawing';

interface UseCanvasDrawingArgs {
  isDrawing: boolean;
  instance: any;
  color: string;
  /** Line width in screen pixels; converted to flow units at capture time. */
  size: number;
  pushSnapshot: () => void;
  setViewNodes: (updater: (nodes: Node[]) => Node[]) => void;
  /** Live node list, used to notice when undo removed the session's ink node. */
  nodesRef: React.MutableRefObject<any[]>;
  onExit: () => void;
}

interface UseCanvasDrawingResult {
  /** Live stroke in screen coordinates, for the preview overlay. */
  previewPoints: InkPoint[];
  /** True while drawing straight segments (Shift): the preview must not smooth. */
  isPreviewStraight: boolean;
}

const isInsideCanvas = (target: EventTarget | null): boolean => {
  const el = target as HTMLElement | null;
  if (!el || typeof el.closest !== 'function') return false;
  // Panels (toolbar, controls, minimap) keep their own clicks.
  if (el.closest('.react-flow__panel')) return false;
  return !!el.closest('.react-flow');
};

const paneRectOf = (target: EventTarget | null): { left: number; top: number } => {
  const pane = (target as HTMLElement | null)?.closest?.('.react-flow') as HTMLElement | null;
  const rect = pane?.getBoundingClientRect();
  return { left: rect?.left ?? 0, top: rect?.top ?? 0 };
};

/**
 * Freehand drawing on the node canvas.
 *
 * Every stroke drawn without leaving draw mode lands in the same `canvas_ink`
 * node: one DOM element and one graph entry per drawing session instead of one
 * per stroke. A snapshot is pushed before each committed stroke, so undo stays
 * stroke by stroke.
 *
 * Holding Shift switches to straight segments: each click pins a corner and the
 * next segment starts from there, until Shift is released.
 */
export function useCanvasDrawing({
  isDrawing,
  instance,
  color,
  size,
  pushSnapshot,
  setViewNodes,
  nodesRef,
  onExit,
}: UseCanvasDrawingArgs): UseCanvasDrawingResult {
  const [previewPoints, setPreviewPoints] = useState<InkPoint[]>([]);
  const [isPreviewStraight, setIsPreviewStraight] = useState(false);

  const screenPointsRef = useRef<InkPoint[]>([]);
  // Flow coordinates are captured point by point, not converted at mouse-up:
  // zooming or panning mid-stroke must not warp what was already drawn.
  const flowPointsRef = useRef<InkPoint[]>([]);
  const strokeZoomRef = useRef(1);
  const paneRectRef = useRef<{ left: number; top: number }>({ left: 0, top: 0 });
  const isStrokingRef = useRef(false);
  const sessionNodeIdRef = useRef<string | null>(null);

  // Shift mode: corners pinned by successive clicks.
  const isLineModeRef = useRef(false);
  const lineScreenRef = useRef<InkPoint[]>([]);
  const lineFlowRef = useRef<InkPoint[]>([]);

  // Live values for the window listeners, which are bound once per draw session.
  const styleRef = useRef({ color, size });
  styleRef.current = { color, size };

  /** Empty the preview without handing React a fresh array when it is already
   *  empty: the effect cleanup calls this, and a new [] every time would keep
   *  re-rendering (and re-running the effect) forever. */
  const clearPreview = useCallback(() => {
    setPreviewPoints(prev => (prev.length === 0 ? prev : []));
  }, []);

  const resetCapture = useCallback(() => {
    isStrokingRef.current = false;
    screenPointsRef.current = [];
    flowPointsRef.current = [];
    lineScreenRef.current = [];
    lineFlowRef.current = [];
    clearPreview();
  }, [clearPreview]);

  const commitStroke = useCallback((flowPoints: InkPoint[], zoom: number, straight = false) => {
    if (flowPoints.length === 0) return;

    const stroke: InkStroke = {
      // Straight segments are already exact — smoothing them would round the
      // corners the user explicitly pinned. Freehand gets the full treatment:
      // smooth away the tremble, then drop the points carrying no shape.
      pts: straight ? flowPoints : simplifyPath(smoothPath(flowPoints), SIMPLIFY_TOLERANCE / zoom),
      color: styleRef.current.color,
      size: Math.max(0.5, styleRef.current.size / zoom),
      ...(straight ? { straight: true } : {}),
    };

    pushSnapshot();

    // Undo can delete the session's node underneath us; without this check the
    // update below would match nothing and the stroke would vanish.
    const sessionId = sessionNodeIdRef.current;
    const sessionAlive = !!sessionId && nodesRef.current.some((n: any) => n.id === sessionId);

    if (!sessionAlive) {
      const id = `ink-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      sessionNodeIdRef.current = id;
      const layout = addStroke(null, null, stroke);
      setViewNodes(nds => [
        ...nds,
        {
          id,
          type: INK_NODE_TYPE,
          position: layout.position,
          style: { width: layout.width, height: layout.height, zIndex: INK_Z_INDEX },
          data: { label: 'Ink', params: layout.params },
        } as Node,
      ]);
      return;
    }

    setViewNodes(nds => nds.map(n => {
      if (n.id !== sessionId) return n;
      const layout = addStroke(readInkParams(n.data?.params), n.position, stroke);
      return {
        ...n,
        position: layout.position,
        style: { ...n.style, width: layout.width, height: layout.height },
        data: { ...n.data, params: layout.params },
      };
    }));
  }, [nodesRef, pushSnapshot, setViewNodes]);

  // A session lasts as long as draw mode: strokes accumulate in one node.
  useEffect(() => {
    if (!isDrawing) sessionNodeIdRef.current = null;
  }, [isDrawing]);

  useEffect(() => {
    if (!isDrawing || !instance) return;

    const onDown = (e: MouseEvent) => {
      // Left button only, no Cmd/Ctrl/Alt: Cmd-drag still bundles edges into a ribbon.
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.altKey) return;
      if (!isInsideCanvas(e.target)) return;
      e.preventDefault();
      e.stopImmediatePropagation();

      const point = { x: e.clientX, y: e.clientY };

      // Shift: pin one corner per click, chaining straight segments.
      if (isLineModeRef.current) {
        if (lineFlowRef.current.length === 0) {
          paneRectRef.current = paneRectOf(e.target);
          strokeZoomRef.current = instance.getViewport().zoom || 1;
        }
        lineScreenRef.current = [...lineScreenRef.current, point];
        lineFlowRef.current = [
          ...lineFlowRef.current,
          screenToFlowPoint(point, paneRectRef.current, instance.getViewport()),
        ];
        setPreviewPoints(lineScreenRef.current);
        return;
      }

      paneRectRef.current = paneRectOf(e.target);
      isStrokingRef.current = true;
      strokeZoomRef.current = instance.getViewport().zoom || 1;
      screenPointsRef.current = [point];
      flowPointsRef.current = [screenToFlowPoint(point, paneRectRef.current, instance.getViewport())];
      setPreviewPoints(screenPointsRef.current);
    };

    const onMove = (e: MouseEvent) => {
      const next = { x: e.clientX, y: e.clientY };

      if (isLineModeRef.current) {
        // Rubber band: the open end follows the cursor until the next click.
        if (lineScreenRef.current.length === 0) return;
        setPreviewPoints([...lineScreenRef.current, next]);
        return;
      }

      if (!isStrokingRef.current) return;
      const pts = screenPointsRef.current;
      if (pts.length > 0 && distance(pts[pts.length - 1], next) < MIN_POINT_DISTANCE) return;
      screenPointsRef.current = [...pts, next];
      flowPointsRef.current = [
        ...flowPointsRef.current,
        screenToFlowPoint(next, paneRectRef.current, instance.getViewport()),
      ];
      setPreviewPoints(screenPointsRef.current);
    };

    const onUp = () => {
      if (isLineModeRef.current || !isStrokingRef.current) return;
      isStrokingRef.current = false;
      const flowPts = flowPointsRef.current;
      screenPointsRef.current = [];
      flowPointsRef.current = [];
      clearPreview();
      if (flowPts.length > 0) commitStroke(flowPts, strokeZoomRef.current);
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        isLineModeRef.current = false;
        setIsPreviewStraight(false);
        resetCapture();
        onExit();
        return;
      }
      // Never switch to straight mode in the middle of a freehand drag.
      if (e.key === 'Shift' && !isStrokingRef.current && !isLineModeRef.current) {
        isLineModeRef.current = true;
        setIsPreviewStraight(true);
      }
    };

    const onKeyUp = (e: KeyboardEvent) => {
      if (e.key !== 'Shift' || !isLineModeRef.current) return;
      isLineModeRef.current = false;
      setIsPreviewStraight(false);
      const flowPts = lineFlowRef.current;
      lineScreenRef.current = [];
      lineFlowRef.current = [];
      clearPreview();
      // A single pinned point is an abandoned polyline, not a stroke.
      if (flowPts.length >= 2) commitStroke(flowPts, strokeZoomRef.current, true);
    };

    document.body.classList.add(DRAWING_CLASS);
    document.addEventListener('mousedown', onDown, { capture: true });
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);

    return () => {
      document.body.classList.remove(DRAWING_CLASS);
      document.removeEventListener('mousedown', onDown, { capture: true });
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
      isLineModeRef.current = false;
      setIsPreviewStraight(false);
      resetCapture();
    };
  }, [isDrawing, instance, commitStroke, onExit, resetCapture, clearPreview]);

  return { previewPoints, isPreviewStraight };
}
