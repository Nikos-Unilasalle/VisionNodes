/**
 * Geometry for freehand ink drawn on the node canvas.
 *
 * Stroke points are stored in flow units, relative to the ink node's own
 * position, so the node behaves like any other: React Flow's pane transform
 * handles zoom/pan, and the .vn file persists the strokes for free.
 */

export interface InkPoint {
  x: number;
  y: number;
}

export interface InkStroke {
  /** Polyline points. Node-local for stored strokes, absolute while drawing. */
  pts: InkPoint[];
  color: string;
  /** Line width in flow units (screen px ÷ zoom at capture time). */
  size: number;
  /** Shift-drawn segments: rendered as exact straight lines, never splined. */
  straight?: boolean;
}

export interface InkParams {
  strokes: InkStroke[];
  version: number;
}

/** Where a node must sit, and how big it must be, to hold a set of strokes. */
export interface InkLayout {
  params: InkParams;
  position: InkPoint;
  width: number;
  height: number;
}

export const INK_VERSION = 1;

/**
 * Douglas-Peucker tolerance, in *screen* pixels: divided by the zoom at capture
 * time so a stroke keeps the same visible fidelity whatever the zoom level.
 */
export const SIMPLIFY_TOLERANCE = 0.8;

/** Viewport transform, as React Flow exposes it. */
export interface FlowViewport {
  x: number;
  y: number;
  zoom: number;
}

/**
 * Screen point → flow point.
 *
 * React Flow's own `screenToFlowPosition` snaps to the grid whenever
 * `snapToGrid` is on (@reactflow/core, no opt-out in v11), which turns freehand
 * strokes into staircases. Ink needs the raw, unsnapped position.
 */
export function screenToFlowPoint(
  point: InkPoint,
  paneRect: { left: number; top: number },
  viewport: FlowViewport,
): InkPoint {
  const zoom = viewport.zoom || 1;
  return {
    x: (point.x - paneRect.left - viewport.x) / zoom,
    y: (point.y - paneRect.top - viewport.y) / zoom,
  };
}

/** Points closer than this to the previous one are dropped while capturing. */
export const MIN_POINT_DISTANCE = 1.5;

/**
 * Moving-average window, in points. Odd, so each point stays centred.
 * 7 kills the tremble without eating real detail: a 14px loop and a sharp
 * corner both survive it intact.
 */
export const SMOOTHING_WINDOW = 7;

const MIN_EXTENT = 1;

export function distance(a: InkPoint, b: InkPoint): number {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

function perpendicularDistance(p: InkPoint, start: InkPoint, end: InkPoint): number {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const span = Math.hypot(dx, dy);
  if (span < 1e-9) return distance(p, start);
  return Math.abs(dy * p.x - dx * p.y + end.x * start.y - end.y * start.x) / span;
}

/**
 * Moving average over the point list — takes the tremble out of a freehand line.
 * Both endpoints are left untouched so a stroke still starts and ends where the
 * hand did.
 */
export function smoothPath(pts: InkPoint[], window = SMOOTHING_WINDOW): InkPoint[] {
  if (pts.length <= 2 || window <= 1) return [...pts];
  const half = Math.floor(window / 2);

  return pts.map((pt, i) => {
    if (i === 0 || i === pts.length - 1) return pt;
    // The window shrinks symmetrically near the ends: a one-sided window would
    // drag points along the stroke instead of just averaging out the tremble.
    const reach = Math.min(half, i, pts.length - 1 - i);
    let sumX = 0;
    let sumY = 0;
    for (let j = i - reach; j <= i + reach; j++) {
      sumX += pts[j].x;
      sumY += pts[j].y;
    }
    const n = 2 * reach + 1;
    return { x: sumX / n, y: sumY / n };
  });
}

/** Ramer-Douglas-Peucker: drops points that add no visible detail. */
export function simplifyPath(pts: InkPoint[], tolerance = SIMPLIFY_TOLERANCE): InkPoint[] {
  if (pts.length <= 2) return [...pts];

  let worstIdx = 0;
  let worstDist = 0;
  for (let i = 1; i < pts.length - 1; i++) {
    const d = perpendicularDistance(pts[i], pts[0], pts[pts.length - 1]);
    if (d > worstDist) {
      worstDist = d;
      worstIdx = i;
    }
  }

  if (worstDist <= tolerance) return [pts[0], pts[pts.length - 1]];

  const head = simplifyPath(pts.slice(0, worstIdx + 1), tolerance);
  const tail = simplifyPath(pts.slice(worstIdx), tolerance);
  return [...head.slice(0, -1), ...tail];
}

/** Bounding box of every stroke, padded by half a line width so caps aren't clipped. */
export function strokeBounds(strokes: InkStroke[]): { minX: number; minY: number; maxX: number; maxY: number } {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const stroke of strokes) {
    const pad = stroke.size / 2 + 1;
    for (const pt of stroke.pts) {
      minX = Math.min(minX, pt.x - pad);
      minY = Math.min(minY, pt.y - pad);
      maxX = Math.max(maxX, pt.x + pad);
      maxY = Math.max(maxY, pt.y + pad);
    }
  }

  if (!Number.isFinite(minX)) return { minX: 0, minY: 0, maxX: 0, maxY: 0 };
  return { minX, minY, maxX, maxY };
}

function shiftStroke(stroke: InkStroke, dx: number, dy: number): InkStroke {
  return { ...stroke, pts: stroke.pts.map(p => ({ x: p.x + dx, y: p.y + dy })) };
}

/**
 * Add a freshly drawn stroke (absolute flow coordinates) to an ink node.
 * Returns the new params plus the position/size the node must take: the bbox
 * grows around every stroke, and stored points are rebased on the new origin.
 */
export function addStroke(
  current: InkParams | null,
  position: InkPoint | null,
  strokeAbs: InkStroke,
): InkLayout {
  const origin = position ?? { x: 0, y: 0 };
  const existingAbs = (current?.strokes ?? []).map(s => shiftStroke(s, origin.x, origin.y));
  const allAbs = [...existingAbs, strokeAbs];

  const { minX, minY, maxX, maxY } = strokeBounds(allAbs);
  const localStrokes = allAbs.map(s => shiftStroke(s, -minX, -minY));

  return {
    params: { strokes: localStrokes, version: INK_VERSION },
    position: { x: minX, y: minY },
    width: Math.max(MIN_EXTENT, maxX - minX),
    height: Math.max(MIN_EXTENT, maxY - minY),
  };
}

/** Catmull-Rom parametrisation. 0.5 = centripetal: no cusps, no overshoot. */
const CATMULL_ALPHA = 0.5;

const fmt = (v: number): string => (Number.isFinite(v) ? v : 0).toFixed(2);

/**
 * The two cubic control points of the segment p1 → p2, using a centripetal
 * Catmull-Rom spline. Uniform parametrisation would loop or overshoot wherever
 * simplification left points unevenly spaced; centripetal never does.
 */
function segmentControlPoints(
  p0: InkPoint, p1: InkPoint, p2: InkPoint, p3: InkPoint,
): [InkPoint, InkPoint] {
  const d1 = Math.pow(distance(p0, p1), CATMULL_ALPHA);
  const d2 = Math.pow(distance(p1, p2), CATMULL_ALPHA);
  const d3 = Math.pow(distance(p2, p3), CATMULL_ALPHA);

  // Coincident neighbours collapse the formula: fall back to a straight segment.
  const c1 = d1 > 1e-6
    ? {
        x: (d1 * d1 * p2.x - d2 * d2 * p0.x + (2 * d1 * d1 + 3 * d1 * d2 + d2 * d2) * p1.x) / (3 * d1 * (d1 + d2)),
        y: (d1 * d1 * p2.y - d2 * d2 * p0.y + (2 * d1 * d1 + 3 * d1 * d2 + d2 * d2) * p1.y) / (3 * d1 * (d1 + d2)),
      }
    : { ...p1 };

  const c2 = d3 > 1e-6
    ? {
        x: (d3 * d3 * p1.x - d2 * d2 * p3.x + (2 * d3 * d3 + 3 * d3 * d2 + d2 * d2) * p2.x) / (3 * d3 * (d3 + d2)),
        y: (d3 * d3 * p1.y - d2 * d2 * p3.y + (2 * d3 * d3 + 3 * d3 * d2 + d2 * d2) * p2.y) / (3 * d3 * (d3 + d2)),
      }
    : { ...p2 };

  return [c1, c2];
}

/**
 * SVG path data for a stroke: a centripetal Catmull-Rom spline through every
 * point, emitted as cubic Bézier segments. A single point renders as a round dot.
 *
 * `straight` emits plain line segments instead — Shift-drawn corners are
 * deliberate and must stay sharp.
 */
export function strokeToPathD(pts: InkPoint[], straight = false): string {
  if (pts.length === 0) return '';
  const head = `M ${fmt(pts[0].x)} ${fmt(pts[0].y)}`;
  if (pts.length === 1) return `${head} L ${fmt(pts[0].x)} ${fmt(pts[0].y)}`;
  if (pts.length === 2) return `${head} L ${fmt(pts[1].x)} ${fmt(pts[1].y)}`;

  if (straight) {
    return [head, ...pts.slice(1).map(p => `L ${fmt(p.x)} ${fmt(p.y)}`)].join(' ');
  }

  const segments: string[] = [head];
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? pts[i + 1];
    const [c1, c2] = segmentControlPoints(p0, p1, p2, p3);
    segments.push(`C ${fmt(c1.x)} ${fmt(c1.y)} ${fmt(c2.x)} ${fmt(c2.y)} ${fmt(p2.x)} ${fmt(p2.y)}`);
  }
  return segments.join(' ');
}

/** Read strokes off a node's params, tolerating older/absent payloads. */
export function readInkParams(params: unknown): InkParams {
  const raw = (params ?? {}) as { strokes?: unknown; version?: unknown };
  const strokes = Array.isArray(raw.strokes) ? (raw.strokes as InkStroke[]) : [];
  return {
    strokes: strokes.filter(s => Array.isArray(s?.pts) && s.pts.length > 0),
    version: typeof raw.version === 'number' ? raw.version : INK_VERSION,
  };
}
