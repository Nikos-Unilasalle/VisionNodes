import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Image, Ruler } from 'lucide-react';
import { useNodeData } from '../../context/NodesDataContext';

const LineEditorOverlay = ({ node, edges, onClose }: any) => {
  const [pts, setPts] = useState<{ x: number; y: number }[]>([]);
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
      if (node?.data?.params?.points) {
        const p = JSON.parse(node.data.params.points);
        if (Array.isArray(p)) setPts(p);
      }
    } catch (_) {}
  }, [node?.id]);

  const getRelPos = (e: React.MouseEvent) => {
    const r = imgRef.current?.getBoundingClientRect();
    if (!r) return { x: 0, y: 0 };
    return {
      x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)),
      y: Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)),
    };
  };

  const maxPts = node?.type === 'sci_visual_measure' ? 3 : 2;

  const handleClick = (e: React.MouseEvent) => {
    if (e.button !== 0 || e.altKey) return;
    const pos = getRelPos(e);
    setPts(prev => prev.length >= maxPts ? [pos] : [...prev, pos]);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const vp = viewportRef.current?.getBoundingClientRect();
    if (!vp) return;
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    const nz = Math.max(0.1, Math.min(20, zoom * factor));
    const cx = e.clientX - vp.left - vp.width / 2;
    const cy = e.clientY - vp.top - vp.height / 2;
    setPan({ x: cx - (cx - pan.x) * (nz / zoom), y: cy - (cy - pan.y) * (nz / zoom) });
    setZoom(nz);
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      isPanning.current = true;
      panOrigin.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y };
    } else if (e.button === 0) {
      handleClick(e);
    }
  };

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isPanning.current) return;
      setPan({ x: panOrigin.current.px + (e.clientX - panOrigin.current.mx), y: panOrigin.current.py + (e.clientY - panOrigin.current.my) });
    };
    const onUp = () => { isPanning.current = false; };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  const lineLength = pts.length === 2
    ? (Math.hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y) * 100).toFixed(1)
    : null;

  const save = () => {
    node.data.onChangeParams({ points: JSON.stringify(pts) });
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-[1000] bg-black/95 backdrop-blur-3xl flex flex-col items-center justify-center select-none nodrag"
      onContextMenu={e => e.preventDefault()}
    >
      {/* Header */}
      <div className="absolute top-8 left-8 flex items-center gap-4 z-10">
        <div className="p-3 bg-yellow-500/20 rounded-2xl text-yellow-400 shadow-2xl shadow-yellow-500/20">
          <Ruler size={28} />
        </div>
        <div>
          <h2 className="text-2xl font-black uppercase tracking-[0.2em] text-white">LINE EDITOR</h2>
          <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest opacity-50 mt-1">
            {maxPts === 3 ? 'Click 3 points for angle · 4th click resets' : 'Click point 1 · Click point 2 · Third click resets'}
          </p>
        </div>
      </div>

      <div className="absolute top-8 right-8 flex items-center gap-4 z-10">
        <div className="text-[10px] font-black font-mono text-yellow-400/60 bg-yellow-400/5 border border-yellow-400/10 px-3 py-1.5 rounded-full">
          {Math.round(zoom * 100)}%
        </div>
      </div>

      {/* Viewport */}
      <div ref={viewportRef} className="relative flex-1 w-full overflow-hidden cursor-crosshair" onWheel={handleWheel}>
        <div
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: 'center center' }}
        >
          <div
            className="relative inline-block shadow-[0_0_100px_rgba(0,0,0,0.5)] rounded-2xl overflow-hidden border border-white/10 bg-[#0c0c0c] pointer-events-auto"
            onMouseDown={handleMouseDown}
          >
            {frame ? (
              <img ref={imgRef} src={`data:image/jpeg;base64,${frame}`} className="block w-auto h-auto max-w-[90vw] max-h-[75vh]" draggable={false} />
            ) : (
              <div className="w-[800px] h-[450px] flex items-center justify-center text-gray-700">
                <Image size={48} className="opacity-10" />
              </div>
            )}
            <svg className="absolute inset-0 w-full h-full" style={{ pointerEvents: 'none' }}>
              {pts.length >= 2 && (
                <>
                  <line
                    x1={`${pts[0].x * 100}%`} y1={`${pts[0].y * 100}%`}
                    x2={`${pts[1].x * 100}%`} y2={`${pts[1].y * 100}%`}
                    stroke="#facc15" strokeWidth={2 / zoom} strokeDasharray={`${6 / zoom} ${3 / zoom}`}
                  />
                  {pts.length >= 3 && (
                    <line
                      x1={`${pts[1].x * 100}%`} y1={`${pts[1].y * 100}%`}
                      x2={`${pts[2].x * 100}%`} y2={`${pts[2].y * 100}%`}
                      stroke="#facc15" strokeWidth={2 / zoom} strokeDasharray={`${6 / zoom} ${3 / zoom}`}
                    />
                  )}
                  <text
                    x={`${(pts[0].x + pts[1].x) / 2 * 100}%`}
                    y={`${(pts[0].y + pts[1].y) / 2 * 100}%`}
                    dy={-10 / zoom}
                    textAnchor="middle"
                    fill="#facc15"
                    fontSize={13 / zoom}
                    fontWeight="bold"
                    style={{ filter: 'drop-shadow(0 1px 2px black)' }}
                  >
                    {lineLength}%
                  </text>
                </>
              )}
              {pts.map((p, i) => (
                <g key={i}>
                  <circle cx={`${p.x * 100}%`} cy={`${p.y * 100}%`} r={6 / zoom} fill="#facc15" opacity={0.9} />
                  <circle cx={`${p.x * 100}%`} cy={`${p.y * 100}%`} r={8 / zoom} fill="none" stroke="white" strokeWidth={1.5 / zoom} opacity={0.6} />
                  <text
                    x={`${p.x * 100}%`} y={`${p.y * 100}%`} dy={-14 / zoom}
                    textAnchor="middle" fill="white" fontSize={11 / zoom} fontWeight="bold" opacity={0.8}
                  >
                    {i + 1}
                  </text>
                </g>
              ))}
            </svg>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="p-8 w-full flex flex-col items-center gap-6 bg-gradient-to-t from-black/80 to-transparent">
        <div className="flex items-center gap-6 px-8 py-4 bg-white/5 rounded-3xl border border-white/10 shadow-2xl backdrop-blur-xl">
          <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-400">
            <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded-lg border border-yellow-500/20">CLICK</span>
            <span>Place point</span>
          </div>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-400">
            <span className="px-2 py-1 bg-white/10 text-white rounded-lg border border-white/10">ALT+DRAG</span>
            <span>Pan</span>
          </div>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-2 text-[10px] font-black uppercase text-gray-400">
            <span className="px-2 py-1 bg-white/10 text-white rounded-lg border border-white/10">SCROLL</span>
            <span>Zoom</span>
          </div>
          <div className="w-px h-4 bg-white/10" />
          <div className="font-mono text-[11px] text-yellow-400">
            {pts.length === 0 && 'Click to place point 1'}
            {pts.length > 0 && pts.length < maxPts && `Click to place point ${pts.length + 1}`}
            {pts.length === maxPts && `Line defined · ${lineLength}% rel. length`}
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button onClick={onClose} className="px-10 py-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all active:scale-95">Cancel</button>
          <button onClick={() => setPts([])} className="px-10 py-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all active:scale-95">Clear</button>
          <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} className="px-6 py-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all active:scale-95">Reset View</button>
          <button
            onClick={save}
            disabled={pts.length < 2}
            className="px-20 py-4 bg-yellow-600 hover:bg-yellow-500 disabled:opacity-30 disabled:cursor-not-allowed shadow-2xl shadow-yellow-500/40 rounded-2xl text-[10px] font-black uppercase tracking-widest text-white transition-all scale-110 hover:scale-115 active:scale-95 border border-white/10"
          >
            Apply Line
          </button>
        </div>
      </div>
    </div>
  );
};

export default LineEditorOverlay;
