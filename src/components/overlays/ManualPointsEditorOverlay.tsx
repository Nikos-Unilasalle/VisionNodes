import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Image, Crosshair } from 'lucide-react';
import { useNodeData } from '../../context/NodesDataContext';

const ManualPointsEditorOverlay = ({ node, edges, onClose }: any) => {
  const [points, setPoints] = useState<{x:number, y:number, label:number}[]>([]);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const viewportRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const isPanning = useRef(false);
  const panOrigin = useRef({ mx: 0, my: 0, px: 0, py: 0 });

  // Live-subscribing node data (re-renders on each WebSocket update for this node)
  const nd = useNodeData(node?.id ?? null);

  // Trace back to the upstream image node for fallback frame
  const srcNodeId = useMemo(() => {
    const imgEdge = edges?.find((e: any) => e.target === node?.id && e.targetHandle === 'image__image');
    return imgEdge?.source ?? null;
  }, [edges, node?.id]);
  const srcNd = useNodeData(srcNodeId);

  const frame = srcNd?.main_preview || srcNd?.main || nd?.main_preview || nd?.main;

  useEffect(() => {
    try {
      if (node?.data?.params?.points) setPoints(JSON.parse(node.data.params.points));
    } catch(e) {}
  }, [node?.id]);

  const REMOVE_THRESHOLD = 0.03;

  const getRelPos = (e: MouseEvent | React.MouseEvent) => {
    const r = imgRef.current?.getBoundingClientRect();
    if (!r) return { x: 0, y: 0 };
    return { 
      x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), 
      y: Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)) 
    };
  };

  const handleClick = (e: React.MouseEvent) => {
    if (e.button === 1 || (e.button === 0 && e.altKey)) return;
    if (!imgRef.current) return;
    
    const pos = getRelPos(e);
    
    // Check if there's a point nearby to remove (scaled by zoom)
    const threshold = REMOVE_THRESHOLD / zoom;
    const nearIdx = points.findIndex(p =>
      Math.abs(p.x - pos.x) < threshold && Math.abs(p.y - pos.y) < threshold
    );

    if (nearIdx >= 0) {
      setPoints(points.filter((_, i) => i !== nearIdx));
    } else {
      const label = e.button === 2 ? 0 : 1;
      setPoints([...points, { x: pos.x, y: pos.y, label }]);
    }
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    handleClick(e);
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

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
        isPanning.current = true;
        panOrigin.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y };
        return;
    }
    if (e.button === 0 && !e.altKey) {
        handleClick(e);
    }
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

  const save = () => { 
    node.data.onChangeParams({ points: JSON.stringify(points) }); 
    onClose(); 
  };

  return (
    <div className="fixed inset-0 z-[1000] bg-black/95 backdrop-blur-3xl flex flex-col items-center justify-center select-none nodrag" onContextMenu={e => e.preventDefault()}>
      {/* Header */}
      <div className="absolute top-8 left-8 flex items-center gap-4 z-10">
        <div className="p-3 bg-purple-500/20 rounded-2xl text-purple-400 shadow-2xl shadow-purple-500/20"><Crosshair size={28} /></div>
        <div>
          <h2 className="text-2xl font-black uppercase tracking-[0.2em] text-white">POINTS EDITOR</h2>
          <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest opacity-50 mt-1">Left-click: Foreground · Right-click: Background</p>
        </div>
      </div>

      <div className="absolute top-8 right-8 flex items-center gap-4 z-10">
        <div className="text-[10px] font-black font-mono text-purple-400/60 bg-purple-400/5 border border-purple-400/10 px-3 py-1.5 rounded-full backdrop-blur-md">
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
          <div className="relative inline-block shadow-[0_0_100px_rgba(0,0,0,0.5)] rounded-2xl overflow-hidden border border-white/10 bg-[#0c0c0c] pointer-events-auto" 
               onMouseDown={handleMouseDown} onContextMenu={handleContextMenu}>
            {frame ? (
              <img ref={imgRef} src={`data:image/jpeg;base64,${frame}`} className="block w-auto h-auto max-w-[90vw] max-h-[75vh]" draggable={false} />
            ) : (
              <div className="w-[800px] h-[450px] flex items-center justify-center text-gray-700"><Image size={48} className="opacity-10" /></div>
            )}
            <svg className="absolute inset-0 w-full h-full" style={{ pointerEvents: 'none' }}>
              {points.map((p, i) => {
                const isFg = p.label === 1;
                return (
                  <g key={i}>
                    <circle 
                      cx={`${p.x * 100}%`} 
                      cy={`${p.y * 100}%`} 
                      r={12 / zoom}
                      fill={isFg ? '#22dc50' : '#ff4444'}
                      opacity={0.9}
                    />
                    <circle 
                      cx={`${p.x * 100}%`} 
                      cy={`${p.y * 100}%`} 
                      r={14 / zoom}
                      fill="none"
                      stroke="white"
                      strokeWidth={2 / zoom}
                      opacity={0.8}
                    />
                    <text
                      x={`${p.x * 100}%`}
                      y={`${p.y * 100}%`}
                      dy={-22 / zoom}
                      textAnchor="middle"
                      fill="white"
                      fontSize={14 / zoom}
                      fontWeight="bold"
                      className="drop-shadow-md"
                      opacity={0.9}
                    >{i+1}</text>
                  </g>
                );
              })}
            </svg>
          </div>
        </div>
      </div>

      {/* Footer / Controls */}
      <div className="p-8 w-full flex flex-col items-center gap-6 bg-gradient-to-t from-black/80 to-transparent">
        <div className="flex flex-col items-center gap-4">
          <div className="flex items-center gap-6 px-8 py-4 bg-white/5 rounded-3xl border border-white/10 shadow-2xl backdrop-blur-xl">
            <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-400">
              <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded-lg border border-green-500/20">L-CLIC</span><span>FG</span>
            </div>
            <div className="w-px h-4 bg-white/10" />
            <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-400">
              <span className="px-2 py-1 bg-red-500/20 text-red-400 rounded-lg border border-red-500/20">R-CLIC</span><span>BG</span>
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
            <span className="text-green-400">{points.filter(p => p.label === 1).length} Foreground</span>
            <span className="mx-3">·</span>
            <span className="text-red-400">{points.filter(p => p.label === 0).length} Background</span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button onClick={onClose} className="px-10 py-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all active:scale-95">Cancel</button>
          <button onClick={() => setPoints([])} className="px-10 py-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all active:scale-95">Clear All</button>
          <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} className="px-6 py-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all active:scale-95">Reset View</button>
          <button onClick={save} className="px-20 py-4 bg-purple-600 hover:bg-purple-500 shadow-2xl shadow-purple-500/40 rounded-2xl text-[10px] font-black uppercase tracking-widest text-white transition-all scale-110 hover:scale-115 active:scale-95 border border-white/10">Apply Points</button>
        </div>
      </div>
    </div>
  );
};

export default ManualPointsEditorOverlay;
