import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Image, Crosshair, Layers } from 'lucide-react';
import { useNodeData } from '../../context/NodesDataContext';

type PointType = 0 | 1 | 2;
interface SamplePoint { x: number; y: number; type: PointType }

const TYPE_COLOR: Record<PointType, string>   = { 0: '#22dc50', 1: '#ff4444', 2: '#00d4ff' };
const TYPE_GESTURE: Record<PointType, string> = { 0: 'L-click', 1: 'R-click', 2: 'Shift+L' };

const REMOVE_THRESHOLD = 0.03;

interface Props { node: any; onClose: () => void }

const GeoInteractiveSamplerEditorOverlay = ({ node, onClose }: Props) => {
  const [points, setPoints]                     = useState<SamplePoint[]>([]);
  const [selectedIndices, setSelectedIndices]   = useState<string[]>([]);
  const [basemap, setBasemap]                   = useState<string>('__image__');
  const [zoom, setZoom]                         = useState(1);
  const [pan, setPan]                           = useState({ x: 0, y: 0 });

  const viewportRef = useRef<HTMLDivElement>(null);
  const imgRef      = useRef<HTMLImageElement>(null);
  const isPanning   = useRef(false);
  const panOrigin   = useRef({ mx: 0, my: 0, px: 0, py: 0 });

  const nd          = useNodeData(node?.id ?? null);
  const bandPreviews: Record<string, string> = nd?.band_previews ?? {};
  const bandNames: string[] = nd?.band_names ?? [];

  // Resolve current basemap frame — never use the annotated preview (nd.preview)
  const frame = useMemo(() => {
    if (basemap && bandPreviews[basemap]) return bandPreviews[basemap];
    // Fallback: first available
    const first = Object.values(bandPreviews)[0];
    return first ?? null;
  }, [basemap, bandPreviews]);

  useEffect(() => {
    try { const p = JSON.parse(node?.data?.params?.points  || '[]'); if (Array.isArray(p)) setPoints(p); }  catch {}
    try { const i = JSON.parse(node?.data?.params?.indices || '[]'); if (Array.isArray(i)) setSelectedIndices(i.slice(0, 3)); } catch {}
    // Default basemap: image input if available, else first band
    const previews = nd?.band_previews ?? {};
    if (previews['__image__'])    setBasemap('__image__');
    else if (Object.keys(previews).length > 0) setBasemap(Object.keys(previews)[0]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node?.id]);

  const getRelPos = useCallback((e: React.MouseEvent) => {
    const r = imgRef.current?.getBoundingClientRect();
    if (!r) return { x: 0, y: 0 };
    return { x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), y: Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)) };
  }, []);

  const pushParams = useCallback((newPoints: SamplePoint[], newIndices: string[]) => {
    node.data.onChangeParams({ points: JSON.stringify(newPoints), indices: JSON.stringify(newIndices) });
  }, [node]);

  // Left-click only (no right-click here — handled by onContextMenu)
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      isPanning.current = true;
      panOrigin.current = { mx: e.clientX, my: e.clientY, px: pan.x, py: pan.y };
      return;
    }
    if (e.button !== 0) return; // right-click exclusively handled by onContextMenu
    if (!imgRef.current) return;

    const pos       = getRelPos(e);
    const threshold = REMOVE_THRESHOLD / zoom;
    const nearIdx   = points.findIndex(p => Math.abs(p.x - pos.x) < threshold && Math.abs(p.y - pos.y) < threshold);
    if (nearIdx >= 0) {
      const next = points.filter((_, i) => i !== nearIdx);
      setPoints(next);
      pushParams(next, selectedIndices);
      return;
    }

    const ptype: PointType = e.shiftKey ? 2 : 0;
    if (!selectedIndices[ptype]) return;
    const next = [...points, { x: pos.x, y: pos.y, type: ptype }];
    setPoints(next);
    pushParams(next, selectedIndices);
  }, [getRelPos, pan, points, selectedIndices, zoom, pushParams]);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    if (!imgRef.current) return;

    const pos       = getRelPos(e);
    const threshold = REMOVE_THRESHOLD / zoom;
    const nearIdx   = points.findIndex(p => Math.abs(p.x - pos.x) < threshold && Math.abs(p.y - pos.y) < threshold);
    if (nearIdx >= 0) {
      const next = points.filter((_, i) => i !== nearIdx);
      setPoints(next);
      pushParams(next, selectedIndices);
      return;
    }

    if (!selectedIndices[1]) return;
    const next = [...points, { x: pos.x, y: pos.y, type: 1 }];
    setPoints(next);
    pushParams(next, selectedIndices);
  }, [getRelPos, points, selectedIndices, zoom, pushParams]);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const vp = viewportRef.current?.getBoundingClientRect();
    if (!vp) return;
    const factor  = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = Math.max(0.1, Math.min(20, zoom * factor));
    const cx = e.clientX - vp.left - vp.width / 2;
    const cy = e.clientY - vp.top  - vp.height / 2;
    setPan(p => ({ x: cx - (cx - p.x) * (newZoom / zoom), y: cy - (cy - p.y) * (newZoom / zoom) }));
    setZoom(newZoom);
  }, [zoom]);

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

  const toggleIndex = useCallback((name: string) => {
    setSelectedIndices(prev => {
      if (prev.includes(name)) {
        const removedSlot = prev.indexOf(name);
        const nextIndices = prev.filter(n => n !== name);
        setTimeout(() => setPoints(pts => {
          const nextPoints = pts.filter(p => p.type !== removedSlot);
          pushParams(nextPoints, nextIndices);
          return nextPoints;
        }), 0);
        return nextIndices;
      }
      if (prev.length >= 3) return prev;
      const nextIndices = [...prev, name];
      setTimeout(() => pushParams(points, nextIndices), 0);
      return nextIndices;
    });
  }, [points, pushParams]);

  const counts = useMemo(() => ({
    0: points.filter(p => p.type === 0).length,
    1: points.filter(p => p.type === 1).length,
    2: points.filter(p => p.type === 2).length,
  }), [points]);

  const save = () => {
    pushParams(points, selectedIndices);
    onClose();
  };

  const basemapKeys = Object.keys(bandPreviews);

  return (
    <div className="fixed inset-0 z-[1000] bg-black/95 backdrop-blur-3xl flex flex-col items-center justify-center select-none nodrag" onContextMenu={e => e.preventDefault()}>

      {/* Header */}
      <div className="absolute top-6 left-8 flex items-center gap-4 z-10">
        <div className="p-3 bg-emerald-500/20 rounded-2xl text-emerald-400"><Crosshair size={26} /></div>
        <div>
          <h2 className="text-xl font-black uppercase tracking-[0.2em] text-white">GEO SAMPLER</h2>
          <p className="text-[9px] text-gray-500 font-bold uppercase tracking-widest mt-0.5">
            Sélectionner indices en bas · Cliquer pour placer · Re-cliquer pour supprimer
          </p>
        </div>
      </div>
      <div className="absolute top-6 right-8 z-10">
        <span className="text-[10px] font-mono text-emerald-400/50 bg-emerald-400/5 border border-emerald-400/10 px-3 py-1.5 rounded-full">{Math.round(zoom * 100)}%</span>
      </div>

      {/* Basemap selector */}
      {basemapKeys.length > 1 && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 px-4 py-2 bg-black/60 border border-white/10 rounded-2xl backdrop-blur-md">
          <Layers size={11} className="text-gray-500" />
          <span className="text-[8px] font-black uppercase tracking-widest text-gray-500 mr-1">Fond</span>
          {basemapKeys.map(key => (
            <button key={key} onClick={() => setBasemap(key)}
              className={`px-2.5 py-1 rounded-lg text-[8px] font-black uppercase tracking-widest transition-all border ${
                basemap === key
                  ? 'bg-white/15 border-white/30 text-white'
                  : 'bg-white/3 border-white/8 text-gray-500 hover:bg-white/8'
              }`}>
              {key === '__image__' ? 'Image' : key}
            </button>
          ))}
        </div>
      )}

      {/* Viewport */}
      <div ref={viewportRef} className="relative flex-1 w-full overflow-hidden cursor-crosshair mt-8" onWheel={handleWheel}>
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: 'center center' }}>
          <div className="relative inline-block shadow-[0_0_100px_rgba(0,0,0,0.5)] rounded-2xl overflow-hidden border border-white/10 bg-[#0c0c0c] pointer-events-auto"
            onMouseDown={handleMouseDown} onContextMenu={handleContextMenu}>
            {frame
              ? <img ref={imgRef} src={`data:image/jpeg;base64,${frame}`} className="block w-auto h-auto max-w-[90vw] max-h-[65vh]" draggable={false} />
              : <div className="w-[800px] h-[450px] flex flex-col items-center justify-center text-gray-700 gap-3">
                  <Image size={40} className="opacity-10" />
                  <span className="text-[9px] font-mono opacity-20">Connecter geo_spectral_indices</span>
                </div>
            }
            <svg className="absolute inset-0 w-full h-full" style={{ pointerEvents: 'none' }}>
              {points.map((p, i) => {
                const r         = 12 / zoom;
                const fs        = 13 / zoom;
                const indexName = selectedIndices[p.type] ?? '?';
                const pv        = (nd as any)?.point_values?.[String(i)];
                const label     = pv != null ? `${indexName}=${pv.value}` : indexName;
                return (
                  <g key={i}>
                    <circle cx={`${p.x * 100}%`} cy={`${p.y * 100}%`} r={r} fill={TYPE_COLOR[p.type]} opacity={0.9} />
                    <circle cx={`${p.x * 100}%`} cy={`${p.y * 100}%`} r={r + 2 / zoom} fill="none" stroke="white" strokeWidth={2 / zoom} opacity={0.8} />
                    <text x={`${p.x * 100}%`} y={`${p.y * 100}%`} dy={-(r + 16 / zoom)} textAnchor="middle" fill="white" fontSize={fs} fontWeight="bold" opacity={0.9}
                      style={{ textShadow: '0 1px 3px rgba(0,0,0,0.9)' }}>{label}</text>
                  </g>
                );
              })}
            </svg>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="p-5 w-full flex flex-col items-center gap-3 bg-gradient-to-t from-black/80 to-transparent">

        {/* Index checkboxes */}
        <div className="flex flex-col items-center gap-2 w-full max-w-3xl">
          <p className="text-[8px] font-black uppercase tracking-widest text-gray-600">
            Indices — cocher jusqu'à 3 · L'ordre détermine le type de clic
          </p>
          {bandNames.length === 0
            ? <p className="text-[8px] text-gray-700 font-mono">En attente de geo_spectral_indices…</p>
            : (
              <div className="flex flex-wrap justify-center gap-2">
                {bandNames.map(name => {
                  const slotIdx  = selectedIndices.indexOf(name);
                  const active   = slotIdx >= 0;
                  const blocked  = !active && selectedIndices.length >= 3;
                  const slotColor = active ? TYPE_COLOR[slotIdx as PointType] : undefined;
                  return (
                    <button key={name} onClick={() => !blocked && toggleIndex(name)}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-xl border text-[9px] font-black uppercase tracking-widest transition-all ${
                        active    ? 'text-white border-white/20'
                        : blocked ? 'opacity-30 cursor-not-allowed bg-white/3 border-white/5 text-gray-600'
                                  : 'bg-white/5 border-white/10 text-gray-400 hover:bg-white/10'
                      }`}
                      style={active ? { background: slotColor + '1a', borderColor: slotColor + '55' } : undefined}
                    >
                      {active && (
                        <span className="text-[8px] font-black px-1.5 py-0.5 rounded" style={{ background: slotColor + '33', color: slotColor }}>
                          {TYPE_GESTURE[slotIdx as PointType]}
                        </span>
                      )}
                      {name}
                      {active && <span className="ml-0.5 opacity-50 text-[8px]">({counts[slotIdx as PointType]})</span>}
                    </button>
                  );
                })}
              </div>
            )
          }
        </div>

        {/* Active bindings summary */}
        {selectedIndices.length > 0 && (
          <div className="flex items-center gap-5 px-5 py-2 bg-white/4 rounded-2xl border border-white/8">
            {([0, 1, 2] as PointType[]).map(t => {
              if (!selectedIndices[t]) return null;
              return (
                <span key={t} className="text-[9px] font-black uppercase tracking-widest" style={{ color: TYPE_COLOR[t] }}>
                  {TYPE_GESTURE[t]} → {selectedIndices[t]} ({counts[t]})
                </span>
              );
            })}
            <div className="w-px h-3 bg-white/10" />
            <span className="text-[8px] text-gray-600 font-mono">ALT+drag pan · scroll zoom</span>
          </div>
        )}

        {/* Buttons */}
        <div className="flex items-center gap-3">
          <button onClick={onClose} className="px-8 py-3.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[9px] font-black uppercase tracking-widest text-gray-400 transition-all active:scale-95">Cancel</button>
          <button onClick={() => setPoints([])} className="px-8 py-3.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[9px] font-black uppercase tracking-widest text-gray-400 transition-all active:scale-95">Clear All</button>
          <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} className="px-5 py-3.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[9px] font-black uppercase tracking-widest text-gray-400 transition-all active:scale-95">Reset View</button>
          <button onClick={save} className="px-16 py-3.5 bg-emerald-600 hover:bg-emerald-500 shadow-2xl shadow-emerald-500/30 rounded-2xl text-[9px] font-black uppercase tracking-widest text-white transition-all scale-110 hover:scale-115 active:scale-95 border border-white/10">Apply</button>
        </div>
      </div>
    </div>
  );
};

export default GeoInteractiveSamplerEditorOverlay;
