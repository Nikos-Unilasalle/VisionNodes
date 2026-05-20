import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Palette, Eraser, Undo2, Trash2, X } from 'lucide-react';
import { useNodeData } from '../../context/NodesDataContext';

type IndexClass = { label: string; value: number; color: string };
type Stroke = { class_idx: number; pts: [number, number][]; radius: number };

const DEFAULT_CLASSES: IndexClass[] = [
  { label: 'Water',      value: -0.50, color: '#2196f3' },
  { label: 'Bare Soil',  value:  0.10, color: '#ff9800' },
  { label: 'Sparse Veg', value:  0.40, color: '#8bc34a' },
  { label: 'Dense Veg',  value:  0.80, color: '#2e7d32' },
  { label: 'Urban',      value: -0.10, color: '#9e9e9e' },
];

const IndexPainterOverlay = ({ node, onClose }: any) => {
  const [strokes, setStrokes]         = useState<Stroke[]>([]);
  const [classes, setClasses]         = useState<IndexClass[]>(DEFAULT_CLASSES);
  const [activeClass, setActiveClass] = useState(0);
  const [brushRadius, setBrushRadius] = useState(0.03);
  const [eraser, setEraser]           = useState(false);

  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const imgRef     = useRef<HTMLImageElement | null>(null);
  const placeholderRef = useRef<HTMLDivElement>(null);
  const isDrawing  = useRef(false);
  const strokesRef = useRef<Stroke[]>([]);
  strokesRef.current = strokes;
  const classesRef = useRef<IndexClass[]>(DEFAULT_CLASSES);
  classesRef.current = classes;

  const nd      = useNodeData(node?.id ?? null);
  const preview = nd?.main_preview;

  useEffect(() => {
    try {
      const s = JSON.parse(node?.data?.params?.strokes || '[]');
      if (Array.isArray(s)) setStrokes(s);
    } catch {}
    try {
      const c = JSON.parse(node?.data?.params?.classes || '[]');
      if (Array.isArray(c) && c.length > 0) setClasses(c);
    } catch {}
  }, [node?.id]);

  const getContainer = useCallback((): HTMLElement | null => {
    return imgRef.current ?? placeholderRef.current;
  }, []);

  const getRelPos = useCallback((e: MouseEvent | React.MouseEvent): [number, number] => {
    const el = getContainer();
    if (!el) return [0, 0];
    const r = el.getBoundingClientRect();
    return [
      Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)),
      Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)),
    ];
  }, [getContainer]);

  const redraw = useCallback((strks: Stroke[]) => {
    const canvas = canvasRef.current;
    const el = getContainer();
    if (!canvas || !el) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = el.offsetWidth;
    const h = el.offsetHeight;
    if (w === 0 || h === 0) return;
    canvas.width  = w;
    canvas.height = h;
    ctx.clearRect(0, 0, w, h);

    for (const stroke of strks) {
      const cls = classesRef.current[stroke.class_idx] ?? DEFAULT_CLASSES[0];
      const r   = Math.max(2, stroke.radius * Math.min(w, h));

      ctx.save();
      ctx.strokeStyle = cls.color + 'cc';
      ctx.fillStyle   = cls.color + 'cc';
      ctx.lineWidth   = r * 2;
      ctx.lineCap     = 'round';
      ctx.lineJoin    = 'round';

      if (stroke.pts.length === 1) {
        ctx.beginPath();
        ctx.arc(stroke.pts[0][0] * w, stroke.pts[0][1] * h, r, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.beginPath();
        ctx.moveTo(stroke.pts[0][0] * w, stroke.pts[0][1] * h);
        for (let i = 1; i < stroke.pts.length; i++) {
          ctx.lineTo(stroke.pts[i][0] * w, stroke.pts[i][1] * h);
        }
        ctx.stroke();
      }
      ctx.restore();
    }
  }, [getContainer]);

  useEffect(() => { redraw(strokes); }, [strokes, redraw]);

  const commit = useCallback((strks: Stroke[]) => {
    node?.data?.onChangeParams?.({ strokes: JSON.stringify(strks) });
  }, [node]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    const pos = getRelPos(e);

    if (eraser) {
      const el = getContainer();
      const ew = el?.offsetWidth  ?? 512;
      const eh = el?.offsetHeight ?? 512;
      const updated = strokesRef.current.filter(stroke =>
        !stroke.pts.some(pt =>
          Math.abs(pt[0] - pos[0]) * ew < stroke.radius * ew * 4 &&
          Math.abs(pt[1] - pos[1]) * eh < stroke.radius * eh * 4
        )
      );
      setStrokes(updated);
      commit(updated);
      return;
    }

    isDrawing.current = true;
    const newStroke: Stroke = { class_idx: activeClass, pts: [pos], radius: brushRadius };
    const liveRef = { current: newStroke };

    const onMove = (ev: MouseEvent) => {
      if (!isDrawing.current) return;
      const p   = getRelPos(ev);
      const el  = getContainer();
      const ew  = el?.offsetWidth  ?? 512;
      const eh  = el?.offsetHeight ?? 512;
      const last = liveRef.current.pts[liveRef.current.pts.length - 1];
      const dx  = (p[0] - last[0]) * ew;
      const dy  = (p[1] - last[1]) * eh;
      if (Math.sqrt(dx * dx + dy * dy) < 3) return;
      liveRef.current = { ...liveRef.current, pts: [...liveRef.current.pts, p] };
      redraw([...strokesRef.current, liveRef.current]);
    };

    const onUp = () => {
      isDrawing.current = false;
      const finished = liveRef.current;
      if (finished.pts.length > 0) {
        const updated = [...strokesRef.current, finished];
        setStrokes(updated);
        commit(updated);
      }
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [activeClass, brushRadius, eraser, getContainer, getRelPos, redraw, commit]);

  const undo = useCallback(() => {
    setStrokes(prev => {
      const updated = prev.slice(0, -1);
      commit(updated);
      return updated;
    });
  }, [commit]);

  const clear = useCallback(() => {
    setStrokes([]);
    commit([]);
  }, [commit]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if ((e.metaKey || e.ctrlKey) && e.key === 'z') {
        e.preventDefault();
        undo();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, undo]);

  const valueLabel = (v: number) => (v >= 0 ? '+' : '') + v.toFixed(2);

  return (
    <div className="fixed inset-0 z-[1000] bg-black/95 backdrop-blur-3xl flex select-none nodrag"
      onContextMenu={e => e.preventDefault()}>

      {/* Canvas area */}
      <div className="flex-1 flex items-center justify-center relative overflow-hidden bg-[#0a0a0a]">
        {/* Subtle grid background */}
        <div className="absolute inset-0 opacity-5"
          style={{ backgroundImage: 'linear-gradient(#fff 1px,transparent 1px),linear-gradient(90deg,#fff 1px,transparent 1px)', backgroundSize: '32px 32px' }} />

        <div
          className="relative shadow-2xl"
          style={{ cursor: eraser ? 'cell' : 'crosshair', userSelect: 'none' }}
          onMouseDown={handleMouseDown}
        >
          {preview ? (
            <img
              ref={imgRef}
              src={`data:image/jpeg;base64,${preview}`}
              className="block rounded-lg border border-white/10"
              draggable={false}
              style={{ maxWidth: '75vw', maxHeight: '80vh' }}
              onLoad={() => redraw(strokes)}
            />
          ) : (
            <div
              ref={placeholderRef}
              className="w-[512px] h-[512px] bg-gray-900/60 rounded-lg border border-white/10 flex items-center justify-center"
            >
              <Palette size={48} className="opacity-10 text-white" />
            </div>
          )}
          <canvas
            ref={canvasRef}
            className="absolute inset-0 rounded-lg pointer-events-none"
            style={{ width: '100%', height: '100%', mixBlendMode: 'normal' }}
          />
        </div>
      </div>

      {/* Right panel */}
      <div className="w-72 bg-black/70 border-l border-white/5 flex flex-col p-5 gap-5 overflow-y-auto">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-cyan-500/15 rounded-xl text-cyan-400">
              <Palette size={16} />
            </div>
            <div>
              <div className="text-[11px] font-black uppercase tracking-[0.15em] text-white">Index Painter</div>
              <div className="text-[9px] text-gray-500 font-bold mt-0.5">{strokes.length} stroke{strokes.length !== 1 ? 's' : ''}</div>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-600 hover:text-white transition-colors p-1">
            <X size={16} />
          </button>
        </div>

        {/* Classes */}
        <div className="flex flex-col gap-1.5">
          <div className="text-[9px] font-black uppercase tracking-widest text-gray-500 px-1">Classes</div>
          {classes.map((cls, i) => (
            <button
              key={i}
              onClick={() => { setActiveClass(i); setEraser(false); }}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-xl border transition-all text-left ${
                activeClass === i && !eraser
                  ? 'border-white/25 bg-white/8 shadow-sm'
                  : 'border-white/5 bg-white/2 hover:bg-white/6'
              }`}
            >
              <div className="w-3.5 h-3.5 rounded-full flex-shrink-0 ring-1 ring-white/20"
                style={{ backgroundColor: cls.color }} />
              <div className="flex-1 min-w-0">
                <div className="text-[10px] font-bold text-white truncate">{cls.label}</div>
              </div>
              <div className="text-[9px] font-mono tabular-nums text-gray-400 flex-shrink-0">
                {valueLabel(cls.value)}
              </div>
              {activeClass === i && !eraser && (
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 flex-shrink-0" />
              )}
            </button>
          ))}
        </div>

        {/* Brush size */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between px-1">
            <div className="text-[9px] font-black uppercase tracking-widest text-gray-500">Brush</div>
            <div className="text-[9px] font-mono text-gray-400">{Math.round(brushRadius * 100)}%</div>
          </div>
          <input
            type="range" min={0.005} max={0.15} step={0.005}
            value={brushRadius}
            onChange={e => setBrushRadius(parseFloat(e.target.value))}
            className="w-full accent-cyan-400 h-1"
          />
        </div>

        {/* Eraser */}
        <button
          onClick={() => setEraser(v => !v)}
          className={`flex items-center justify-center gap-2 py-2.5 rounded-xl border text-[10px] font-black uppercase tracking-widest transition-all ${
            eraser
              ? 'border-amber-400/50 bg-amber-400/10 text-amber-400'
              : 'border-white/10 bg-white/4 text-gray-400 hover:text-white hover:bg-white/8'
          }`}
        >
          <Eraser size={12} />
          Erase Stroke
        </button>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Actions */}
        <div className="flex flex-col gap-2">
          <div className="text-[8px] font-black uppercase tracking-widest text-gray-600 px-1">
            Cmd+Z to undo · Esc to close
          </div>
          <button
            onClick={undo}
            className="flex items-center justify-center gap-2 py-2.5 rounded-xl border border-white/10 bg-white/4 text-gray-400 hover:text-white hover:bg-white/8 text-[10px] font-black uppercase tracking-widest transition-all"
          >
            <Undo2 size={12} />
            Undo
          </button>
          <button
            onClick={clear}
            className="flex items-center justify-center gap-2 py-2.5 rounded-xl border border-red-400/20 bg-red-400/5 text-red-400/50 hover:text-red-400 hover:bg-red-400/10 text-[10px] font-black uppercase tracking-widest transition-all"
          >
            <Trash2 size={12} />
            Clear All
          </button>
        </div>
      </div>
    </div>
  );
};

export default IndexPainterOverlay;
