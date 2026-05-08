import React, { useState, useRef, useEffect } from 'react';
import { Image, Crop } from 'lucide-react';

const CropEditorOverlay = ({ node, nodesData, onClose }: any) => {
  const nd = (() => {
    if (!node?.id || !nodesData) return {};
    const dataKeys = Object.keys(nodesData).filter((k: string) => k.startsWith(`${node.id}:`));
    return dataKeys.length > 0
      ? Object.fromEntries(dataKeys.map((k: string) => [k.split(':')[1], nodesData[k]]))
      : (nodesData[node.id] ?? {});
  })();
  const frame = nd?.main_preview || nd?.main;
  const containerRef = useRef<HTMLDivElement>(null);
  const [rect, setRect] = useState({ x: 0.1, y: 0.1, w: 0.8, h: 0.8 });
  const dragMode = useRef<string | null>(null);
  const dragStart = useRef({ mx: 0, my: 0, rect: { x: 0, y: 0, w: 0, h: 0 } });

  useEffect(() => {
    try {
      if (node?.data?.params?.rect) setRect(JSON.parse(node.data.params.rect));
    } catch(e) {}
  }, [node?.id]);

  const getRelPos = (e: MouseEvent | React.MouseEvent) => {
    const r = containerRef.current?.getBoundingClientRect();
    if (!r) return { x: 0, y: 0 };
    return { x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), y: Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)) };
  };

  const HANDLE = 0.025;
  const getMode = (mx: number, my: number, r: typeof rect) => {
    const corners = { nw: [r.x, r.y], ne: [r.x+r.w, r.y], sw: [r.x, r.y+r.h], se: [r.x+r.w, r.y+r.h] } as Record<string,[number,number]>;
    for (const [name, [cx, cy]] of Object.entries(corners))
      if (Math.abs(mx - cx) < HANDLE && Math.abs(my - cy) < HANDLE) return name;
    if (mx > r.x && mx < r.x+r.w && my > r.y && my < r.y+r.h) return 'move';
    return 'draw';
  };

  const handleMouseDown = (e: React.MouseEvent) => {
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

  const save = () => { node.data.onChangeParams({ rect: JSON.stringify(rect) }); onClose(); };

  const corners = [
    { id: 'nw', x: rect.x, y: rect.y, cursor: 'nwse-resize' },
    { id: 'ne', x: rect.x+rect.w, y: rect.y, cursor: 'nesw-resize' },
    { id: 'sw', x: rect.x, y: rect.y+rect.h, cursor: 'nesw-resize' },
    { id: 'se', x: rect.x+rect.w, y: rect.y+rect.h, cursor: 'nwse-resize' },
  ];

  return (
    <div className="fixed inset-0 z-[1000] bg-black/95 backdrop-blur-3xl flex flex-col items-center justify-center p-8 select-none nodrag" onContextMenu={e => e.preventDefault()}>
      <div className="absolute top-8 left-8 flex items-center gap-4">
        <div className="p-2 bg-accent/20 rounded-lg text-accent"><Crop size={24} /></div>
        <div>
          <h2 className="text-xl font-black uppercase tracking-widest text-white">CROP EDITOR</h2>
          <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest opacity-50">Drag to draw · Corners to resize · Interior to move</p>
        </div>
      </div>

      <div className="relative flex-1 w-full flex items-center justify-center p-4">
        <div ref={containerRef} className="relative inline-block shadow-2xl rounded-2xl overflow-hidden border border-white/10 bg-[#0c0c0c]" onMouseDown={handleMouseDown} style={{ cursor: 'crosshair' }}>
          {frame ? (
            <img src={`data:image/jpeg;base64,${frame}`} className="block w-auto h-auto max-w-[90vw] max-h-[70vh]" draggable={false} />
          ) : (
            <div className="w-[800px] h-[450px] flex items-center justify-center text-gray-700"><Image size={48} className="opacity-10" /></div>
          )}
          <svg className="absolute inset-0 w-full h-full" style={{ pointerEvents: 'none' }}>
            <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 w-full h-full overflow-visible">
              <rect x="0" y="0" width="1" height={rect.y} fill="rgba(0,0,0,0.55)" />
              <rect x="0" y={rect.y+rect.h} width="1" height={1-(rect.y+rect.h)} fill="rgba(0,0,0,0.55)" />
              <rect x="0" y={rect.y} width={rect.x} height={rect.h} fill="rgba(0,0,0,0.55)" />
              <rect x={rect.x+rect.w} y={rect.y} width={1-(rect.x+rect.w)} height={rect.h} fill="rgba(0,0,0,0.55)" />
              <rect x={rect.x} y={rect.y} width={rect.w} height={rect.h} fill="none" stroke="var(--color-accent)" style={{ strokeWidth: 0.004 }} />
              {[1/3, 2/3].flatMap(t => [
                <line key={`v${t}`} x1={rect.x+rect.w*t} y1={rect.y} x2={rect.x+rect.w*t} y2={rect.y+rect.h} stroke="rgba(255,255,255,0.2)" style={{ strokeWidth: 0.002 }} />,
                <line key={`h${t}`} x1={rect.x} y1={rect.y+rect.h*t} x2={rect.x+rect.w} y2={rect.y+rect.h*t} stroke="rgba(255,255,255,0.2)" style={{ strokeWidth: 0.002 }} />
              ])}
            </svg>
            {corners.map(c => (
              <circle key={c.id} cx={`${c.x*100}%`} cy={`${c.y*100}%`} r={7}
                fill="white" stroke="var(--color-accent)" strokeWidth="2" style={{ pointerEvents: 'auto', cursor: c.cursor }} />
            ))}
          </svg>
        </div>
      </div>

      <div className="flex flex-col items-center gap-4">
        <div className="text-[10px] font-mono text-gray-600">
          x:{(rect.x*100).toFixed(1)}%  y:{(rect.y*100).toFixed(1)}%  —  {(rect.w*100).toFixed(1)}% × {(rect.h*100).toFixed(1)}%
        </div>
        <div className="flex items-center gap-4">
          <button onClick={onClose} className="px-10 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all">Cancel</button>
          <button onClick={() => setRect({ x: 0, y: 0, w: 1, h: 1 })} className="px-10 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all">Reset</button>
          <button onClick={save} className="px-16 py-3 bg-accent hover:bg-blue-600 shadow-2xl shadow-accent/20 rounded-2xl text-[10px] font-black uppercase tracking-widest text-white transition-all scale-105 active:scale-95 border border-white/10">Apply Crop</button>
        </div>
      </div>
    </div>
  );
};

export default CropEditorOverlay;
