import React, { useState, useRef, useEffect } from 'react';
import { Image, Crop } from 'lucide-react';

const CropEditorOverlay = ({ node, nodesData, onClose }: any) => {
  const [rect, setRect] = useState({ x: 0.1, y: 0.1, w: 0.8, h: 0.8 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const viewportRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const isPanning = useRef(false);
  const panOrigin = useRef({ mx: 0, my: 0, px: 0, py: 0 });

  const dragMode = useRef<string | null>(null);
  const dragStart = useRef({ mx: 0, my: 0, rect: { x: 0, y: 0, w: 0, h: 0 } });

  const nd = (() => {
    if (!node?.id || !nodesData) return {};
    const dataKeys = Object.keys(nodesData).filter((k: string) => k.startsWith(`${node.id}:`));
    return dataKeys.length > 0
      ? Object.fromEntries(dataKeys.map((k: string) => [k.split(':')[1], nodesData[k]]))
      : (nodesData[node.id] ?? {});
  })();
  const frame = nd?.main_preview || nd?.main;

  useEffect(() => {
    try {
      if (node?.data?.params?.rect) setRect(JSON.parse(node.data.params.rect));
    } catch(e) {}
  }, [node?.id]);

  const getRelPos = (e: MouseEvent | React.MouseEvent) => {
    const r = imgRef.current?.getBoundingClientRect();
    if (!r) return { x: 0, y: 0 };
    return { x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), y: Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)) };
  };

  const HANDLE = 0.025;
  const getMode = (mx: number, my: number, r: typeof rect) => {
    const h = HANDLE / zoom;
    const corners = { nw: [r.x, r.y], ne: [r.x+r.w, r.y], sw: [r.x, r.y+r.h], se: [r.x+r.w, r.y+r.h] } as Record<string,[number,number]>;
    for (const [name, [cx, cy]] of Object.entries(corners))
      if (Math.abs(mx - cx) < h && Math.abs(my - cy) < h) return name;
    if (mx > r.x && mx < r.x+r.w && my > r.y && my < r.y+r.h) return 'move';
    return 'draw';
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
        isPanning.current = true;
        panOrigin.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y };
        return;
    }
    if (e.button !== 0) return;
    e.preventDefault();
    const pos = getRelPos(e);
    dragMode.current = getMode(pos.x, pos.y, rect);
    dragStart.current = { mx: pos.x, my: pos.y, rect: { ...rect } };

    const onMove = (ev: MouseEvent) => {
      const p = getRelPos(ev);
      const dx = p.x - dragStart.current.mx;
      const dy = p.y - dragStart.current.my;
      const sr = dragStart.current.rect;
      setRect(() => {
        let { x, y, w, h } = sr;
        switch (dragMode.current) {
          case 'draw':
            x = Math.min(dragStart.current.mx, p.x); y = Math.min(dragStart.current.my, p.y);
            w = Math.abs(p.x - dragStart.current.mx); h = Math.abs(p.y - dragStart.current.my);
            break;
          case 'move':
            x = Math.max(0, Math.min(1 - w, sr.x + dx)); y = Math.max(0, Math.min(1 - h, sr.y + dy));
            break;
          case 'nw':
            x = Math.max(0, Math.min(sr.x+sr.w-0.01, sr.x+dx)); y = Math.max(0, Math.min(sr.y+sr.h-0.01, sr.y+dy));
            w = sr.x+sr.w-x; h = sr.y+sr.h-y; break;
          case 'ne':
            y = Math.max(0, Math.min(sr.y+sr.h-0.01, sr.y+dy));
            w = Math.max(0.01, Math.min(1-sr.x, sr.w+dx)); h = sr.y+sr.h-y; break;
          case 'sw':
            x = Math.max(0, Math.min(sr.x+sr.w-0.01, sr.x+dx));
            w = sr.x+sr.w-x; h = Math.max(0.01, Math.min(1-sr.y, sr.h+dy)); break;
          case 'se':
            w = Math.max(0.01, Math.min(1-sr.x, sr.w+dx)); h = Math.max(0.01, Math.min(1-sr.y, sr.h+dy)); break;
        }
        return { x: Math.max(0, x), y: Math.max(0, y), w: Math.max(0.01, Math.min(1-Math.max(0,x), w)), h: Math.max(0.01, Math.min(1-Math.max(0,y), h)) };
      });
    };
    const onUp = () => { dragMode.current = null; window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const vp = viewportRef.current?.getBoundingClientRect();
    if (!vp) return;
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = Math.max(0.1, Math.min(20, zoom * factor));
    const mouseX = e.clientX - vp.left;
    const mouseY = e.clientY - vp.top;
    const cx = mouseX - vp.width / 2;
    const cy = mouseY - vp.height / 2;
    setPan({
      x: cx - (cx - pan.x) * (newZoom / zoom),
      y: cy - (cy - pan.y) * (newZoom / zoom)
    });
    setZoom(newZoom);
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

  const save = () => { node.data.onChangeParams({ rect: JSON.stringify(rect) }); onClose(); };

  const corners = [
    { id: 'nw', x: rect.x, y: rect.y, cursor: 'nwse-resize' },
    { id: 'ne', x: rect.x+rect.w, y: rect.y, cursor: 'nesw-resize' },
    { id: 'sw', x: rect.x, y: rect.y+rect.h, cursor: 'nesw-resize' },
    { id: 'se', x: rect.x+rect.w, y: rect.y+rect.h, cursor: 'nwse-resize' },
  ];

  const maskColor = "rgba(37, 99, 235, 0.4)";

  return (
    <div className="fixed inset-0 z-[1000] bg-black/95 backdrop-blur-3xl flex flex-col items-center justify-center select-none nodrag" onContextMenu={e => e.preventDefault()}>
      {/* Header */}
      <div className="absolute top-8 left-8 flex items-center gap-4 z-10">
        <div className="p-3 bg-blue-500/20 rounded-2xl text-blue-400 shadow-2xl shadow-blue-500/20"><Crop size={28} /></div>
        <div>
          <h2 className="text-2xl font-black uppercase tracking-[0.2em] text-white">CROP EDITOR</h2>
          <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest opacity-50 mt-1">Fullscreen Spatial Editor · Precision Cropping</p>
        </div>
      </div>

      <div className="absolute top-8 right-8 flex items-center gap-4 z-10">
        <div className="text-[10px] font-black font-mono text-blue-400/60 bg-blue-400/5 border border-blue-400/10 px-3 py-1.5 rounded-full backdrop-blur-md">
          {Math.round(zoom * 100)}%
        </div>
      </div>

      {/* Editor Viewport */}
      <div
        ref={viewportRef}
        className="relative flex-1 w-full overflow-hidden cursor-crosshair"
        onWheel={handleWheel}
      >
        <div
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: 'center center' }}
        >
          <div className="relative inline-block shadow-[0_0_100px_rgba(0,0,0,0.5)] rounded-2xl overflow-hidden border border-white/10 bg-[#0c0c0c] pointer-events-auto" onMouseDown={handleMouseDown}>
            {frame ? (
              <img ref={imgRef} src={`data:image/jpeg;base64,${frame}`} className="block w-auto h-auto max-w-[90vw] max-h-[75vh]" draggable={false} />
            ) : (
              <div className="w-[800px] h-[450px] flex items-center justify-center text-gray-700"><Image size={48} className="opacity-10" /></div>
            )}
            <svg className="absolute inset-0 w-full h-full" style={{ pointerEvents: 'none' }}>
              <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 w-full h-full overflow-visible">
                {/* Blue Mask Overlay */}
                <rect x="0" y="0" width="1" height={rect.y} fill={maskColor} />
                <rect x="0" y={rect.y+rect.h} width="1" height={1-(rect.y+rect.h)} fill={maskColor} />
                <rect x="0" y={rect.y} width={rect.x} height={rect.h} fill={maskColor} />
                <rect x={rect.x+rect.w} y={rect.y} width={1-(rect.x+rect.w)} height={rect.h} fill={maskColor} />
                
                {/* Crop Outline */}
                <rect x={rect.x} y={rect.y} width={rect.w} height={rect.h} fill="none" stroke="#3b82f6" style={{ strokeWidth: 0.003 / zoom }} />
                
                {/* Grid Lines */}
                {[1/3, 2/3].flatMap(t => [
                  <line key={`v${t}`} x1={rect.x+rect.w*t} y1={rect.y} x2={rect.x+rect.w*t} y2={rect.y+rect.h} stroke="rgba(255,255,255,0.2)" style={{ strokeWidth: 0.001 / zoom }} />,
                  <line key={`h${t}`} x1={rect.x} y1={rect.y+rect.h*t} x2={rect.x+rect.w} y2={rect.y+rect.h*t} stroke="rgba(255,255,255,0.2)" style={{ strokeWidth: 0.001 / zoom }} />
                ])}
              </svg>
              {corners.map(c => (
                <circle key={c.id} cx={`${c.x*100}%`} cy={`${c.y*100}%`} r={8/zoom}
                  fill="white" stroke="#3b82f6" strokeWidth={2/zoom} style={{ pointerEvents: 'auto', cursor: c.cursor }} />
              ))}
            </svg>
          </div>
        </div>
      </div>

      {/* Footer / Controls */}
      <div className="p-8 w-full flex flex-col items-center gap-6 bg-gradient-to-t from-black/80 to-transparent">
        <div className="flex flex-col items-center gap-4">
           <div className="flex items-center gap-6 px-8 py-4 bg-white/5 rounded-3xl border border-white/10 shadow-2xl backdrop-blur-xl">
            <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-400">
                <span className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded-lg border border-blue-500/20">DRAG</span><span>CROP</span>
            </div>
            <div className="w-px h-4 bg-white/10" />
            <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-400">
                <span className="px-2 py-1 bg-white/10 text-white rounded-lg border border-white/10">ALT+DRAG</span><span>PAN</span>
            </div>
            <div className="w-px h-4 bg-white/10" />
            <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-400">
                <span className="px-2 py-1 bg-white/10 text-white rounded-lg border border-white/10">SCROLL</span><span>ZOOM</span>
            </div>
          </div>
          
          <div className="text-[10px] font-mono text-gray-500 mt-2">
            Selection: {Math.round(rect.w*100)}% × {Math.round(rect.h*100)}% at ({Math.round(rect.x*100)}%, {Math.round(rect.y*100)}%)
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button onClick={onClose} className="px-10 py-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all active:scale-95">Cancel</button>
          <button onClick={() => setRect({ x: 0, y: 0, w: 1, h: 1 })} className="px-10 py-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all active:scale-95">Reset Crop</button>
          <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} className="px-6 py-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all active:scale-95">Reset View</button>
          <button onClick={save} className="px-20 py-4 bg-blue-600 hover:bg-blue-500 shadow-2xl shadow-blue-500/40 rounded-2xl text-[10px] font-black uppercase tracking-widest text-white transition-all scale-110 hover:scale-115 active:scale-95 border border-white/10">Apply Crop</button>
        </div>
      </div>
    </div>
  );
};

export default CropEditorOverlay;
