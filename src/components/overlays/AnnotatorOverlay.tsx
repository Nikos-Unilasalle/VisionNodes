import React, { useState, useRef, useEffect, useCallback } from 'react';
import { PenTool, Minus, Type, Circle, Undo2, Trash2, Image } from 'lucide-react';
import { useNodeData } from '../../context/NodesDataContext';
import { PALETTES } from '../Nodes';

type Tool = 'brush' | 'line' | 'text' | 'circle';

type Stroke = {
  tool: Tool;
  pts: [number, number][];
  color: string;
  size: number;
  text?: string;
};

const FIXED_COLORS = ['#ffffff', '#000000', '#ff3333', '#ffcc00', '#33ff88', '#ff33cc'];

const AnnotatorOverlay = ({ node, onClose }: any) => {
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [tool, setTool] = useState<Tool>('brush');
  const [color, setColor] = useState('#ffffff');
  const [size, setSize] = useState(4);
  const [textPos, setTextPos] = useState<[number, number] | null>(null);
  const [textInput, setTextInput] = useState('');
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const isDrawing = useRef(false);
  const isPanning = useRef(false);
  const panOrigin = useRef({ mx: 0, my: 0, px: 0, py: 0 });
  const currentStroke = useRef<Stroke | null>(null);
  const lineStart = useRef<[number, number] | null>(null);
  const strokesRef = useRef<Stroke[]>([]);
  strokesRef.current = strokes;

  const nd = useNodeData(node?.id ?? null);
  const frame = nd?.main_preview || nd?.main;

  const palIdx = node?.data?.activePaletteIndex ?? 6;
  const paletteColors = (PALETTES[palIdx % PALETTES.length]?.colors ?? []).map((c: any) => c.bg);
  const allColors = [...FIXED_COLORS, ...paletteColors];

  useEffect(() => {
    try {
      const saved = node?.data?.params?.annotations;
      if (saved) setStrokes(JSON.parse(saved));
    } catch {}
  }, [node?.id]);

  const getRelPos = useCallback((e: MouseEvent | React.MouseEvent): [number, number] => {
    const el = imgRef.current ?? containerRef.current;
    if (!el) return [0, 0];
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return [0, 0];
    return [
      Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)),
      Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)),
    ];
  }, []);

  const redraw = useCallback((strks: Stroke[], live: Stroke | null = null) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const renderStroke = (s: Stroke | null) => {
      if (!s) return;
      ctx.strokeStyle = s.color;
      ctx.fillStyle = s.color;
      ctx.lineWidth = s.size;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      if (s.tool === 'brush' && s.pts.length > 1) {
        ctx.beginPath();
        ctx.moveTo(s.pts[0][0] * w, s.pts[0][1] * h);
        for (let i = 1; i < s.pts.length; i++) {
          ctx.lineTo(s.pts[i][0] * w, s.pts[i][1] * h);
        }
        ctx.stroke();
      } else if (s.tool === 'line' && s.pts.length >= 2) {
        ctx.beginPath();
        ctx.moveTo(s.pts[0][0] * w, s.pts[0][1] * h);
        ctx.lineTo(s.pts[s.pts.length - 1][0] * w, s.pts[s.pts.length - 1][1] * h);
        ctx.stroke();
      } else if (s.tool === 'circle' && s.pts.length > 0) {
        const cx = s.pts[0][0] * w;
        const cy = s.pts[0][1] * h;
        const r = s.size * Math.min(w, h) / 100;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.stroke();
      } else if (s.tool === 'text' && s.pts.length > 0 && s.text) {
        const fontSize = Math.max(12, s.size * 4);
        ctx.font = `bold ${fontSize}px sans-serif`;
        ctx.shadowColor = 'rgba(0,0,0,0.9)';
        ctx.shadowBlur = 4;
        ctx.shadowOffsetX = 1;
        ctx.shadowOffsetY = 1;
        ctx.fillText(s.text, s.pts[0][0] * w, s.pts[0][1] * h);
        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
      }
    };

    strks.forEach(renderStroke);
    if (live) renderStroke(live);
  }, []);

  // Canvas sizing: use offsetWidth/offsetHeight (layout size, unaffected by CSS transform/zoom)
  useEffect(() => {
    const syncSize = () => {
      const canvas = canvasRef.current;
      const el = imgRef.current ?? containerRef.current;
      if (!canvas || !el) return;
      const newW = el.offsetWidth;
      const newH = el.offsetHeight;
      if (newW > 0 && newH > 0 && (canvas.width !== newW || canvas.height !== newH)) {
        canvas.width = newW;
        canvas.height = newH;
      }
      redraw(strokesRef.current);
    };
    const ro = new ResizeObserver(syncSize);
    if (containerRef.current) ro.observe(containerRef.current);
    syncSize();
    return () => ro.disconnect();
  }, [frame, redraw]);

  useEffect(() => {
    redraw(strokes);
  }, [strokes, redraw]);

  // Pan via global mousemove
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isPanning.current) return;
      setPan({
        x: panOrigin.current.px + (e.clientX - panOrigin.current.mx),
        y: panOrigin.current.py + (e.clientY - panOrigin.current.my),
      });
    };
    const onUp = () => { isPanning.current = false; };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  // Wheel zoom: attach non-passive to prevent scroll
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      const vp = el.getBoundingClientRect();
      const factor = e.deltaY > 0 ? 0.9 : 1.1;
      setZoom(prevZoom => {
        const newZoom = Math.max(0.2, Math.min(15, prevZoom * factor));
        const cx = (e.clientX - vp.left) - vp.width / 2;
        const cy = (e.clientY - vp.top) - vp.height / 2;
        setPan(prevPan => ({
          x: cx - (cx - prevPan.x) * (newZoom / prevZoom),
          y: cy - (cy - prevPan.y) * (newZoom / prevZoom),
        }));
        return newZoom;
      });
    };
    el.addEventListener('wheel', handler, { passive: false });
    return () => el.removeEventListener('wheel', handler);
  }, []);

  const handleMouseDown = (e: React.MouseEvent) => {
    // Middle button or Alt+left = pan
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      e.preventDefault();
      isPanning.current = true;
      panOrigin.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y };
      return;
    }
    if (e.button !== 0) return;
    e.preventDefault();

    const pos = getRelPos(e);

    if (tool === 'text') {
      setTextPos(pos);
      setTextInput('');
      return;
    }

    if (tool === 'circle') {
      setStrokes(prev => [...prev, { tool: 'circle', pts: [pos], color, size }]);
      return;
    }

    isDrawing.current = true;
    currentStroke.current = { tool, pts: [pos], color, size };
    if (tool === 'line') lineStart.current = pos;

    const onMove = (ev: MouseEvent) => {
      if (!isDrawing.current || !currentStroke.current) return;
      const p = getRelPos(ev);
      if (tool === 'brush') {
        currentStroke.current = { ...currentStroke.current, pts: [...currentStroke.current.pts, p] };
      } else if (tool === 'line') {
        currentStroke.current = { ...currentStroke.current, pts: [lineStart.current!, p] };
      }
      redraw(strokesRef.current, currentStroke.current);
    };

    const onUp = () => {
      const finished = currentStroke.current;
      isDrawing.current = false;
      currentStroke.current = null;
      if (finished && finished.pts.length > 0) {
        setStrokes(prev => [...prev, finished]);
      }
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  const commitText = () => {
    if (textPos && textInput.trim()) {
      setStrokes(prev => [...prev, { tool: 'text', pts: [textPos], color, size, text: textInput.trim() }]);
    }
    setTextPos(null);
    setTextInput('');
  };

  const save = () => {
    node.data.onChangeParams({ annotations: JSON.stringify(strokes) });
    onClose();
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (textPos) { setTextPos(null); return; }
        onClose();
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !textPos) {
        e.preventDefault();
        setStrokes(prev => prev.slice(0, -1));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, textPos]);

  const TOOLS: [Tool, React.ElementType, string][] = [
    ['brush',  PenTool, 'Brush'],
    ['line',   Minus,   'Line'],
    ['circle', Circle,  'Circle'],
    ['text',   Type,    'Text'],
  ];

  const cursorStyle = tool === 'text' ? 'text' : 'crosshair';

  return (
    <div
      className="fixed inset-0 z-[1000] bg-black/95 backdrop-blur-3xl flex flex-col items-center justify-center select-none nodrag"
      onContextMenu={e => e.preventDefault()}
    >
      {/* Header */}
      <div className="absolute top-8 left-8 flex items-center gap-4 z-10">
        <div className="p-3 bg-violet-500/20 rounded-2xl text-violet-400 shadow-2xl shadow-violet-500/20">
          <PenTool size={28} />
        </div>
        <div>
          <h2 className="text-2xl font-black uppercase tracking-[0.2em] text-white">ANNOTATOR</h2>
          <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest opacity-50 mt-1">
            {strokes.length} annotation{strokes.length !== 1 ? 's' : ''} · Cmd+Z to undo
          </p>
        </div>
      </div>

      {/* Zoom badge */}
      <div className="absolute top-8 right-8 flex items-center gap-3 z-10">
        <div className="text-[10px] font-black font-mono text-violet-400/60 bg-violet-400/5 border border-violet-400/10 px-3 py-1.5 rounded-full backdrop-blur-md">
          {Math.round(zoom * 100)}%
        </div>
        {(zoom !== 1 || pan.x !== 0 || pan.y !== 0) && (
          <button
            onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}
            className="text-[9px] font-black uppercase tracking-widest text-gray-500 hover:text-gray-300 bg-white/5 hover:bg-white/10 border border-white/10 px-3 py-1.5 rounded-full transition-all"
          >
            Reset View
          </button>
        )}
      </div>

      {/* Canvas area */}
      <div
        ref={viewportRef}
        className="relative flex-1 w-full overflow-hidden"
        onMouseDown={e => {
          if (e.button === 1) {
            isPanning.current = true;
            panOrigin.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y };
          }
        }}
      >
        <div
          className="absolute inset-0 flex items-center justify-center"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: 'center center' }}
        >
          <div
            ref={containerRef}
            className="relative inline-block shadow-[0_0_100px_rgba(0,0,0,0.5)] rounded-2xl overflow-hidden border border-white/10 bg-[#0c0c0c]"
          >
            {frame ? (
              <img
                ref={imgRef}
                src={`data:image/jpeg;base64,${frame}`}
                className="block w-auto h-auto max-w-[90vw] max-h-[72vh]"
                draggable={false}
                alt="annotator"
              />
            ) : (
              <div className="w-[800px] h-[450px] flex items-center justify-center text-gray-700">
                <Image size={48} className="opacity-10" />
              </div>
            )}

            <canvas
              ref={canvasRef}
              className="absolute inset-0 w-full h-full"
              style={{ cursor: cursorStyle }}
              onMouseDown={handleMouseDown}
            />

            {textPos && (
              <input
                autoFocus
                value={textInput}
                onChange={e => setTextInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') commitText();
                  if (e.key === 'Escape') { setTextPos(null); setTextInput(''); }
                }}
                onBlur={commitText}
                style={{
                  position: 'absolute',
                  left: `${textPos[0] * 100}%`,
                  top: `${textPos[1] * 100}%`,
                  transform: 'translateY(-50%)',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: `2px solid ${color}`,
                  color,
                  outline: 'none',
                  fontSize: `${Math.max(14, size * 4)}px`,
                  fontWeight: 'bold',
                  fontFamily: 'sans-serif',
                  minWidth: '80px',
                  textShadow: '1px 1px 3px rgba(0,0,0,1)',
                  zIndex: 10,
                }}
              />
            )}
          </div>
        </div>
      </div>

      {/* Footer toolbar */}
      <div className="p-6 w-full flex flex-col items-center gap-4 bg-gradient-to-t from-black/80 to-transparent">
        <div className="flex items-center gap-5 px-8 py-4 bg-white/5 rounded-3xl border border-white/10 shadow-2xl backdrop-blur-xl flex-wrap justify-center">

          {/* Tool selector */}
          <div className="flex items-center gap-1.5">
            {TOOLS.map(([t, Icon, label]) => (
              <button
                key={t}
                onClick={() => setTool(t)}
                className={`px-3 py-2 rounded-xl flex flex-col items-center gap-1 transition-all ${
                  tool === t
                    ? 'bg-violet-500/40 text-violet-300 border border-violet-500/50'
                    : 'bg-white/5 text-gray-400 border border-white/5 hover:bg-white/10'
                }`}
              >
                <Icon size={15} />
                <span className="text-[8px] font-black uppercase tracking-wider">{label}</span>
              </button>
            ))}
          </div>

          <div className="w-px h-10 bg-white/10" />

          {/* Color palette */}
          <div className="flex items-center gap-1.5 flex-wrap max-w-[280px]">
            {allColors.map((c, i) => (
              <button
                key={i}
                onClick={() => setColor(c)}
                style={{ background: c, boxShadow: color === c ? `0 0 0 2px white, 0 0 0 4px ${c}` : undefined }}
                className={`w-5 h-5 rounded-full border border-white/20 transition-transform ${color === c ? 'scale-125' : 'hover:scale-110'}`}
              />
            ))}
          </div>

          <div className="w-px h-10 bg-white/10" />

          {/* Size */}
          <div className="flex flex-col items-center gap-1.5 min-w-[80px]">
            <span className="text-[8px] font-black text-gray-500 uppercase tracking-wider">Size · {size}</span>
            <input
              type="range" min={1} max={40} value={size}
              onChange={e => setSize(Number(e.target.value))}
              className="w-24 accent-violet-500"
            />
          </div>

          <div className="w-px h-10 bg-white/10" />

          {/* Undo / Clear */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setStrokes(prev => prev.slice(0, -1))}
              disabled={strokes.length === 0}
              className="px-3 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-[9px] font-black uppercase tracking-widest text-gray-400 transition-all flex items-center gap-1.5 disabled:opacity-25"
            >
              <Undo2 size={12} /> Undo
            </button>
            <button
              onClick={() => setStrokes([])}
              disabled={strokes.length === 0}
              className="px-3 py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-xl text-[9px] font-black uppercase tracking-widest text-red-400 transition-all flex items-center gap-1.5 disabled:opacity-25"
            >
              <Trash2 size={12} /> Clear all
            </button>
          </div>

          <div className="w-px h-10 bg-white/10" />

          {/* Navigation hints */}
          <div className="flex items-center gap-3 text-[8px] font-black uppercase tracking-wider text-gray-600">
            <span className="flex items-center gap-1"><kbd className="px-1.5 py-0.5 bg-white/5 border border-white/10 rounded text-[7px]">Scroll</kbd> Zoom</span>
            <span className="flex items-center gap-1"><kbd className="px-1.5 py-0.5 bg-white/5 border border-white/10 rounded text-[7px]">Alt</kbd> Pan</span>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-4">
          <button
            onClick={onClose}
            className="px-8 py-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all active:scale-95"
          >
            Cancel
          </button>
          <button
            onClick={save}
            className="px-16 py-4 bg-violet-600 hover:bg-violet-500 shadow-2xl shadow-violet-500/40 rounded-2xl text-[10px] font-black uppercase tracking-widest text-white transition-all scale-110 hover:scale-[1.15] active:scale-95 border border-white/10"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
};

export default AnnotatorOverlay;
