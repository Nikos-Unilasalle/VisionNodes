import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, fireEvent, screen, act } from '@testing-library/react';
import TutorialOverlay, { formatKey, HOVER_DWELL_MS } from '../components/overlays/TutorialOverlay';

describe('TutorialOverlay', () => {
  it('shows it is on before any input happens', () => {
    render(<TutorialOverlay />);
    expect(screen.getByText(/Tutorial/)).toBeInTheDocument();
  });

  it('badges an event once, not once per listener', () => {
    render(<TutorialOverlay />);
    fireEvent.keyDown(window, { key: 'a', code: 'KeyA' });
    fireEvent.mouseDown(document.body, { button: 2 });

    expect(screen.getAllByText('A')).toHaveLength(1);
    expect(screen.getAllByText('R')).toHaveLength(1);
  });

  it('renders badges without relying on an animation to reveal them', () => {
    const { container } = render(<TutorialOverlay />);
    fireEvent.keyDown(window, { key: 'a', code: 'KeyA' });

    const badge = screen.getByText('A');
    // No inline opacity/transform: nothing to get stuck at 0 if JS animation fails.
    expect(badge.getAttribute('style')).toBeNull();
    expect(container.querySelector('.vn-tutorial-pop')).not.toBeNull();
  });

  describe('hovering a node', () => {
    const NODE_INFO = { label: 'DF Slice', description: 'Keep a contiguous range of rows.' };
    const getNodeInfo = vi.fn((id: string) => (id === 'n1' ? NODE_INFO : null));

    const renderWithNode = () => {
      const view = render(
        <>
          <div className="react-flow__node" data-id="n1" data-testid="node" />
          <div data-testid="empty-canvas" />
          <TutorialOverlay getNodeInfo={getNodeInfo} />
        </>,
      );
      return view;
    };

    const dwell = (ms = HOVER_DWELL_MS) => act(() => { vi.advanceTimersByTime(ms); });

    afterEach(() => {
      vi.useRealTimers();
      getNodeInfo.mockClear();
    });

    it('explains the node once the pointer has rested on it', () => {
      vi.useFakeTimers();
      const { getByTestId } = renderWithNode();

      fireEvent.mouseMove(getByTestId('node'));
      expect(screen.queryByText(NODE_INFO.description)).not.toBeInTheDocument();

      dwell();
      expect(screen.getByText('DF Slice')).toBeInTheDocument();
      expect(screen.getByText(NODE_INFO.description)).toBeInTheDocument();
    });

    it('stays quiet while the pointer merely crosses the node', () => {
      vi.useFakeTimers();
      const { getByTestId } = renderWithNode();

      fireEvent.mouseMove(getByTestId('node'));
      dwell(HOVER_DWELL_MS - 50);
      fireEvent.mouseMove(getByTestId('empty-canvas'));
      dwell();

      expect(screen.queryByText(NODE_INFO.description)).not.toBeInTheDocument();
      expect(getNodeInfo).not.toHaveBeenCalled();
    });

    it('clears the panel when the pointer leaves the node', () => {
      vi.useFakeTimers();
      const { getByTestId } = renderWithNode();

      fireEvent.mouseMove(getByTestId('node'));
      dwell();
      expect(screen.getByText('DF Slice')).toBeInTheDocument();

      fireEvent.mouseMove(getByTestId('empty-canvas'));
      expect(screen.queryByText('DF Slice')).not.toBeInTheDocument();
    });

    it('stays silent over a node the app declines to explain', () => {
      // How ink is excluded: the lookup returns null for it.
      vi.useFakeTimers();
      render(
        <>
          <div className="react-flow__node" data-id="ink-1" data-testid="ink" />
          <TutorialOverlay getNodeInfo={() => null} />
        </>,
      );

      fireEvent.mouseMove(screen.getByTestId('ink'));
      dwell();
      expect(screen.queryByRole('heading')).not.toBeInTheDocument();
      expect(screen.getByText('Tutorial')).toBeInTheDocument();
    });

    it('shows the label alone when the node has no description', () => {
      vi.useFakeTimers();
      render(
        <>
          <div className="react-flow__node" data-id="bare" data-testid="bare" />
          <TutorialOverlay getNodeInfo={() => ({ label: 'Reroute' })} />
        </>,
      );

      fireEvent.mouseMove(screen.getByTestId('bare'));
      dwell();
      expect(screen.getByText('Reroute')).toBeInTheDocument();
    });
  });

  it('labels Option+letter by physical key, not the macOS symbol', () => {
    // macOS turns Option+T into '†'; the badge must still read ⌥T.
    const label = formatKey({
      key: '†', code: 'KeyT', altKey: true, metaKey: false, ctrlKey: false, shiftKey: false,
    } as KeyboardEvent);
    expect(label).toBe('⌥T');
  });

  it('badges a key press', () => {
    render(<TutorialOverlay />);
    fireEvent.keyDown(window, { key: 'a' });
    expect(screen.getByText('A')).toBeInTheDocument();
  });

  it('spells out modifier combinations', () => {
    render(<TutorialOverlay />);
    fireEvent.keyDown(window, { key: 's', metaKey: true, shiftKey: true });
    expect(screen.getByText('⌘⇧S')).toBeInTheDocument();
  });

  it('ignores a modifier pressed on its own', () => {
    render(<TutorialOverlay />);
    fireEvent.keyDown(window, { key: 'Shift', shiftKey: true });
    expect(screen.queryByText('⇧')).not.toBeInTheDocument();
  });

  it('badges each mouse button', () => {
    render(<TutorialOverlay />);
    fireEvent.mouseDown(document.body, { button: 0 });
    fireEvent.mouseDown(document.body, { button: 2 });
    expect(screen.getByText('L')).toBeInTheDocument();
    expect(screen.getByText('R')).toBeInTheDocument();
  });
});
