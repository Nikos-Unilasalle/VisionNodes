import { memo } from 'react';
import type { EdgeProps, NodeProps } from 'reactflow';
import { getBezierPath } from 'reactflow';

interface RibbonWaypoint {
  x: number;
  yCenter: number;
}

function buildRibbonPath(
  sourceX: number, sourceY: number,
  targetX: number, targetY: number,
  waypoints: RibbonWaypoint[],
): string {
  if (waypoints.length === 0) {
    const [d] = getBezierPath({ sourceX, sourceY, targetX, targetY });
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

export const RibbonEdge = memo(({
  id, sourceX, sourceY, targetX, targetY,
  style, markerEnd, data,
}: EdgeProps) => {
  const raw = data?.ribbon;
  const waypoints: RibbonWaypoint[] = Array.isArray(raw) ? raw : raw ? [raw] : [];
  const d = buildRibbonPath(sourceX, sourceY, targetX, targetY, waypoints);

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
      <path d={d} stroke="transparent" strokeWidth={20} fill="none" className="react-flow__edge-interaction" />
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
        ? 'linear-gradient(to right, rgba(251,191,36,0.1), rgba(251,191,36,0.35), rgba(251,191,36,0.1))'
        : 'linear-gradient(to right, rgba(255,255,255,0.03), rgba(255,255,255,0.18), rgba(255,255,255,0.03))',
      border: selected
        ? '1px solid rgba(251,191,36,0.7)'
        : '1px solid rgba(255,255,255,0.22)',
      boxShadow: selected ? '0 0 0 2px rgba(251,191,36,0.3)' : '0 1px 8px rgba(0,0,0,0.4)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      cursor: 'grab',
      overflow: 'hidden',
    }}>
      <span style={{
        color: selected ? 'rgba(251,191,36,0.95)' : 'rgba(255,255,255,0.6)',
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
