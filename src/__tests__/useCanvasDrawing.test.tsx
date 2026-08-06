import React, { useCallback, useRef } from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { useCanvasDrawing } from '../hooks/useCanvasDrawing';

/**
 * The hook drives real DOM listeners, so the tests drive real events: a pane
 * element stands in for the React Flow canvas and a plain array for the node store.
 */

let nodes: any[] = [];
const pushSnapshot = vi.fn();

const applyUpdater = (updater: (nds: any[]) => any[]) => {
  nodes = updater(nodes);
};

const instance = {
  getViewport: () => ({ x: 0, y: 0, zoom: 1 }),
};

function Harness({ isDrawing = true }: { isDrawing?: boolean }) {
  const nodesRef = useRef<any[]>(nodes);
  nodesRef.current = nodes;
  const onExit = useCallback(() => {}, []);

  useCanvasDrawing({
    isDrawing,
    instance,
    color: '#ffd400',
    size: 4,
    pushSnapshot,
    setViewNodes: applyUpdater,
    nodesRef,
    onExit,
  });

  return <div className="react-flow" data-testid="pane" style={{ width: 500, height: 500 }} />;
}

const drawStroke = (pane: HTMLElement, from: [number, number], to: [number, number]) => {
  fireEvent.mouseDown(pane, { button: 0, clientX: from[0], clientY: from[1] });
  fireEvent.mouseMove(window, { clientX: (from[0] + to[0]) / 2, clientY: (from[1] + to[1]) / 2 });
  fireEvent.mouseMove(window, { clientX: to[0], clientY: to[1] });
  fireEvent.mouseUp(window, { clientX: to[0], clientY: to[1] });
};

const inkNodes = () => nodes.filter(n => n.type === 'canvas_ink');
const strokesOf = (node: any) => node.data.params.strokes;

beforeEach(() => {
  nodes = [];
  pushSnapshot.mockClear();
});

describe('useCanvasDrawing', () => {
  it('commits a freehand stroke into a new ink node', () => {
    const { getByTestId } = render(<Harness />);
    drawStroke(getByTestId('pane'), [10, 10], [90, 60]);

    expect(inkNodes()).toHaveLength(1);
    expect(strokesOf(inkNodes()[0])).toHaveLength(1);
    expect(pushSnapshot).toHaveBeenCalledTimes(1);
  });

  it('accumulates later strokes in the same node', () => {
    const { getByTestId } = render(<Harness />);
    const pane = getByTestId('pane');
    drawStroke(pane, [10, 10], [90, 60]);
    drawStroke(pane, [20, 80], [120, 140]);

    expect(inkNodes()).toHaveLength(1);
    expect(strokesOf(inkNodes()[0])).toHaveLength(2);
  });

  it('starts a fresh node when undo removed the one it was drawing into', () => {
    const { getByTestId } = render(<Harness />);
    const pane = getByTestId('pane');
    drawStroke(pane, [10, 10], [90, 60]);
    const firstId = inkNodes()[0].id;

    // Undo: the ink node is gone, but the draw session is still open.
    nodes = [];
    drawStroke(pane, [20, 80], [120, 140]);

    expect(inkNodes()).toHaveLength(1);
    expect(inkNodes()[0].id).not.toBe(firstId);
    expect(strokesOf(inkNodes()[0])).toHaveLength(1);
  });

  it('ignores clicks outside the canvas', () => {
    const { getByTestId } = render(<Harness />);
    render(<div data-testid="outside" />);

    fireEvent.mouseDown(getByTestId('outside'), { button: 0, clientX: 5, clientY: 5 });
    fireEvent.mouseMove(window, { clientX: 40, clientY: 40 });
    fireEvent.mouseUp(window, { clientX: 40, clientY: 40 });

    expect(inkNodes()).toHaveLength(0);
    expect(getByTestId('pane')).toBeTruthy();
  });

  it('does nothing at all when draw mode is off', () => {
    const { getByTestId } = render(<Harness isDrawing={false} />);
    drawStroke(getByTestId('pane'), [10, 10], [90, 60]);

    expect(inkNodes()).toHaveLength(0);
  });

  describe('Shift: straight segments', () => {
    it('chains one segment per click and commits on release', () => {
      const { getByTestId } = render(<Harness />);
      const pane = getByTestId('pane');

      fireEvent.keyDown(window, { key: 'Shift' });
      fireEvent.mouseDown(pane, { button: 0, clientX: 10, clientY: 10 });
      fireEvent.mouseMove(window, { clientX: 60, clientY: 10 });
      fireEvent.mouseDown(pane, { button: 0, clientX: 100, clientY: 10 });
      fireEvent.mouseDown(pane, { button: 0, clientX: 100, clientY: 90 });
      expect(inkNodes()).toHaveLength(0); // nothing committed while Shift is held
      fireEvent.keyUp(window, { key: 'Shift' });

      const stroke = strokesOf(inkNodes()[0])[0];
      expect(stroke.straight).toBe(true);
      expect(stroke.pts).toHaveLength(3);
    });

    it('keeps the pinned corners exactly where they were clicked', () => {
      const { getByTestId } = render(<Harness />);
      const pane = getByTestId('pane');

      fireEvent.keyDown(window, { key: 'Shift' });
      fireEvent.mouseDown(pane, { button: 0, clientX: 40, clientY: 40 });
      fireEvent.mouseDown(pane, { button: 0, clientX: 140, clientY: 40 });
      fireEvent.keyUp(window, { key: 'Shift' });

      const node = inkNodes()[0];
      const stroke = strokesOf(node)[0];
      // Node-local + node position must land back on the clicked screen points
      // (pane at the origin, zoom 1, so screen and flow coordinates coincide).
      const absolute = stroke.pts.map((p: any) => ({
        x: p.x + node.position.x,
        y: p.y + node.position.y,
      }));
      expect(absolute[0].x).toBeCloseTo(40);
      expect(absolute[1].x).toBeCloseTo(140);
      expect(absolute[0].y).toBeCloseTo(40);
    });

    it('drops a polyline that never got a second corner', () => {
      const { getByTestId } = render(<Harness />);
      fireEvent.keyDown(window, { key: 'Shift' });
      fireEvent.mouseDown(getByTestId('pane'), { button: 0, clientX: 40, clientY: 40 });
      fireEvent.keyUp(window, { key: 'Shift' });

      expect(inkNodes()).toHaveLength(0);
    });

    it('does not hijack a freehand stroke already in progress', () => {
      const { getByTestId } = render(<Harness />);
      const pane = getByTestId('pane');

      fireEvent.mouseDown(pane, { button: 0, clientX: 10, clientY: 10 });
      fireEvent.keyDown(window, { key: 'Shift' });
      fireEvent.mouseMove(window, { clientX: 80, clientY: 40 });
      fireEvent.mouseUp(window, { clientX: 80, clientY: 40 });

      expect(strokesOf(inkNodes()[0])[0].straight).toBeUndefined();
    });
  });

  it('places ink behind the nodes', () => {
    const { getByTestId } = render(<Harness />);
    drawStroke(getByTestId('pane'), [10, 10], [90, 60]);
    expect(inkNodes()[0].style.zIndex).toBeLessThan(0);
  });
});
