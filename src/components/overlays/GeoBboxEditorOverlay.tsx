/**
 * GeoBboxEditorOverlay.tsx
 *
 * Simplified map editor for the geo_bbox node.
 * OSM slippy-map basemap. Shift+drag to draw the bounding box.
 * Saves lon_min / lat_min / lon_max / lat_max to node params.
 */
import React, {
  useRef, useEffect, useState, useCallback, useReducer,
} from 'react';
import { X, Square, Trash2 } from 'lucide-react';

// ── Tile math ─────────────────────────────────────────────────────────────────

const TS = 256;

const lonToTX = (lon: number, z: number) => ((lon + 180) / 360) * 2 ** z;
const latToTY = (lat: number, z: number) => {
  const r = (lat * Math.PI) / 180;
  return ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * 2 ** z;
};
const txToLon = (x: number, z: number) => (x / 2 ** z) * 360 - 180;
const tyToLat = (y: number, z: number) => {
  const n = Math.PI - (2 * Math.PI * y) / 2 ** z;
  return (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
};

const canvasToLL = (px: number, py: number, z: number, ox: number, oy: number): [number, number] =>
  [tyToLat((py - oy) / TS, z), txToLon((px - ox) / TS, z)];

const llToCanvas = (lat: number, lon: number, z: number, ox: number, oy: number): [number, number] =>
  [lonToTX(lon, z) * TS + ox, latToTY(lat, z) * TS + oy];

const fmtC = (v: number, d: 'lat' | 'lon') => {
  const dir = d === 'lat' ? (v >= 0 ? 'N' : 'S') : (v >= 0 ? 'E' : 'W');
  return `${Math.abs(v).toFixed(5)}° ${dir}`;
};

// ── Map state reducer ─────────────────────────────────────────────────────────

interface MT { zoom: number; ox: number; oy: number }
type MA =
  | { type: 'zoom'; mx: number; my: number; delta: number }
  | { type: 'pan';  ox: number; oy: number }
  | { type: 'set';  zoom: number; ox: number; oy: number };

function mapReducer(s: MT, a: MA): MT {
  switch (a.type) {
    case 'zoom': {
      const nz = Math.max(2, Math.min(18, s.zoom + a.delta));
      if (nz === s.zoom) return s;
      const sc = 2 ** (nz - s.zoom);
      return { zoom: nz, ox: a.mx - (a.mx - s.ox) * sc, oy: a.my - (a.my - s.oy) * sc };
    }
    case 'pan': return { ...s, ox: a.ox, oy: a.oy };
    case 'set': return { zoom: a.zoom, ox: a.ox, oy: a.oy };
    default:    return s;
  }
}

interface Bbox { west: number; south: number; east: number; north: number }
interface Props { node: any; onClose: () => void }

// ── Component ─────────────────────────────────────────────────────────────────

const GeoBboxEditorOverlay: React.FC<Props> = ({ node, onClose }) => {
  const params = node?.data?.params ?? {};
  const [map, dispatchMap] = useReducer(mapReducer, { zoom: 5, ox: 0, oy: 0 });
  const [bbox, setBbox]       = useState<Bbox | null>(null);
  const [cursor, setCursor]   = useState<[number, number] | null>(null);
  const [shiftHeld, setShift] = useState(false);

  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const tileCache   = useRef<Map<string, HTMLImageElement>>(new Map());
  const mapRef      = useRef(map);
  useEffect(() => { mapRef.current = map; }, [map]);

  const isPanning   = useRef(false);
  const panStart    = useRef({ mx: 0, my: 0, ox: 0, oy: 0 });
  const isDrawing   = useRef(false);
  const drawStart   = useRef<[number, number] | null>(null);
  const drawNow     = useRef<[number, number] | null>(null);

  // Shift tracking
  useEffect(() => {
    const fn = (e: KeyboardEvent) => setShift(e.shiftKey);
    window.addEventListener('keydown', fn);
    window.addEventListener('keyup',   fn);
    return () => { window.removeEventListener('keydown', fn); window.removeEventListener('keyup', fn); };
  }, []);

  // Init bbox from params
  useEffect(() => {
    const lon_min = parseFloat(params.lon_min);
    const lat_min = parseFloat(params.lat_min);
    const lon_max = parseFloat(params.lon_max);
    const lat_max = parseFloat(params.lat_max);
    if ([lon_min, lat_min, lon_max, lat_max].every(isFinite)) {
      setBbox({ west: lon_min, south: lat_min, east: lon_max, north: lat_max });
      const lat = (lat_min + lat_max) / 2;
      const lon = (lon_min + lon_max) / 2;
      const z = 6;
      dispatchMap({ type: 'set', zoom: z,
        ox: window.innerWidth / 2 - lonToTX(lon, z) * TS,
        oy: window.innerHeight / 2 - latToTY(lat, z) * TS,
      });
    } else {
      // Default: Guyane
      const lat = 4.0, lon = -53.0, z = 7;
      dispatchMap({ type: 'set', zoom: z,
        ox: window.innerWidth / 2 - lonToTX(lon, z) * TS,
        oy: window.innerHeight / 2 - latToTY(lat, z) * TS,
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tile loader
  const getTile = useCallback((z: number, tx: number, ty: number): HTMLImageElement => {
    const n = 2 ** z;
    const cx = ((tx % n) + n) % n;
    const cy = Math.max(0, Math.min(n - 1, ty));
    const key = `${z}/${cx}/${cy}`;
    if (tileCache.current.has(key)) return tileCache.current.get(key)!;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = `https://tile.openstreetmap.org/${z}/${cx}/${cy}.png`;
    img.onload = () => renderFrame();
    tileCache.current.set(key, img);
    return img;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const drawRect = (ctx: CanvasRenderingContext2D, x1: number, y1: number, x2: number, y2: number, fill: string, stroke: string) => {
    const rx = Math.min(x1, x2), ry = Math.min(y1, y2), rw = Math.abs(x2 - x1), rh = Math.abs(y2 - y1);
    ctx.fillStyle = fill; ctx.fillRect(rx, ry, rw, rh);
    ctx.strokeStyle = stroke; ctx.lineWidth = 2; ctx.setLineDash([6, 4]); ctx.strokeRect(rx, ry, rw, rh); ctx.setLineDash([]);
  };

  const renderFrame = useCallback(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    const ctx = canvas.getContext('2d'); if (!ctx) return;
    const W = canvas.width, H = canvas.height;
    const { zoom: z, ox, oy } = mapRef.current;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#1a1a2e'; ctx.fillRect(0, 0, W, H);

    const intZ = Math.round(z);
    const ts   = TS * 2 ** (z - intZ);
    const stx  = Math.floor(-ox / ts) - 1, sty = Math.floor(-oy / ts) - 1;
    const etx  = Math.ceil((W - ox) / ts) + 1, ety = Math.ceil((H - oy) / ts) + 1;
    for (let ty = sty; ty <= ety; ty++) for (let tx = stx; tx <= etx; tx++) {
      const img = getTile(intZ, tx, ty);
      const px = tx * ts + ox, py = ty * ts + oy;
      if (img.complete && img.naturalWidth > 0) ctx.drawImage(img, px, py, ts, ts);
      else { ctx.fillStyle = '#1e1e35'; ctx.fillRect(px, py, ts, ts); }
    }

    ctx.save(); ctx.font = '9px sans-serif';
    ctx.fillStyle = 'rgba(0,0,0,0.5)'; ctx.fillRect(W - 180, H - 16, 180, 16);
    ctx.fillStyle = '#bbb'; ctx.fillText('© OpenStreetMap contributors', W - 175, H - 4);
    ctx.restore();

    if (isDrawing.current && drawStart.current && drawNow.current) {
      const [la1, lo1] = drawStart.current; const [la2, lo2] = drawNow.current;
      const [x1, y1] = llToCanvas(la1, lo1, z, ox, oy); const [x2, y2] = llToCanvas(la2, lo2, z, ox, oy);
      drawRect(ctx, x1, y1, x2, y2, 'rgba(251,146,60,0.2)', '#fb923c');
    }
    if (bbox) {
      const [x1, y1] = llToCanvas(bbox.north, bbox.west, z, ox, oy);
      const [x2, y2] = llToCanvas(bbox.south, bbox.east, z, ox, oy);
      drawRect(ctx, x1, y1, x2, y2, 'rgba(34,197,94,0.12)', '#22c55e');
      ctx.save(); ctx.font = 'bold 10px monospace'; ctx.fillStyle = '#22c55e';
      ctx.fillText(`${bbox.north.toFixed(3)}° N`, Math.min(x1, x2) + 6, Math.min(y1, y2) + 14);
      ctx.fillText(`${bbox.south.toFixed(3)}° S`, Math.min(x1, x2) + 6, Math.max(y1, y2) - 4);
      ctx.restore();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, bbox, getTile]);

  useEffect(() => { renderFrame(); }, [renderFrame]);

  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    const ro = new ResizeObserver(entries => {
      const e = entries[0]; canvas.width = e.contentRect.width; canvas.height = e.contentRect.height; renderFrame();
    });
    ro.observe(canvas.parentElement ?? canvas);
    return () => ro.disconnect();
  }, [renderFrame]);

  const handleWheel = useCallback((e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const r = canvasRef.current!.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    const raw = e.deltaMode === 0 ? e.deltaY : e.deltaY * 40;
    dispatchMap({ type: 'zoom', mx, my, delta: Math.max(-0.5, Math.min(0.5, -raw * 0.003)) });
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const r = canvasRef.current!.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    const { zoom: z, ox, oy } = mapRef.current;
    if (e.shiftKey) {
      const ll = canvasToLL(mx, my, z, ox, oy);
      isDrawing.current = true; drawStart.current = ll; drawNow.current = ll;
    } else {
      isPanning.current = true; panStart.current = { mx: e.clientX, my: e.clientY, ox, oy };
    }
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const canvas = canvasRef.current; if (!canvas) return;
      const r = canvas.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      const { zoom: z, ox, oy } = mapRef.current;
      setCursor(canvasToLL(mx, my, z, ox, oy));
      if (isPanning.current) dispatchMap({ type: 'pan', ox: panStart.current.ox + (e.clientX - panStart.current.mx), oy: panStart.current.oy + (e.clientY - panStart.current.my) });
      if (isDrawing.current) { drawNow.current = canvasToLL(mx, my, z, ox, oy); renderFrame(); }
    };
    const onUp = () => {
      if (isDrawing.current && drawStart.current && drawNow.current) {
        const [la1, lo1] = drawStart.current; const [la2, lo2] = drawNow.current;
        const b: Bbox = { west: Math.min(lo1, lo2), east: Math.max(lo1, lo2), south: Math.min(la1, la2), north: Math.max(la1, la2) };
        if (Math.abs(b.east - b.west) > 0.001 && Math.abs(b.north - b.south) > 0.001) setBbox(b);
      }
      isPanning.current = false; isDrawing.current = false; drawStart.current = null; drawNow.current = null;
    };
    window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, [renderFrame]);

  const handleSave = () => {
    if (!bbox) return;
    node?.data?.onChangeParams?.({ lon_min: bbox.west, lat_min: bbox.south, lon_max: bbox.east, lat_max: bbox.north });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[1000] flex flex-row select-none nodrag" onContextMenu={e => e.preventDefault()}>

      {/* Left panel */}
      <div className="w-64 flex flex-col bg-[#0d0d1a] border-r border-white/5 shrink-0">
        <div className="flex items-center gap-3 px-4 pt-5 pb-4 border-b border-white/5">
          <div className="p-2 bg-green-500/20 rounded-xl text-green-400"><Square size={16} /></div>
          <div>
            <div className="text-xs font-black uppercase tracking-widest text-white">Bounding Box</div>
            <div className="text-[9px] text-gray-500 font-mono">Map Editor</div>
          </div>
          <button onClick={onClose} className="ml-auto p-1.5 rounded-lg hover:bg-white/10 text-gray-500 hover:text-white transition-colors"><X size={14} /></button>
        </div>

        <div className="flex flex-col gap-4 px-4 py-4 flex-1">

          {bbox ? (
            <div className="bg-green-500/5 border border-green-500/15 rounded-xl p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[9px] font-black uppercase tracking-widest text-green-400">ROI</span>
                <button onClick={() => setBbox(null)} className="text-red-400/60 hover:text-red-400 transition-colors"><Trash2 size={11} /></button>
              </div>
              <div className="font-mono text-[8px] text-gray-400 space-y-0.5 leading-relaxed">
                <div>W {bbox.west.toFixed(5)}°</div>
                <div>E {bbox.east.toFixed(5)}°</div>
                <div>S {bbox.south.toFixed(5)}°</div>
                <div>N {bbox.north.toFixed(5)}°</div>
              </div>
            </div>
          ) : (
            <div className="px-3 py-4 bg-white/3 rounded-xl border border-white/8 text-center">
              <p className="text-[9px] text-gray-600 font-mono">Hold <span className="text-orange-400">Shift</span> + drag to draw</p>
            </div>
          )}

          <div className="flex-1" />

          <button onClick={handleSave} disabled={!bbox}
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all disabled:opacity-30 disabled:pointer-events-none bg-green-600 hover:bg-green-500 text-white shadow-lg shadow-green-500/20">
            <Square size={11} /> Save ROI
          </button>
        </div>
      </div>

      {/* Map area */}
      <div className="flex-1 flex flex-col bg-[#12121f] relative overflow-hidden">
        {/* Top bar */}
        <div className="flex items-center gap-3 px-4 py-2 bg-black/40 border-b border-white/5 z-10">
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${
            shiftHeld ? 'bg-orange-500/20 border border-orange-500/40 text-orange-400' : 'bg-white/5 border border-white/10 text-gray-500'
          }`}>
            {shiftHeld ? '✏ Drawing ROI' : '✦ Pan mode'}
          </div>
          <span className="text-[9px] font-mono text-gray-600">
            {shiftHeld ? 'Drag to define area' : 'Scroll zoom · drag pan · Shift+drag ROI'}
          </span>
          <div className="ml-auto flex items-center gap-3 text-[9px] font-mono">
            {cursor && <span className="text-gray-500">{fmtC(cursor[0], 'lat')} &nbsp; {fmtC(cursor[1], 'lon')}</span>}
            <span className="text-green-400/50 bg-green-400/5 border border-green-400/10 px-2 py-0.5 rounded-full">z{map.zoom.toFixed(1)}</span>
          </div>
        </div>

        <div className="flex-1 relative">
          <canvas ref={canvasRef} className={`absolute inset-0 w-full h-full ${shiftHeld ? 'cursor-crosshair' : 'cursor-grab active:cursor-grabbing'}`}
            onWheel={handleWheel} onMouseDown={handleMouseDown} />
          {!bbox && !shiftHeld && (
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 pointer-events-none">
              <div className="px-4 py-2 bg-black/70 backdrop-blur-md rounded-full text-[10px] font-black uppercase tracking-widest text-gray-400 border border-white/10">
                Hold <span className="text-orange-400">Shift</span> + drag to draw your ROI
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default GeoBboxEditorOverlay;
