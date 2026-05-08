import React from 'react';

interface RerouteOverlayProps {
  isRerouting: boolean;
  rerouteDragRef: React.MutableRefObject<{
    capturedEdges: any[];
    handleType: 'source' | 'target';
    freeEndpoints: { x: number; y: number }[];
  } | null>;
  reroutePos: { x: number; y: number };
}

const RerouteOverlay: React.FC<RerouteOverlayProps> = ({ isRerouting, rerouteDragRef, reroutePos }) => {
  if (!isRerouting || !rerouteDragRef.current) return null;

  return (
    <div className="fixed inset-0 z-[9999] pointer-events-none">
      <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0 }}>
        {rerouteDragRef.current.freeEndpoints.map((ep, i) => (
          <line key={i} x1={ep.x} y1={ep.y} x2={reroutePos.x} y2={reroutePos.y}
            stroke="#ffffff" strokeWidth={2} strokeDasharray="6 4" strokeOpacity={0.5} />
        ))}
      </svg>
      <div style={{
        position: 'absolute',
        left: reroutePos.x - 8, top: reroutePos.y - 8,
        width: 16, height: 16, borderRadius: '50%',
        background: '#ffffff', border: '2px solid #111',
        boxShadow: '0 0 0 3px #3b82f6, 0 0 12px #3b82f699',
      }} />
    </div>
  );
};

export default RerouteOverlay;
