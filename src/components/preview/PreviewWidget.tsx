import React, { useRef } from 'react';
import { motion } from 'framer-motion';
import { ExternalLink, Minimize2 } from 'lucide-react';

interface PreviewWidgetProps {
  frame: string | null;
  previewSize: { w: number; h: number };
  previewPos: { x: number; y: number };
  previewZoom: number;
  previewPan: { x: number; y: number };
  previewPopped: boolean;
  pickColorNodeId: string | null;
  setPreviewPos: (p: { x: number; y: number }) => void;
  setPreviewZoom: (z: number) => void;
  setPreviewPan: React.Dispatch<React.SetStateAction<{ x: number; y: number }>>;
  setPreviewSize: React.Dispatch<React.SetStateAction<{ w: number; h: number }>>;
  previewZoomRef: React.MutableRefObject<number>;
  previewAspect: React.MutableRefObject<number>;
  previewResizeRef: React.RefObject<HTMLDivElement>;
  handlePopout: () => void;
  handleBringBack: () => void;
  updateNodeParams: (id: string, params: any) => void;
  setPickColorNodeId: (id: string | null) => void;
  isPanning: React.MutableRefObject<boolean>;
  panStart: React.MutableRefObject<{ mx: number; my: number; px: number; py: number }>;
}

const PreviewWidget: React.FC<PreviewWidgetProps> = ({
  frame, previewSize, previewPos, previewZoom, previewPan, previewPopped,
  pickColorNodeId, setPreviewPos, setPreviewZoom, setPreviewPan, setPreviewSize,
  previewZoomRef, previewAspect, previewResizeRef, handlePopout, handleBringBack,
  updateNodeParams, setPickColorNodeId, isPanning, panStart,
}) => {
  if (previewPopped) {
    return (
      <button
        className="absolute bottom-6 right-6 z-20 flex items-center gap-2 bg-[#3d4452] hover:bg-accent border border-[#4f5b6b] hover:border-accent text-gray-400 hover:text-white rounded-2xl px-3 py-2.5 shadow-xl transition-all text-[11px] font-bold"
        onClick={handleBringBack}
        title="Ramener la preview dans l'application"
      >
        <Minimize2 size={14} />
        Preview
      </button>
    );
  }

  return (
    <motion.div
      drag
      dragMomentum={false}
      animate={{ x: previewPos.x, y: previewPos.y }}
      onDragEnd={(e, info) => setPreviewPos({ x: previewPos.x + info.offset.x, y: previewPos.y + info.offset.y })}
      whileHover={{ cursor: 'grab' }}
      whileDrag={{ cursor: 'grabbing', zIndex: 100 }}
      onDoubleClick={() => { previewZoomRef.current = 1; setPreviewZoom(1); setPreviewPan({ x: 0, y: 0 }); }}
      onWheel={(e) => {
        e.stopPropagation();
        const oldZoom = previewZoomRef.current;
        const newZoom = Math.max(0.25, Math.min(8, oldZoom * (e.deltaY < 0 ? 1.1 : 0.9)));
        previewZoomRef.current = newZoom;
        setPreviewZoom(newZoom);
        const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const cx = rect.width / 2;
        const cy = rect.height / 2;
        setPreviewPan((p: { x: number; y: number }) => ({
          x: p.x + (mx - cx) * (1 / newZoom - 1 / oldZoom),
          y: p.y + (my - cy) * (1 / newZoom - 1 / oldZoom),
        }));
      }}
      onMouseDown={(e) => {
        if (e.button !== 1) return;
        e.preventDefault();
        isPanning.current = true;
        panStart.current = { mx: e.clientX, my: e.clientY, px: previewPan.x, py: previewPan.y };
        const onMove = (ev: MouseEvent) => {
          if (!isPanning.current) return;
          document.body.style.cursor = 'grabbing';
          setPreviewPan({
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
      }}
      className="absolute bottom-6 left-[49px] bg-black border-2 border-[#4f5b6b] rounded-3xl shadow-2xl overflow-hidden z-20 group hover:border-accent transition-colors duration-300"
      style={{ width: previewSize.w, height: previewSize.h }}
    >
      {frame && <img src={frame} alt="Vision"
        className="w-full h-full object-contain pointer-events-none"
        style={{ transform: `translate(${previewPan.x}px, ${previewPan.y}px) scale(${previewZoom})`, transformOrigin: 'center' }}
        onLoad={(e) => {
          const img = e.currentTarget;
          if (img.naturalWidth && img.naturalHeight) {
            const newAspect = img.naturalWidth / img.naturalHeight;
            if (Math.abs(newAspect - previewAspect.current) > 0.02) {
              previewAspect.current = newAspect;
              setPreviewSize((prev: { w: number; h: number }) => ({ w: prev.w, h: Math.round(prev.w / newAspect) }));
            }
          }
        }} />}
      {previewZoom !== 1 && (
        <div className="absolute top-2 left-2 bg-black/60 text-white text-[9px] font-black px-2 py-1 rounded-lg pointer-events-none">
          {Math.round(previewZoom * 100)}%
        </div>
      )}
      <button
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity z-20 bg-black/60 hover:bg-accent text-white/60 hover:text-white rounded-lg p-1.5 cursor-pointer"
        title="Externaliser la preview"
        onPointerDown={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => { e.stopPropagation(); handlePopout(); }}
      >
        <ExternalLink size={12} />
      </button>
      {pickColorNodeId && (
        <div
          className="absolute inset-0 z-30"
          style={{ cursor: 'crosshair' }}
          onClick={(e) => {
            const container = e.currentTarget.parentElement!;
            const imgEl = container.querySelector('img') as HTMLImageElement | null;
            if (!imgEl || !frame) return;
            const rect = imgEl.getBoundingClientRect();
            const px = e.clientX - rect.left;
            const py = e.clientY - rect.top;
            const canvas = document.createElement('canvas');
            canvas.width = imgEl.naturalWidth;
            canvas.height = imgEl.naturalHeight;
            const ctx = canvas.getContext('2d')!;
            ctx.drawImage(imgEl, 0, 0);
            const scaleX = imgEl.naturalWidth / rect.width;
            const scaleY = imgEl.naturalHeight / rect.height;
            const [r, g, b] = ctx.getImageData(Math.floor(px * scaleX), Math.floor(py * scaleY), 1, 1).data;
            const hex = '#' + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join('').toUpperCase();
            updateNodeParams(pickColorNodeId, { color: hex, r, g, b });
            setPickColorNodeId(null);
          }}
        />
      )}
      <div
        ref={previewResizeRef as any}
        className="absolute bottom-0 right-0 w-5 h-5 cursor-se-resize z-10 flex items-end justify-end pb-1 pr-1 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <svg width="8" height="8" viewBox="0 0 8 8" className="text-white/30">
          <path d="M8 0 L8 8 L0 8" fill="none" stroke="currentColor" strokeWidth="1.5"/>
        </svg>
      </div>
    </motion.div>
  );
};

export default PreviewWidget;
