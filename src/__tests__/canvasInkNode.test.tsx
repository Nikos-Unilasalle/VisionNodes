import React from 'react';
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { CanvasInkNode } from '../components/nodes/ink';

const params = {
  version: 1,
  strokes: [
    { pts: [{ x: 0, y: 0 }, { x: 20, y: 20 }, { x: 40, y: 0 }], color: '#ffd400', size: 4 },
    { pts: [{ x: 5, y: 30 }], color: '#ff4d4d', size: 2 },
  ],
};

describe('CanvasInkNode', () => {
  it('renders one visible path per stroke, plus its hit twin', () => {
    const { container } = render(<CanvasInkNode selected={false} data={{ params }} />);
    const paths = container.querySelectorAll('path');
    expect(paths).toHaveLength(4);

    const visible = container.querySelectorAll('path[stroke="#ffd400"], path[stroke="#ff4d4d"]');
    expect(visible).toHaveLength(2);
  });

  it('never intercepts pointer events outside the strokes themselves', () => {
    const { container } = render(<CanvasInkNode selected={false} data={{ params }} />);
    const wrapper = container.querySelector('.vn-ink-node') as HTMLElement;
    expect(wrapper.style.pointerEvents).toBe('none');

    const hitPath = container.querySelector('path[stroke="transparent"]') as SVGPathElement;
    expect(hitPath.style.pointerEvents).toBe('stroke');
  });

  it('sizes its viewBox to the stroke bounds', () => {
    const { container } = render(<CanvasInkNode selected={false} data={{ params }} />);
    const svg = container.querySelector('svg') as SVGSVGElement;
    // Padding is half the line width + 1: x 40 + 2 + 1 = 43, y 30 + 1 + 1 = 32.
    expect(svg.getAttribute('viewBox')).toBe('0 0 43 32');
  });

  it('outlines the drawing when selected', () => {
    const { container } = render(<CanvasInkNode selected data={{ params }} />);
    expect(container.querySelector('rect[stroke-dasharray]')).not.toBeNull();
  });

  it('renders nothing but an empty canvas without strokes', () => {
    const { container } = render(<CanvasInkNode selected={false} data={{}} />);
    expect(container.querySelectorAll('path')).toHaveLength(0);
  });
});
