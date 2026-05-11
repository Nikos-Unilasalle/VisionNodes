import React, { useState, useRef, useEffect } from 'react';
import { Image, Crosshair } from 'lucide-react';

const ManualPointsEditorOverlay = ({ node, nodesData, onClose }: any) => {
  const nd = (() => {
    if (!node?.id || !nodesData) return {};
    const dataKeys = Object.keys(nodesData).filter((k: string) => k.startsWith(`${node.id}:`));
    return dataKeys.length > 0
      ? Object.fromEntries(dataKeys.map((k: string) => [k.split(':')[1], nodesData[k]]))
      : (nodesData[node.id] ?? {});
  })();
  
  const frame = nd?.main_preview || nd?.main;
  const containerRef = useRef<HTMLDivElement>(null);
  const [points, setPoints] = useState<{x:number, y:number, label:number}[]>([]);

  useEffect(() => {
    try {
      if (node?.data?.params?.points) setPoints(JSON.parse(node.data.params.points));
    } catch(e) {}
  }, [node?.id]);

  const REMOVE_THRESHOLD = 0.04;

  const getRelPos = (e: MouseEvent | React.MouseEvent) => {
    const r = containerRef.current?.getBoundingClientRect();
    if (!r) return { x: 0, y: 0 };
    return { 
      x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), 
      y: Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)) 
    };
  };

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (!containerRef.current) return;
    
    const pos = getRelPos(e);
    
    // Check if there's a point nearby to remove
    const nearIdx = points.findIndex(p =>
      Math.abs(p.x - pos.x) < REMOVE_THRESHOLD && Math.abs(p.y - pos.y) < REMOVE_THRESHOLD
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

  const save = () => { 
    node.data.onChangeParams({ points: JSON.stringify(points) }); 
    onClose(); 
  };

  return (
    <div className="fixed inset-0 z-[1000] bg-black/95 backdrop-blur-3xl flex flex-col items-center justify-center p-8 select-none nodrag" onContextMenu={e => e.preventDefault()}>
      <div className="absolute top-8 left-8 flex items-center gap-4">
        <div className="p-2 bg-purple-500/20 rounded-lg text-purple-400"><Crosshair size={24} /></div>
        <div>
          <h2 className="text-xl font-black uppercase tracking-widest text-white">POINTS EDITOR</h2>
          <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest opacity-50">Left-click: FG · Right-click: BG · Click point to remove</p>
        </div>
      </div>

      <div className="relative flex-1 w-full flex items-center justify-center p-4">
        <div ref={containerRef} className="relative inline-block shadow-2xl rounded-2xl overflow-hidden border border-white/10 bg-[#0c0c0c]" 
             onClick={handleClick} onContextMenu={handleContextMenu} style={{ cursor: 'crosshair' }}>
          {frame ? (
            <img src={`data:image/jpeg;base64,${frame}`} className="block w-auto h-auto max-w-[90vw] max-h-[70vh]" draggable={false} />
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
                    r={12}
                    fill={isFg ? '#22dc50' : '#ff4444'}
                    opacity={0.9}
                  />
                  <circle 
                    cx={`${p.x * 100}%`} 
                    cy={`${p.y * 100}%`} 
                    r={14}
                    fill="none"
                    stroke="white"
                    strokeWidth={2}
                    opacity={0.8}
                  />
                  <text
                    x={`${p.x * 100}%`}
                    y={`${p.y * 100}%`}
                    dy={-22}
                    textAnchor="middle"
                    fill="white"
                    fontSize={14}
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

      <div className="flex flex-col items-center gap-4">
        <div className="text-[10px] font-mono text-gray-600">
          <span className="text-green-400">{points.filter(p => p.label === 1).length} Foreground</span>
          <span className="mx-2">·</span>
          <span className="text-red-400">{points.filter(p => p.label === 0).length} Background</span>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={onClose} className="px-10 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all">Cancel</button>
          <button onClick={() => setPoints([])} className="px-10 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[10px] font-black uppercase tracking-widest text-gray-400 transition-all">Clear All</button>
          <button onClick={save} className="px-16 py-3 bg-purple-600 hover:bg-purple-500 shadow-2xl shadow-purple-500/20 rounded-2xl text-[10px] font-black uppercase tracking-widest text-white transition-all scale-105 active:scale-95 border border-white/10">Apply Points</button>
        </div>
      </div>
    </div>
  );
};

export default ManualPointsEditorOverlay;
