import React, { useState, useRef, useEffect } from 'react';
import { Image, Scaling } from 'lucide-react';

const ROIEditorOverlay = ({ nodeId, node, nodesData, onClose }: any) => {
  const [points, setPoints] = useState<any[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const viewportRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const isPanning = useRef(false);
  const panOrigin = useRef({ mx: 0, my: 0, px: 0, py: 0 });

  const nd = (() => {
    if (!nodeId || !nodesData) return {};
    const dataKeys = Object.keys(nodesData).filter((k: string) => k.startsWith(`${nodeId}:`));
    return dataKeys.length > 0
      ? Object.fromEntries(dataKeys.map((k: string) => [k.split(':')[1], nodesData[k]]))
      : (nodesData[nodeId] ?? {});
  })();
  const frame = nd?.main_preview || nd?.main;

  useEffect(() => {
    if (node.data.params?.points) {
      try {
        const p = JSON.parse(node.data.params.points);
        if (Array.isArray(p)) setPoints(p);
      } catch (e) {}
    }
  }, [node.id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return; }
      if (selectedIndex === null) return;
      const step = e.shiftKey ? 0.01 : 0.002;
      let dx = 0, dy = 0;
      if (e.key === 'ArrowLeft')  dx = -step;
      if (e.key === 'ArrowRight') dx =  step;
      if (e.key === 'ArrowUp')    dy = -step;
      if (e.key === 'ArrowDown')  dy =  step;
      if (dx || dy) {
        e.preventDefault();
        setPoints(prev => {
          const next = [...prev];
          next[selectedIndex] = {
            x: Math.max(0, Math.min(1, next[selectedIndex].x + dx)),
            y: Math.max(0, Math.min(1, next[selectedIndex].y + dy)),
          };
          return next;
        });
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        setPoints(prev => prev.filter((_, i) => i !== selectedIndex));
        setSelectedIndex(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedIndex, onClose]);

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const vp = viewportRef.current?.getBoundingClientRect();
    if (!vp) return;
    const factor = e.deltaY > 0 ? 0.85 : 1.18;
    const newZoom = Math.max(0.5, Math.min(10, zoom * factor));
    const ox = (e.clientX - vp.left) - vp.width  / 2;
    const oy = (e.clientY - vp.top)  - vp.height / 2;
    setPan({ x: ox - (ox - pan.x) * (newZoom / zoom), y: oy - (oy - pan.y) * (newZoom / zoom) });
    setZoom(newZoom);
  };

  const imgCoords = (clientX: number, clientY: number) => {
    const r = imgRef.current?.getBoundingClientRect();
    if (!r) return null;
    return {
      x: Math.max(0, Math.min(1, (clientX - r.left) / r.width)),
      y: Math.max(0, Math.min(1, (clientY - r.top)  / r.height)),
    };
  };

  const handleSvgMouseDown = (e: React.MouseEvent) => {
    if (e.button === 1) return;
    if (e.button !== 0) return;
    if (e.shiftKey) {
      const c = imgCoords(e.clientX, e.clientY);
      if (!c) return;
      const newPoints = [...points, c];
      setPoints(newPoints);
      setSelectedIndex(newPoints.length - 1);
      return;
    }
    isPanning.current = true;
    panOrigin.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y };
    setSelectedIndex(null);
  };

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
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  const updatePoint = (index: number, x: number, y: number) => {
    setPoints(prev => { const next = [...prev]; if (!next[index]) return prev; next[index] = { x, y }; return next; });
  };

  const save = () => { node.data.onChangeParams({ points: JSON.stringify(points) }); onClose(); };

  return (
    <div className="fixed inset-0 z-[1000] bg-black/95 backdrop-blur-3xl flex flex-col items-center justify-center p-3 select-none nodrag" onContextMenu={e => e.preventDefault()}>
      <div className="absolute top-3 left-5 flex items-center gap-4">
        <div className="p-2 bg-accent/20 rounded-lg text-accent"><Scaling size={24} /></div>
        <div>
          <h2 className="text-xl font-black uppercase tracking-widest text-white">MASK POLYGON EDITOR</h2>
          <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest opacity-50">Scroll to zoom · Drag to pan · Shift+click to add</p>
        </div>
      </div>

      <div className="absolute top-4 right-5 text-[10px] font-black font-mono text-accent/60 bg-accent/5 border border-accent/10 px-2 py-1 rounded-lg">
        {Math.round(zoom * 100)}%
      </div>

      <div
        ref={viewportRef}
        className="relative flex-1 w-full overflow-hidden cursor-crosshair"
        onWheel={handleWheel}
        onMouseDown={e => { if (e.button === 1) { isPanning.current = true; panOrigin.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y }; }}}
      >
        <div
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: 'center center' }}
        >
          <div className="relative inline-block shadow-2xl rounded-2xl overflow-hidden border border-white/10 bg-[#0c0c0c] pointer-events-auto">
            {frame ? (
              <img
                ref={imgRef}
                src={`data:image/jpeg;base64,${frame}`}
                className="block w-auto h-auto max-w-[90vw] max-h-[80vh]"
                draggable={false}
              />
            ) : (
              <div className="w-[800px] h-[450px] flex flex-col items-center justify-center text-gray-700">
                <Image size={48} className="opacity-10" />
              </div>
            )}

            <svg className="absolute inset-0 w-full h-full" onMouseDown={handleSvgMouseDown}>
              <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 w-full h-full overflow-visible">
                {points.length >= 3 && (
                  <polygon points={points.map(p => `${p.x},${p.y}`).join(' ')} className="fill-accent/20 stroke-accent" style={{ strokeWidth: 0.004, pointerEvents: 'none' }} />
                )}
                {points.length > 0 && (
                  <polyline points={points.map(p => `${p.x},${p.y}`).join(' ')} fill="none" stroke="var(--color-accent)" style={{ strokeWidth: 0.004, strokeDasharray: points.length >= 3 ? 'none' : '0.01 0.01', pointerEvents: 'none' }} />
                )}
              </svg>
              {points.map((p, i) => (
                <circle
                  key={i}
                  cx={`${p.x * 100}%`} cy={`${p.y * 100}%`}
                  r={(selectedIndex === i ? 8 : 6) / zoom}
                  fill={selectedIndex === i ? 'white' : 'var(--color-accent)'}
                  stroke={selectedIndex === i ? 'var(--color-accent)' : 'white'}
                  strokeWidth={2 / zoom}
                  className="cursor-move"
                  onMouseDown={e => {
                    e.stopPropagation();
                    if (e.button === 2) { setPoints(prev => prev.filter((_, idx) => idx !== i)); setSelectedIndex(null); return; }
                    setSelectedIndex(i);
                    const move = (me: MouseEvent) => {
                      const c = imgCoords(me.clientX, me.clientY);
                      if (c) updatePoint(i, c.x, c.y);
                    };
                    const up = () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
                    window.addEventListener('mousemove', move);
                    window.addEventListener('mouseup', up);
                  }}
                />
              ))}
            </svg>
          </div>
        </div>
      </div>

      <div className="mt-3 flex flex-col items-center gap-3">
        <div className="flex items-center gap-6 px-8 py-3 bg-white/5 rounded-3xl border border-white/5 shadow-inner backdrop-blur-md">
          <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-500">
            <span className="px-2 py-1 bg-accent/20 text-accent rounded-lg border border-accent/20">SHIFT+CLIC</span><span>ADD</span>
          </div>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-500">
            <span className="px-2 py-1 bg-white/10 text-white rounded-lg border border-white/10">DRAG</span><span>PAN</span>
          </div>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-500">
            <span className="px-2 py-1 bg-white/10 text-white rounded-lg border border-white/10">SCROLL</span><span>ZOOM</span>
          </div>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-500">
            <span className="px-2 py-1 bg-white/10 text-white rounded-lg border border-white/10">ARROWS</span><span>NUDGE</span>
          </div>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-500">
            <span className="px-2 py-1 bg-red-500/10 text-red-500 rounded-lg border border-red-500/20">R-CLIC</span><span>DELETE</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={onClose} className="px-10 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all">Cancel</button>
          <button onClick={() => setPoints([])} className="px-10 py-3 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-2xl text-[10px] font-black uppercase tracking-widest text-red-500 transition-all">Clear All</button>
          <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} className="px-6 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all">Reset View</button>
          <button onClick={save} className="px-16 py-3 bg-accent hover:bg-blue-600 shadow-2xl shadow-accent/20 rounded-2xl text-[10px] font-black uppercase tracking-widest text-white transition-all scale-105 active:scale-95 border border-white/10">Apply Mask</button>
        </div>
      </div>
    </div>
  );
};

export default ROIEditorOverlay;
