import React, { useEffect, useRef, useState } from 'react';

function PopoutPreview() {
  const [frame, setFrame] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const [zoom, setZoom] = useState(1);
  const zoomRef = useRef(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const isPanning = useRef(false);
  const panStart = useRef({ mx: 0, my: 0, px: 0, py: 0 });

  useEffect(() => {
    let active = true;
    function connect() {
      if (!active) return;
      const ws = new WebSocket('ws://localhost:8765');
      wsRef.current = ws;
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'update' && msg.image) {
            setFrame(`data:image/jpeg;base64,${msg.image}`);
          }
        } catch {}
      };
      ws.onclose = () => { if (active) setTimeout(connect, 1200); };
    }
    connect();
    return () => { active = false; wsRef.current?.close(); };
  }, []);

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    const oldZoom = zoomRef.current;
    const newZoom = Math.max(0.25, Math.min(8, oldZoom * (e.deltaY < 0 ? 1.1 : 0.9)));
    zoomRef.current = newZoom;
    setZoom(newZoom);
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    setPan(p => ({
      x: p.x + (mx - cx) * (1 / newZoom - 1 / oldZoom),
      y: p.y + (my - cy) * (1 / newZoom - 1 / oldZoom),
    }));
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.button !== 1) return;
    e.preventDefault();
    isPanning.current = true;
    panStart.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y };
    const onMove = (ev: MouseEvent) => {
      if (!isPanning.current) return;
      document.body.style.cursor = 'grabbing';
      setPan({
        x: panStart.current.px + (ev.clientX - panStart.current.mx),
        y: panStart.current.py + (ev.clientY - panStart.current.my),
      });
    };
    const onUp = (ev: MouseEvent) => {
      if (ev.button !== 1) return;
      isPanning.current = false;
      document.body.style.cursor = '';
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  const resetView = () => {
    zoomRef.current = 1;
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <div
      className="w-screen h-screen bg-black flex items-center justify-center overflow-hidden"
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onDoubleClick={resetView}
    >
      {frame ? (
        <img
          src={frame}
          className="w-full h-full object-contain pointer-events-none"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: 'center' }}
          alt="Preview"
          draggable={false}
        />
      ) : (
        <div className="text-white/20 text-[11px] font-mono tracking-widest uppercase">
          Connecting to engine...
        </div>
      )}
      {zoom !== 1 && (
        <div className="absolute top-3 left-3 bg-black/60 text-white text-[9px] font-black px-2 py-1 rounded-lg pointer-events-none">
          {Math.round(zoom * 100)}%
        </div>
      )}
    </div>
  );
}

export default PopoutPreview;
