import { useRef, useCallback, useState } from 'react';
import type { Node, Edge } from 'reactflow';

export interface HistorySnapshot {
  nodes: Node[];
  edges: Edge[];
}

const MAX = 50;

export function useHistory() {
  const ref = useRef<Map<string, { past: HistorySnapshot[]; future: HistorySnapshot[] }>>(new Map());
  const [, tick] = useState(0);
  const bump = () => tick(n => n + 1);

  const stack = useCallback((id: string) => {
    if (!ref.current.has(id)) ref.current.set(id, { past: [], future: [] });
    return ref.current.get(id)!;
  }, []);

  const push = useCallback((canvasId: string, snap: HistorySnapshot) => {
    const s = stack(canvasId);
    s.past = [...s.past.slice(-(MAX - 1)), snap];
    s.future = [];
    bump();
  }, [stack]);

  const undo = useCallback((canvasId: string, current: HistorySnapshot): HistorySnapshot | null => {
    const s = stack(canvasId);
    if (!s.past.length) return null;
    const prev = s.past[s.past.length - 1];
    s.past = s.past.slice(0, -1);
    s.future = [current, ...s.future.slice(0, MAX - 1)];
    bump();
    return prev;
  }, [stack]);

  const redo = useCallback((canvasId: string, current: HistorySnapshot): HistorySnapshot | null => {
    const s = stack(canvasId);
    if (!s.future.length) return null;
    const next = s.future[0];
    s.future = s.future.slice(1);
    s.past = [...s.past.slice(-(MAX - 1)), current];
    bump();
    return next;
  }, [stack]);

  const canUndo = useCallback((canvasId: string) =>
    (ref.current.get(canvasId)?.past.length ?? 0) > 0, []);

  const canRedo = useCallback((canvasId: string) =>
    (ref.current.get(canvasId)?.future.length ?? 0) > 0, []);

  return { push, undo, redo, canUndo, canRedo };
}
