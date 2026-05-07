import React, { useEffect, useRef, useState } from 'react';

function PopoutPreview() {
  const [frame, setFrame] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

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

  return (
    <div className="w-screen h-screen bg-black flex items-center justify-center overflow-hidden">
      {frame ? (
        <img
          src={frame}
          className="w-full h-full object-contain"
          alt="Preview"
          draggable={false}
        />
      ) : (
        <div className="text-white/20 text-[11px] font-mono tracking-widest uppercase">
          Connecting to engine...
        </div>
      )}
    </div>
  );
}

export default PopoutPreview;
