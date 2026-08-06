import { useEffect, useRef, useState } from 'react';

interface KeyEvent {
  id: number;
  label: string;
}

interface MouseEvent_ {
  id: number;
  button: 'L' | 'M' | 'R';
}

const KEY_LABELS: Record<string, string> = {
  Meta: '⌘', Control: '⌃', Alt: '⌥', Shift: '⇧',
  Enter: '↵', Backspace: '⌫', Delete: '⌦', Escape: 'Esc',
  Tab: '⇥', CapsLock: '⇪', Space: 'Space',
  ArrowUp: '↑', ArrowDown: '↓', ArrowLeft: '←', ArrowRight: '→',
};

const KEY_TTL_MS = 2000;
const MOUSE_TTL_MS = 700;

/** How long the pointer must rest on a node before its description shows. */
export const HOVER_DWELL_MS = 450;

export interface TutorialNodeInfo {
  label: string;
  description?: string;
}

interface TutorialOverlayProps {
  /** Resolves a React Flow node id to what should be explained about it. */
  getNodeInfo?: (nodeId: string) => TutorialNodeInfo | null;
}

export function formatKey(e: KeyboardEvent): string {
  const parts: string[] = [];
  if (e.metaKey)  parts.push('⌘');
  if (e.ctrlKey)  parts.push('⌃');
  if (e.altKey)   parts.push('⌥');
  if (e.shiftKey && !['Shift'].includes(e.key)) parts.push('⇧');

  const key = e.key;
  if (['Meta', 'Control', 'Alt', 'Shift'].includes(key)) return '';

  // Option+letter yields a symbol on macOS (†, ∂…): fall back to the physical
  // key so the badge shows ⌥T rather than ⌥†.
  const physical = /^Key([A-Z])$/.exec(e.code)?.[1] ?? /^Digit(\d)$/.exec(e.code)?.[1];
  const label = KEY_LABELS[key]
    ?? (e.altKey && physical ? physical : undefined)
    ?? (key.length === 1 ? key.toUpperCase() : key);
  parts.push(label);
  return parts.join('');
}

const MOUSE_COLORS = {
  L: 'bg-blue-500/80',
  M: 'bg-yellow-500/80',
  R: 'bg-red-500/80',
} as const;

let _uid = 0;
const uid = () => ++_uid;

/**
 * Screencast helper: shows the keys and mouse buttons being pressed.
 *
 * Deliberately plain DOM — no animation library. Badges are short-lived, and an
 * animation that fails to start would leave them stuck at opacity 0, i.e. an
 * overlay that looks dead while working perfectly.
 */
export default function TutorialOverlay({ getNodeInfo }: TutorialOverlayProps = {}) {
  const [keyEvents, setKeyEvents]     = useState<KeyEvent[]>([]);
  const [mouseEvents, setMouseEvents] = useState<MouseEvent_[]>([]);
  const [hovered, setHovered]         = useState<TutorialNodeInfo | null>(null);
  const keyTimers   = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());
  const mouseTimers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const label = formatKey(e);
      if (!label) return;
      const id = uid();
      setKeyEvents(prev => [...prev.slice(-4), { id, label }]);

      const t = setTimeout(() => {
        setKeyEvents(prev => prev.filter(k => k.id !== id));
        keyTimers.current.delete(id);
      }, KEY_TTL_MS);
      keyTimers.current.set(id, t);
    };

    const onMouseDown = (e: globalThis.MouseEvent) => {
      const map: Record<number, 'L' | 'M' | 'R'> = { 0: 'L', 1: 'M', 2: 'R' };
      const button = map[e.button];
      if (!button) return;
      const id = uid();
      setMouseEvents(prev => [...prev.slice(-2), { id, button }]);

      const t = setTimeout(() => {
        setMouseEvents(prev => prev.filter(m => m.id !== id));
        mouseTimers.current.delete(id);
      }, MOUSE_TTL_MS);
      mouseTimers.current.set(id, t);
    };

    const keys = keyTimers.current;
    const mice = mouseTimers.current;

    // Window capture fires before anything else on the page; adding the same
    // handler on document too would count every event twice.
    window.addEventListener('keydown', onKeyDown, true);
    window.addEventListener('mousedown', onMouseDown, true);
    return () => {
      window.removeEventListener('keydown', onKeyDown, true);
      window.removeEventListener('mousedown', onMouseDown, true);
      keys.forEach(t => clearTimeout(t));
      mice.forEach(t => clearTimeout(t));
    };
  }, []);

  // Resting the pointer on a node explains it. A dwell delay keeps the panel
  // from flickering while the pointer merely crosses the canvas.
  const hoveredIdRef = useRef<string | null>(null);
  const dwellTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!getNodeInfo) return;

    const cancelDwell = () => {
      if (dwellTimer.current) clearTimeout(dwellTimer.current);
      dwellTimer.current = null;
    };

    const onMouseMove = (e: globalThis.MouseEvent) => {
      const el = e.target as HTMLElement | null;
      const nodeEl = el?.closest?.('.react-flow__node') as HTMLElement | null;
      const nodeId = nodeEl?.getAttribute('data-id') ?? null;
      if (nodeId === hoveredIdRef.current) return;

      hoveredIdRef.current = nodeId;
      cancelDwell();
      if (!nodeId) {
        setHovered(null);
        return;
      }
      dwellTimer.current = setTimeout(() => {
        // The pointer may have moved on while the timer was pending.
        if (hoveredIdRef.current !== nodeId) return;
        setHovered(getNodeInfo(nodeId));
      }, HOVER_DWELL_MS);
    };

    window.addEventListener('mousemove', onMouseMove, true);
    return () => {
      window.removeEventListener('mousemove', onMouseMove, true);
      cancelDwell();
      hoveredIdRef.current = null;
    };
  }, [getNodeInfo]);

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 pointer-events-none z-[9999]">
      {/* Mouse indicators */}
      <div className="flex gap-2 h-8 items-center">
        {mouseEvents.map(ev => (
          <div
            key={ev.id}
            className={`${MOUSE_COLORS[ev.button]} vn-tutorial-pop text-white text-xs font-bold w-8 h-8 rounded-full flex items-center justify-center shadow-lg`}
          >
            {ev.button}
          </div>
        ))}
      </div>

      {/* Hovered node: label + description */}
      {hovered && (
        <div className="vn-tutorial-pop max-w-xl bg-gray-900/92 border border-emerald-400/25 rounded-xl px-4 py-2.5 shadow-2xl text-center">
          <div className="text-emerald-300 text-[10px] font-black uppercase tracking-[0.15em]">
            {hovered.label}
          </div>
          {hovered.description && (
            <div className="text-gray-300 text-[11px] leading-snug mt-1">
              {hovered.description}
            </div>
          )}
        </div>
      )}

      {/* Key indicators */}
      <div className="flex flex-wrap justify-center gap-2 max-w-sm items-center">
        {/* Always on screen: without it, an idle tutorial mode looks broken. */}
        <span className="bg-emerald-500/15 border border-emerald-400/40 text-emerald-300 text-[9px] font-black uppercase tracking-[0.18em] px-2 py-1 rounded-lg">
          Tutorial
        </span>
        {keyEvents.map(ev => (
          <div
            key={ev.id}
            className="bg-gray-900/90 vn-tutorial-pop border border-gray-600 text-white text-sm font-mono px-3 py-1.5 rounded-lg shadow-xl"
          >
            {ev.label}
          </div>
        ))}
      </div>
    </div>
  );
}
