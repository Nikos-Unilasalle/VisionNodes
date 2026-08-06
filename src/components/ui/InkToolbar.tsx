import React from 'react';
import { Check, Pencil } from 'lucide-react';
import { smoothPath, strokeToPathD, type InkPoint } from '../../utils/inkGeometry';

export const INK_SIZES: Array<{ label: string; value: number }> = [
  { label: 'S', value: 2 },
  { label: 'M', value: 4 },
  { label: 'L', value: 8 },
];

interface InkToolbarProps {
  /** Swatches of the palette the user picked in the top menu. */
  colors: string[];
  color: string;
  size: number;
  onChangeColor: (color: string) => void;
  onChangeSize: (size: number) => void;
  onDone: () => void;
}

/** Floating palette shown while draw mode is active. */
export function InkToolbar({ colors, color, size, onChangeColor, onChangeSize, onDone }: InkToolbarProps) {
  return (
    <div className="flex items-center gap-3 bg-[#2c333f]/95 backdrop-blur-md border border-[#4f5b6b] rounded-2xl px-3 py-2 shadow-2xl">
      <span className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-amber-300">
        <Pencil size={11} /> Draw
      </span>

      <div className="flex items-center gap-1">
        {colors.map(c => (
          <button
            key={c}
            aria-label={`Ink color ${c}`}
            onClick={() => onChangeColor(c)}
            className={`w-4 h-4 rounded-full border transition-all ${
              c === color ? 'border-white scale-125' : 'border-white/20 hover:border-white/60'
            }`}
            style={{ background: c }}
          />
        ))}
      </div>

      <div className="flex items-center gap-1">
        {INK_SIZES.map(s => (
          <button
            key={s.label}
            aria-label={`Ink size ${s.label}`}
            onClick={() => onChangeSize(s.value)}
            className={`w-6 h-6 rounded-lg text-[9px] font-black transition-all ${
              s.value === size
                ? 'bg-amber-400/20 text-amber-300 border border-amber-400/50'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:text-gray-200'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <button
        onClick={onDone}
        className="flex items-center gap-1 bg-amber-500 hover:bg-amber-400 text-black rounded-xl px-2.5 py-1 text-[9px] font-black uppercase tracking-widest transition-colors"
      >
        <Check size={11} /> Done
      </button>

      <span className="text-[8px] text-gray-500 font-mono">Shift = straight · Esc</span>
    </div>
  );
}

interface InkPreviewProps {
  points: InkPoint[];
  color: string;
  size: number;
  /** Straight (Shift) segments must not be smoothed, in preview as on commit. */
  straight?: boolean;
}

/** Screen-space preview of the stroke being drawn, above everything else. */
export function InkPreview({ points, color, size, straight = false }: InkPreviewProps) {
  if (points.length === 0) return null;
  return (
    <svg
      style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 9999 }}
      width="100%"
      height="100%"
    >
      {/* Same treatment as the committed stroke, so nothing shifts on release. */}
      <path
        d={strokeToPathD(straight ? points : smoothPath(points), straight)}
        fill="none"
        stroke={color}
        strokeWidth={size}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
