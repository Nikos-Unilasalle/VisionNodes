import React, { memo, useMemo } from 'react';
import { readInkParams, strokeBounds, strokeToPathD } from '../../utils/inkGeometry';

/** Invisible widening of thin strokes so they stay clickable. Flow units. */
const MIN_HIT_WIDTH = 12;

interface CanvasInkNodeProps {
  selected: boolean;
  data: { params?: unknown };
}

/**
 * Freehand ink drawn on the canvas.
 *
 * The node box is only a bounding box: it never swallows pointer events, so
 * clicks pass through to the nodes underneath. Only the drawn strokes are
 * clickable — that is what selects the drawing and lets it be dragged.
 */
export const CanvasInkNode = memo(({ selected, data }: CanvasInkNodeProps) => {
  const { strokes } = useMemo(() => readInkParams(data?.params), [data?.params]);

  const { width, height } = useMemo(() => {
    const b = strokeBounds(strokes);
    return { width: Math.max(1, b.maxX), height: Math.max(1, b.maxY) };
  }, [strokes]);

  const paths = useMemo(
    () => strokes.map(stroke => ({
      d: strokeToPathD(stroke.pts, stroke.straight),
      color: stroke.color,
      size: stroke.size,
    })),
    [strokes],
  );

  return (
    <div className="vn-ink-node" style={{ width: '100%', height: '100%', pointerEvents: 'none' }}>
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        style={{ overflow: 'visible', display: 'block' }}
      >
        {selected && (
          <rect
            x={0}
            y={0}
            width={width}
            height={height}
            fill="none"
            stroke="#38bdf8"
            strokeWidth={1.5}
            strokeDasharray="6 4"
            vectorEffect="non-scaling-stroke"
            pointerEvents="none"
          />
        )}
        {paths.map((path, i) => (
          <g key={i}>
            {/* Widened transparent twin: the actual hit area for thin strokes. */}
            <path
              d={path.d}
              fill="none"
              stroke="transparent"
              strokeWidth={Math.max(path.size, MIN_HIT_WIDTH)}
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ pointerEvents: 'stroke', cursor: 'grab' }}
            />
            <path
              d={path.d}
              fill="none"
              stroke={path.color}
              strokeWidth={path.size}
              strokeLinecap="round"
              strokeLinejoin="round"
              pointerEvents="none"
            />
          </g>
        ))}
      </svg>
    </div>
  );
});

CanvasInkNode.displayName = 'CanvasInkNode';
