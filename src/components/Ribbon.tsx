import { memo } from 'react';
import type { EdgeProps, NodeProps } from 'reactflow';
import { getBezierPath, Position, useStore } from 'reactflow';

// Right-click hit area of a link, in screen pixels. The stroke lives in flow
// coordinates, so it is divided by the zoom to stay constant on screen — deleting a
// link on a zoomed-out graph no longer requires zooming in to aim.
const EDGE_HIT_WIDTH_PX = 34;
const EDGE_HIT_WIDTH_MIN = 20;

interface RibbonWaypoint {
  x: number;
  yCenter: number;
}

function buildRibbonPath(
  sourceX: number, sourceY: number,
  targetX: number, targetY: number,
  waypoints: RibbonWaypoint[],
  sourcePosition: Position, targetPosition: Position,
): string {
  if (waypoints.length === 0) {
    const [d] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });
    return d;
  }
  const pts = [
    { x: sourceX, y: sourceY },
    ...waypoints.map(w => ({ x: w.x, y: w.yCenter })),
    { x: targetX, y: targetY },
  ];
  const segs: string[] = [`M ${pts[0].x} ${pts[0].y}`];
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i];
    const b = pts[i + 1];
    const mx = (a.x + b.x) / 2;
    segs.push(`C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x} ${b.y}`);
  }
  return segs.join(' ');
}

// Point at half the cumulative length of a polyline — keeps the conflict badge on the
// actual visible route (following ribbon waypoints) instead of a straight source→target line.
function midpointAlongPolyline(pts: { x: number; y: number }[]): { x: number; y: number } {
  const segLens: number[] = [];
  let total = 0;
  for (let i = 0; i < pts.length - 1; i++) {
    const len = Math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].y - pts[i].y);
    segLens.push(len);
    total += len;
  }
  let half = total / 2;
  for (let i = 0; i < segLens.length; i++) {
    if (half <= segLens[i]) {
      const t = segLens[i] === 0 ? 0 : half / segLens[i];
      return { x: pts[i].x + (pts[i + 1].x - pts[i].x) * t, y: pts[i].y + (pts[i + 1].y - pts[i].y) * t };
    }
    half -= segLens[i];
  }
  return pts[pts.length - 1];
}

export const RibbonEdge = memo(({
  id, sourceX, sourceY, targetX, targetY,
  sourcePosition = Position.Right, targetPosition = Position.Left,
  style, markerEnd, data,
}: EdgeProps) => {
  const zoom = useStore(s => s.transform[2]);
  const hitWidth = Math.max(EDGE_HIT_WIDTH_MIN, EDGE_HIT_WIDTH_PX / (zoom || 1));
  const raw = data?.ribbon;
  const waypoints: RibbonWaypoint[] = Array.isArray(raw) ? raw : raw ? [raw] : [];
  const d = buildRibbonPath(sourceX, sourceY, targetX, targetY, waypoints, sourcePosition, targetPosition);

  const conflictStatus: 'active' | 'inactive' | undefined = data?.conflictStatus;
  const onActivate: (() => void) | undefined = data?.onActivate;
  let dotX: number, dotY: number;
  if (waypoints.length > 0) {
    // Follow the ribbon route so the badge stays on the visible path.
    const pts = [
      { x: sourceX, y: sourceY },
      ...waypoints.map(w => ({ x: w.x, y: w.yCenter })),
      { x: targetX, y: targetY },
    ];
    ({ x: dotX, y: dotY } = midpointAlongPolyline(pts));
  } else {
    const [, bx, by] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });
    dotX = bx; dotY = by;
  }

  return (
    <>
      <path
        id={id}
        d={d}
        style={style}
        fill="none"
        className="react-flow__edge-path"
        markerEnd={markerEnd}
      />
      <path d={d} stroke="transparent" strokeWidth={hitWidth} fill="none" strokeLinecap="round" className="react-flow__edge-interaction" />
      {conflictStatus && (
        <g
          transform={`translate(${dotX},${dotY})`}
          onClick={e => { e.stopPropagation(); onActivate?.(); }}
          style={{ cursor: conflictStatus === 'inactive' ? 'pointer' : 'default', pointerEvents: 'all' }}
        >
          <circle r={8} fill={conflictStatus === 'active' ? '#22c55e' : '#ef4444'} stroke="rgba(0,0,0,0.6)" strokeWidth={1.5} />
          {conflictStatus === 'inactive' && (
            <circle r={3} fill="white" opacity={0.8} />
          )}
          {conflictStatus === 'active' && (
            <path d="M-3,0 L-1,2.5 L3,-2.5" stroke="white" strokeWidth={1.5} fill="none" strokeLinecap="round" strokeLinejoin="round" />
          )}
        </g>
      )}
    </>
  );
});
RibbonEdge.displayName = 'RibbonEdge';

export const RibbonNode = memo(({ data, selected }: NodeProps) => {
  const count = (data?.edgeIds as string[])?.length ?? 0;
  return (
    <div style={{
      width: '100%',
      height: '100%',
      borderRadius: 4,
      background: selected
        ? 'linear-gradient(to right, rgba(20,184,166,0.15), rgba(20,184,166,0.5), rgba(20,184,166,0.15))'
        : 'linear-gradient(to right, rgba(20,184,166,0.06), rgba(20,184,166,0.28), rgba(20,184,166,0.06))',
      border: selected
        ? '1px solid rgba(20,184,166,0.85)'
        : '1px solid rgba(20,184,166,0.45)',
      boxShadow: selected ? '0 0 0 2px rgba(20,184,166,0.3), 0 0 12px rgba(20,184,166,0.2)' : '0 0 8px rgba(20,184,166,0.15)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      cursor: 'grab',
      overflow: 'hidden',
    }}>
      <span style={{
        color: selected ? 'rgba(20,184,166,1)' : 'rgba(20,184,166,0.75)',
        fontSize: 8,
        fontWeight: 700,
        writingMode: 'vertical-rl',
        letterSpacing: '0.08em',
        userSelect: 'none',
        pointerEvents: 'none',
      }}>
        ×{count}
      </span>
    </div>
  );
});
RibbonNode.displayName = 'RibbonNode';
