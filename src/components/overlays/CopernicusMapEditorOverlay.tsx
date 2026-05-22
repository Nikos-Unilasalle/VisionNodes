/**
 * CopernicusMapEditorOverlay.tsx
 *
 * Full-screen map editor for the Copernicus CDSE node.
 * Canvas-based slippy map (OpenStreetMap tiles) with rectangle ROI drawing.
 * No external map library required.
 */
import React, {
  useRef, useEffect, useState, useCallback, useMemo,
} from 'react';
import { X, Satellite, MousePointer, Square, Download, Trash2 } from 'lucide-react';

// ── Tile math (Web Mercator / EPSG:3857) ─────────────────────────────────────

const TILE_SIZE = 256;

const lonToTileX = (lon: number, z: number) =>
  ((lon + 180) / 360) * Math.pow(2, z);

const latToTileY = (lat: number, z: number) => {
  const r = (lat * Math.PI) / 180;
  return (
    ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) *
    Math.pow(2, z)
  );
};

const tileXToLon = (x: number, z: number) =>
  (x / Math.pow(2, z)) * 360 - 180;

const tileYToLat = (y: number, z: number) => {
  const n = Math.PI - (2 * Math.PI * y) / Math.pow(2, z);
  return (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
};

// ── Pixel ↔ world coords ─────────────────────────────────────────────────────
// offsetX/Y: pixel position of tile (0,0) on canvas.

const canvasToLatLon = (
  px: number, py: number,
  zoom: number, offsetX: number, offsetY: number,
): [number, number] => {
  const tx = (px - offsetX) / TILE_SIZE;
  const ty = (py - offsetY) / TILE_SIZE;
  return [tileYToLat(ty, zoom), tileXToLon(tx, zoom)];
};

const latLonToCanvas = (
  lat: number, lon: number,
  zoom: number, offsetX: number, offsetY: number,
): [number, number] => {
  const tx = lonToTileX(lon, zoom);
  const ty = latToTileY(lat, zoom);
  return [tx * TILE_SIZE + offsetX, ty * TILE_SIZE + offsetY];
};

const fmtCoord = (v: number, d: 'lat' | 'lon') => {
  const abs = Math.abs(v).toFixed(5);
  const dir = d === 'lat' ? (v >= 0 ? 'N' : 'S') : (v >= 0 ? 'E' : 'W');
  return `${abs}° ${dir}`;
};

// ── Collection data (mirrors Python backend) ─────────────────────────────────

const COLLECTIONS: Record<string, { allBands: string[]; defaultBands: string[]; hasClouds: boolean }> = {
  'Sentinel-2 L2A': {
    allBands:    ['B01','B02','B03','B04','B05','B06','B07','B08','B8A','B09','B11','B12'],
    defaultBands:['B04','B03','B02','B08'],
    hasClouds: true,
  },
  'Sentinel-2 L1C': {
    allBands:    ['B01','B02','B03','B04','B05','B06','B07','B08','B8A','B09','B10','B11','B12'],
    defaultBands:['B04','B03','B02','B08'],
    hasClouds: true,
  },
  'Sentinel-1 GRD': {
    allBands:    ['VV','VH'],
    defaultBands:['VV','VH'],
    hasClouds: false,
  },
  'Copernicus DEM': {
    allBands:    ['DEM'],
    defaultBands:['DEM'],
    hasClouds: false,
  },
};

const COLLECTION_NAMES = Object.keys(COLLECTIONS);

// ── Types ─────────────────────────────────────────────────────────────────────

interface Bbox { west: number; south: number; east: number; north: number }

interface Props {
  node: any;
  onClose: () => void;
}

// ── Component ─────────────────────────────────────────────────────────────────

const CopernicusMapEditorOverlay: React.FC<Props> = ({ node, onClose }) => {
  const params = node?.data?.params ?? {};

  // ── Map state
  const [zoom,    setZoom]    = useState(5);
  const [offsetX, setOffsetX] = useState(0);
  const [offsetY, setOffsetY] = useState(0);

  // ── Draw mode
  const [drawMode, setDrawMode] = useState(false);
  const [bbox,     setBbox]     = useState<Bbox | null>(null);

  // ── Mouse position
  const [cursor, setCursor] = useState<[number, number] | null>(null);

  // ── Form state (mirrors node params)
  const colIdx0 = parseInt(String(params.collection ?? '0'), 10);
  const [colIdx,      setColIdx]      = useState(isNaN(colIdx0) ? 0 : colIdx0);
  const [dateStart,   setDateStart]   = useState<string>(params.date_start   ?? '2024-01-01');
  const [dateEnd,     setDateEnd]     = useState<string>(params.date_end     ?? '2024-06-01');
  const [cloudMax,    setCloudMax]    = useState<number>(parseInt(params.cloud_max ?? '20', 10));
  const [resolution,  setResolution]  = useState<number>(parseInt(params.resolution ?? '10', 10));
  const [selectedBands, setSelectedBands] = useState<string[]>(() => {
    const raw = (params.bands ?? '').split(',').map((s: string) => s.trim()).filter(Boolean);
    return raw.length > 0 ? raw : COLLECTIONS[COLLECTION_NAMES[colIdx0] ?? 'Sentinel-2 L2A'].defaultBands;
  });

  const colName = COLLECTION_NAMES[colIdx] ?? 'Sentinel-2 L2A';
  const colCfg  = COLLECTIONS[colName];

  // ── Canvas & tile cache
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const tileCache  = useRef<Map<string, HTMLImageElement>>(new Map());

  // ── Panning state (refs to avoid stale closures)
  const isPanning    = useRef(false);
  const panStart     = useRef({ mx: 0, my: 0, ox: 0, oy: 0 });
  const isDrawing    = useRef(false);
  const drawStart    = useRef<[number, number] | null>(null); // [lat, lon]
  const drawCurrent  = useRef<[number, number] | null>(null); // [lat, lon]

  // ── Init bbox from params ─────────────────────────────────────────────────
  useEffect(() => {
    const raw = (params.bbox ?? '').trim();
    if (!raw) return;
    const parts = raw.split(',').map(Number);
    if (parts.length === 4 && parts.every(isFinite)) {
      const [w, s, e, n] = parts;
      setBbox({ west: w, south: s, east: e, north: n });
      // Center map on existing bbox
      const lat = (s + n) / 2;
      const lon = (w + e) / 2;
      const z = 6;
      setZoom(z);
      const tx = lonToTileX(lon, z) * TILE_SIZE;
      const ty = latToTileY(lat, z) * TILE_SIZE;
      const w2 = window.innerWidth * 0.6;
      const h2 = window.innerHeight;
      setOffsetX(w2 / 2 - tx);
      setOffsetY(h2 / 2 - ty);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Init map center (default: France) ─────────────────────────────────────
  useEffect(() => {
    const raw = (params.bbox ?? '').trim();
    if (raw) return;  // handled above
    const lat = 46.5, lon = 2.5, z = 5;
    setZoom(z);
    const tx = lonToTileX(lon, z) * TILE_SIZE;
    const ty = latToTileY(lat, z) * TILE_SIZE;
    const w2 = window.innerWidth * 0.6;
    const h2 = window.innerHeight;
    setOffsetX(w2 / 2 - tx);
    setOffsetY(h2 / 2 - ty);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Tile loader ───────────────────────────────────────────────────────────
  const getTile = useCallback((z: number, x: number, y: number): HTMLImageElement => {
    const numTiles = Math.pow(2, z);
    const cx = ((x % numTiles) + numTiles) % numTiles;
    const cy = Math.max(0, Math.min(numTiles - 1, y));
    const key = `${z}/${cx}/${cy}`;
    if (tileCache.current.has(key)) return tileCache.current.get(key)!;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    // Use a 1×1 transparent placeholder while loading
    img.src = `https://tile.openstreetmap.org/${z}/${cx}/${cy}.png`;
    img.onload = () => renderFrame();
    tileCache.current.set(key, img);
    return img;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Canvas render ─────────────────────────────────────────────────────────
  const renderFrame = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, W, H);

    const ox = offsetX;
    const oy = offsetY;
    const z  = zoom;

    const startTX = Math.floor(-ox / TILE_SIZE) - 1;
    const startTY = Math.floor(-oy / TILE_SIZE) - 1;
    const endTX   = Math.ceil((W - ox) / TILE_SIZE) + 1;
    const endTY   = Math.ceil((H - oy) / TILE_SIZE) + 1;

    // OSM tiles
    for (let ty = startTY; ty <= endTY; ty++) {
      for (let tx = startTX; tx <= endTX; tx++) {
        const img = getTile(z, tx, ty);
        const px  = tx * TILE_SIZE + ox;
        const py  = ty * TILE_SIZE + oy;
        if (img.complete && img.naturalWidth > 0) {
          ctx.drawImage(img, px, py, TILE_SIZE, TILE_SIZE);
        } else {
          ctx.fillStyle = '#262640';
          ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);
        }
      }
    }

    // Attribution
    ctx.save();
    ctx.font = '9px sans-serif';
    ctx.fillStyle = 'rgba(0,0,0,0.5)';
    ctx.fillRect(W - 180, H - 16, 180, 16);
    ctx.fillStyle = '#ccc';
    ctx.fillText('© OpenStreetMap contributors', W - 175, H - 4);
    ctx.restore();

    // Live draw rect
    if (isDrawing.current && drawStart.current && drawCurrent.current) {
      const [lat1, lon1] = drawStart.current;
      const [lat2, lon2] = drawCurrent.current;
      const [x1, y1] = latLonToCanvas(lat1, lon1, z, ox, oy);
      const [x2, y2] = latLonToCanvas(lat2, lon2, z, ox, oy);
      drawRect(ctx, x1, y1, x2, y2, 'rgba(251,146,60,0.25)', '#fb923c', 2.5);
    }

    // Saved bbox
    if (bbox) {
      const [x1, y1] = latLonToCanvas(bbox.north, bbox.west, z, ox, oy);
      const [x2, y2] = latLonToCanvas(bbox.south, bbox.east, z, ox, oy);
      drawRect(ctx, x1, y1, x2, y2, 'rgba(34,197,94,0.15)', '#22c55e', 2);

      // Corner labels
      ctx.save();
      ctx.font = 'bold 10px monospace';
      ctx.fillStyle = '#22c55e';
      ctx.fillText(`${bbox.north.toFixed(3)}° N`, x1 + 6, y1 + 14);
      ctx.fillText(`${bbox.south.toFixed(3)}° S`, x1 + 6, y2 - 4);
      ctx.restore();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoom, offsetX, offsetY, bbox, getTile]);

  const drawRect = (
    ctx: CanvasRenderingContext2D,
    x1: number, y1: number, x2: number, y2: number,
    fill: string, stroke: string, lw: number,
  ) => {
    const rx = Math.min(x1, x2), ry = Math.min(y1, y2);
    const rw = Math.abs(x2 - x1),  rh = Math.abs(y2 - y1);
    ctx.fillStyle = fill;
    ctx.fillRect(rx, ry, rw, rh);
    ctx.strokeStyle = stroke;
    ctx.lineWidth = lw;
    ctx.setLineDash([6, 4]);
    ctx.strokeRect(rx, ry, rw, rh);
    ctx.setLineDash([]);
  };

  useEffect(() => { renderFrame(); }, [renderFrame]);

  // ── Resize observer ───────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver(entries => {
      const e = entries[0];
      canvas.width  = e.contentRect.width;
      canvas.height = e.contentRect.height;
      renderFrame();
    });
    ro.observe(canvas.parentElement ?? canvas);
    return () => ro.disconnect();
  }, [renderFrame]);

  // ── Wheel zoom ────────────────────────────────────────────────────────────
  const handleWheel = useCallback((e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1 : -1;
    setZoom(z => {
      const newZ = Math.max(2, Math.min(18, z + factor));
      if (newZ === z) return z;
      // Zoom towards mouse position
      const canvas = canvasRef.current;
      if (!canvas) return newZ;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const scale = Math.pow(2, newZ - z);
      setOffsetX(ox => mx - (mx - ox) * scale);
      setOffsetY(oy => my - (my - oy) * scale);
      return newZ;
    });
  }, []);

  // ── Mouse events ──────────────────────────────────────────────────────────
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect  = canvas.getBoundingClientRect();
    const mx    = e.clientX - rect.left;
    const my    = e.clientY - rect.top;

    if (drawMode) {
      const [lat, lon] = canvasToLatLon(mx, my, zoom, offsetX, offsetY);
      isDrawing.current = true;
      drawStart.current   = [lat, lon];
      drawCurrent.current = [lat, lon];
    } else {
      isPanning.current = true;
      panStart.current  = { mx: e.clientX, my: e.clientY, ox: offsetX, oy: offsetY };
    }
  }, [drawMode, zoom, offsetX, offsetY]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const mx   = e.clientX - rect.left;
      const my   = e.clientY - rect.top;

      // Update cursor coords
      const [lat, lon] = canvasToLatLon(mx, my, zoom, offsetX, offsetY);
      setCursor([lat, lon]);

      if (isPanning.current) {
        setOffsetX(panStart.current.ox + (e.clientX - panStart.current.mx));
        setOffsetY(panStart.current.oy + (e.clientY - panStart.current.my));
      }
      if (isDrawing.current) {
        drawCurrent.current = [lat, lon];
        renderFrame();
      }
    };

    const onUp = (e: MouseEvent) => {
      if (isDrawing.current && drawStart.current && drawCurrent.current) {
        const [lat1, lon1] = drawStart.current;
        const [lat2, lon2] = drawCurrent.current;
        const bbox: Bbox = {
          west:  Math.min(lon1, lon2),
          east:  Math.max(lon1, lon2),
          south: Math.min(lat1, lat2),
          north: Math.max(lat1, lat2),
        };
        const minDelta = 0.001;
        if (Math.abs(bbox.east - bbox.west) > minDelta &&
            Math.abs(bbox.north - bbox.south) > minDelta) {
          setBbox(bbox);
        }
      }
      isPanning.current = false;
      isDrawing.current = false;
      drawStart.current   = null;
      drawCurrent.current = null;
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup',   onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup',   onUp);
    };
  }, [zoom, offsetX, offsetY, renderFrame]);

  // ── Estimated image size ──────────────────────────────────────────────────
  const estimatedSize = useMemo(() => {
    if (!bbox) return null;
    const latC   = (bbox.south + bbox.north) / 2;
    const widthM = Math.abs(bbox.east - bbox.west) * 111320 * Math.cos((latC * Math.PI) / 180);
    const heightM = Math.abs(bbox.north - bbox.south) * 111320;
    const W = Math.round(widthM / Math.max(1, resolution));
    const H = Math.round(heightM / Math.max(1, resolution));
    return { W, H, mb: (W * H * selectedBands.length * 4 / 1024 / 1024).toFixed(1) };
  }, [bbox, resolution, selectedBands]);

  // ── Save & fetch ──────────────────────────────────────────────────────────
  const handleFetch = useCallback(() => {
    if (!bbox) return;
    const bboxStr = `${bbox.west.toFixed(6)},${bbox.south.toFixed(6)},${bbox.east.toFixed(6)},${bbox.north.toFixed(6)}`;
    node?.data?.onChangeParams?.({
      bbox:        bboxStr,
      bands:       selectedBands.join(','),
      collection:  String(colIdx),
      date_start:  dateStart,
      date_end:    dateEnd,
      cloud_max:   String(cloudMax),
      resolution:  String(resolution),
      fetch:       true,   // trigger rising edge
    });
    onClose();
  }, [bbox, selectedBands, colIdx, dateStart, dateEnd, cloudMax, resolution, node, onClose]);

  const handleSaveOnly = useCallback(() => {
    if (!bbox) return;
    const bboxStr = `${bbox.west.toFixed(6)},${bbox.south.toFixed(6)},${bbox.east.toFixed(6)},${bbox.north.toFixed(6)}`;
    node?.data?.onChangeParams?.({
      bbox:        bboxStr,
      bands:       selectedBands.join(','),
      collection:  String(colIdx),
      date_start:  dateStart,
      date_end:    dateEnd,
      cloud_max:   String(cloudMax),
      resolution:  String(resolution),
    });
    onClose();
  }, [bbox, selectedBands, colIdx, dateStart, dateEnd, cloudMax, resolution, node, onClose]);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div
      className="fixed inset-0 z-[1000] flex flex-row select-none nodrag"
      onContextMenu={e => e.preventDefault()}
    >
      {/* ── Left settings panel ─────────────────────────────────────────── */}
      <div className="w-72 flex flex-col bg-[#0d0d1a] border-r border-white/5 overflow-y-auto shrink-0">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 pt-5 pb-4 border-b border-white/5">
          <div className="p-2 bg-blue-500/20 rounded-xl text-blue-400">
            <Satellite size={18} />
          </div>
          <div>
            <div className="text-xs font-black uppercase tracking-widest text-white">Copernicus CDSE</div>
            <div className="text-[9px] text-gray-500 font-mono">Map Editor</div>
          </div>
          <button
            onClick={onClose}
            className="ml-auto p-1.5 rounded-lg hover:bg-white/10 text-gray-500 hover:text-white transition-colors"
          >
            <X size={14} />
          </button>
        </div>

        <div className="flex flex-col gap-4 px-4 py-4 flex-1">
          {/* Collection */}
          <div>
            <label className="block text-[9px] font-black uppercase tracking-widest text-gray-500 mb-1.5">Collection</label>
            <select
              value={colIdx}
              onChange={e => {
                const idx = parseInt(e.target.value, 10);
                setColIdx(idx);
                setSelectedBands(COLLECTIONS[COLLECTION_NAMES[idx]].defaultBands);
              }}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1.5 text-[10px] text-white font-mono focus:outline-none focus:border-blue-500/50"
            >
              {COLLECTION_NAMES.map((n, i) => (
                <option key={n} value={i} className="bg-[#0d0d1a]">{n}</option>
              ))}
            </select>
          </div>

          {/* Bands */}
          <div>
            <label className="block text-[9px] font-black uppercase tracking-widest text-gray-500 mb-1.5">Bands</label>
            <div className="flex flex-wrap gap-1.5">
              {colCfg.allBands.map(band => (
                <button
                  key={band}
                  onClick={() => setSelectedBands(prev =>
                    prev.includes(band)
                      ? prev.filter(b => b !== band)
                      : [...prev, band]
                  )}
                  className={`px-2 py-0.5 rounded-full text-[9px] font-black font-mono transition-all ${
                    selectedBands.includes(band)
                      ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/30'
                      : 'bg-white/5 text-gray-500 hover:bg-white/10 hover:text-white'
                  }`}
                >
                  {band}
                </button>
              ))}
            </div>
            {selectedBands.length === 0 && (
              <p className="text-[8px] text-amber-500 mt-1">Select at least one band</p>
            )}
          </div>

          {/* Dates */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[9px] font-black uppercase tracking-widest text-gray-500 mb-1">Start</label>
              <input
                type="date"
                value={dateStart}
                onChange={e => setDateStart(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-[10px] text-white font-mono focus:outline-none focus:border-blue-500/50"
              />
            </div>
            <div>
              <label className="block text-[9px] font-black uppercase tracking-widest text-gray-500 mb-1">End</label>
              <input
                type="date"
                value={dateEnd}
                onChange={e => setDateEnd(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-[10px] text-white font-mono focus:outline-none focus:border-blue-500/50"
              />
            </div>
          </div>

          {/* Cloud cover */}
          {colCfg.hasClouds && (
            <div>
              <label className="block text-[9px] font-black uppercase tracking-widest text-gray-500 mb-1">
                Max clouds: <span className="text-blue-400">{cloudMax}%</span>
              </label>
              <input
                type="range" min={0} max={100} step={5}
                value={cloudMax}
                onChange={e => setCloudMax(parseInt(e.target.value, 10))}
                className="w-full accent-blue-500"
              />
            </div>
          )}

          {/* Resolution */}
          <div>
            <label className="block text-[9px] font-black uppercase tracking-widest text-gray-500 mb-1">Resolution (m/px)</label>
            <input
              type="number" min={1} max={1000} step={1}
              value={resolution}
              onChange={e => setResolution(parseInt(e.target.value, 10) || 10)}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-2.5 py-1 text-[10px] text-white font-mono focus:outline-none focus:border-blue-500/50"
            />
          </div>

          {/* Bbox info */}
          {bbox && (
            <div className="bg-green-500/5 border border-green-500/15 rounded-xl p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[9px] font-black uppercase tracking-widest text-green-400">ROI Selected</span>
                <button
                  onClick={() => setBbox(null)}
                  className="text-red-400/60 hover:text-red-400 transition-colors"
                  title="Clear ROI"
                >
                  <Trash2 size={11} />
                </button>
              </div>
              <div className="font-mono text-[8px] text-gray-400 space-y-0.5">
                <div>W: {bbox.west.toFixed(5)}°  E: {bbox.east.toFixed(5)}°</div>
                <div>S: {bbox.south.toFixed(5)}°  N: {bbox.north.toFixed(5)}°</div>
              </div>
              {estimatedSize && (
                <div className="mt-2 pt-2 border-t border-white/5 font-mono text-[8px] text-blue-400">
                  {estimatedSize.W} × {estimatedSize.H} px · {selectedBands.length} band{selectedBands.length !== 1 ? 's' : ''} · ~{estimatedSize.mb} MB
                </div>
              )}
            </div>
          )}

          <div className="flex-1" />

          {/* Action buttons */}
          <div className="flex flex-col gap-2">
            <button
              onClick={handleFetch}
              disabled={!bbox || selectedBands.length === 0}
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all disabled:opacity-30 disabled:pointer-events-none bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/25"
            >
              <Download size={12} /> Fetch Image
            </button>
            <button
              onClick={handleSaveOnly}
              disabled={!bbox}
              className="flex items-center justify-center gap-2 px-4 py-2 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all disabled:opacity-30 disabled:pointer-events-none bg-white/5 hover:bg-white/10 text-gray-300"
            >
              Save ROI only
            </button>
          </div>
        </div>
      </div>

      {/* ── Map area ────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col bg-[#12121f] relative overflow-hidden">
        {/* Top bar */}
        <div className="flex items-center gap-3 px-4 py-2 bg-black/40 border-b border-white/5 z-10">
          {/* Draw mode toggle */}
          <button
            onClick={() => setDrawMode(m => !m)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${
              drawMode
                ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30'
                : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
            }`}
          >
            {drawMode ? <Square size={10} /> : <MousePointer size={10} />}
            {drawMode ? 'Drawing ROI' : 'Pan mode'}
          </button>

          <div className="text-[9px] font-mono text-gray-600">
            {drawMode ? 'Click + drag to define area of interest' : 'Scroll to zoom · Drag to pan'}
          </div>

          <div className="ml-auto flex items-center gap-3 text-[9px] font-mono">
            {cursor && (
              <span className="text-gray-500">
                {fmtCoord(cursor[0], 'lat')} &nbsp; {fmtCoord(cursor[1], 'lon')}
              </span>
            )}
            <span className="text-blue-400/60 bg-blue-400/5 border border-blue-400/10 px-2 py-0.5 rounded-full">
              z{zoom}
            </span>
          </div>
        </div>

        {/* Canvas */}
        <div className="flex-1 relative">
          <canvas
            ref={canvasRef}
            className={`absolute inset-0 w-full h-full ${drawMode ? 'cursor-crosshair' : 'cursor-grab active:cursor-grabbing'}`}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
          />
          {/* No-bbox hint */}
          {!bbox && !drawMode && (
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 pointer-events-none">
              <div className="px-4 py-2 bg-black/70 backdrop-blur-md rounded-full text-[10px] font-black uppercase tracking-widest text-gray-400 border border-white/10">
                Switch to <span className="text-orange-400">Drawing mode</span> to define your ROI
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CopernicusMapEditorOverlay;
