import React, { memo, useState, useMemo, useEffect } from 'react';
import { Handle, Position, useNodeId, useEdges, useUpdateNodeInternals, NodeResizer, useStore, useStoreApi } from 'reactflow';
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
import { ScientificPlotterNode, PlotterProNode, ScientificHistogramNode, ScientificStatsNode, RootAnatomyReportNodeUI, TurbidityStatsNodeUI } from './scientific';
import { DrawTextNode } from './tools';
import { UtilCSVExportNode, DFCollectNode } from './data';
import { GeoTIFFReaderNode, GeoEarthEngineNode, GeoBandInfoNode, GeoLandCoverNode, GeoSedimentLoaderNode, GeoIndexNode, RasterColorizerNode } from './geo';
import { MatrixDistNode } from './analysis';
import { MLClassifierNodeUI, MLDfStatsNodeUI } from './ml';

export const ScalarInputNode = memo(({ selected, data }: any) => {
  const format = data.params?.format ?? 1; // 0 = Integer, 1 = Float
  const val = Number(data.params?.value ?? 0.0);
  const minVal = Number(data.params?.min ?? 0.0);
  const maxVal = Number(data.params?.max ?? 100.0);
  const stepVal = Number(data.params?.step ?? (format === 0 ? 1 : 0.01));

  const actualMin = Math.min(minVal, maxVal);
  const actualMax = Math.max(minVal, maxVal);

  const [localVal, setLocalVal] = useState(String(val));

  useEffect(() => {
    setLocalVal(String(val));
  }, [val]);

  const handleValueChange = (newVal: number) => {
    const clamped = Math.max(actualMin, Math.min(actualMax, newVal));
    const finalVal = format === 0 ? Math.round(clamped) : clamped;
    data.onChangeParams?.({ value: finalVal });
  };

  return (
    <BaseNode title={data.label || "Number"} icon={Hash} selected={selected} data={data} color="accent" outputs={[{ id: 'value', color: 'scalar' }]}>
      <div className="flex flex-col gap-2 p-1 nodrag">
        {/* Input box */}
        <div className="flex items-center gap-1.5 bg-black/25 rounded-lg px-2 py-1 border border-white/5 shadow-inner">
          <input
            type="number"
            value={localVal}
            step={stepVal}
            onChange={(e) => {
              setLocalVal(e.target.value);
              const num = parseFloat(e.target.value);
              if (!isNaN(num)) {
                handleValueChange(num);
              }
            }}
            onBlur={() => {
              const num = parseFloat(localVal);
              if (!isNaN(num)) {
                handleValueChange(num);
              } else {
                setLocalVal(String(val));
              }
            }}
            className="w-full bg-transparent text-[11px] font-mono text-accent font-bold outline-none border-none text-center"
          />
          <span className="text-[7px] text-gray-500 font-mono tracking-tighter uppercase shrink-0">
            {format === 0 ? 'Int' : 'Float'}
          </span>
        </div>

        {/* Slider control */}
        <div className="flex flex-col gap-0.5 px-1">
          <input
            type="range"
            min={actualMin}
            max={actualMax}
            step={stepVal}
            value={val}
            onChange={(e) => {
              const num = parseFloat(e.target.value);
              handleValueChange(num);
            }}
            className="w-full h-1 bg-white/10 rounded-lg appearance-none cursor-pointer accent-accent"
          />
          <div className="flex justify-between text-[7px] text-gray-500 font-mono">
            <span>{actualMin}</span>
            <span>{actualMax}</span>
          </div>
        </div>
      </div>
    </BaseNode>
  );
});


export const MathNode = memo(({ selected, data }: any) => {
  const schema = data.schema || { label: 'Math', icon: 'Calculator', inputs: [], outputs: [] };
  const IconCmp = getIcon(schema.icon, Calculator);
  return <BaseNode title={data.label || schema.label} icon={IconCmp} selected={selected} data={data} color="blue" inputs={schema.inputs} outputs={schema.outputs} />;
});


export const StringNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  const schema = data.schema || { label: 'String', icon: 'Type', inputs: [], outputs: [] };
  const IconCmp = getIcon(schema.icon, Type);
  return (
    <BaseNode title={data.label || schema.label} icon={IconCmp} selected={selected} data={data} color="accent" inputs={schema.inputs} outputs={schema.outputs}>
       {nd?.result && <div className="text-[9px] font-mono text-cyan-400 bg-black/10 p-2 rounded border border-white/5 truncate">{nd.result}</div>}
    </BaseNode>
  );
});


export const PythonNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId();
  const updateNodeInternals = useUpdateNodeInternals();
  const code = data.params?.code || '';
  const lines = code.split('\n').map(l => l.trim());
  const firstComment = lines.find(l => l.startsWith('#'));
  const displayLine = firstComment || lines.find(l => l !== '') || '';
  const onOpenEditor = data.onOpenEditor;

  // Dynamic, auto-typed I/O. Inputs in data.ports (a, b, c…), outputs in data.outPorts (out_a…).
  const inPorts: { id: string; color: string; label?: string }[] = data?.ports ?? [];
  const outPorts: { id: string; color: string; label?: string }[] = data?.outPorts ?? [];

  useEffect(() => {
    if (nodeId) updateNodeInternals(nodeId);
  }, [inPorts.length, outPorts.length, nodeId, updateNodeInternals]);

  const stripColor = (id: string) => { const i = id.indexOf('__'); return i >= 0 ? id.slice(i + 2) : id; };
  const inputs = [
    ...inPorts.map(p => ({ id: stripColor(p.id), color: p.color, label: p.label || stripColor(p.id) })),
    { id: 'DYNAMIC_NEW_HANDLE', color: 'any', label: '+' },
  ];
  const outputs = [
    ...outPorts.map(p => ({ id: stripColor(p.id), color: p.color, label: p.label || stripColor(p.id) })),
    { id: 'DYNAMIC_NEW_HANDLE', color: 'any', label: '+' },
  ];

  return (
    <BaseNode title="Python Script" icon={Zap} selected={selected} data={data} color="red"
              inputs={inputs} outputs={outputs}>
      <div 
        className="relative group nodrag flex flex-col items-center justify-center min-h-[56px] w-full bg-black/10 rounded-xl p-3 border border-white/5 shadow-inner overflow-hidden cursor-pointer"
        onDoubleClick={e => { e.stopPropagation(); onOpenEditor?.(); }}
      >
        <div className="text-[8px] font-mono text-emerald-400/70 truncate text-center italic w-full group-hover:opacity-0 transition-opacity duration-200">
          {displayLine || "# Double-click to edit"}
        </div>
        
        {/* Hover overlay — open editor */}
        <div className="absolute inset-0 bg-red-950/20 opacity-0 group-hover:opacity-100 transition-all duration-200 flex items-center justify-center backdrop-blur-[2px]">
          <button
            onClick={e => { e.stopPropagation(); onOpenEditor?.(); }}
            className="bg-red-600 hover:bg-red-500 text-white px-3 py-1.5 rounded-xl shadow-2xl transition-all font-black text-[9px] uppercase tracking-widest flex items-center gap-1.5"
          >
            <LucideIcons.FileCode size={11} /> Edit Script
          </button>
        </div>
      </div>
    </BaseNode>
  );
});




export const DataFrameEditorNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  const dfMeta = nd?.df_meta;
  const onOpenEditor = data.onOpenEditor;

  const summaryText = useMemo(() => {
    if (dfMeta && Array.isArray(dfMeta.shape)) {
      const [rows, cols] = dfMeta.shape;
      return `${rows.toLocaleString()} rows × ${cols} cols`;
    }
    return "No DataFrame connected";
  }, [dfMeta]);

  return (
    <BaseNode title="DF Editor" icon={LucideIcons.Table} selected={selected} data={data} color="orange"
              inputs={[{id: 'table', color: 'data', label: 'DataFrame'}]}
              outputs={[
                {id: 'table', color: 'data', label: 'DataFrame'},
                {id: 'df_meta', color: 'dict', label: 'DF Metadata'},
                {id: 'preview', color: 'image', label: 'Preview'}
              ]}>
      <div 
        className="relative group nodrag flex flex-col items-center justify-center min-h-[56px] w-full bg-black/10 rounded-xl p-3 border border-white/5 shadow-inner overflow-hidden cursor-pointer"
        onDoubleClick={e => { e.stopPropagation(); onOpenEditor?.(); }}
      >
        <div className="text-[9px] font-mono text-orange-300 font-semibold truncate text-center w-full group-hover:opacity-0 transition-opacity duration-200">
          {summaryText}
        </div>
        
        {/* Hover overlay — open editor */}
        <div className="absolute inset-0 bg-orange-950/20 opacity-0 group-hover:opacity-100 transition-all duration-200 flex items-center justify-center backdrop-blur-[2px]">
          <button
            onClick={e => { e.stopPropagation(); onOpenEditor?.(); }}
            className="bg-orange-600 hover:bg-orange-500 text-white px-3 py-1.5 rounded-xl shadow-2xl transition-all font-black text-[9px] uppercase tracking-widest flex items-center gap-1.5"
          >
            <LucideIcons.Edit3 size={11} /> Edit Data
          </button>
        </div>
      </div>
    </BaseNode>
  );
});




export const GenericCustomNode = memo((props: any) => {
  const { data, type: nodeType } = props;
  const schema = data.schema || { label: 'Unknown Plugin', icon: 'Box', inputs: [], outputs: [] };
  // Use the ReactFlow node type prop as the authoritative type — works even before schema loads.
  const t = nodeType || schema.type;

  if (t === 'sci_plotter') return <ScientificPlotterNode {...props} />;
  if (t === 'plotter_pro') return <PlotterProNode {...props} />;
  if (t === 'sci_histogram') return <ScientificHistogramNode {...props} />;
  if (t === 'sci_stats') return <ScientificStatsNode {...props} />;
  if (t === 'draw_text') return <DrawTextNode {...props} />;
  if (t === 'util_csv_export') return <UtilCSVExportNode {...props} />;
  if (t === 'df_collect') return <DFCollectNode {...props} />;
  if (t === 'geo_geotiff_reader') return <GeoTIFFReaderNode {...props} />;
  if (t === 'geo_earth_engine') return <GeoEarthEngineNode {...props} />;
  if (t === 'geo_band_info') return <GeoBandInfoNode {...props} />;
  if (t === 'geo_land_cover') return <GeoLandCoverNode {...props} />;
  if (t === 'sci_matrix_dist') return <MatrixDistNode {...props} />;
  if (t === 'geo_sediment_loader') return <GeoSedimentLoaderNode {...props} />;
  if (t === 'geo_index') return <GeoIndexNode {...props} />;
  if (t === 'root_anatomy_report') return <RootAnatomyReportNodeUI {...props} />;
  if (t === 'geo_turbidity_stats') return <TurbidityStatsNodeUI {...props} />;
  if (t === 'ml_knn_classifier')  return <MLClassifierNodeUI {...props} />;
  if (t === 'ml_svm_classifier')  return <MLClassifierNodeUI {...props} />;
  if (t === 'ml_df_stats')        return <MLDfStatsNodeUI {...props} />;
  if (t === 'raster_colorizer')   return <RasterColorizerNode {...props} />;
  if (t === 'llm_conversation')   return <LLMConversationNode {...props} />;

  return <GenericCustomNodeInternal {...props} schema={schema} />;
});


const _LLM_INPUTS = [
  { id: 'image', color: 'image',  label: 'Image' },
  { id: 'seed',  color: 'string', label: 'Message' },
];

const _LLM_OUTPUTS = [
  { id: 'transcript', color: 'string', label: 'Transcript' },
  { id: 'turns',      color: 'list',   label: 'Turns' },
  { id: 'last',       color: 'string', label: 'Last' },
];

// Node types that carry no useful "parameter advice" context.

const _LLM_CTX_SKIP = new Set([
  'llm_conversation', 'canvas_note', 'canvas_frame', 'canvas_reroute',
  'canvas_ribbon', 'canvas_teleport', 'note', 'group_input', 'group_output',
]);

/** Build a compact text snapshot of a node for the LLM auto-context feature. */

const _buildNodeContext = (n: any): string => {
  const sc = n?.data?.schema;
  const label = n?.data?.label || sc?.label || n?.type || 'Node';
  const desc = n?.data?.description || sc?.description || '';
  const params = n?.data?.params || {};
  const specs = (sc?.params || []) as any[];

  const lines = [`Node: ${label} (type: ${n?.type})`];
  if (desc) lines.push(`Description: ${desc}`);

  const paramLines: string[] = [];
  for (const sp of specs) {
    if (!sp?.id || sp.id.startsWith('_')) continue;
    if (sp.type === 'section') continue;
    let val = params[sp.id];
    if (val === undefined) val = sp.default;
    if (sp.type === 'enum' && Array.isArray(sp.options)) {
      const idx = typeof val === 'number' ? val : sp.options.indexOf(val);
      if (idx >= 0 && sp.options[idx] !== undefined) val = sp.options[idx];
    }
    const range = (sp.min !== undefined && sp.max !== undefined) ? ` (range ${sp.min}–${sp.max})` : '';
    paramLines.push(`  - ${sp.label || sp.id}: ${val}${range}`);
  }
  if (paramLines.length) {
    lines.push('Current parameters:');
    lines.push(...paramLines);
  }
  return lines.join('\n');
};

// Pure-decoration node types that add no topology and only clutter the graph.
const _LLM_CANVAS_SKIP = new Set([
  'canvas_note', 'canvas_frame', 'canvas_ribbon', 'note',
]);

/** Compact topology snapshot of the whole canvas for the LLM help node.
 *  Nodes numbered [n] as `label (type)`; edges as `[src].port -> [dst].port`.
 *  Excludes the LLM node itself and decoration nodes. '' if nothing useful. */
const _buildCanvasContext = (
  nodeInternals: Map<string, any>, edges: any[], selfId: string,
): string => {
  const nodes = [...nodeInternals.values()]
    .filter((n) => n.id !== selfId && !_LLM_CANVAS_SKIP.has(n.type));
  if (!nodes.length) return '';
  const idx = new Map<string, number>();
  nodes.forEach((n, i) => idx.set(n.id, i + 1));

  const nodeLines = nodes.map((n) => {
    const label = n.data?.label || n.data?.schema?.label || n.type;
    return `  [${idx.get(n.id)}] ${label} (${n.type})`;
  });
  const edgeLines = (edges || [])
    .filter((e) => idx.has(e.source) && idx.has(e.target))
    .map((e) => {
      const sp = e.sourceHandle ? `.${e.sourceHandle}` : '';
      const tp = e.targetHandle ? `.${e.targetHandle}` : '';
      return `  [${idx.get(e.source)}]${sp} -> [${idx.get(e.target)}]${tp}`;
    });

  const out = [`Nodes on canvas (${nodeLines.length}):`, ...nodeLines];
  if (edgeLines.length) out.push(`Connections (${edgeLines.length}):`, ...edgeLines);
  return out.join('\n');
};


export const LLMConversationNode = memo(({ selected, data }: any) => {
  const selfId = useNodeId();
  const storeApi = useStoreApi();
  const MessagesSquare = getIcon('MessagesSquare', Box);
  const keepCtx  = !!(data.params?.keep_context);
  const autoCtx  = !!(data.params?.auto_context);
  const modeIdx  = data.params?.num_personas ?? 0;
  const modeLabel = modeIdx === 1 ? '2 Personas' : '1 Persona';

  // Watch canvas selection: the first selected node that isn't this LLM (or a
  // pure-canvas helper) becomes the auto-context target. Returns a JSON string
  // so the component only re-renders when the captured node actually changes.
  const targetJson = useStore((s: any) => {
    for (const n of s.nodeInternals.values()) {
      if (!n.selected || n.id === selfId) continue;
      if (_LLM_CTX_SKIP.has(n.type)) continue;
      return JSON.stringify(_buildNodeContext(n)) + '|' + (n.data?.label || n.data?.schema?.label || n.type);
    }
    return '';
  });

  const captured = React.useMemo(() => {
    if (!targetJson) return null;
    const sep = targetJson.lastIndexOf('|');
    try {
      return { text: JSON.parse(targetJson.slice(0, sep)) as string, label: targetJson.slice(sep + 1) };
    } catch { return null; }
  }, [targetJson]);

  // Persist the latest captured context into _ctx so it survives selecting the
  // LLM node itself (which deselects the target). Never wipe on deselect.
  const lastCtxRef = React.useRef<string>('');
  React.useEffect(() => {
    if (autoCtx && captured && captured.text !== lastCtxRef.current) {
      lastCtxRef.current = captured.text;
      data.onChangeParams?.({ _ctx: captured.text, _ctx_label: captured.label });
    }
  }, [autoCtx, captured, data]);

  const storedLabel = data.params?._ctx_label || captured?.label || '';
  const hasCtx = !!(data.params?._ctx);

  // Persist provider + model choices so new nodes start with the last used values.
  const a_provider = data.params?.a_provider;
  const a_model    = data.params?.a_model;
  const b_provider = data.params?.b_provider;
  const b_model    = data.params?.b_model;
  React.useEffect(() => {
    if (a_provider === undefined) return;
    try {
      localStorage.setItem('vn_llm_last_params', JSON.stringify({
        a_provider, a_model: a_model ?? '',
        b_provider: b_provider ?? 0, b_model: b_model ?? '',
      }));
    } catch {}
  }, [a_provider, a_model, b_provider, b_model]);

  const handleRun    = (e: React.MouseEvent) => {
    e.stopPropagation();
    // Capture the current canvas topology fresh at Run (wiped after use by the
    // engine). The Python side sends it as optional context so the assistant can
    // advise on the actual pipeline even when no node is selected.
    let graph = '';
    try {
      const { nodeInternals, edges } = storeApi.getState() as any;
      graph = _buildCanvasContext(nodeInternals, edges, selfId || '');
    } catch { /* store unavailable — fall back to no graph */ }
    data.onChangeParams?.({ _graph: graph, run: true });
  };
  const handleClear  = (e: React.MouseEvent) => { e.stopPropagation(); data.onChangeParams?.({ clear: true }); };
  const toggleAuto   = (e: React.MouseEvent) => { e.stopPropagation(); data.onChangeParams?.({ auto_context: !autoCtx }); };

  return (
    <BaseNode
      title={data.label || 'LLM'}
      icon={MessagesSquare}
      selected={selected}
      data={data}
      color="accent"
      width={224}
      inputs={_LLM_INPUTS}
      outputs={_LLM_OUTPUTS}
    >
      {/* Spacer: push content below the lowest port (top=109px, header≈42px → need 75px from content top) */}
      <div style={{ marginTop: 72 }} className="px-2 pb-2 nodrag flex flex-col gap-1.5">
        {/* mode + keep-context badge */}
        <div className="flex items-center justify-between">
          <span className="text-[7px] font-black uppercase tracking-widest text-gray-500">{modeLabel}</span>
          {keepCtx && (
            <span className="text-[7px] font-black uppercase tracking-widest text-accent/60 bg-accent/10 px-1.5 py-0.5 rounded">context</span>
          )}
        </div>

        {/* Auto node-context toggle */}
        <button
          onClick={toggleAuto}
          className={`flex items-center justify-between px-2 py-1 rounded-lg border transition-all ${
            autoCtx
              ? 'bg-accent/15 border-accent/40 text-accent'
              : 'bg-black/20 border-white/10 text-gray-500 hover:border-white/20'
          }`}
          title="Feed the selected node's params to the LLM automatically"
        >
          <span className="flex items-center gap-1 text-[7px] font-black uppercase tracking-widest">
            <Crosshair size={8} /> Auto Context
          </span>
          <span className={`w-2 h-2 rounded-full ${autoCtx ? 'bg-accent' : 'bg-gray-600'}`} />
        </button>

        {/* Captured target indicator */}
        {autoCtx && (
          hasCtx ? (
            <div className="flex items-center gap-1 px-1.5 py-0.5 text-[7px] font-bold uppercase tracking-wider text-emerald-400/90 truncate">
              <span className="text-emerald-500">→</span>
              <span className="truncate">{storedLabel || 'node captured'}</span>
            </div>
          ) : (
            <div className="px-1.5 py-0.5 text-[7px] font-bold uppercase tracking-wider text-gray-600 truncate">
              select a node…
            </div>
          )
        )}

        {/* Run / Clear buttons */}
        <div className="flex gap-1.5">
          <button
            onClick={handleRun}
            className="flex-1 bg-accent/10 hover:bg-accent/25 border border-accent/30 hover:border-accent/60 text-accent text-[8px] font-black uppercase tracking-widest py-1.5 rounded-lg flex items-center justify-center gap-1 transition-all active:scale-95"
          >
            <Play size={9} /> Run
          </button>
          <button
            onClick={handleClear}
            className="flex-1 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-gray-400 hover:text-gray-200 text-[8px] font-black uppercase tracking-widest py-1.5 rounded-lg flex items-center justify-center gap-1 transition-all active:scale-95"
          >
            <RotateCcw size={9} /> Clear
          </button>
        </div>
      </div>
    </BaseNode>
  );
});

// Params excluded from the on-node chip summary (internal / non-visual)

const _HIDDEN_PARAMS = new Set([
  'cache_dir', 'node_note', 'output_dir', 'file_path', 'model_path',
  'expression', 'code', 'label', 'title', 'text', '_v',
]);

// Nodes with many ports + params: hide the in-body param chips for a clean look.
// Settings live in the inspector instead.

const _COMPACT_NODE_TYPES = new Set([
  'llm_conversation', 'variable_store',
]);


const GenericCustomNodeInternal = ({ selected, data, schema }: any) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const updateNodeInternals = useUpdateNodeInternals();
  const IconCmp = getIcon(schema.icon, Box);

  // Dynamic ports (created by onConnect when dynamic_inputs=true)
  const dynPorts: { id: string; color: string; label: string }[] = data?.ports ?? [];

  useEffect(() => {
    if (nodeId) updateNodeInternals(nodeId);
  }, [dynPorts.length, nodeId, updateNodeInternals]);

  const outputs = data.dynamicColor
    ? schema.outputs.map((out: any) => ({ ...out, color: data.dynamicColor }))
    : schema.outputs;

  // Build input list: static schema inputs + dynamic ports + factory handle (if dynamic_inputs).
  // Fallback: if data.ports is non-empty but schema is not loaded yet, still show saved ports.
  const inputs = React.useMemo(() => {
    const staticInputs: any[] = schema.inputs ?? [];
    const hasDynamic = schema.dynamic_inputs || dynPorts.length > 0;
    if (!hasDynamic) return staticInputs;
    const dynMapped = dynPorts.map((p: any) => {
      const idx = p.id.indexOf('__');
      const shortId = idx >= 0 ? p.id.slice(idx + 2) : p.id;
      return { id: shortId, color: p.color, label: p.label };
    });
    return [...staticInputs, ...dynMapped, { id: 'DYNAMIC_NEW_HANDLE', color: 'any' }];
  }, [schema.inputs, schema.dynamic_inputs, dynPorts]);

  const preview = nd?.preview_b64 || (typeof nd?.preview === 'string' ? nd.preview : null);

  // Build visible param chips: enum + bool params, excluding internal ones, max 4
  const paramChips: { label: string; value: string }[] = React.useMemo(() => {
    if (!schema?.params || _COMPACT_NODE_TYPES.has(schema.type)) return [];
    const chips: { label: string; value: string }[] = [];
    for (const p of schema.params) {
      if (_HIDDEN_PARAMS.has(p.id)) continue;
      if (p.type === 'enum') {
        const raw = data.params?.[p.id];
        const idx = typeof raw === 'number' ? raw : (p.options?.indexOf(raw) ?? -1);
        const val = (idx >= 0 && p.options?.[idx]) ? p.options[idx] : (raw ?? p.default ?? '');
        // Truncate long option names to 18 chars
        chips.push({ label: p.label || p.id, value: String(val).slice(0, 22) });
      } else if (p.type === 'bool' || p.type === 'toggle') {
        const val = data.params?.[p.id] ?? p.default;
        if (val === true || val === false) {
          chips.push({ label: p.label || p.id, value: val ? 'on' : 'off' });
        }
      } else if (p.type === 'string' && !_HIDDEN_PARAMS.has(p.id)) {
        const val = data.params?.[p.id] ?? p.default ?? '';
        if (val && String(val).length <= 30) {
          chips.push({ label: p.label || p.id, value: String(val).slice(0, 22) });
        }
      }
      if (chips.length >= 4) break;
    }
    return chips;
  }, [schema, data.params]);

  return (
    <BaseNode title={data.label || schema.label} icon={IconCmp} selected={selected} data={data} color="accent" inputs={inputs} outputs={outputs}>
      {preview && (
        <div className="px-2 pb-1">
          <img
            src={`data:image/jpeg;base64,${preview}`}
            alt="Node Preview"
            className="w-full h-auto max-h-32 object-cover rounded-lg border border-white/10"
          />
        </div>
      )}
      {paramChips.length > 0 && (
        <div className="px-2 pb-2 flex flex-col gap-0.5">
          {paramChips.map(chip => (
            <div key={chip.label} className="flex items-center justify-between px-2 py-0.5 bg-black/20 rounded-md border border-white/5">
              <span className="text-[7px] font-black uppercase tracking-widest text-gray-600 truncate mr-1">{chip.label}</span>
              <span className="text-[8px] font-mono text-accent/80 truncate max-w-[120px]">{chip.value}</span>
            </div>
          ))}
        </div>
      )}
    </BaseNode>
  );
};

