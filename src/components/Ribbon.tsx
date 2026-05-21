import { memo } from 'react';
import type { EdgeProps, NodeProps } from 'reactflow';
import { getBezierPath } from 'reactflow';

interface RibbonRouting {
  x: number;
  yCenter: number;
}

export const RibbonEdge = memo(({
  id, sourceX, sourceY, targetX, targetY,
  style, markerEnd, data,
}: EdgeProps) => {
  const ribbon = data?.ribbon as RibbonRouting | undefined;

  let d: string;
  if (ribbon) {
    const rx = ribbon.x;
    const ry = ribbon.yCenter;
    d = `M ${sourceX} ${sourceY} C ${(sourceX + rx) / 2} ${sourceY}, ${rx} ${(sourceY + ry) / 2}, ${rx} ${ry} C ${rx} ${(ry + targetY) / 2}, ${(rx + targetX) / 2} ${targetY}, ${targetX} ${targetY}`;
  } else {
    [d] = getBezierPath({ sourceX, sourceY, targetX, targetY });
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
