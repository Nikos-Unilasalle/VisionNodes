import React, { memo, useState, useMemo, useEffect } from 'react';
import { Handle, Position, useNodeId, useEdges, useUpdateNodeInternals, NodeResizer, useStore } from 'reactflow';
import { useNodeData } from '../../context/NodesDataContext';
import { useComputingNodeId } from '../../context/ComputingNodeContext';
import { open, save } from '@tauri-apps/plugin-dialog';
import { openPath } from '@tauri-apps/plugin-opener';
import {
  Camera, Waves, Ghost, Maximize, Search, User, Zap, Activity,
  Hash, Eye, Layout, PenTool, Database, Wind, Target, Palette, Scaling, Move, Layers, Box, Image, Film, Play, Pause,
  Plus, Info, Save, FolderOpen, BookOpen, Video, Type, Calculator, PlusSquare, Minus, Divide, Scissors, Keyboard, HelpCircle, ChevronDown, ChevronUp,
  Crosshair, Monitor, Lock, LockOpen, Crop, Filter, Package, LogIn, LogOut, BarChart2, Music, Volume2, RotateCcw, Repeat, Download, FileCode, ZapOff,
  Clipboard, FileText
} from 'lucide-react';
import * as LucideIcons from 'lucide-react';
import {
  AreaChart, Area, ResponsiveContainer, YAxis, XAxis, Tooltip,
  BarChart, Bar, Cell, LineChart, Line, CartesianGrid, ReferenceLine,
  ComposedChart,
} from 'recharts';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { MarkdownToolbar } from '../MarkdownToolbar';
import { getIcon, StyledHandle, BaseNode, HANDLE_COLORS, NodeColorContext, useNodeColor, NodeColorProvider, PALETTES } from './_shared';

export const GeoStatisticsNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const area = nd?.area_ha ?? 0;
  const pixels = nd?.pixels ?? 0;
  const mean = nd?.mean_val ?? 0;
  const min = nd?.min_val ?? 0;
  const max = nd?.max_val ?? 0;

  return (
    <BaseNode
      title="Geo Statistics"
      icon={BarChart2}
      selected={selected}
      data={data}
      color="green"
      inputs={[
        {id: 'geotiff', color: 'geotiff'},
        {id: 'mask',    color: 'mask'}
      ]}
      outputs={[
        {id: 'area_ha',  color: 'scalar'},
        {id: 'pixels',   color: 'scalar'},
        {id: 'mean_val', color: 'scalar'}
      ]}
    >
      <div className="flex flex-col gap-3 p-1">
        <div className="flex items-center justify-between bg-white/5 border border-white/5 rounded-xl px-3 py-2.5 shadow-inner group hover:bg-white/10 transition-colors relative overflow-hidden">
          <div className="flex flex-col z-10">
            <span className="text-[7px] font-black text-gray-500 uppercase tracking-widest">Detected Area</span>
            <div className="flex items-baseline gap-1">
              <span className="text-xl font-black text-emerald-400 font-mono tracking-tighter tabular-nums">{area.toFixed(area < 0.1 ? 4 : 2)}</span>
              <span className="text-[8px] font-bold text-emerald-500/60 uppercase">ha</span>
            </div>
          </div>
          <div className="bg-emerald-500/10 p-1.5 rounded-lg border border-emerald-500/20 z-10">
            <Maximize size={14} className="text-emerald-500" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="bg-black/20 border border-white/5 rounded-xl p-2.5 flex flex-col gap-0.5 shadow-inner">
            <span className="text-[7px] font-black text-gray-600 uppercase tracking-tighter">Pixels</span>
            <span className="text-[11px] font-bold text-white/80 font-mono tabular-nums">{pixels.toLocaleString()}</span>
          </div>
          <div className="bg-black/20 border border-white/5 rounded-xl p-2.5 flex flex-col gap-0.5 border-l-2 border-l-accent/40 shadow-inner">
            <span className="text-[7px] font-black text-gray-600 uppercase tracking-tighter">Mean Index</span>
            <span className="text-[11px] font-bold text-accent font-mono tabular-nums">{mean.toFixed(3)}</span>
          </div>
        </div>

        <div className="flex items-center justify-between px-3 py-2 bg-white/5 rounded-xl border border-white/5 text-[9px] font-mono">
            <div className="flex flex-col">
                <span className="text-[6px] text-gray-500 uppercase">Min</span>
                <span className="text-white/60">{min.toFixed(3)}</span>
            </div>
            <div className="h-4 w-[1px] bg-white/10" />
            <div className="flex flex-col text-right">
                <span className="text-[6px] text-gray-500 uppercase">Max</span>
                <span className="text-white/60">{max.toFixed(3)}</span>
            </div>
        </div>
      </div>
    </BaseNode>
  );
});


export const RasterStatsNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const mean = nd?.mean ?? 0;
  const min = nd?.min ?? 0;
  const max = nd?.max ?? 0;
  const std = nd?.std ?? 0;
  const band = data.params?.band ?? 1;

  const statsDict = (nd?.stats || {}) as any;
  const bandName = `B${band}`;
  const bandStats = (statsDict[bandName] || Object.values(statsDict)[0] || {}) as any;
  const entries = [
    { label: 'Mean',   v: bandStats.mean ?? mean, color: 'text-cyan-400' },
    { label: 'Median', v: bandStats.median ?? 0, color: 'text-blue-400' },
    { label: 'Std Dev', v: bandStats.std ?? std, color: 'text-purple-400' },
    { label: 'Range',  v: (bandStats.max ?? max) - (bandStats.min ?? min), color: 'text-emerald-400' },
  ];

  return (
    <BaseNode
      title="Band Statistics"
      icon={Activity}
      selected={selected}
      data={data}
      color="blue"
      inputs={[
        {id: 'geotiff', color: 'geotiff'},
        {id: 'data',    color: 'any'}
      ]}
      outputs={[
        {id: 'geotiff', color: 'geotiff'},
        {id: 'min',     color: 'scalar'},
        {id: 'max',     color: 'scalar'},
        {id: 'mean',    color: 'scalar'},
        {id: 'std',     color: 'scalar'},
      ]}
    >
      <div className="flex flex-col gap-2 p-1">
        <div className="text-[7px] font-black text-blue-400 uppercase tracking-[0.2em] px-1">
            Band {band}
        </div>
        <div className="grid grid-cols-2 gap-2">
          {entries.map(e => (
            <div key={e.label} className="bg-black/10 p-2 rounded-lg border border-white/5">
               <div className="text-[7px] text-gray-500 uppercase font-black">{e.label}</div>
               <div className={`text-[9px] font-mono ${e.color} font-bold`}>{typeof e.v === 'number' ? e.v.toFixed(4) : '---'}</div>
            </div>
          ))}
        </div>
      </div>
    </BaseNode>
  );
});


export const GeoTIFFReaderNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  const thumbRef = React.useRef<string>('');
  if (nd?._thumb) thumbRef.current = nd._thumb;
  const thumb = thumbRef.current;
  const schema = data.schema;
  const IconCmp = getIcon('Globe', Box);
  const outputs = schema?.outputs || [{ id: 'geotiff', color: 'geotiff' }, { id: 'preview', color: 'image' }, { id: 'meta', color: 'dict' }];

  const handleBrowse = async () => {
    try {
      const file = await open({ multiple: false, filters: [{ name: 'GeoTIFF', extensions: ['tif', 'tiff'] }] });
      if (file && typeof file === 'string') data.onChangeParams?.({ file_path: file });
    } catch {}
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) data.onChangeParams?.({ file_path: (file as any).path || file.name });
  };

  return (
    <BaseNode title="GeoTIFF Reader" icon={IconCmp} selected={selected} data={data} color="green" inputs={[]} outputs={outputs}>
      {thumb ? (
        <div className="relative group" onClick={handleBrowse}>
          <img src={`data:image/jpeg;base64,${thumb}`} alt="Preview" className="w-full h-32 object-cover rounded-lg border border-[#4f5b6b] mb-1" />
          <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer rounded-lg border-2 border-dashed border-green-500/50"
            onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
            <Search size={20} className="text-white mb-1" />
            <div className="text-[7px] text-white uppercase font-black">Browse / Drop</div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center border-2 border-dashed border-[#4f5b6b] rounded-lg p-4 opacity-40 hover:opacity-100 transition-opacity cursor-pointer h-32"
          onDragOver={(e) => e.preventDefault()} onDrop={onDrop} onClick={handleBrowse}>
          <Search size={20} className="text-gray-500 mb-2" />
          <div className="text-[7px] text-gray-500 uppercase font-black text-center">Click to Browse<br/>or Drop GeoTIFF</div>
        </div>
      )}
    </BaseNode>
  );
});


export const GeoEarthEngineNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  const thumbRef = React.useRef<string>('');
  if (nd?._thumb) thumbRef.current = nd._thumb;
  const thumb = thumbRef.current;
  const schema = data.schema;
  const IconCmp = getIcon('Map', Box);
  const outputs = schema?.outputs || [{ id: 'geotiff', color: 'geotiff' }, { id: 'preview', color: 'image' }, { id: 'meta', color: 'dict' }];

  const inputs = schema?.inputs || [];

  return (
    <BaseNode title="Earth Engine Source" icon={IconCmp} selected={selected} data={data} color="green" inputs={inputs} outputs={outputs}>
      {thumb ? (
        <img src={`data:image/jpeg;base64,${thumb}`} alt="Preview" className="w-full h-32 object-cover rounded-lg border border-[#4f5b6b]" />
      ) : (
        <div className="flex flex-col items-center justify-center border-2 border-dashed border-[#4f5b6b] rounded-lg p-4 opacity-40 h-32">
          <div className="text-[7px] text-gray-500 uppercase font-black text-center">Configure params<br/>then toggle Fetch</div>
        </div>
      )}
    </BaseNode>
  );
});


export const GeoBandInfoNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  const schema = data.schema;
  const IconCmp = getIcon('List', Box);
  const inputs  = schema?.inputs  || [{ id: 'geotiff', color: 'geotiff' }];
  const outputs = schema?.outputs || [{ id: 'geotiff', color: 'geotiff' }];

  const bandNames: string[] = nd?.band_names || [];
  const count:  number = nd?.count  || 0;
  const width:  number = nd?.width  || 0;
  const height: number = nd?.height || 0;
  const crs:    string = nd?.crs    || '—';
  const dtype:  string = nd?.dtype  || '—';

  return (
    <BaseNode title="Band Info" icon={IconCmp} selected={selected} data={data} color="accent" inputs={inputs} outputs={outputs}>
      <div className="px-2 pb-2 pt-1 space-y-1 min-w-[160px]">
        {count === 0 ? (
          <div className="text-[9px] text-gray-500 italic text-center py-3">Connecte un GeoTIFF</div>
        ) : (
          <>
            <div className="flex justify-between text-[9px] text-gray-400 border-b border-white/10 pb-1 mb-1">
              <span>{width}×{height}</span>
              <span className="font-mono text-[8px] text-gray-500">{dtype}</span>
            </div>
            <div className="text-[8px] text-gray-500 truncate" title={crs}>{crs}</div>
            <div className="mt-1 space-y-0.5">
              {bandNames.map((name, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <span className="text-[8px] font-mono text-emerald-400 w-4 text-right shrink-0">{i + 1}</span>
                  <span className="text-[9px] font-bold text-white/80">{name}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </BaseNode>
  );
});


export const GeoLandCoverNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const schema = data.schema;
  const IconCmp = getIcon('Layers', Box);

  return (
    <BaseNode title="Geo Land Cover" icon={IconCmp} selected={selected} data={data} color="green" inputs={schema?.inputs} outputs={schema?.outputs}>
      {nd?.meta && (
        <div className="mt-2 px-2 py-1 bg-black/20 rounded border border-white/5 text-[8px] font-mono text-gray-400 truncate">
          {nd.meta}
        </div>
      )}
    </BaseNode>
  );
});


export const GeoSedimentLoaderNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  const preview = nd?.preview;
  const schema = data.schema;
  const IconCmp = getIcon(schema?.icon, Layers);

  const handleBrowse = async () => {
    try {
      const selectedFile = await open({
        multiple: false,
        filters: [{
          name: 'CSV Data',
          extensions: ['csv', 'txt']
        }]
      });
      if (selectedFile && typeof selectedFile === 'string') {
        data.onChangeParams?.({ path: selectedFile });
      }
    } catch (err) {
      console.error('Failed to open dialog:', err);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) {
      data.onChangeParams?.({ path: (file as any).path || file.name });
    }
  };

  return (
    <BaseNode title="Sediment Layers" icon={IconCmp} selected={selected} data={data} color="green" inputs={[]} outputs={schema?.outputs}>
      <div 
        className="relative group mb-1" 
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
      >
        {preview ? (
          <img 
            src={`data:image/jpeg;base64,${preview}`} 
            alt="Heatmap Preview" 
            className="w-full h-32 object-contain rounded-lg border border-[#4f5b6b] bg-black/20" 
          />
        ) : (
          <div className="flex flex-col items-center justify-center border-2 border-dashed border-[#4f5b6b] rounded-lg p-4 opacity-40 h-32">
            <Search size={20} className="text-gray-500 mb-2" />
            <div className="text-[7px] text-gray-500 uppercase font-black text-center italic">Drop CSV or Click Browse</div>
          </div>
        )}
        
        <div className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer rounded-lg border-2 border-dashed border-green-500/50"
             onClick={handleBrowse}>
          <Search size={20} className="text-white mb-1" />
          <div className="text-[7px] text-white uppercase font-black">Change CSV</div>
        </div>
      </div>
      {data.params?.path && (
        <div className="px-1 text-[7px] text-gray-500 truncate italic">
          {data.params.path.split(/[/\\]/).pop()}
        </div>
      )}
    </BaseNode>
  );
});


export const GeoIndexNode = memo(({ selected, data }: any) => {
  const schema = data.schema;
  const IconCmp = getIcon(schema?.icon, Divide);

  return (
    <BaseNode title="Geophysics Index" icon={IconCmp} selected={selected} data={data} color="red" 
              inputs={schema?.inputs} outputs={schema?.outputs}>
    </BaseNode>
  );
});



export const RasterColorizerNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];

  useEffect(() => { updateNodeInternals(nodeId); }, [ports.length, nodeId, updateNodeInternals]);

  const inputs = [
    { id: 'a', color: 'any', label: 'A' },
    ...ports.map((p: any) => {
      const idx = p.id.indexOf('__');
      const shortId = idx >= 0 ? p.id.slice(idx + 2) : p.id;
      return { id: shortId, color: p.color, label: p.label };
    }),
    { id: 'DYNAMIC_NEW_HANDLE', color: 'any' },
  ];

  return (
    <BaseNode
      title={data.label || 'Raster Colorizer'}
      icon={Palette}
      selected={selected}
      data={data}
      color="accent"
      inputs={inputs}
      outputs={[{ id: 'main', color: 'image', label: 'Colorized image' }]}
    />
  );
});


export const GeoBboxNode = memo(({ selected, data }: any) => {
  const onOpenEditor = data.onOpenEditor;
  const p = data.params ?? {};
  const lon_min = parseFloat(p.lon_min), lat_min = parseFloat(p.lat_min);
  const lon_max = parseFloat(p.lon_max), lat_max = parseFloat(p.lat_max);
  const hasBbox = [lon_min, lat_min, lon_max, lat_max].every(isFinite);
  const SquareIcon = (LucideIcons as any).Square;
  const MapIcon    = (LucideIcons as any).Map;

  return (
    <BaseNode title="Bounding Box" icon={SquareIcon} selected={selected} data={data} color="green"
      inputs={[]}
      outputs={[{ id: 'bbox', color: 'string', label: 'BBox (str)' }]}
    >
      <div className="flex flex-col gap-2 nodrag">
        <div className="relative bg-black/30 rounded-xl overflow-hidden border border-white/5 group/bbox">
          {hasBbox ? (
            <div className="px-3 py-3 font-mono text-[8px] leading-relaxed text-gray-400 space-y-0.5">
              <div className="flex justify-between"><span className="text-gray-600">W</span><span>{lon_min.toFixed(5)}°</span></div>
              <div className="flex justify-between"><span className="text-gray-600">E</span><span>{lon_max.toFixed(5)}°</span></div>
              <div className="flex justify-between"><span className="text-gray-600">S</span><span>{lat_min.toFixed(5)}°</span></div>
              <div className="flex justify-between"><span className="text-gray-600">N</span><span>{lat_max.toFixed(5)}°</span></div>
            </div>
          ) : (
            <div className="w-full py-6 flex items-center justify-center text-gray-700">
              <SquareIcon size={20} className="opacity-10" />
            </div>
          )}
          <div className="absolute inset-0 bg-black/10 opacity-0 group-hover/bbox:opacity-100 transition-all duration-300 flex items-center justify-center backdrop-blur-[2px]">
            <button onClick={e => { e.stopPropagation(); onOpenEditor?.(); }}
              className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded-xl shadow-2xl transition-all font-black text-[10px] uppercase tracking-widest flex items-center gap-2">
              <MapIcon size={11} /> Edit on Map
            </button>
          </div>
        </div>
      </div>
    </BaseNode>
  );
});

// ── Geo Interactive Sampler Node ─────────────────────────────────────────────


const GEO_SAMPLER_TYPE_COLORS: Record<number, string> = { 0: '#22dc50', 1: '#ff4444', 2: '#00d4ff' };

const GEO_SAMPLER_TYPE_LABELS: Record<number, string> = { 0: 'A', 1: 'B', 2: 'C' };


export const GeoInteractiveSamplerNode = memo(({ selected, data }: any) => {
  const nd          = useNodeData(useNodeId());
  const frame       = nd?.preview;
  const bandNames: string[] = nd?.band_names ?? [];
  const onOpenEditor = data.onOpenEditor;
  const imgRef      = React.useRef<HTMLImageElement>(null);

  const points: { x: number; y: number; type: number }[] = React.useMemo(() => {
    try { const p = JSON.parse(data.params?.points || '[]'); return Array.isArray(p) ? p : []; }
    catch { return []; }
  }, [data.params?.points]);

  const selectedIndices: string[] = React.useMemo(() => {
    try { const i = JSON.parse(data.params?.indices || '[]'); return Array.isArray(i) ? i : []; }
    catch { return []; }
  }, [data.params?.indices]);

  const counts = React.useMemo(() => ({
    0: points.filter(p => p.type === 0).length,
    1: points.filter(p => p.type === 1).length,
    2: points.filter(p => p.type === 2).length,
  }), [points]);

  return (
    <BaseNode title="Geo Interactive Sampler" icon={Crosshair} selected={selected} data={data} color="emerald"
      inputs={[{ id: 'geotiff', color: 'geotiff', label: 'Feature stack' }, { id: 'image', color: 'image', label: 'Preview (opt)' }]}
      outputs={[{ id: 'table', color: 'data', label: 'Samples table' }, { id: 'preview', color: 'image', label: 'Annotated' }]}
    >
      <div className="flex flex-col gap-2 nodrag">
        <div className="relative bg-black rounded-xl overflow-hidden border border-white/5 group/gs shadow-inner">
          {frame ? (
            <img ref={imgRef} src={`data:image/jpeg;base64,${frame}`} className="w-full h-auto block opacity-80" alt="Sampler Preview" />
          ) : (
            <div className="w-full aspect-video flex items-center justify-center text-gray-800">
              <Crosshair size={24} className="opacity-10" />
            </div>
          )}
          {/* SVG point overlay */}
          <svg
            className="absolute inset-0 w-full h-full pointer-events-none"
            viewBox={imgRef.current?.naturalWidth ? `0 0 ${imgRef.current.naturalWidth} ${imgRef.current.naturalHeight}` : '0 0 1 1'}
            preserveAspectRatio="xMidYMid meet"
          >
            {points.map((p, i) => {
              const nw = imgRef.current?.naturalWidth || 1;
              const nh = imgRef.current?.naturalHeight || 1;
              const r  = Math.min(nw, nh) * 0.025;
              const cx = p.x * nw;
              const cy = p.y * nh;
              return (
                <g key={i}>
                  <circle cx={cx} cy={cy} r={r} fill={GEO_SAMPLER_TYPE_COLORS[p.type] ?? '#fff'} opacity={0.9} />
                  <circle cx={cx} cy={cy} r={r + Math.min(nw, nh) * 0.005} fill="none" stroke="white" strokeWidth={Math.max(1, Math.min(nw, nh) * 0.003)} opacity={0.8} />
                  <text x={cx} y={cy} dy={-(r + Math.min(nw, nh) * 0.015)} textAnchor="middle" fill="white" fontSize={Math.max(10, Math.min(nw, nh) * 0.022)} fontWeight="bold" opacity={0.9}>
                    {GEO_SAMPLER_TYPE_LABELS[p.type] ?? '?'}{i + 1}
                  </text>
                </g>
              );
            })}
          </svg>
          <div className="absolute inset-0 bg-black/10 opacity-0 group-hover/gs:opacity-100 transition-all duration-300 flex items-center justify-center backdrop-blur-[2px]">
            <button onClick={e => { e.stopPropagation(); onOpenEditor?.(); }}
              className="bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2.5 rounded-xl shadow-2xl transition-all font-black text-[10px] uppercase tracking-widest scale-90 active:scale-95 flex items-center gap-2">
              <Crosshair size={12} /> Edit Points
            </button>
          </div>
        </div>

        {/* Type counts */}
        <div className="grid grid-cols-3 gap-1">
          {([0, 1, 2] as const).map(t => (
            <div key={t} className="flex items-center justify-between px-2 py-1 bg-black/20 rounded-lg border border-white/5">
              <span className="text-[8px] font-black uppercase" style={{ color: GEO_SAMPLER_TYPE_COLORS[t] }}>
                {GEO_SAMPLER_TYPE_LABELS[t]}
              </span>
              <span className="text-[8px] font-mono text-gray-400">{counts[t]}</span>
            </div>
          ))}
        </div>

        {/* Selected indices */}
        {selectedIndices.length > 0 && (
          <div className="flex flex-wrap gap-1 px-1">
            {selectedIndices.map(idx => (
              <span key={idx} className="px-2 py-0.5 bg-emerald-500/15 border border-emerald-500/25 rounded text-[8px] font-black text-emerald-400 uppercase">
                {idx}
              </span>
            ))}
          </div>
        )}

        {bandNames.length === 0 && (
          <p className="text-[8px] text-gray-600 text-center font-mono px-2">Connect geo_spectral_indices</p>
        )}
      </div>
    </BaseNode>
  );
});

// ── Index Painter Node ────────────────────────────────────────────────────────
// ── Copernicus CDSE Node ──────────────────────────────────────────────────────


const COPERNICUS_COLLECTIONS = [
  'Sentinel-2 L2A', 'Sentinel-2 L1C', 'Sentinel-1 GRD',
  'Copernicus DEM GLO-30', 'Copernicus DEM GLO-90',
  'Sentinel-1 RTC (Planetary)', 'ESA WorldCover (10m)', 'io-lulc Annual',
  'Sentinel-2 L2A (Planetary)', 'Copernicus DEM GLO-30 (Planetary)', 'JRC Global Surface Water',
  'Google Satellite', 'Google Hybrid', 'Google Roadmap', 'Google Terrain',
  'OpenStreetMap', 'Carto Positron', 'Carto Dark Matter',
] as const;


export const CopernicusNode = memo(({ selected, data }: any) => {
  const nd           = useNodeData(useNodeId());
  const thumbRef     = React.useRef<string | undefined>(undefined);
  if (nd?._thumb) thumbRef.current = nd._thumb;
  const thumb        = thumbRef.current;
  const onOpenEditor = data.onOpenEditor;
  const cachePath    = nd?.meta?.cache_path as string | undefined;

  const bbox    = data.params?.bbox ?? '';
  const colIdx  = parseInt(data.params?.collection ?? '0', 10);
  const colName = COPERNICUS_COLLECTIONS[colIdx] ?? 'Sentinel-2 L2A';
  const bands   = (data.params?.bands ?? 'B04,B03,B02,B08').split(',').filter(Boolean);

  const bboxParts = bbox ? bbox.split(',').map(Number) : null;
  const hasBbox   = bboxParts && bboxParts.length === 4 && bboxParts.every(isFinite);

  const inputs = data.schema?.inputs || [];

  return (
    <BaseNode title="Copernicus CDSE" icon={(LucideIcons as any).Satellite} selected={selected} data={data} color="blue"
      inputs={inputs}
      outputs={[
        { id: 'geotiff', color: 'geotiff', label: 'GeoTIFF' },
        { id: 'preview', color: 'image',   label: 'Preview' },
        { id: 'meta',    color: 'dict',    label: 'Meta' },
      ]}
    >
      <div className="flex flex-col gap-2 nodrag">
        {/* Map preview / thumbnail */}
        <div className="relative bg-black rounded-xl overflow-hidden border border-white/5 group/cop shadow-inner">
          {thumb ? (
            <img src={`data:image/jpeg;base64,${thumb}`} className="w-full h-auto block" draggable={false} alt="Satellite preview" />
          ) : (
            <div className="w-full aspect-video flex flex-col items-center justify-center text-gray-700 gap-2">
              <LucideIcons.Satellite size={24} className="opacity-10" />
              <span className="text-[8px] font-mono opacity-30">No data</span>
            </div>
          )}
          {/* Hover overlay — open editor */}
          <div className="absolute inset-0 bg-black/20 opacity-0 group-hover/cop:opacity-100 transition-all flex items-center justify-center backdrop-blur-[2px]">
            <button
              onClick={e => { e.stopPropagation(); onOpenEditor?.(); }}
              className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-xl shadow-2xl transition-all font-black text-[10px] uppercase tracking-widest flex items-center gap-2"
            >
              <LucideIcons.Map size={11} /> Open Editor
            </button>
          </div>
        </div>

        {/* Info row */}
        <div className="grid grid-cols-1 gap-1 px-0.5">
          <div className="flex items-center justify-between px-2 py-1 bg-black/20 rounded-lg border border-white/5">
            <span className="text-[8px] font-black uppercase tracking-widest text-gray-600">Collection</span>
            <span className="text-[8px] font-mono text-blue-400 truncate max-w-[140px]">{colName}</span>
          </div>
          <div className="flex items-center justify-between px-2 py-1 bg-black/20 rounded-lg border border-white/5">
            <span className="text-[8px] font-black uppercase tracking-widest text-gray-600">Bands</span>
            <span className="text-[8px] font-mono text-gray-400 truncate max-w-[140px]">{bands.join(', ')}</span>
          </div>
          {hasBbox && (
            <div className="px-2 py-1 bg-green-500/5 rounded-lg border border-green-500/15">
              <div className="text-[7px] font-mono text-green-400 leading-4">
                W {bboxParts![0].toFixed(3)}° · E {bboxParts![2].toFixed(3)}°
              </div>
              <div className="text-[7px] font-mono text-green-400 leading-4">
                S {bboxParts![1].toFixed(3)}° · N {bboxParts![3].toFixed(3)}°
              </div>
            </div>
          )}
          {cachePath && (
            <button
              onClick={e => { e.stopPropagation(); openPath(cachePath.substring(0, cachePath.lastIndexOf('/'))); }}
              className="w-full flex items-center justify-center gap-1.5 px-2 py-1 bg-blue-500/5 hover:bg-blue-500/15 border border-blue-500/15 hover:border-blue-500/30 rounded-lg transition-all"
              title="Open cache folder in Finder"
            >
              <LucideIcons.FolderOpen size={9} className="text-blue-400" />
              <span className="text-[7px] font-black uppercase tracking-widest text-blue-400">Open Folder</span>
            </button>
          )}
        </div>
      </div>
    </BaseNode>
  );
});


export const IndexPainterNode = memo(({ selected, data }: any) => {
  const nd           = useNodeData(useNodeId());
  const preview      = nd?.main_preview;
  const onOpenEditor = data.onOpenEditor;

  const classes: { label: string; value: number; color: string }[] = React.useMemo(() => {
    try { return JSON.parse(data.params?.classes || '[]'); } catch { return []; }
  }, [data.params?.classes]);

  const strokeCount: number = React.useMemo(() => {
    try { return JSON.parse(data.params?.strokes || '[]').length; } catch { return 0; }
  }, [data.params?.strokes]);

  return (
    <BaseNode title="Index Painter" icon={Palette} selected={selected} data={data} color="cyan"
      inputs={[]}
      outputs={[
        { id: 'index',  color: 'image',  label: 'Index' },
        { id: 'labels', color: 'image',  label: 'Labels' },
      ]}
    >
      <div className="flex flex-col gap-2 nodrag">
        {/* Preview */}
        <div className="relative bg-black rounded-xl overflow-hidden border border-white/5 group/ip shadow-inner">
          {preview ? (
            <img src={`data:image/jpeg;base64,${preview}`}
              className="w-full h-auto block" draggable={false} alt="Index map" />
          ) : (
            <div className="w-full aspect-square flex items-center justify-center text-gray-800">
              <Palette size={24} className="opacity-10" />
            </div>
          )}
          <div className="absolute inset-0 bg-black/20 opacity-0 group-hover/ip:opacity-100 transition-all flex items-center justify-center backdrop-blur-[2px]">
            <button onClick={e => { e.stopPropagation(); onOpenEditor?.(); }}
              className="bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-xl shadow-2xl transition-all font-black text-[10px] uppercase tracking-widest flex items-center gap-2">
              <Palette size={11} /> Paint
            </button>
          </div>
        </div>

        {/* Class swatches */}
        {classes.length > 0 && (
          <div className="flex items-center gap-1 px-1 flex-wrap">
            {classes.map((cls, i) => (
              <div key={i} title={`${cls.label}: ${cls.value >= 0 ? '+' : ''}${cls.value.toFixed(2)}`}
                className="flex items-center gap-1 bg-white/5 rounded-full px-1.5 py-0.5">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: cls.color }} />
                <span className="text-[7px] font-mono text-gray-400 tabular-nums">
                  {cls.value >= 0 ? '+' : ''}{cls.value.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between px-1">
          <div className="text-[8px] font-black text-gray-600 uppercase tracking-widest">
            {strokeCount} stroke{strokeCount !== 1 ? 's' : ''}
          </div>
          <button onClick={e => { e.stopPropagation(); onOpenEditor?.(); }}
            className="text-[8px] font-black text-cyan-400 uppercase tracking-widest hover:underline">
            Paint
          </button>
        </div>
      </div>
    </BaseNode>
  );
});

// ── Teleport Node ─────────────────────────────────────────────────────────────
// Ghost clone of a source node. Mirrors outputs without re-computing.
// Semi-transparent, dashed border, no input handles.
