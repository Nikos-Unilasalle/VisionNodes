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

const JsonTreeView = ({ data, level = 0 }: { data: any, level?: number }) => {
  if (data === null || data === undefined) return <span className="text-gray-500 italic">null</span>;
  
  if (typeof data === 'number') return <span className="text-yellow-400 font-mono">{data.toFixed(4)}</span>;
  if (typeof data === 'boolean') return <span className="text-orange-400 font-mono uppercase text-[8px]">{data.toString()}</span>;
  if (typeof data === 'string') return <span className="text-cyan-300 font-mono">"{data}"</span>;
  
  if (Array.isArray(data)) {
    if (data.length === 0) return <span className="text-gray-500">[]</span>;
    return (
      <div className="flex flex-col gap-1">
        <span className="text-[7px] text-purple-400/60 uppercase font-black tracking-widest">List ({data.length})</span>
        <div className="pl-2 border-l border-white/5 flex flex-col gap-1">
          {data.slice(0, 10).map((val, i) => (
            <div key={i} className="flex gap-2 items-start shrink-0">
               <span className="text-[7px] text-gray-600 font-mono mt-1">{i}</span>
               <JsonTreeView data={val} level={level + 1} />
            </div>
          ))}
          {data.length > 10 && <span className="text-[7px] text-gray-600 italic">... and {data.length - 10} more</span>}
        </div>
      </div>
    );
  }
  
  if (typeof data === 'object') {
    const keys = Object.keys(data);
    if (keys.length === 0) return <span className="text-gray-500">{"{}"}</span>;
    return (
      <div className="flex flex-col gap-1 w-full overflow-hidden">
        <div className="pl-2 border-l border-white/10 flex flex-col gap-1.5 py-1">
          {keys.map(key => {
            const isGraphics = key === '_type' || key === 'shape' || key === 'pts';
            if (isGraphics && level > 0) return null; // Skip deep graphics props to save space
            
            return (
              <div key={key} className="flex flex-col gap-0.5 shrink-0 max-w-full overflow-hidden">
                <span className="text-[7px] font-black uppercase tracking-tight text-cyan-500/80">{key}</span>
                <div className="pl-2 border-l border-cyan-500/10 min-w-0 break-all overflow-hidden flex flex-wrap">
                  <JsonTreeView data={data[key]} level={level + 1} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }
  
  return <span>{String(data)}</span>;
};


const HIDDEN_KEYS = new Set(['_type', 'shape', 'pts', 'r', 'g', 'b', 'thickness']);


export const DataInspectorNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId();
  const d = useNodeData(nodeId)?.data_out;
  const [filterKey, setFilterKey] = useState<string | null>(data?.params?.filter_key ?? null);
  const { customBg } = useNodeColor();
  const accentBorder = customBg ? '' : (selected ? 'border-accent shadow-accent/20 shadow-lg' : 'border-[#4f5b6b]');
  const isMinified = !!(data as any)?.minified;
  const updateNodeInternals = useUpdateNodeInternals();
  useEffect(() => { if (nodeId) updateNodeInternals(nodeId); }, [isMinified, nodeId, updateNodeInternals]);

  // Extract available keys from dict or list-of-dicts
  const keys = useMemo(() => {
    if (!d) return [];
    const keySet = new Set<string>();
    if (Array.isArray(d)) {
      d.slice(0, 8).forEach(item => {
        if (item && typeof item === 'object' && !Array.isArray(item))
          Object.keys(item).forEach(k => { if (!HIDDEN_KEYS.has(k)) keySet.add(k); });
      });
    } else if (d && typeof d === 'object' && !Array.isArray(d)) {
      Object.keys(d).forEach(k => { if (!HIDDEN_KEYS.has(k)) keySet.add(k); });
    }
    return Array.from(keySet);
  }, [d]);

  // Reset filter when keys change (different data type connected)
  useEffect(() => {
    if (filterKey && !keys.includes(filterKey)) setFilterKey(null);
  }, [keys]);

  // Compute filtered display value
  const displayData = useMemo(() => {
    if (!filterKey || !d) return d;
    if (Array.isArray(d)) return d.map(item =>
      (item && typeof item === 'object') ? item[filterKey] : item
    );
    if (typeof d === 'object') return (d as any)[filterKey];
    return d;
  }, [d, filterKey]);

  const isScalar = displayData !== null && (typeof displayData === 'number' || typeof displayData === 'string' || typeof displayData === 'boolean');

  return (
    <div
      className={`w-full h-full rounded-xl bg-[#2c333f] border-2 ${accentBorder} shadow-2xl flex flex-col overflow-hidden transition-all duration-300`}
      style={{ 
        position: 'relative', 
        zIndex: 0, 
        minHeight: isMinified ? 24 : 120,
        ...(customBg ? { borderColor: customBg, boxShadow: selected ? `0 10px 15px -3px ${customBg}40` : `0 0 10px ${customBg}10` } : {}) 
      }}
    >
      <div className="absolute left-0 w-full flex items-center pointer-events-none" style={{ top: isMinified ? '12px' : '50%', transform: 'translateY(-50%)' }}>
        <StyledHandle type="target" position={Position.Left} id="data" color="any" top="50%" noBorder={isMinified} />
      </div>
      <div className="absolute right-0 w-full flex items-center justify-end pointer-events-none" style={{ top: isMinified ? '12px' : '50%', transform: 'translateY(-50%)' }}>
        <StyledHandle type="source" position={Position.Right} id="data_out" color="any" top="50%" noBorder={isMinified} />
      </div>

      {isMinified ? (
        <div className="absolute inset-0 flex items-center justify-center px-4 overflow-hidden pointer-events-none">
          <span className={`text-[9px] font-black uppercase tracking-widest truncate ${isScalar ? 'text-yellow-400' : ''}`}
                style={!isScalar && customBg ? { color: customBg } : {}}>
            {isScalar ? String(displayData) : 'Inspector'}
          </span>
        </div>
      ) : (
        <>
          {/* Title bar */}
          <div className="bg-[#3d4452] px-4 py-2 flex items-center justify-between gap-3 border-b border-[#4f5b6b] rounded-t-xl shrink-0"
               style={customBg ? { backgroundColor: `${customBg}20`, borderBottomColor: `${customBg}40` } : {}}>
            <div className="flex items-center gap-3 truncate">
              <Eye size={14} className="shrink-0" style={customBg ? { color: customBg } : { color: '#9ca3af' }} />
              <span className="font-bold text-[10px] uppercase tracking-widest truncate" style={customBg ? { color: customBg } : { color: '#e5e7eb' }}>Inspector</span>
            </div>
            {data?.isVisualized && <Eye size={11} className="text-yellow-400 animate-pulse shrink-0" />}
          </div>

          {/* Key filter pills — only shown when dict/list-of-dicts detected */}
          {keys.length > 0 && (
        <div className="flex items-center gap-1 px-2.5 py-1.5 border-b border-[#4f5b6b] bg-[#3d4452] overflow-x-auto scrollbar-hide shrink-0">
          <button
            onClick={() => setFilterKey(null)}
            className={`px-2 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider shrink-0 transition-colors ${
              filterKey === null
                ? 'bg-accent/80 text-white'
                : 'bg-white/5 text-gray-500 hover:bg-white/10 hover:text-gray-300'
            }`}
          >all</button>
          {keys.map(k => (
            <button
              key={k}
              onClick={() => setFilterKey(k === filterKey ? null : k)}
              className={`px-2 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider shrink-0 transition-colors ${
                filterKey === k
                  ? 'bg-cyan-500/70 text-white'
                  : 'bg-white/5 text-gray-500 hover:bg-white/10 hover:text-gray-300'
              }`}
            >{k}</button>
          ))}
        </div>
      )}

      {/* Scrollable content */}
          <div className="flex-1 overflow-auto scrollbar-hide p-2.5 min-h-0 nowheel">
            <JsonTreeView data={displayData} />
          </div>
        </>
      )}
    </div>
  );
});





export const DataListSelectorNode = memo(({ selected, data }: any) => (
  <BaseNode title="List Selector" icon={Database} selected={selected} data={data} color="green" inputs={[{id: 'list_in', color: 'list'}]} outputs={[{id: 'item_out', color: 'dict'}]} />
));


export const RegionSelectorNode = memo(({ selected, data }: any) => (
  <BaseNode title="Region Selector" icon={Filter} selected={selected} data={data} color="green"
    inputs={[{id: 'list_in', color: 'list'}]}
    outputs={[
      {id: 'item',     color: 'dict'},
      {id: 'pts',      color: 'list'},
      {id: 'list_out', color: 'list'},
      {id: 'count',    color: 'scalar'},
    ]}
  />
));


export const DataCoordSplitterNode = memo(({ selected, data }: any) => (
  <BaseNode title="Coord Splitter" icon={Database} selected={selected} data={data} color="green" inputs={[{id: 'dict_in', color: 'dict'}]} outputs={[
    {id: 'a', color: 'scalar'}, {id: 'b', color: 'scalar'}
  ]} />
));




export const DataCoordCombineNode = memo(({ selected, data }: any) => (
  <BaseNode title="Coord Combine" icon={Database} selected={selected} data={data} color="green" inputs={[
    {id: 'x', color: 'scalar'}, {id: 'y', color: 'scalar'}, {id: 'w', color: 'scalar'}, {id: 'h', color: 'scalar'}
  ]} outputs={[
    {id: 'dict_out', color: 'dict'}
  ]} />
));


export const UtilCoordToMaskNode = memo(({ selected, data }: any) => (
  <BaseNode title="Coord To Mask" icon={Layers} selected={selected} data={data} color="accent" inputs={[{id: 'image', color: 'image'}, {id: 'data', color: 'dict'}]} outputs={[{id: 'mask', color: 'mask'}]} />
));


export const UtilLandmarkSelectorNode = memo(({ selected, data }: any) => (
  <BaseNode title="Landmark Selector" icon={Target} selected={selected} data={data} color="accent" inputs={[{id: 'data', color: 'dict'}]} outputs={[{id: 'data', color: 'dict'}]} />
));


export const UtilMaskBlendNode = memo(({ selected, data }: any) => (
  <BaseNode title="Mask Blend" icon={Layers} selected={selected} data={data} color="accent" inputs={[
    {id: 'image_a', color: 'image'},
    {id: 'image_b', color: 'image'},
    {id: 'mask', color: 'mask'}
  ]} outputs={[{id: 'main', color: 'image'}]} />
));


export const MaskOperationsNode = memo(({ selected, data }: any) => (
  <BaseNode title="Mask Operations" icon={Layers} selected={selected} data={data} color="accent"
    inputs={[{id: 'mask_a', color: 'mask'}, {id: 'mask_b', color: 'mask'}]}
    outputs={[{id: 'mask', color: 'mask'}]} />
));


export const MaskPointQueryNode = memo(({ selected, data }: any) => (
  <BaseNode title="Mask Point Query" icon={Crosshair} selected={selected} data={data} color="accent"
    inputs={[{id: 'mask', color: 'mask'}, {id: 'x', color: 'scalar'}, {id: 'y', color: 'scalar'}]}
    outputs={[{id: 'inside', color: 'boolean'}]} />
));



// --- SCIENTIFIC NODES ---


export const DictMergeNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];

  useEffect(() => { updateNodeInternals(nodeId); }, [ports.length, nodeId, updateNodeInternals]);

  const inputs = [
    ...ports.map(p => {
      const idx = p.id.indexOf('__');
      return { 
        id: idx >= 0 ? p.id.slice(idx + 2) : p.id, 
        color: idx >= 0 ? p.id.slice(0, idx) : 'dict',
        label: p.label
      };
    }),
    { id: 'DYNAMIC_NEW_HANDLE', color: 'dict', label: 'Add Dict' },
  ];

  return (
    <BaseNode 
        title="Merge Dicts" 
        icon={PlusSquare} 
        selected={selected} 
        data={data} 
        color="indigo" 
        inputs={inputs} 
        outputs={[{id: 'main', color: 'dict'}]}
    />
  );
});

export const DictBuilderNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];
  const params = data?.params ?? {};

  useEffect(() => { updateNodeInternals(nodeId); }, [ports.length, nodeId, updateNodeInternals]);

  const inputs = [
    ...ports.map(p => {
      const idx = p.id.indexOf('__');
      const short = idx >= 0 ? p.id.slice(idx + 2) : p.id;
      return {
        id: short,
        color: idx >= 0 ? p.id.slice(0, idx) : 'scalar',
        // Show the renamed key if set, else the auto source-derived name.
        label: params[`name_${short}`] || p.label || short,
      };
    }),
    { id: 'DYNAMIC_NEW_HANDLE', color: 'scalar', label: 'Add Value' },
  ];

  return (
    <BaseNode
        title="Build Dict"
        icon={Package}
        selected={selected}
        data={data}
        color="green"
        inputs={inputs}
        outputs={[{ id: 'dict', color: 'dict' }]}
    />
  );
});


export const UtilCSVExportNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];

  useEffect(() => { updateNodeInternals(nodeId); }, [ports.length, nodeId, updateNodeInternals]);

  const inputs = [
    ...ports.map(p => {
      const idx = p.id.indexOf('__');
      const shortId = idx >= 0 ? p.id.slice(idx + 2) : p.id;
      return { id: shortId, color: p.color, label: p.label };
    }),
    { id: 'DYNAMIC_NEW_HANDLE', color: 'any' },
  ];

  const handleBrowse = async () => {
    try {
      const result = await save({ filters: [{ name: 'CSV', extensions: ['csv'] }] });
      if (result && typeof result === 'string') {
        const lastSlash = Math.max(result.lastIndexOf('/'), result.lastIndexOf('\\'));
        const path = result.substring(0, lastSlash);
        let filename = result.substring(lastSlash + 1);
        if (filename.toLowerCase().endsWith('.csv')) filename = filename.slice(0, -4);
        data.onChangeParams?.({ path, filename });
      }
    } catch (err) { console.error('Failed to open dialog:', err); }
  };

  const handleSnapshot = (e: React.MouseEvent) => {
    e.stopPropagation();
    data.onChangeParams?.({ snapshot: 1 });
    setTimeout(() => data.onChangeParams?.({ snapshot: 0 }), 400);
  };

  const isRecording = !!data.params?.record;

  const headerExtra = (
    <div className={`w-2.5 h-2.5 rounded-full ${isRecording ? 'bg-red-500 animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.6)]' : 'bg-gray-600'}`} />
  );

  return (
    <BaseNode
      title="CSV Export"
      icon={Database}
      selected={selected}
      data={data}
      color="accent"
      inputs={inputs}
      headerExtra={headerExtra}
    >
      <div className="p-3 space-y-2 mx-2">
        <button
          onClick={handleBrowse}
          className="w-full py-3 bg-accent/10 hover:bg-accent/20 border border-dashed border-accent/30 rounded-2xl flex items-center justify-center gap-2 transition-all group"
        >
          <FolderOpen size={14} className="text-accent group-hover:scale-110 transition-transform" />
          <span className="text-[10px] font-black text-accent uppercase tracking-widest">Select Path</span>
        </button>

        <div className="px-3 py-2 bg-black/10 rounded-xl border border-white/5 shadow-inner">
          <div className="text-[9px] font-mono text-gray-400 truncate">{data.params?.path || "No folder"} / <span className="text-white/70">{data.params?.filename || "capture"}.csv</span></div>
        </div>

        <button
          onClick={handleSnapshot}
          className="w-full py-2.5 bg-white/5 hover:bg-accent/15 border border-white/10 hover:border-accent/30 rounded-xl flex items-center justify-center gap-2 transition-all group active:scale-95"
        >
          <Download size={12} className="text-gray-400 group-hover:text-accent transition-colors" />
          <span className="text-[10px] font-black text-gray-400 group-hover:text-accent uppercase tracking-widest transition-colors">Snapshot</span>
        </button>
      </div>
    </BaseNode>
  );
});

