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

export const ScientificPlotterNode = memo(({ selected, data }: any) => {
  const { customBg } = useNodeColor();
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  const palIdx = data?.activePaletteIndex ?? 6;
  const SERIES_COLORS = PALETTES[palIdx].colors.map((c: any) => c.bg);
  const nd = useNodeData(nodeId);
  const bufSize = Number(data.params?.buffer_size ?? 100);
  const frozen = !!data.params?.freeze;
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];

  // Force ReactFlow to recalculate handle positions when ports change
  useEffect(() => { updateNodeInternals(nodeId); }, [ports.length, nodeId, updateNodeInternals]);

  // Extract Python key (last segment after __) from each port id
  const portKeys = React.useMemo(() =>
    ports.map(p => p.id.split('__').pop() ?? p.id),
    [ports]
  );

  // Chart series keys: union of declared ports AND any live numeric/array data the engine
  // emits for this node. Decoupling the chart from data.ports keeps it working for legacy
  // scenes (saved before dynamic ports) and any time ports drift out of sync with the data.
  const seriesKeys = React.useMemo(() => {
    const keys = new Set<string>(portKeys);
    for (const k of Object.keys(nd || {})) {
      const v = (nd as any)[k];
      if (typeof v === 'number' || Array.isArray(v)) keys.add(k);
    }
    return Array.from(keys);
  }, [nd, portKeys]);

  const [histories, setHistories] = React.useState<Record<string, number[]>>({});

  React.useEffect(() => {
    if (frozen) return;
    setHistories(prev => {
      const next: Record<string, number[]> = {};
      let changed = false;
      for (const k of seriesKeys) {
        const v = (nd as any)[k];
        const cur = prev[k] ?? [];
        if (v === undefined || v === null) { next[k] = cur; continue; }
        if (typeof v === 'number') {
          if (cur.length === 0 || cur[cur.length - 1] !== v) {
            next[k] = [...cur, v].slice(-bufSize);
            changed = true;
          } else { next[k] = cur; }
        } else if (Array.isArray(v)) {
          next[k] = (v as any[]).map(Number).filter((n: number) => !isNaN(n)).slice(-bufSize);
          changed = true;
        } else { next[k] = cur; }
      }
      const prevKeys = Object.keys(prev);
      return (changed || prevKeys.length !== seriesKeys.length || prevKeys.some(k => !seriesKeys.includes(k))) ? next : prev;
    });
  }, [nd, bufSize, frozen, seriesKeys]);

  const chartData = React.useMemo(() => {
    const maxLen = Math.max(0, ...seriesKeys.map(k => histories[k]?.length ?? 0));
    if (maxLen === 0) return [];
    return Array.from({ length: maxLen }, (_, i) => {
      const pt: any = { t: i };
      for (const k of seriesKeys) {
        const arr = histories[k];
        if (arr && i < arr.length) pt[k] = arr[i];
      }
      return pt;
    });
  }, [histories, seriesKeys]);

  const activeSeries = seriesKeys.filter(k => (histories[k]?.length ?? 0) > 0);
  const minY = data.params?.min_y;
  const maxY = data.params?.max_y;
  const yDomain: [any, any] = (minY !== undefined && maxY !== undefined && minY !== maxY) ? [minY, maxY] : ['auto', 'auto'];

  // Pixel-based handle positions — avoids ReactFlow percentage-height measurement issue
  const HANDLE_TOP_START = 45;
  const HANDLE_SPACING = 32;
  const getHandleTop = (i: number) => `${HANDLE_TOP_START + i * HANDLE_SPACING}px`;

  // Dynamic height based on ports count (same pattern as BaseNode)
  const totalHandles = ports.length + 1; // +1 for factory
  const portsHeight = HANDLE_TOP_START + (totalHandles - 1) * HANDLE_SPACING + 35;

  return (
    <div className="relative w-full h-full" style={{ minHeight: Math.max(portsHeight, 150) }}>
    <div
      className={`rounded-xl bg-[#3d4452] border-2 shadow-2xl flex flex-col transition-all duration-300 relative w-full h-full ${customBg ? '' : (selected ? 'border-accent shadow-accent/20 shadow-lg' : 'border-[#4f5b6b]')}`}
      style={customBg ? { borderColor: customBg, boxShadow: selected ? `0 10px 15px -3px ${customBg}40` : `0 0 10px ${customBg}10` } : {}}
    >
      {/* Dynamic input ports — pixel positions, same strategy as BaseNode */}
      {ports.map((p, i) => {
        const idx = p.id.indexOf('__');
        const shortId = idx >= 0 ? p.id.slice(idx + 2) : p.id;
        const color = idx >= 0 ? p.id.slice(0, idx) : 'scalar';
        return (
          <div key={`in-${p.id}`} className="absolute left-0 pointer-events-none flex items-center z-10"
               style={{ top: getHandleTop(i), transform: 'translateY(-50%)' }}>
            <StyledHandle type="target" position={Position.Left} id={shortId} color={color} top="50%" />
            <button
              className="nodrag pointer-events-auto ml-4 text-[8px] text-gray-600 hover:text-red-400 transition-colors leading-none"
              onClick={e => { e.stopPropagation(); data.onRemovePort?.(p.id); }}
              title="Remove"
            >×</button>
          </div>
        );
      })}
      {/* "new" slot — always last */}
      <div className="absolute left-0 pointer-events-none flex items-center z-10"
           style={{ top: getHandleTop(ports.length), transform: 'translateY(-50%)' }}>
        <StyledHandle type="target" position={Position.Left} id="DYNAMIC_NEW_HANDLE" color="any" top="50%" />
      </div>

      {/* Main output */}
      <div className="absolute right-0 flex items-center justify-end pointer-events-none z-10"
           style={{ top: '22px', transform: 'translateY(-50%)' }}>
        <span className="mr-[12px] text-[7px] font-black text-white/40 uppercase tracking-widest">main</span>
        <StyledHandle type="source" position={Position.Right} id="main" color="image" top="50%" />
      </div>

      {/* Header */}
      <div className="bg-[#3d4452] px-3 py-1.5 flex items-center gap-2 border-b border-[#4f5b6b] rounded-t-xl shrink-0"
           style={customBg ? { backgroundColor: `${customBg}20`, borderBottomColor: `${customBg}40` } : {}}>
        <Activity size={12} className="shrink-0" style={customBg ? { color: customBg } : { color: '#22d3ee' }} />
        <span className="text-[10px] font-bold uppercase tracking-widest" style={customBg ? { color: customBg } : { color: '#ffffff' }}>Plotter</span>
        <div className="ml-auto flex items-center gap-2">
          {activeSeries.map(k => (
            <div key={k} className="w-1.5 h-1.5 rounded-full opacity-80"
                 style={{ backgroundColor: SERIES_COLORS[seriesKeys.indexOf(k) % SERIES_COLORS.length] }} />
          ))}
          <button
            className="nodrag pointer-events-auto ml-1 transition-opacity hover:opacity-100"
            style={{ opacity: frozen ? 1 : 0.4 }}
            onClick={e => { e.stopPropagation(); data.onChangeParams?.({ freeze: !frozen }); }}
          >
            {frozen
              ? <Lock size={10} className="text-yellow-400" />
              : <LockOpen size={10} className="text-gray-400" />}
          </button>
        </div>
      </div>

      {/* Chart */}
      <div className="flex-1 min-h-0 w-full px-1 py-1 overflow-hidden">
        {chartData.length === 0
          ? <div className="w-full h-full flex items-center justify-center">
              <span className="text-[8px] text-gray-700 uppercase tracking-widest">connect data</span>
            </div>
          : <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 2, right: 18, bottom: 0, left: 0 }}>
                <YAxis hide domain={yDomain} />
                {activeSeries.map(k => (
                  <Line key={k} type="monotone" dataKey={k}
                    stroke={SERIES_COLORS[seriesKeys.indexOf(k) % SERIES_COLORS.length]} strokeWidth={1.5}
                    dot={false} isAnimationActive={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
        }
      </div>
    </div>
    </div>
  );
});

// Generic DataFrame chart node: renders the engine-produced matplotlib image
// (base64 `preview`) directly in a resizable node body, plus image + dict outputs.

export const DataFramePlotNode = memo(({ selected, data }: any) => {
  const { customBg } = useNodeColor();
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  const nd = useNodeData(nodeId) as any;
  const preview: string | null = nd?.preview_b64 || (typeof nd?.preview === 'string' ? nd.preview : null);

  const CHART_TYPES = ['Line', 'Bar', 'Scatter', 'Histogram', 'Box', 'Area', 'Pie'];
  const ctIdx = Number(data.params?.chart_type ?? 0);
  const chartLabel = CHART_TYPES[ctIdx] ?? 'Chart';

  // Static ports: 2 inputs (table, img_size), 2 outputs (main, df_meta). Pixel tops.
  const HANDLE_TOP_START = 45;
  const HANDLE_SPACING = 32;
  const inTop = (i: number) => `${HANDLE_TOP_START + i * HANDLE_SPACING}px`;

  useEffect(() => { updateNodeInternals(nodeId); }, [nodeId, updateNodeInternals]);

  return (
    <div className="relative w-full h-full" style={{ minHeight: 150 }}>
      <div
        className={`rounded-xl bg-[#2c333f] border-2 shadow-2xl flex flex-col w-full h-full transition-all duration-300 relative ${customBg ? '' : (selected ? 'border-accent shadow-accent/20 shadow-lg' : 'border-[#4f5b6b]')}`}
        style={customBg ? { borderColor: customBg, boxShadow: selected ? `0 10px 15px -3px ${customBg}40` : `0 0 10px ${customBg}10` } : {}}
      >
        {/* Inputs */}
        {[
          { id: 'table', color: 'data', label: 'DataFrame' },
          { id: 'x', color: 'list', label: 'X values' },
          { id: 'y', color: 'list', label: 'Y values' },
          { id: 'img_size', color: 'list', label: 'Img Size' },
        ].map((inp, i) => (
          <div key={inp.id} className="absolute left-0 w-full flex items-center pointer-events-none z-10"
               style={{ top: inTop(i), transform: 'translateY(-50%)' }}>
            <StyledHandle type="target" position={Position.Left} id={inp.id} color={inp.color} top="50%" />
            <span className="ml-[12px] text-[7px] font-medium text-gray-500 uppercase tracking-tighter opacity-80 truncate">{inp.label}</span>
          </div>
        ))}

        {/* Outputs */}
        <div className="absolute right-0 flex items-center justify-end pointer-events-none z-10" style={{ top: '22px', transform: 'translateY(-50%)' }}>
          <span className="mr-[12px] text-[7px] font-black text-white/40 uppercase tracking-widest">main</span>
          <StyledHandle type="source" position={Position.Right} id="main" color="image" top="50%" />
        </div>
        <div className="absolute right-0 flex items-center justify-end pointer-events-none z-10" style={{ top: '54px', transform: 'translateY(-50%)' }}>
          <span className="mr-[12px] text-[7px] font-black text-white/40 uppercase tracking-widest">cols</span>
          <StyledHandle type="source" position={Position.Right} id="df_meta" color="dict" top="50%" />
        </div>

        {/* Header */}
        <div className="bg-[#3d4452] px-3 py-1.5 flex items-center gap-2 border-b border-[#4f5b6b] rounded-t-xl shrink-0"
             style={customBg ? { backgroundColor: `${customBg}20`, borderBottomColor: `${customBg}40` } : {}}>
          <BarChart2 size={12} className="shrink-0" style={customBg ? { color: customBg } : { color: '#22d3ee' }} />
          <span className="text-[10px] font-bold uppercase tracking-widest truncate" style={customBg ? { color: customBg } : { color: '#ffffff' }}>
            {data.label || 'DF Plot'}
          </span>
          <span className="ml-auto text-[8px] font-mono text-accent/70 uppercase tracking-widest shrink-0">{chartLabel}</span>
        </div>

        {/* Chart image fills the body */}
        <div className="flex-1 min-h-0 w-full p-1 overflow-hidden flex items-center justify-center">
          {preview
            ? <img src={`data:image/jpeg;base64,${preview}`} alt="Chart"
                   className="max-w-full max-h-full w-full h-full object-contain rounded-lg" draggable={false} />
            : <span className="text-[8px] text-gray-700 uppercase tracking-widest">connect dataframe</span>}
        </div>
      </div>
    </div>
  );
});


const PRO_COLORS = ['#ff6464', '#64ff64', '#ffb43c', '#64ffff', '#ff64ff', '#ffff64', '#c896ff', '#64c8ff'];
const PRO_MAX_SERIES = 5;


export const PlotterProNode = memo(({ selected, data }: any) => {
  const { customBg } = useNodeColor();
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  // Palette from the global top-menu selector (5 colours per palette).
  const palIdx = data?.activePaletteIndex ?? 6;
  const palette = PALETTES[palIdx].colors.map((c: any) => c.bg);
  const nd = useNodeData(nodeId);
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];

  const bufSize = Number(data.params?.buffer_size ?? 300);
  const showGrid = data.params?.show_grid !== false;
  const lineWidth = Number(data.params?.line_width ?? 2);
  const showAxes = !!data.params?.show_axes;
  const fillCurve = !!data.params?.fill_curve;
  const minY = data.params?.min_y;
  const maxY = data.params?.max_y;
  const autoScale = !!(data.params?.auto_scale ?? true);
  const yDomain: [any, any] = autoScale ? ['auto', 'auto'] : ((minY !== undefined && maxY !== undefined && minY !== maxY) ? [minY, maxY] : [0, 100]);

  useEffect(() => { updateNodeInternals(nodeId); }, [ports.length, nodeId, updateNodeInternals]);

  // Python key (last segment after __) for each declared port.
  const portKeys = React.useMemo(() =>
    ports.map(p => p.id.split('__').pop() ?? p.id),
    [ports]
  );

  // Series = union of declared ports AND any live numeric/array key the engine
  // emits for this node (mirrors ScientificPlotterNode — robust to port/data drift).
  // Capped at 5 series.
  const seriesKeys = React.useMemo(() => {
    const keys = new Set<string>(portKeys);
    for (const k of Object.keys(nd || {})) {
      const v = (nd as any)[k];
      if (typeof v === 'number' || Array.isArray(v)) keys.add(k);
    }
    return Array.from(keys).slice(0, PRO_MAX_SERIES);
  }, [nd, portKeys]);

  const [histories, setHistories] = React.useState<Record<string, number[]>>({});
  const prevReset = React.useRef(0);

  useEffect(() => {
    const r = data.params?.reset ?? 0;
    if (r === 1 && prevReset.current === 0) setHistories({});
    prevReset.current = r;
  }, [data.params?.reset]);

  useEffect(() => {
    setHistories(prev => {
      const next: Record<string, number[]> = {};
      let changed = false;
      for (const k of seriesKeys) {
        const v = (nd as any)[k];
        const cur = prev[k] ?? [];
        if (v === undefined || v === null) { next[k] = cur; continue; }
        if (typeof v === 'number') {
          if (cur.length === 0 || cur[cur.length - 1] !== v) {
            next[k] = [...cur, v].slice(-bufSize);
            changed = true;
          } else { next[k] = cur; }
        } else if (Array.isArray(v)) {
          next[k] = (v as any[]).map(Number).filter((n: number) => !isNaN(n)).slice(-bufSize);
          changed = true;
        } else { next[k] = cur; }
      }
      const prevKeys = Object.keys(prev);
      return (changed || prevKeys.length !== seriesKeys.length || prevKeys.some(k => !seriesKeys.includes(k))) ? next : prev;
    });
  }, [nd, bufSize, seriesKeys]);

  const chartData = React.useMemo(() => {
    const maxLen = Math.max(0, ...seriesKeys.map(k => histories[k]?.length ?? 0));
    if (maxLen === 0) return [];
    return Array.from({ length: maxLen }, (_, i) => {
      const pt: any = { t: i };
      for (const k of seriesKeys) { const arr = histories[k]; if (arr && i < arr.length) pt[k] = arr[i]; }
      return pt;
    });
  }, [histories, seriesKeys]);

  const activeSeries = seriesKeys.filter(k => (histories[k]?.length ?? 0) > 0);

  const HANDLE_TOP_START = 45;
  const HANDLE_SPACING = 32;
  const portsHeight = HANDLE_TOP_START + ports.length * HANDLE_SPACING + 35;

  return (
    <div className="relative w-full h-full" style={{ minHeight: Math.max(portsHeight, 180) }}>
      <div
        className={`rounded-xl bg-[#3d4452] border-2 shadow-2xl flex flex-col transition-all duration-300 relative w-full h-full ${customBg ? '' : (selected ? 'border-accent shadow-accent/20 shadow-lg' : 'border-[#4f5b6b]')}`}
        style={customBg ? { borderColor: customBg, boxShadow: selected ? `0 10px 15px -3px ${customBg}40` : `0 0 10px ${customBg}10` } : {}}
      >
        {/* Dynamic input ports */}
        {ports.map((p, i) => {
          const idx = p.id.indexOf('__');
          const shortId = idx >= 0 ? p.id.slice(idx + 2) : p.id;
          const color = idx >= 0 ? p.id.slice(0, idx) : 'any';
          return (
            <div key={`in-${p.id}`} className="absolute left-0 pointer-events-none flex items-center z-10"
                 style={{ top: `${HANDLE_TOP_START + i * HANDLE_SPACING}px`, transform: 'translateY(-50%)' }}>
              <StyledHandle type="target" position={Position.Left} id={shortId} color={color} top="50%" />
              <button
                className="nodrag pointer-events-auto ml-4 text-[8px] text-gray-600 hover:text-red-400 transition-colors leading-none"
                onClick={e => { e.stopPropagation(); data.onRemovePort?.(p.id); }}
                title="Remove"
              >×</button>
            </div>
          );
        })}
        {/* Factory handle */}
        <div className="absolute left-0 pointer-events-none flex items-center z-10"
             style={{ top: `${HANDLE_TOP_START + ports.length * HANDLE_SPACING}px`, transform: 'translateY(-50%)' }}>
          <StyledHandle type="target" position={Position.Left} id="DYNAMIC_NEW_HANDLE" color="any" top="50%" />
        </div>

        {/* Output: main image */}
        <div className="absolute right-0 flex items-center justify-end pointer-events-none z-10"
             style={{ top: '22px', transform: 'translateY(-50%)' }}>
          <span className="mr-[12px] text-[7px] font-black text-white/40 uppercase tracking-widest">main</span>
          <StyledHandle type="source" position={Position.Right} id="main" color="image" top="50%" />
        </div>
        {/* Output: DataFrame */}
        <div className="absolute right-0 flex items-center justify-end pointer-events-none z-10"
             style={{ top: '44px', transform: 'translateY(-50%)' }}>
          <span className="mr-[12px] text-[7px] font-black text-white/40 uppercase tracking-widest">table</span>
          <StyledHandle type="source" position={Position.Right} id="table" color="data" top="50%" />
        </div>

        {/* Header */}
        <div className="bg-[#3d4452] px-3 py-1.5 flex items-center gap-2 border-b border-[#4f5b6b] rounded-t-xl shrink-0"
             style={customBg ? { backgroundColor: `${customBg}20`, borderBottomColor: `${customBg}40` } : {}}>
          <Activity size={12} className="shrink-0" style={customBg ? { color: customBg } : { color: '#a78bfa' }} />
          <span className="text-[10px] font-bold uppercase tracking-widest" style={customBg ? { color: customBg } : { color: '#ffffff' }}>Plotter Pro</span>
          <div className="ml-auto flex items-center gap-1.5">
            {activeSeries.map(k => (
              <div key={k} className="w-1.5 h-1.5 rounded-full opacity-80"
                   style={{ backgroundColor: palette[seriesKeys.indexOf(k) % palette.length] }} />
            ))}
          </div>
        </div>

        {/* Chart */}
        <div className="flex-1 min-h-0 w-full px-1 py-1 overflow-hidden">
          {chartData.length === 0
            ? <div className="w-full h-full flex flex-col items-center justify-center gap-1">
                <span className="text-[8px] text-gray-600 uppercase tracking-widest">
                  {seriesKeys.length === 0 ? 'connect data' : `${seriesKeys.length} series — waiting`}
                </span>
              </div>
            : <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData}
                  margin={showAxes ? { top: 4, right: 35, bottom: 4, left: 4 } : { top: 2, right: 35, bottom: 0, left: 0 }}>
                  <defs>
                    {activeSeries.map(k => {
                      const ci = seriesKeys.indexOf(k);
                      const c = palette[ci % palette.length];
                      return (
                        <linearGradient key={`grad-${k}`} id={`proFill-${nodeId}-${ci}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={c} stopOpacity={0.35} />
                          <stop offset="100%" stopColor={c} stopOpacity={0.02} />
                        </linearGradient>
                      );
                    })}
                  </defs>
                  <YAxis hide={!showAxes} domain={yDomain}
                    tick={{ fill: '#94a3b8', fontSize: 7 }} width={showAxes ? 30 : 0} />
                  <XAxis dataKey="t" hide={!showAxes}
                    tick={{ fill: '#94a3b8', fontSize: 7 }} height={showAxes ? 14 : 0} />
                  {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#4a5568" vertical={false} />}
                  {fillCurve && activeSeries.map(k => (
                    <Area key={`a-${k}`} type="monotone" dataKey={k}
                      stroke="none" fill={`url(#proFill-${nodeId}-${seriesKeys.indexOf(k)})`}
                      isAnimationActive={false} connectNulls />
                  ))}
                  {activeSeries.map(k => (
                    <Line key={k} type="monotone" dataKey={k}
                      stroke={palette[seriesKeys.indexOf(k) % palette.length]} strokeWidth={lineWidth}
                      dot={false} isAnimationActive={false} connectNulls />
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
          }
        </div>
      </div>
    </div>
  );
});


export const ScientificCalibrationNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);

  return (
    <BaseNode 
        title="Unit Calibration" 
        icon={Scaling} 
        selected={selected} 
        data={data} 
        color="indigo" 
        inputs={[{id: 'input', color: 'any', label: 'Pixels'}]} 
        outputs={[{id: 'main', color: 'any', label: 'Physical'}]}
    >
      <div className="flex flex-col items-center justify-center py-4 px-2 bg-black/20 rounded-lg border border-white/5 mt-1">
        <span className="text-[8px] text-indigo-400 font-bold uppercase tracking-widest mb-1">Calibrated Value</span>
        <div className="text-xl font-mono text-white tabular-nums tracking-tighter">
            {nd?.display_value || "---"}
        </div>
      </div>
    </BaseNode>
  );
});


export const ScientificHistogramNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);

  const chartData = useMemo(() => {
    const h0 = nd?.hist_0 || [];
    const h1 = nd?.hist_1 || [];
    const h2 = nd?.hist_2 || [];
    const len = Math.max(h0.length, h1.length, h2.length);
    if (len === 0) return [];
    
    return Array.from({ length: len }, (_, i) => ({
      x: i,
      b: h0[i] || 0,
      g: h1[i] || 0,
      r: h2[i] || 0,
      v: h0[i] || 0
    }));
  }, [nd?.hist_0, nd?.hist_1, nd?.hist_2]);

  const isColor = nd?.is_color;
  const mode = nd?.mode;

  return (
    <BaseNode 
        title="Histogram" 
        icon={BarChart2} 
        selected={selected} 
        data={data} 
        color="blue" 
        inputs={[{id: 'image', color: 'any', label: 'Image'}]} 
        outputs={[{id: 'main', color: 'image', label: 'Main'}]}
        width="100%"
        height="100%"
        className="w-full h-full"
    >
      <div className="flex-1 min-h-0 w-full flex flex-col p-1">
          <div className="flex-1 min-h-0 w-full">
            {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                    <defs>
                        <linearGradient id="gradB" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="gradG" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#22c55e" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="gradR" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="gradV" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#94a3b8" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#94a3b8" stopOpacity={0}/>
                        </linearGradient>
                    </defs>
                    <Tooltip 
                        contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '10px' }}
                        itemStyle={{ padding: '0 2px' }}
                        labelStyle={{ display: 'none' }}
                    />
                    {mode === 0 && isColor ? (
                        <>
                        <Area type="monotone" dataKey="b" stroke="#3b82f6" fillOpacity={1} fill="url(#gradB)" isAnimationActive={false} />
                        <Area type="monotone" dataKey="g" stroke="#22c55e" fillOpacity={1} fill="url(#gradG)" isAnimationActive={false} />
                        <Area type="monotone" dataKey="r" stroke="#ef4444" fillOpacity={1} fill="url(#gradR)" isAnimationActive={false} />
                        </>
                    ) : (
                        <Area type="monotone" dataKey="v" stroke="#94a3b8" fillOpacity={1} fill="url(#gradV)" isAnimationActive={false} />
                    )}
                    </AreaChart>
                </ResponsiveContainer>
            ) : (
                <div className="w-full h-full flex flex-col items-center justify-center opacity-40 gap-2 min-h-[100px]">
                    <BarChart2 size={24} className="text-gray-500 animate-pulse" />
                    <span className="text-[7px] font-black uppercase tracking-widest text-gray-600">Waiting for Data...</span>
                </div>
            )}
          </div>

          {nd?.avg_0 !== undefined && (
            <div className="grid grid-cols-2 gap-1 border-t border-white/5 pt-2 mt-1 shrink-0 px-2 pb-1">
                <div className="flex flex-col">
                    <span className="text-[7px] text-gray-500 uppercase font-bold tracking-tighter">Average</span>
                    <span className="text-[10px] font-mono text-white/80 tabular-nums">{nd.avg_0.toFixed(1)}</span>
                </div>
                <div className="flex flex-col text-right">
                    <span className="text-[7px] text-gray-500 uppercase font-bold tracking-tighter">Std Dev</span>
                    <span className="text-[10px] font-mono text-white/80 tabular-nums">{nd.std_0.toFixed(1)}</span>
                </div>
            </div>
          )}
      </div>
    </BaseNode>
  );
});


export const ScientificStatsNode = memo(({ selected, data }: any) => {
  const stats = useNodeData(useNodeId());
  const entries = [
    { label: 'Mean', v: stats.mean, color: 'text-cyan-400' },
    { label: 'Median', v: stats.median, color: 'text-blue-400' },
    { label: 'Std Dev', v: stats.std, color: 'text-purple-400' },
    { label: 'Range', v: (stats.max - stats.min), color: 'text-emerald-400' }
  ];

  return (
    <BaseNode title="Statistics" icon={Info} selected={selected} data={data} color="accent" inputs={[{id: 'data_list', color: 'list'}]} outputs={[
      {id: 'mean', color: 'scalar'}, {id: 'median', color: 'scalar'}, {id: 'std', color: 'scalar'}, {id: 'min', color: 'scalar'}, {id: 'max', color: 'scalar'}
    ]}>
      <div className="grid grid-cols-2 gap-2 mt-2">
        {entries.map(e => (
          <div key={e.label} className="bg-black/10 p-2 rounded-lg border border-white/5">
             <div className="text-[7px] text-gray-500 uppercase font-black">{e.label}</div>
             <div className={`text-[9px] font-mono ${e.color} font-bold`}>{e.v?.toFixed(3) ?? '---'}</div>
          </div>
        ))}
      </div>
    </BaseNode>
  );
});


const ScientificReportNodeUI = ({ data, selected }: { data: any, selected: boolean }) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const stats = nd?.report || {};
  const title = data.params?.title || 'Analysis Report';
  
  const keys = Object.keys(stats);
  const formatVal = (v: any) => typeof v === 'number' ? (v % 1 === 0 ? v : v.toFixed(3)) : String(v || '—');
  
  const COLORS = [
    { text: 'text-cyan-400', bg: 'bg-cyan-500/10', border: 'border-cyan-500/20' },
    { text: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
    { text: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20' },
    { text: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20' },
    { text: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/20' },
  ];

  return (
    <BaseNode title={title} icon={Clipboard} selected={selected} data={data} color="accent" inputs={[{id: 'data', color: 'dict'}]} outputs={[{id: 'report', color: 'dict'}]} width="18rem">
       <div className="flex flex-col gap-2 mt-2 w-full">
          {keys.length === 0 ? (
            <div className="p-4 rounded-xl border border-white/5 bg-white/5 text-center">
               <span className="text-[10px] text-gray-500 uppercase tracking-widest">Awaiting Data...</span>
            </div>
          ) : (
            <div className="p-3 rounded-xl border border-white/5 bg-white/5 space-y-2">
               {keys.map((k, i) => {
                  const theme = COLORS[i % COLORS.length];
                  return (
                    <div key={k} className="flex justify-between items-center text-[10px] border-b border-white/5 pb-1.5 last:border-0 last:pb-0">
                       <span className="text-gray-400 font-medium tracking-tight">{k}</span>
                       <span className={`font-mono font-black ${theme.text} ${theme.bg} ${theme.border} px-2 py-0.5 rounded-md border shadow-sm`}>
                          {formatVal(stats[k])}
                       </span>
                    </div>
                  );
               })}
            </div>
          )}
       </div>
    </BaseNode>
  );
};


export const ScientificReportNode = memo(ScientificReportNodeUI);


export const RootAnatomyReportNodeUI = ({ data, selected }: { data: any, selected: boolean }) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const [expanded, setExpanded] = React.useState(false);
  
  const stats = nd?.report || {};
  const hasData = Object.keys(stats).length > 0 && !stats.id; // basic check to see if we have real keys

  const categories = [
    { label: 'Root & Stele', keys: ['RXSA', 'TSA', 'TSA:RXSA', 'TSA:TCA'], bg: 'bg-blue-500/5', color: 'text-blue-400' },
    { label: 'Vascular', keys: ['XVA', '#PX', 'PXA', 'SCWA'], bg: 'bg-emerald-500/5', color: 'text-emerald-400' },
    { label: 'Cortex', keys: ['TCA', 'AA', '#Lac', '%A'], bg: 'bg-purple-500/5', color: 'text-purple-400' },
  ];

  const extendedCategories = [
    { label: 'Morphometry', keys: ['RXSA', 'TSA', 'TCA', 'EA', 'ExA'], bg: 'bg-blue-500/5', color: 'text-blue-400' },
    { label: 'Vascular System', keys: ['XVA', 'XSCWA', 'PXA', '#PX', 'SCWA'], bg: 'bg-emerald-500/5', color: 'text-emerald-400' },
    { label: 'Cortex & Lacunae', keys: ['TCA', 'AA', '%A', '#Lac', 'CCA', '%CCA'], bg: 'bg-purple-500/5', color: 'text-purple-400' },
    { label: 'Phénotypage Ratios', keys: ['TSA:RXSA', 'TSA:TCA', 'quality_score', 'focus_score'], bg: 'bg-amber-500/5', color: 'text-amber-400' },
  ];

  const formatKey = (key: string) => key.toUpperCase();
  const formatVal = (v: any) => typeof v === 'number' ? (v > 100 ? Math.round(v) : v.toFixed(3)) : v || '—';

  return (
    <BaseNode title="Anatomy Report" icon={BarChart2} selected={selected} data={data} color="accent" inputs={[{id: 'data', color: 'root_data'}]} outputs={[{id: 'report', color: 'dict'}]} width={expanded ? "45rem" : "20rem"}>
       <div className="flex flex-col gap-3 mt-2 w-full">
          {!expanded ? (
            <div className="flex flex-col gap-2">
              {categories.map(cat => (
                 <div key={cat.label} className={`p-2 rounded-xl border border-white/5 ${cat.bg}`}>
                    <div className="text-[7px] text-gray-500 uppercase font-black mb-2 tracking-widest flex justify-between">
                       <span>{cat.label}</span>
                       <div className={`w-1 h-1 rounded-full ${cat.color.replace('text', 'bg')}`} />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                       {cat.keys.map(k => (
                          <div key={k} className="flex flex-col">
                             <span className="text-[8px] text-gray-400 truncate">{formatKey(k)}</span>
                             <span className={`text-[11px] font-bold ${cat.color}`}>{formatVal(stats[k])}</span>
                          </div>
                       ))}
                    </div>
                 </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4">
               {extendedCategories.map(cat => (
                 <div key={cat.label} className={`p-3 rounded-xl border border-white/5 ${cat.bg}`}>
                    <h5 className={`text-[9px] font-black uppercase tracking-wider ${cat.color} mb-3 border-b border-white/10 pb-1 flex justify-between items-center`}>
                        {cat.label}
                        <div className={`w-1.5 h-1.5 rounded-full ${cat.color.replace('text', 'bg')} opacity-50`} />
                    </h5>
                    <div className="space-y-1.5">
                       {cat.keys.map(k => (
                          <div key={k} className="flex justify-between items-center text-[10px]">
                             <span className="text-gray-400">{formatKey(k)}</span>
                             <span className={`font-mono font-bold ${cat.color} bg-black/20 px-1.5 py-0.5 rounded border border-white/5`}>{formatVal(stats[k])}</span>
                          </div>
                       ))}
                    </div>
                 </div>
               ))}
            </div>
          )}

          <button 
            onClick={() => setExpanded(!expanded)}
            className="w-full py-2 mt-1 rounded-xl bg-white/5 border border-white/10 text-[9px] font-black uppercase tracking-widest text-gray-400 hover:bg-[var(--accent)] hover:text-white hover:border-[var(--accent)] transition-all flex items-center justify-center gap-2"
          >
             {expanded ? 'Collapse View' : 'Precision Report'}
             <BarChart2 size={10} />
          </button>
       </div>
    </BaseNode>
  );
};


const PETRO_SECTION_COLORS: Record<string, { text: string; bg: string; dot: string }> = {
  'Modal Analysis':    { text: 'text-cyan-400',    bg: 'bg-cyan-500/5',    dot: 'bg-cyan-400'    },
  'Morphometry':       { text: 'text-emerald-400', bg: 'bg-emerald-500/5', dot: 'bg-emerald-400' },
  'Opaques':           { text: 'text-amber-400',   bg: 'bg-amber-500/5',   dot: 'bg-amber-400'   },
  'Neighbor Analysis': { text: 'text-purple-400',  bg: 'bg-purple-500/5',  dot: 'bg-purple-400'  },
  'Classification':    { text: 'text-rose-400',    bg: 'bg-rose-500/5',    dot: 'bg-rose-400'    },
};

const PETRO_FALLBACK_COLORS = [
  { text: 'text-cyan-400',    bg: 'bg-cyan-500/5',    dot: 'bg-cyan-400'    },
  { text: 'text-emerald-400', bg: 'bg-emerald-500/5', dot: 'bg-emerald-400' },
  { text: 'text-purple-400',  bg: 'bg-purple-500/5',  dot: 'bg-purple-400'  },
  { text: 'text-amber-400',   bg: 'bg-amber-500/5',   dot: 'bg-amber-400'   },
  { text: 'text-rose-400',    bg: 'bg-rose-500/5',    dot: 'bg-rose-400'    },
];


const PetrographicReportNodeUI = ({ data, selected }: { data: any; selected: boolean }) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const [expanded, setExpanded] = React.useState(false);

  const report = (nd as any)?.report || {};
  const sections = Object.entries(report).filter(([, v]) => v && typeof v === 'object' && !Array.isArray(v)) as [string, Record<string, any>][];
  const hasData = sections.length > 0;

  const fmt = (v: any): string => {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'number') return v > 1000 ? Math.round(v).toLocaleString() : v % 1 === 0 ? String(v) : v.toFixed(3);
    return String(v);
  };

  const colorFor = (name: string, idx: number) =>
    PETRO_SECTION_COLORS[name] ?? PETRO_FALLBACK_COLORS[idx % PETRO_FALLBACK_COLORS.length];

  const sampleName = data.params?.sample_name || '';
  const title = sampleName ? `Petro — ${sampleName}` : 'Petrography Report';

  return (
    <BaseNode title={title} icon={FileText} selected={selected} data={data} color="accent"
      inputs={[
        { id: 'modal_stats',   color: 'any',    label: 'Modal Stats' },
        { id: 'neighbor_data', color: 'any',    label: 'Neighbor Data' },
        { id: 'grain_count',   color: 'scalar', label: 'Grain Count' },
        { id: 'mean_dia_um',   color: 'scalar', label: 'Mean Diam.' },
        { id: 'circularity',   color: 'scalar', label: 'Circularity' },
        { id: 'grain_frac',    color: 'scalar', label: 'Grain Frac.' },
        { id: 'opaque_count',  color: 'scalar', label: 'Opaque Count' },
        { id: 'opaque_frac',   color: 'scalar', label: 'Opaque Frac.' },
        { id: 'aspect_ratio',  color: 'scalar', label: 'Aspect Ratio' },
      ]}
      outputs={[{ id: 'report', color: 'any', label: 'Report Dict' }]}
      width={expanded ? '44rem' : '20rem'}>
      <div className="flex flex-col gap-2 mt-2 w-full">
        {!hasData ? (
          <div className="p-4 rounded-xl border border-white/5 bg-white/5 text-center">
            <span className="text-[10px] text-gray-500 uppercase tracking-widest">Awaiting data...</span>
          </div>
        ) : !expanded ? (
          <div className="flex flex-col gap-2">
            {sections.map(([name, vals], i) => {
              const c = colorFor(name, i);
              const entries = Object.entries(vals).slice(0, 4);
              return (
                <div key={name} className={`p-2 rounded-xl border border-white/5 ${c.bg}`}>
                  <div className="text-[7px] uppercase font-black mb-1.5 tracking-widest flex justify-between items-center text-gray-400">
                    <span>{name}</span>
                    <div className={`w-1 h-1 rounded-full ${c.dot}`} />
                  </div>
                  <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
                    {entries.map(([k, v]) => (
                      <div key={k} className="flex flex-col">
                        <span className="text-[7px] text-gray-500 truncate">{k}</span>
                        <span className={`text-[10px] font-bold ${c.text} truncate`}>{fmt(v)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {sections.map(([name, vals], i) => {
              const c = colorFor(name, i);
              return (
                <div key={name} className={`p-3 rounded-xl border border-white/5 ${c.bg}`}>
                  <h5 className={`text-[9px] font-black uppercase tracking-wider ${c.text} mb-2 border-b border-white/10 pb-1 flex justify-between items-center`}>
                    {name}
                    <div className={`w-1.5 h-1.5 rounded-full ${c.dot} opacity-60`} />
                  </h5>
                  <div className="space-y-1">
                    {Object.entries(vals).map(([k, v]) => (
                      <div key={k} className="flex justify-between items-center text-[10px]">
                        <span className="text-gray-400 truncate max-w-[55%]">{k}</span>
                        <span className={`font-mono font-bold ${c.text} bg-black/20 px-1.5 py-0.5 rounded border border-white/5 text-right`}>{fmt(v)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <button onClick={() => setExpanded(e => !e)}
          className="w-full py-1.5 mt-0.5 rounded-xl bg-white/5 border border-white/10 text-[9px] font-black uppercase tracking-widest text-gray-400 hover:bg-[var(--accent)] hover:text-white hover:border-[var(--accent)] transition-all flex items-center justify-center gap-2">
          {expanded ? 'Compact' : 'Full Report'}
          <BarChart2 size={10} />
        </button>
      </div>
    </BaseNode>
  );
};


export const PetrographicReportNode = memo(PetrographicReportNodeUI);


const GrainHistogramNodeUI = ({ data, selected }: { data: any; selected: boolean }) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);

  const chartData = useMemo(() => {
    const bins  = nd?.bins       as number[] | undefined;
    const cnts  = nd?.counts     as number[] | undefined;
    const cumul = nd?.cumulative as number[] | undefined;
    if (!bins?.length) return [];
    return bins.map((b, i) => ({ b, count: cnts?.[i] ?? 0, cum: cumul?.[i] ?? 0 }));
  }, [nd?.bins, nd?.counts, nd?.cumulative]);

  const d50   = nd?.d50   as number | undefined;
  const d10   = nd?.d10   as number | undefined;
  const d90   = nd?.d90   as number | undefined;
  const count = nd?.count as number | undefined;
  const mean  = nd?.mean  as number | undefined;
  const std   = nd?.std   as number | undefined;
  const unit  = (nd?.unit  as string | undefined) ?? 'µm';
  const label = (nd?.label as string | undefined) ?? 'Size';

  const hasData = chartData.length > 0;

  return (
    <BaseNode title="Grain Size Histogram" icon={BarChart2} selected={selected} data={data}
      color="blue"
      inputs={[{ id: 'regions', color: 'list', label: 'Regions' }]}
      outputs={[]}
      width="100%" height="100%" className="w-full h-full">
      <div className="flex flex-col gap-1 mt-1 w-full h-full min-h-0">
        {!hasData ? (
          <div className="flex-1 flex items-center justify-center text-[10px] text-gray-500 uppercase tracking-widest">
            Awaiting data…
          </div>
        ) : (
          <>
            <div className="flex-1 min-h-0 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 4, right: 28, left: 0, bottom: 2 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="b" tick={{ fontSize: 8, fill: '#6b7280' }}
                    tickFormatter={(v: number) => v.toFixed(0)} />
                  <YAxis yAxisId="left" tick={{ fontSize: 8, fill: '#6b7280' }} width={28} />
                  <YAxis yAxisId="right" orientation="right" domain={[0, 100]}
                    tick={{ fontSize: 8, fill: '#a78bfa' }} unit="%" width={28} />
                  <Tooltip
                    contentStyle={{ background: '#1e1e2e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, fontSize: 10 }}
                    formatter={(val: number, name: string) =>
                      name === 'cum' ? [`${val.toFixed(1)}%`, 'Cumul.'] : [val, 'Count']
                    }
                    labelFormatter={(v: number) => `${v.toFixed(1)} ${unit}`}
                  />
                  {d50 != null && (
                    <ReferenceLine yAxisId="left" x={d50} stroke="#f59e0b"
                      strokeDasharray="4 3" label={{ value: 'D50', fill: '#f59e0b', fontSize: 8, position: 'top' }} />
                  )}
                  <Bar yAxisId="left" dataKey="count" fill="#3b82f6" opacity={0.75} radius={[2, 2, 0, 0]} />
                  <Line yAxisId="right" type="monotone" dataKey="cum"
                    stroke="#a78bfa" strokeWidth={1.5} dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-3 gap-x-2 gap-y-0.5 px-1 pb-1">
              {[
                ['n', count],
                [`D10 (${unit})`, d10],
                [`D50 (${unit})`, d50],
                [`D90 (${unit})`, d90],
                [`Mean`, mean != null ? `${mean} ${unit}` : '—'],
                [`Std`,  std  != null ? `${std} ${unit}`  : '—'],
              ].map(([k, v]) => (
                <div key={String(k)} className="flex flex-col">
                  <span className="text-[7px] text-gray-500 truncate">{k}</span>
                  <span className="text-[9px] font-bold text-blue-300 font-mono">{v ?? '—'}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </BaseNode>
  );
};


export const GrainHistogramNode = memo(GrainHistogramNodeUI);


export const RootAnatomyReportNode = memo(({ data, selected }: any) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const [expanded, setExpanded] = React.useState(false);
  const stats = nd?.report || {};
  const categories = [
    { label: 'Root & Stele', keys: ['RXSA', 'TSA', 'TSA:RXSA', 'TSA:TCA'], bg: 'bg-blue-500/5', color: 'text-blue-400' },
    { label: 'Vascular', keys: ['XVA', '#PX', 'PXA', 'SCWA'], bg: 'bg-emerald-500/5', color: 'text-emerald-400' },
    { label: 'Cortex', keys: ['TCA', 'AA', '#Lac', '%A'], bg: 'bg-purple-500/5', color: 'text-purple-400' },
  ];
  const extendedCategories = [
    { label: 'Morphometry', keys: ['RXSA', 'TSA', 'TCA', 'EA', 'ExA'], bg: 'bg-blue-500/5', color: 'text-blue-400' },
    { label: 'Vascular System', keys: ['XVA', 'XSCWA', 'PXA', '#PX', 'SCWA'], bg: 'bg-emerald-500/5', color: 'text-emerald-400' },
    { label: 'Cortex & Lacunae', keys: ['TCA', 'AA', '%A', '#Lac', 'CCA', '%CCA'], bg: 'bg-purple-500/5', color: 'text-purple-400' },
    { label: 'Ratios', keys: ['TSA:RXSA', 'TSA:TCA', 'quality_score', 'focus_score'], bg: 'bg-amber-500/5', color: 'text-amber-400' },
  ];
  const formatVal = (v: any) => typeof v === 'number' ? (v > 100 ? Math.round(v) : v.toFixed(3)) : v || '—';
  return (
    <BaseNode title="Anatomy Report" icon={BarChart2} selected={selected} data={data} color="accent" inputs={[{id: 'data', color: 'root_data'}]} outputs={[{id: 'report', color: 'dict'}]} width={expanded ? "45rem" : "20rem"}>
      <div className="flex flex-col gap-3 mt-2 w-full">
        {!expanded ? (
          <div className="flex flex-col gap-2">
            {categories.map(cat => (
              <div key={cat.label} className={`p-2 rounded-xl border border-white/5 ${cat.bg}`}>
                <div className="text-[7px] text-gray-500 uppercase font-black mb-2 tracking-widest flex justify-between">
                  <span>{cat.label}</span><div className={`w-1 h-1 rounded-full ${cat.color.replace('text', 'bg')}`} />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {cat.keys.map(k => (
                    <div key={k} className="flex flex-col">
                      <span className="text-[8px] text-gray-400 truncate">{k.toUpperCase()}</span>
                      <span className={`text-[11px] font-bold ${cat.color}`}>{formatVal(stats[k])}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            {extendedCategories.map(cat => (
              <div key={cat.label} className={`p-3 rounded-xl border border-white/5 ${cat.bg}`}>
                <h5 className={`text-[9px] font-black uppercase tracking-wider ${cat.color} mb-3 border-b border-white/10 pb-1 flex justify-between items-center`}>
                  {cat.label}<div className={`w-1.5 h-1.5 rounded-full ${cat.color.replace('text', 'bg')} opacity-50`} />
                </h5>
                <div className="space-y-1.5">
                  {cat.keys.map(k => (
                    <div key={k} className="flex justify-between items-center text-[10px]">
                      <span className="text-gray-400">{k.toUpperCase()}</span>
                      <span className={`font-mono font-bold ${cat.color} bg-black/20 px-1.5 py-0.5 rounded border border-white/5`}>{formatVal(stats[k])}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
        <button onClick={() => setExpanded(!expanded)}
          className="w-full py-2 mt-1 rounded-xl bg-white/5 border border-white/10 text-[9px] font-black uppercase tracking-widest text-gray-400 hover:bg-[var(--accent)] hover:text-white hover:border-[var(--accent)] transition-all flex items-center justify-center gap-2">
          {expanded ? 'Collapse View' : 'Precision Report'}<BarChart2 size={10} />
        </button>
      </div>
    </BaseNode>
  );
});


const TURB_CLASSES: { label: string; short: string; color: string; bg: string }[] = [
  { label: 'Crystal (0-1)',          short: 'Crystal',   color: 'text-blue-300',   bg: 'bg-blue-500/5'   },
  { label: 'Clear (1-5)',            short: 'Clear',     color: 'text-cyan-400',   bg: 'bg-cyan-500/5'   },
  { label: 'Slightly turbid',        short: 'Slight.',   color: 'text-green-400',  bg: 'bg-green-500/5'  },
  { label: 'Turbid',                 short: 'Turbid',    color: 'text-amber-400',  bg: 'bg-amber-500/5'  },
  { label: 'Very turbid',            short: 'Very T.',   color: 'text-orange-400', bg: 'bg-orange-500/5' },
  { label: 'Extremely turbid',       short: 'Extreme',   color: 'text-red-400',    bg: 'bg-red-500/5'    },
];


export const TurbidityStatsNodeUI = ({ data, selected }: { data: any; selected: boolean }) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const [expanded, setExpanded] = React.useState(false);

  const stats = (nd as any)?.stats || {};
  const classes = stats.classes || {};
  const hasData = typeof stats.mean === 'number';

  const fmt = (v: any, dec = 2) =>
    typeof v === 'number' ? (v >= 1000 ? Math.round(v).toString() : v.toFixed(dec)) : '—';

  const metricsLeft = [
    { label: 'Mean',    key: 'mean',   color: 'text-cyan-400' },
    { label: 'Median',  key: 'median', color: 'text-cyan-400' },
    { label: 'P90',     key: 'p90',    color: 'text-amber-400' },
    { label: 'Max',     key: 'max',    color: 'text-red-400'  },
  ];

  return (
    <BaseNode
      title="Turbidity Stats"
      icon={BarChart2}
      selected={selected}
      data={data}
      color="accent"
      inputs={[
        { id: 'turbidity', color: 'geotiff' },
        { id: 'mask',      color: 'mask'    },
      ]}
      outputs={[
        { id: 'stats',     color: 'dict'   },
        { id: 'histogram', color: 'image'  },
        { id: 'class_map', color: 'image'  },
        { id: 'mean_ntu',  color: 'scalar' },
        { id: 'area_km2',  color: 'scalar' },
      ]}
      width={expanded ? '42rem' : '18rem'}
    >
      <div className="flex flex-col gap-3 mt-2 w-full">
        {!expanded ? (
          /* ── Compact view ──────────────────────────── */
          <div className="flex flex-col gap-2">
            {/* Metric pills */}
            <div className="p-2 rounded-xl border border-white/5 bg-cyan-500/5">
              <div className="text-[7px] text-cyan-500/70 uppercase font-black mb-2 tracking-widest">NTU Metrics</div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                {metricsLeft.map(m => (
                  <div key={m.key} className="flex flex-col">
                    <span className="text-[8px] text-gray-500">{m.label}</span>
                    <span className={`text-[11px] font-bold font-mono ${m.color}`}>{fmt(stats[m.key])} NTU</span>
                  </div>
                ))}
              </div>
              <div className="mt-2 pt-1 border-t border-white/5 text-[8px] text-gray-400 flex justify-between">
                <span>Water surface</span>
                <span className="text-emerald-400 font-mono font-bold">{fmt(stats.area_km2, 1)} km²</span>
              </div>
            </div>
            {/* Class distribution mini */}
            <div className="p-2 rounded-xl border border-white/5 bg-white/3">
              <div className="text-[7px] text-gray-500 uppercase font-black mb-1.5 tracking-widest">WFD Distribution</div>
              <div className="space-y-1">
                {TURB_CLASSES.filter(tc => {
                  const d = classes[tc.label];
                  const pct = typeof d === 'number' ? d : (d?.pct ?? 0);
                  return pct > 0.5;
                }).map(tc => {
                  const raw = classes[tc.label];
                  const pct = typeof raw === 'number' ? raw : (raw?.pct || 0);
                  return (
                    <div key={tc.label} className="flex items-center gap-2">
                      <span className={`text-[8px] font-bold w-12 shrink-0 ${tc.color}`}>{tc.short}</span>
                      <div className="flex-1 h-1 bg-white/5 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${tc.color.replace('text', 'bg')} opacity-70`} style={{ width: `${Math.min(100, pct)}%` }} />
                      </div>
                      <span className="text-[8px] text-gray-400 font-mono w-9 text-right">{pct.toFixed(1)}%</span>
                    </div>
                  );
                })}
                {!hasData && <div className="text-[8px] text-gray-600 italic">En attente…</div>}
              </div>
            </div>
          </div>
        ) : (
          /* ── Expanded view ─────────────────────────── */
          <div className="grid grid-cols-2 gap-4">
            {/* Metrics panel */}
            <div className="p-3 rounded-xl border border-white/5 bg-cyan-500/5">
              <h5 className="text-[9px] font-black uppercase tracking-wider text-cyan-400 mb-3 border-b border-white/10 pb-1 flex justify-between items-center">
                NTU Metrics
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 opacity-50" />
              </h5>
              <div className="space-y-1.5">
                {metricsLeft.map(m => (
                  <div key={m.key} className="flex justify-between items-center text-[10px]">
                    <span className="text-gray-400">{m.label}</span>
                    <span className={`font-mono font-bold ${m.color} bg-black/20 px-1.5 py-0.5 rounded border border-white/5`}>{fmt(stats[m.key])} NTU</span>
                  </div>
                ))}
                <div className="flex justify-between items-center text-[10px] pt-1 border-t border-white/5 mt-1">
                  <span className="text-gray-400">Water surface</span>
                  <span className="font-mono font-bold text-emerald-400 bg-black/20 px-1.5 py-0.5 rounded border border-white/5">{fmt(stats.area_km2, 1)} km²</span>
                </div>
                <div className="flex justify-between items-center text-[10px]">
                  <span className="text-gray-400">Water pixels</span>
                  <span className="font-mono font-bold text-gray-300 bg-black/20 px-1.5 py-0.5 rounded border border-white/5">{stats.count ? stats.count.toLocaleString() : '—'}</span>
                </div>
              </div>
            </div>
            {/* WFD classes panel */}
            <div className="p-3 rounded-xl border border-white/5 bg-white/3">
              <h5 className="text-[9px] font-black uppercase tracking-wider text-amber-400 mb-3 border-b border-white/10 pb-1 flex justify-between items-center">
                WFD Distribution
                <div className="w-1.5 h-1.5 rounded-full bg-amber-400 opacity-50" />
              </h5>
              <div className="space-y-2">
                {TURB_CLASSES.map(tc => {
                  const rawD = classes[tc.label];
                  const pct = typeof rawD === 'number' ? rawD : (rawD?.pct || 0);
                  return (
                    <div key={tc.label} className="flex flex-col gap-0.5">
                      <div className="flex justify-between items-center text-[9px]">
                        <span className={`font-bold ${tc.color}`}>{tc.label}</span>
                        <span className="font-mono text-gray-300 bg-black/20 px-1.5 py-0.5 rounded border border-white/5">{pct.toFixed(1)}%</span>
                      </div>
                      <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${tc.color.replace('text', 'bg')} opacity-60`} style={{ width: `${Math.min(100, pct)}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full py-2 mt-1 rounded-xl bg-white/5 border border-white/10 text-[9px] font-black uppercase tracking-widest text-gray-400 hover:bg-[var(--accent)] hover:text-white hover:border-[var(--accent)] transition-all flex items-center justify-center gap-2"
        >
          {expanded ? 'Collapse View' : 'WFD Distribution'}
          <BarChart2 size={10} />
        </button>
      </div>
    </BaseNode>
  );
};


export const HemogrammeNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);

  const rbc = nd?.rbc_count ?? nd?.stats?.rbc ?? 0;
  const wbc = nd?.wbc_count ?? nd?.stats?.wbc ?? 0;
  const plt = nd?.plt_count ?? nd?.stats?.plt ?? 0;

  const neu = nd?.stats?.neu || '0.0';
  const lym = nd?.stats?.lym || '0.0';
  const mon = nd?.stats?.mon || '0.0';

  const diamUm  = parseFloat(nd?.stats?.rbc_diam_um ?? 0);
  const areaUm  = parseFloat(nd?.stats?.rbc_area_um ?? 0);
  const cvDiam  = parseFloat(nd?.stats?.rbc_cv      ?? 0);

  const diamColor  = diamUm === 0 ? 'text-gray-600'
    : diamUm < 5.5 ? 'text-orange-400' : diamUm > 8.5 ? 'text-red-400' : 'text-sky-400';
  const cvColor    = cvDiam === 0 ? 'text-gray-600'
    : cvDiam > 25 ? 'text-red-400' : cvDiam > 15 ? 'text-orange-400' : 'text-emerald-400';

  // Extract interpretation lines from the report
  const interpretation: string[] = React.useMemo(() => {
    if (!nd?.report) return [];
    const match = String(nd.report).match(/INTERPRETATION:\n([\s\S]*)/);
    if (!match) return [];
    return match[1].trim().split('\n').filter(l => l.trim().length > 0).slice(0, 4);
  }, [nd?.report]);

  return (
    <BaseNode title="Hemogramme" icon={FileText} selected={selected} data={data} color="rose"
      width={380}
      inputs={data.schema?.inputs}
      outputs={data.schema?.outputs}
    >
      <div className="flex flex-col gap-2.5 px-10 py-2 nodrag">

        {/* ── Counts ─────────────────────────────────────────────────── */}
        <div className="grid grid-cols-3 gap-1.5">
          <div className="bg-black/40 rounded-xl p-2 flex flex-col items-center border border-white/5 shadow-inner">
            <span className="text-[7px] text-rose-500/70 uppercase font-black tracking-tighter">RBC</span>
            <span className="text-sm font-black font-mono text-rose-400">{rbc}</span>
          </div>
          <div className="bg-black/40 rounded-xl p-2 flex flex-col items-center border border-white/5 shadow-inner">
            <span className="text-[7px] text-gray-500 uppercase font-black tracking-tighter">WBC</span>
            <span className="text-sm font-black font-mono text-white">{wbc}</span>
          </div>
          <div className="bg-black/40 rounded-xl p-2 flex flex-col items-center border border-white/5 shadow-inner">
            <span className="text-[7px] text-purple-500/70 uppercase font-black tracking-tighter">PLT</span>
            <span className="text-sm font-black font-mono text-purple-400">{plt}</span>
          </div>
        </div>

        {/* ── RBC Morphometry ────────────────────────────────────────── */}
        <div className="bg-black/40 rounded-xl p-2.5 border border-white/5 shadow-inner">
          <div className="text-[8px] font-black uppercase tracking-[0.2em] text-gray-500 border-b border-white/5 pb-1.5 mb-2">
            RBC Morphometry
          </div>
          <div className="grid grid-cols-3 gap-1.5 text-center">
            <div>
              <div className="text-[7px] text-gray-600 uppercase tracking-wide">Mean Ø</div>
              <div className={`text-[11px] font-black font-mono ${diamColor}`}>
                {diamUm > 0 ? `${diamUm.toFixed(2)}` : '—'} <span className="text-[8px] font-normal opacity-60">µm</span>
              </div>
            </div>
            <div>
              <div className="text-[7px] text-gray-600 uppercase tracking-wide">Area</div>
              <div className="text-[11px] font-black font-mono text-sky-400">
                {areaUm > 0 ? `${areaUm.toFixed(1)}` : '—'} <span className="text-[8px] font-normal opacity-60">µm²</span>
              </div>
            </div>
            <div>
              <div className="text-[7px] text-gray-600 uppercase tracking-wide">Aniso CV</div>
              <div className={`text-[11px] font-black font-mono ${cvColor}`}>
                {cvDiam > 0 ? `${cvDiam.toFixed(1)}` : '—'} <span className="text-[8px] font-normal opacity-60">%</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── WBC Differential ──────────────────────────────────────── */}
        <div className="bg-black/40 rounded-xl p-2.5 border border-white/5 shadow-inner">
          <div className="flex items-center justify-between text-[8px] font-black uppercase tracking-[0.2em] text-gray-500 border-b border-white/5 pb-1.5 mb-2">
            <span>Differential</span>
            <span className="opacity-40 font-mono">%</span>
          </div>
          <div className="flex flex-col gap-1.5">
            {([
              ['Neutrophils', neu, 'text-blue-400',    'bg-blue-400'],
              ['Lymphocytes', lym, 'text-cyan-400',    'bg-cyan-400'],
              ['Monocytes',   mon, 'text-emerald-400', 'bg-emerald-400'],
            ] as const).map(([label, val, textCls, bgCls]) => (
              <div key={label} className="flex items-center justify-between font-mono">
                <span className="text-[10px] text-gray-400">{label}</span>
                <div className="flex items-center gap-1">
                  <div className="h-1 rounded-full bg-white/5 w-16 overflow-hidden">
                    <div className={`h-full rounded-full opacity-60 ${bgCls}`}
                         style={{ width: `${Math.min(100, parseFloat(val))}%` }} />
                  </div>
                  <span className={`text-[11px] font-black w-8 text-right ${textCls}`}>{val}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Interpretation ────────────────────────────────────────── */}
        {interpretation.length > 0 && (
          <div className="bg-black/30 rounded-xl p-2.5 border border-amber-500/10 shadow-inner">
            <div className="text-[8px] font-black uppercase tracking-[0.2em] text-amber-500/60 border-b border-white/5 pb-1.5 mb-2">
              Interpretation
            </div>
            <div className="flex flex-col gap-1">
              {interpretation.map((line, i) => (
                <div key={i} className="flex items-start gap-1.5">
                  <span className="text-amber-500/40 text-[8px] mt-0.5">›</span>
                  <span className="text-[9px] text-gray-400 leading-tight">{line}</span>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </BaseNode>
  );
});


