import { describe, it, expect } from 'vitest';
import {
  addStroke,
  readInkParams,
  screenToFlowPoint,
  simplifyPath,
  smoothPath,
  strokeBounds,
  strokeToPathD,
  INK_VERSION,
  type InkStroke,
} from '../utils/inkGeometry';

const stroke = (pts: Array<[number, number]>, size = 4, color = '#fff'): InkStroke => ({
  pts: pts.map(([x, y]) => ({ x, y })),
  color,
  size,
});

describe('simplifyPath', () => {
  it('drops points that sit on a straight line', () => {
    const pts = [
      { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 20, y: 0 }, { x: 30, y: 0 },
    ];
    expect(simplifyPath(pts)).toEqual([{ x: 0, y: 0 }, { x: 30, y: 0 }]);
  });

  it('keeps the point that carries the shape', () => {
    const pts = [{ x: 0, y: 0 }, { x: 10, y: 40 }, { x: 20, y: 0 }];
    const out = simplifyPath(pts);
    expect(out).toHaveLength(3);
    expect(out[1]).toEqual({ x: 10, y: 40 });
  });

  it('leaves short paths untouched', () => {
    const pts = [{ x: 1, y: 2 }];
    expect(simplifyPath(pts)).toEqual(pts);
  });
});

describe('screenToFlowPoint', () => {
  const rect = { left: 100, top: 50 };

  it('undoes pan and zoom', () => {
    const flow = screenToFlowPoint({ x: 300, y: 250 }, rect, { x: 20, y: 10, zoom: 2 });
    expect(flow).toEqual({ x: 90, y: 95 });
  });

  it('is the identity for an untransformed viewport at the origin', () => {
    const flow = screenToFlowPoint({ x: 7, y: 9 }, { left: 0, top: 0 }, { x: 0, y: 0, zoom: 1 });
    expect(flow).toEqual({ x: 7, y: 9 });
  });

  it('keeps sub-grid detail instead of quantising it', () => {
    // React Flow's own screenToFlowPosition snaps to snapGrid, which turned
    // freehand strokes into staircases.
    const diagonal = [0, 3, 7, 11, 14].map(d => ({ x: 100 + d, y: 50 + d }));
    const flow = diagonal.map(p => screenToFlowPoint(p, rect, { x: 0, y: 0, zoom: 1 }));

    expect(flow.map(p => p.x)).toEqual([0, 3, 7, 11, 14]);
    expect(new Set(flow.map(p => p.x)).size).toBe(5);
  });

  it('treats a zero zoom as 1 rather than dividing by it', () => {
    const flow = screenToFlowPoint({ x: 10, y: 10 }, { left: 0, top: 0 }, { x: 0, y: 0, zoom: 0 });
    expect(Number.isFinite(flow.x)).toBe(true);
    expect(Number.isFinite(flow.y)).toBe(true);
  });
});

describe('strokeBounds', () => {
  it('pads the box by half the line width', () => {
    const b = strokeBounds([stroke([[10, 10], [20, 30]], 4)]);
    expect(b).toEqual({ minX: 7, minY: 7, maxX: 23, maxY: 33 });
  });

  it('returns a zero box for no strokes', () => {
    expect(strokeBounds([])).toEqual({ minX: 0, minY: 0, maxX: 0, maxY: 0 });
  });
});

describe('addStroke', () => {
  it('places a first stroke at its own bounding box, rebased on the origin', () => {
    const layout = addStroke(null, null, stroke([[100, 200], [140, 260]], 4));

    expect(layout.position).toEqual({ x: 97, y: 197 });
    expect(layout.width).toBe(46);
    expect(layout.height).toBe(66);
    expect(layout.params.strokes[0].pts[0]).toEqual({ x: 3, y: 3 });
    expect(layout.params.version).toBe(INK_VERSION);
  });

  it('grows the box and rebases existing strokes when drawing above-left', () => {
    const first = addStroke(null, null, stroke([[100, 100], [120, 120]], 4));
    const second = addStroke(first.params, first.position, stroke([[50, 50], [60, 60]], 4));

    expect(second.position).toEqual({ x: 47, y: 47 });
    // The first stroke keeps its place on the canvas: local + position is unchanged.
    const firstPtLocal = second.params.strokes[0].pts[0];
    expect(firstPtLocal.x + second.position.x).toBe(100);
    expect(firstPtLocal.y + second.position.y).toBe(100);
    expect(second.params.strokes).toHaveLength(2);
  });

  it('never produces a degenerate box for a single-point dot', () => {
    const layout = addStroke(null, null, stroke([[10, 10]], 6));
    expect(layout.width).toBeGreaterThan(0);
    expect(layout.height).toBeGreaterThan(0);
  });
});

describe('smoothPath', () => {
  it('pins both endpoints', () => {
    const pts = [{ x: 0, y: 0 }, { x: 10, y: 40 }, { x: 20, y: 0 }, { x: 30, y: 30 }];
    const out = smoothPath(pts);
    expect(out[0]).toEqual(pts[0]);
    expect(out[out.length - 1]).toEqual(pts[pts.length - 1]);
  });

  it('flattens jitter around a straight line', () => {
    const jittery = [0, 1, 2, 3, 4, 5, 6, 7, 8].map(i => ({ x: i * 10, y: i % 2 === 0 ? 1 : -1 }));
    const out = smoothPath(jittery);
    const amplitude = Math.max(...out.slice(1, -1).map(p => Math.abs(p.y)));
    expect(amplitude).toBeLessThan(0.6);
  });

  it('leaves the overall course of the stroke alone', () => {
    const pts = [0, 1, 2, 3, 4, 5].map(i => ({ x: i * 10, y: i * 10 }));
    const out = smoothPath(pts);
    out.forEach((p, i) => {
      expect(Math.abs(p.x - pts[i].x)).toBeLessThan(1e-6);
      expect(Math.abs(p.y - pts[i].y)).toBeLessThan(1e-6);
    });
  });

  it('passes short paths straight through', () => {
    const pts = [{ x: 0, y: 0 }, { x: 5, y: 5 }];
    expect(smoothPath(pts)).toEqual(pts);
  });
});

describe('strokeToPathD', () => {
  it('renders a lone point as a zero-length segment so the round cap shows', () => {
    expect(strokeToPathD([{ x: 5, y: 7 }])).toBe('M 5.00 7.00 L 5.00 7.00');
  });

  it('renders two points as a straight line', () => {
    expect(strokeToPathD([{ x: 0, y: 0 }, { x: 10, y: 5 }])).toBe('M 0.00 0.00 L 10.00 5.00');
  });

  it('emits one cubic per segment, ending on each original point', () => {
    const pts = [{ x: 0, y: 0 }, { x: 10, y: 10 }, { x: 20, y: 0 }];
    const d = strokeToPathD(pts);
    const cubics = d.match(/C /g) ?? [];

    expect(d.startsWith('M 0.00 0.00')).toBe(true);
    expect(cubics).toHaveLength(2);
    // The curve interpolates its points: each segment lands exactly on one.
    expect(d).toContain('10.00 10.00');
    expect(d.trimEnd().endsWith('20.00 0.00')).toBe(true);
  });

  it('keeps control points on the line for a collinear path', () => {
    const d = strokeToPathD([{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 20, y: 0 }, { x: 30, y: 0 }]);
    // Every y in the path data stays at 0: no bulge on a straight stroke.
    const ys = (d.match(/-?\d+\.\d+/g) ?? []).filter((_, i) => i % 2 === 1);
    ys.forEach(y => expect(Math.abs(Number(y))).toBeLessThan(1e-6));
  });

  it('never emits NaN when consecutive points coincide', () => {
    const d = strokeToPathD([
      { x: 0, y: 0 }, { x: 0, y: 0 }, { x: 10, y: 10 }, { x: 10, y: 10 }, { x: 20, y: 0 },
    ]);
    expect(d).not.toContain('NaN');
  });

  it('returns an empty string for no points', () => {
    expect(strokeToPathD([])).toBe('');
  });

  it('keeps Shift-drawn corners sharp instead of splining through them', () => {
    const corners = [{ x: 0, y: 0 }, { x: 50, y: 0 }, { x: 50, y: 50 }];
    const d = strokeToPathD(corners, true);

    expect(d).toBe('M 0.00 0.00 L 50.00 0.00 L 50.00 50.00');
    expect(d).not.toContain('C');
    // Same points, freehand: curved.
    expect(strokeToPathD(corners)).toContain('C');
  });
});

describe('readInkParams', () => {
  it('defaults to an empty drawing', () => {
    expect(readInkParams(undefined)).toEqual({ strokes: [], version: INK_VERSION });
  });

  it('drops malformed strokes', () => {
    const parsed = readInkParams({ strokes: [{ pts: [], color: '#fff', size: 2 }, stroke([[0, 0]])] });
    expect(parsed.strokes).toHaveLength(1);
  });
});
