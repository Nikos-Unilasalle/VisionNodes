import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

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

function formatKey(e: KeyboardEvent): string {
  const parts: string[] = [];
  if (e.metaKey)  parts.push('⌘');
  if (e.ctrlKey)  parts.push('⌃');
  if (e.altKey)   parts.push('⌥');
  if (e.shiftKey && !['Shift'].includes(e.key)) parts.push('⇧');

  const key = e.key;
  if (['Meta', 'Control', 'Alt', 'Shift'].includes(key)) return '';

  const label = KEY_LABELS[key] ?? (key.length === 1 ? key.toUpperCase() : key);
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

export default function TutorialOverlay() {
  const [keyEvents, setKeyEvents]     = useState<KeyEvent[]>([]);
  const [mouseEvents, setMouseEvents] = useState<MouseEvent_[]>([]);
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
      }, 2000);
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
      }, 700);
      mouseTimers.current.set(id, t);
    };

    window.addEventListener('keydown', onKeyDown, true);
    window.addEventListener('mousedown', onMouseDown, true);
    return () => {
      window.removeEventListener('keydown', onKeyDown, true);
      window.removeEventListener('mousedown', onMouseDown, true);
      keyTimers.current.forEach(t => clearTimeout(t));
      mouseTimers.current.forEach(t => clearTimeout(t));
    };
  }, []);

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 pointer-events-none z-[9999]">
      {/* Mouse indicators */}
      <div className="flex gap-2">
        <AnimatePresence>
          {mouseEvents.map(ev => (
            <motion.div
              key={ev.id}
              initial={{ opacity: 0, scale: 0.6 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.6 }}
              transition={{ duration: 0.12 }}
              className={`${MOUSE_COLORS[ev.button]} text-white text-xs font-bold w-8 h-8 rounded-full flex items-center justify-center shadow-lg`}
            >
              {ev.button}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Key indicators */}
      <div className="flex flex-wrap justify-center gap-2 max-w-sm">
        <AnimatePresence>
          {keyEvents.map(ev => (
            <motion.div
              key={ev.id}
              initial={{ opacity: 0, y: 8, scale: 0.85 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.9 }}
              transition={{ duration: 0.15 }}
              className="bg-gray-900/90 border border-gray-600 text-white text-sm font-mono px-3 py-1.5 rounded-lg shadow-xl backdrop-blur-sm"
            >
              {ev.label}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
