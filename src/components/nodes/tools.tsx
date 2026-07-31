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

export const InteractiveCalibrationNode = memo(({ selected, data }: any) => {
  const [points, setPoints] = React.useState<any[]>([]);
  const nd = useNodeData(useNodeId());
  const frame = nd?.main_preview || nd?.main;
  const onOpenEditor = data.onOpenEditor;

  React.useEffect(() => {
    if (data.params?.points) {
      try {
        const p = JSON.parse(data.params.points);
        if (Array.isArray(p)) setPoints(p);
      } catch (e) {}
    }
  }, [data.params?.points]);

  return (
    <BaseNode
      title="Visual Calibration"
      icon={Scaling}
      selected={selected}
      data={data}
      color="indigo"
      inputs={[{id: 'image', color: 'image'}]}
      outputs={[
        {id: 'factor', color: 'scalar', label: 'Px/Unit'},
        {id: 'um_per_px', color: 'scalar', label: 'µm/px'},
        {id: 'unit', color: 'scalar', label: 'Unit Name'},
      ]}
    >
      <div className="flex flex-col gap-3 nodrag">
        <div className="relative bg-black rounded-xl overflow-hidden border border-white/5 group/calib shadow-inner">
          {frame ? (
            <img src={`data:image/jpeg;base64,${frame}`} className="w-full h-auto block opacity-80" alt="Calibration Preview" />
          ) : (
            <div className="w-full aspect-video flex items-center justify-center text-gray-800">
              <Image size={24} className="opacity-10" />
            </div>
          )}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            {points.length >= 2 && (
              <line 
                x1={`${points[0].x * 100}%`} y1={`${points[0].y * 100}%`} 
                x2={`${points[1].x * 100}%`} y2={`${points[1].y * 100}%`} 
                className="stroke-indigo-400" style={{ strokeWidth: 3, strokeDasharray: '4 2' }} 
              />
            )}
            {points.map((p, i) => (
              <circle key={i} cx={`${p.x * 100}%`} cy={`${p.y * 100}%`} r={4} className="fill-white stroke-indigo-500" style={{ strokeWidth: 2 }} />
            ))}
          </svg>
          <div className="absolute inset-0 bg-black/10 opacity-0 group-hover/calib:opacity-100 transition-all duration-300 flex items-center justify-center backdrop-blur-[2px]">
            <button onClick={(e) => { e.stopPropagation(); onOpenEditor?.(); }} className="bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-xl shadow-2xl transition-all font-black text-[10px] uppercase tracking-widest scale-90 active:scale-95 flex items-center gap-2">
              <Scaling size={12} /> Set Scale
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between px-2 py-1.5 bg-black/20 rounded-lg border border-white/5 text-[10px] font-mono">
          <span className="text-indigo-400/80">{nd?.display_value || '—'}</span>
        </div>
      </div>
    </BaseNode>
  );
});


export const VisualSizeGateNode = memo(({ selected, data }: any) => {
  const [pts, setPts] = React.useState<any[]>([]);
  const nd = useNodeData(useNodeId());
  const frame = nd?.main_preview || nd?.main;
  const onOpenEditor = data.onOpenEditor;

  React.useEffect(() => {
    try {
      const p = JSON.parse(data.params?.points || '[]');
      if (Array.isArray(p)) setPts(p);
    } catch (_) {}
  }, [data.params?.points]);

  const RulerIcon = getIcon('Ruler');

  return (
    <BaseNode
      title="Visual Size Gate"
      icon={RulerIcon}
      selected={selected}
      data={data}
      color="indigo"
      inputs={[{ id: 'markers', color: 'markers', label: 'Labels' }, { id: 'image', color: 'image' }]}
      outputs={[
        { id: 'mask_kept',    color: 'mask',    label: 'Kept Mask' },
        { id: 'mask_rej',     color: 'mask',    label: 'Rej Mask' },
        { id: 'markers_out',  color: 'markers', label: 'Kept Labels' },
        { id: 'markers_rej',  color: 'markers', label: 'Rej Labels' },
        { id: 'main',         color: 'image',  label: 'Preview' },
        { id: 'count',        color: 'scalar', label: 'Count' },
        { id: 'ref_area',     color: 'scalar', label: 'Ref px²' },
      ]}
    >
      <div className="flex flex-col gap-2 nodrag">
        <div className="relative bg-black rounded-xl overflow-hidden border border-white/5 group/sg shadow-inner">
          {frame ? (
            <img src={`data:image/jpeg;base64,${frame}`} className="w-full h-auto block opacity-80" alt="Size Gate Preview" />
          ) : (
            <div className="w-full aspect-video flex items-center justify-center text-gray-800">
              <RulerIcon size={24} className="opacity-10" />
            </div>
          )}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            {pts.length >= 2 && (
              <line
                x1={`${pts[0].x * 100}%`} y1={`${pts[0].y * 100}%`}
                x2={`${pts[1].x * 100}%`} y2={`${pts[1].y * 100}%`}
                stroke="#3b82f6" strokeWidth={2} strokeDasharray="4 2"
              />
            )}
            {pts.slice(0, 2).map((p: any, i: number) => (
              <circle key={i} cx={`${p.x * 100}%`} cy={`${p.y * 100}%`} r={4} fill="#3b82f6" stroke="white" strokeWidth={1.5} />
            ))}
          </svg>
          <div className="absolute inset-0 bg-black/10 opacity-0 group-hover/sg:opacity-100 transition-all duration-300 flex items-center justify-center backdrop-blur-[2px]">
            <button
              onClick={e => { e.stopPropagation(); onOpenEditor?.(); }}
              className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-xl shadow-2xl transition-all font-black text-[10px] uppercase tracking-widest scale-90 active:scale-95 flex items-center gap-2"
            >
              <RulerIcon size={12} /> Draw Line
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between px-2 py-1.5 bg-black/20 rounded-lg border border-white/5 text-[10px] font-mono">
          <span className="text-blue-400/70">ref {nd?.ref_area != null ? `${nd.ref_area}` : '—'}</span>
          <span className="text-orange-400/70">med {nd?.median_area != null ? `${Math.round(nd.median_area)}` : '—'}</span>
          <span className="text-white/50">n={nd?.count ?? '—'}</span>
        </div>
      </div>
    </BaseNode>
  );
});


export const VisualMeasureNode = memo(({ selected, data }: any) => {
  const [pts, setPts] = React.useState<any[]>([]);
  const nd = useNodeData(useNodeId());
  const frame = nd?.main_preview || nd?.main;
  const onOpenEditor = data.onOpenEditor;

  React.useEffect(() => {
    try {
      const p = JSON.parse(data.params?.points || '[]');
      if (Array.isArray(p)) setPts(p);
    } catch (_) {}
  }, [data.params?.points]);

  const RulerIcon = getIcon('Ruler');

  return (
    <BaseNode
      title="Ruler"
      icon={RulerIcon}
      selected={selected}
      data={data}
      color="indigo"
      inputs={[{ id: 'image', color: 'image', label: 'Image' }, { id: 'factor', color: 'scalar', label: 'Px/Unit' }, { id: 'unit', color: 'scalar', label: 'Unit' }]}
      outputs={[
        { id: 'main',   color: 'image',  label: 'Preview' },
        { id: 'length', color: 'scalar', label: 'Length' },
        { id: 'angle',  color: 'scalar', label: 'Angle (°)' },
      ]}
    >
      <div className="flex flex-col gap-2 nodrag">
        <div className="relative bg-black rounded-xl overflow-hidden border border-white/5 group/sg shadow-inner">
          {frame ? (
            <img src={`data:image/jpeg;base64,${frame}`} className="w-full h-auto block opacity-80" alt="Measure Preview" />
          ) : (
            <div className="w-full aspect-video flex items-center justify-center text-gray-800">
              <RulerIcon size={24} className="opacity-10" />
            </div>
          )}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            {pts.length >= 2 && (
              <line
                x1={`${pts[0].x * 100}%`} y1={`${pts[0].y * 100}%`}
                x2={`${pts[1].x * 100}%`} y2={`${pts[1].y * 100}%`}
                stroke="#00e6ff" strokeWidth={2} strokeDasharray="4 2"
              />
            )}
            {pts.slice(0, 2).map((p: any, i: number) => (
              <circle key={i} cx={`${p.x * 100}%`} cy={`${p.y * 100}%`} r={4} fill="#00e6ff" stroke="white" strokeWidth={1.5} />
            ))}
          </svg>
          <div className="absolute inset-0 bg-black/10 opacity-0 group-hover/sg:opacity-100 transition-all duration-300 flex items-center justify-center backdrop-blur-[2px]">
            <button
              onClick={e => { e.stopPropagation(); onOpenEditor?.(); }}
              className="bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-xl shadow-2xl transition-all font-black text-[10px] uppercase tracking-widest scale-90 active:scale-95 flex items-center gap-2"
            >
              <RulerIcon size={12} /> Draw Line
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between px-2 py-1.5 bg-black/20 rounded-lg border border-white/5 text-[10px] font-mono">
          <span className="text-cyan-400/70">L: {nd?.length != null ? `${nd.length}` : '—'}</span>
          {pts.length >= 3 && <span className="text-white/50">A: {nd?.angle ?? '—'}°</span>}
        </div>
      </div>
    </BaseNode>
  );
});


export const ROIPolygonNode = memo(({ selected, data }: any) => {
  const [points, setPoints] = React.useState<any[]>([]);
  const nd = useNodeData(useNodeId());
  const frame = nd?.main_preview || nd?.main;
  const onOpenEditor = data.onOpenEditor;

  React.useEffect(() => {
    if (data.params?.points) {
      try {
        const p = JSON.parse(data.params.points);
        if (Array.isArray(p)) setPoints(p);
      } catch (e) {}
    }
  }, [data.params?.points]);

  return (
    <BaseNode
      title="Mask Polygon"
      icon={Scaling}
      selected={selected}
      data={data}
      color="accent"
      inputs={[{id: 'image', color: 'image'}, {id: 'mask_in', color: 'mask'}]}
      outputs={[
        {id: 'main',       color: 'image'},
        {id: 'mask',       color: 'mask'},
        {id: 'masked',     color: 'image'},
        {id: 'masked_inv', color: 'image'},
        {id: 'pts',        color: 'list'}
      ]}
    >
      <div className="flex flex-col gap-3 nodrag">
        <div className="relative bg-black rounded-xl overflow-hidden border border-white/5 group/roi shadow-inner">
          {frame ? (
            <img src={`data:image/jpeg;base64,${frame}`} className="w-full h-auto block opacity-60 grayscale-[50%]" alt="ROI Preview" />
          ) : (
            <div className="w-full aspect-video flex items-center justify-center text-gray-800">
              <Image size={24} className="opacity-10" />
            </div>
          )}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 w-full h-full overflow-visible">
              {points.length >= 3 && (
                <polygon points={points.map(p => `${p.x},${p.y}`).join(' ')} className="fill-accent/30 stroke-accent" style={{ strokeWidth: 0.012, vectorEffect: 'non-scaling-stroke' }} />
              )}
            </svg>
            {points.map((p, i) => (
              <circle key={i} cx={`${p.x * 100}%`} cy={`${p.y * 100}%`} r={3} className="fill-white stroke-accent" style={{ strokeWidth: 1, vectorEffect: 'non-scaling-stroke' }} />
            ))}
          </svg>
          <div className="absolute inset-0 bg-black/10 opacity-0 group-hover/roi:opacity-100 transition-all duration-300 flex items-center justify-center backdrop-blur-[2px]">
            <button onClick={(e) => { e.stopPropagation(); onOpenEditor?.(); }} className="bg-accent hover:bg-blue-600 text-white px-5 py-2.5 rounded-xl shadow-2xl transition-all font-black text-[10px] uppercase tracking-widest scale-90 active:scale-95 flex items-center gap-2">
              <Scaling size={12} /> Edit Region
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between px-1">
          <div className="text-[8px] font-black text-gray-600 uppercase tracking-widest">{points.length} Vertices</div>
        </div>
      </div>
    </BaseNode>
  );
});


export const CropRectNode = memo(({ selected, data }: any) => {
  const frame = useNodeData(useNodeId())?.main_preview;
  const onOpenEditor = data.onOpenEditor;

  let rect = { x: 0.1, y: 0.1, w: 0.8, h: 0.8 };
  try { if (data.params?.rect) rect = JSON.parse(data.params.rect); } catch(e) {}

  return (
    <BaseNode title="Crop" icon={Crop} selected={selected} data={data} color="accent"
      inputs={[{ id: 'image', color: 'image' }]}
      outputs={[{ id: 'main', color: 'image' }, { id: 'width', color: 'scalar' }, { id: 'height', color: 'scalar' }, { id: 'box', color: 'dict' }]}
    >
      <div className="flex flex-col gap-3 nodrag">
        <div className="relative bg-black rounded-xl overflow-hidden border border-white/5 group/crop shadow-inner">
          {frame ? (
            <img src={`data:image/jpeg;base64,${frame}`} className="w-full h-auto block" alt="Crop Preview" />
          ) : (
            <div className="w-full aspect-video flex items-center justify-center text-gray-800">
              <Crop size={24} className="opacity-10" />
            </div>
          )}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 w-full h-full overflow-visible">
              <path
                d={`M 0 0 h 1 v 1 h -1 Z M ${rect.x} ${rect.y} h ${rect.w} v ${rect.h} h -${rect.w} Z`}
                fill="#3b82f6"
                fillOpacity="0.4"
                fillRule="evenodd"
              />
              <rect x={rect.x} y={rect.y} width={rect.w} height={rect.h}
                className="fill-transparent stroke-accent" style={{ strokeWidth: 0.012, vectorEffect: 'non-scaling-stroke' }} />
            </svg>
          </svg>
          <div className="absolute inset-0 bg-black/10 opacity-0 group-hover/crop:opacity-100 transition-all duration-300 flex items-center justify-center backdrop-blur-[2px]">
            <button onClick={(e) => { e.stopPropagation(); onOpenEditor?.(); }}
              className="bg-accent hover:bg-blue-600 text-white px-5 py-2.5 rounded-xl shadow-2xl transition-all font-black text-[10px] uppercase tracking-widest scale-90 active:scale-95 flex items-center gap-2">
              <Crop size={12} /> Edit Crop
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between px-1">
          <div className="text-[8px] font-black text-gray-600 uppercase tracking-widest">
            {Math.round(rect.w * 100)}% × {Math.round(rect.h * 100)}%
          </div>
          <button onClick={(e) => { e.stopPropagation(); onOpenEditor?.(); }}
            className="text-[8px] font-black text-accent uppercase tracking-widest hover:underline">
            Edit Crop
          </button>
        </div>
      </div>
    </BaseNode>
  );
});


export const AnnotatorNode = memo(({ selected, data }: any) => {
  const frame = useNodeData(useNodeId())?.main_preview;
  const onOpenEditor = data.onOpenEditor;
  let annotCount = 0;
  try { annotCount = JSON.parse(data.params?.annotations || '[]').length; } catch {}

  return (
    <BaseNode title="Annotator" icon={PenTool} selected={selected} data={data} color="accent"
      inputs={[{ id: 'image', color: 'image' }]}
      outputs={[{ id: 'main', color: 'image' }]}
    >
      <div className="flex flex-col gap-3 nodrag">
        <div className="relative bg-black rounded-xl overflow-hidden border border-white/5 group/ann shadow-inner">
          {frame ? (
            <img src={`data:image/jpeg;base64,${frame}`} className="w-full h-auto block" alt="Annotator Preview" draggable={false} />
          ) : (
            <div className="w-full aspect-video flex items-center justify-center text-gray-800">
              <PenTool size={24} className="opacity-10" />
            </div>
          )}
          <div className="absolute inset-0 bg-black/20 opacity-0 group-hover/ann:opacity-100 transition-all duration-300 flex items-center justify-center backdrop-blur-[2px]">
            <button onClick={e => { e.stopPropagation(); onOpenEditor?.(); }}
              className="bg-violet-600 hover:bg-violet-500 text-white px-5 py-2.5 rounded-xl shadow-2xl transition-all font-black text-[10px] uppercase tracking-widest scale-90 active:scale-95 flex items-center gap-2">
              <PenTool size={12} /> Annoter
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between px-1">
          <div className="text-[8px] font-black text-gray-600 uppercase tracking-widest">
            {annotCount} annotation{annotCount !== 1 ? 's' : ''}
          </div>
          <button onClick={e => { e.stopPropagation(); onOpenEditor?.(); }}
            className="text-[8px] font-black text-violet-400 uppercase tracking-widest hover:underline">
            Annoter
          </button>
        </div>
      </div>
    </BaseNode>
  );
});


export const ForensicFootprintNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  const frame = nd?.main_preview;
  const staheli   = nd?.staheli   != null ? Number(nd.staheli).toFixed(3)   : '—';
  const asymmetry = nd?.asymmetry != null ? Number(nd.asymmetry).toFixed(3) : '—';

  return (
    <BaseNode title="Barefoot Print Forensics" icon={Activity} selected={selected} data={data} color="accent"
      inputs={[{ id: 'image', color: 'image' }, { id: 'mask', color: 'mask' }, { id: 'px_per_mm', color: 'scalar', label: 'Px/mm' }]}
      outputs={[
        { id: 'main',      color: 'image'  },
        { id: 'report',    color: 'dict'   },
        { id: 'staheli',   color: 'scalar' },
        { id: 'asymmetry', color: 'scalar' },
      ]}
    >
      <div className="flex flex-col gap-2 nodrag">
        <div className="bg-black rounded-xl overflow-hidden border border-white/5 shadow-inner">
          {frame ? (
            <img src={`data:image/jpeg;base64,${frame}`} className="w-full h-auto block" draggable={false} />
          ) : (
            <div className="w-full aspect-video flex items-center justify-center text-gray-800">
              <Activity size={24} className="opacity-10" />
            </div>
          )}
        </div>
        <div className="flex items-center justify-between px-1">
          <div className="text-[8px] font-black text-gray-500 uppercase tracking-widest">Staheli</div>
          <div className="text-[9px] font-mono text-cyan-400">{staheli}</div>
        </div>
        <div className="flex items-center justify-between px-1">
          <div className="text-[8px] font-black text-gray-500 uppercase tracking-widest">Asym</div>
          <div className="text-[9px] font-mono text-yellow-400">{asymmetry}</div>
        </div>
      </div>
    </BaseNode>
  );
});


export const DrawOverlayNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];
  useEffect(() => { updateNodeInternals(nodeId); }, [ports.length, nodeId, updateNodeInternals]);

  const inputs = [
    { id: 'image', color: 'image' },
    ...ports.map(p => {
      const idx = p.id.indexOf('__');
      const shortId = idx >= 0 ? p.id.slice(idx + 2) : p.id;
      const color = idx >= 0 ? p.id.slice(0, idx) : 'any';
      return { id: shortId, color, label: p.label };
    }),
    { id: 'DYNAMIC_NEW_HANDLE', color: 'any' }
  ];
  return <BaseNode title="Draw Overlay" icon={PenTool} selected={selected} data={data} color="accent" inputs={inputs} outputs={[{id: 'main', color: 'image'}]} />;
});

// Recursive Component to render JSON with colors

export const DrawTextNode = memo(({ selected, data }: any) => {
  const schema = data.schema || { label: 'Draw Text', inputs: [], outputs: [] };
  const varCount = data.params?.var_count || 0;
  
  const addVar = () => data.onChangeParams?.({ var_count: Math.min(varCount + 1, 10) });
  const remVar = () => data.onChangeParams?.({ var_count: Math.max(varCount - 1, 0) });

  return (
    <BaseNode title="Draw Text" icon={Type} selected={selected} data={data} inputs={schema.inputs} outputs={schema.outputs} var_count={varCount} width="w-80">
      <div className="flex flex-col gap-2 p-1 mx-6">
        <div className="flex items-center justify-between bg-black/10 p-2 rounded-lg border border-white/5">
          <span className="text-[8px] font-black uppercase text-gray-500 font-mono tracking-tighter">Variables ({varCount})</span>
          <div className="flex gap-1">
            <button onClick={remVar} className="w-5 h-5 flex items-center justify-center bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded border border-red-500/20 transition-all font-black text-xs">-</button>
            <button onClick={addVar} className="w-5 h-5 flex items-center justify-center bg-green-500/10 hover:bg-green-500/20 text-green-500 rounded border border-green-500/20 transition-all font-black text-xs">+</button>
          </div>
        </div>
        {varCount > 0 && (
          <div className="text-[7px] text-gray-500 italic px-1">Placeholders: {'{'}a{'}'}, {'{'}b{'}'}...</div>
        )}
      </div>
    </BaseNode>
  );
});


export const ManualPointsNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  const frame = nd?.main_preview || nd?.main;
  const onOpenEditor = data.onOpenEditor;
  const imgRef = React.useRef<HTMLImageElement>(null);

  const [points, setPoints] = React.useState<{x:number;y:number;label:number}[]>([]);
  React.useEffect(() => {
    try {
      const p = JSON.parse(data.params?.points || '[]');
      if (Array.isArray(p)) setPoints(p);
    } catch {}
  }, [data.params?.points]);

  return (
    <BaseNode title="Manual Points (Analysis)" icon={Crosshair} selected={selected} data={data} color="purple"
      inputs={[{ id: 'image', color: 'image' }]}
      outputs={[{ id: 'main', color: 'image' }, { id: 'points', color: 'list' }, { id: 'count', color: 'scalar' }]}
    >
      <div className="flex flex-col gap-3 nodrag">
        <div className="relative bg-black rounded-xl overflow-hidden border border-white/5 group/pts shadow-inner">
          {frame ? (
            <img ref={imgRef} src={`data:image/jpeg;base64,${frame}`} className="w-full h-auto block opacity-70" alt="Points Preview" />
          ) : (
            <div className="w-full aspect-video flex items-center justify-center text-gray-800">
              <Crosshair size={24} className="opacity-10" />
            </div>
          )}
          {/* Read-only SVG overlay for points and numbers */}
          <svg 
            className="absolute inset-0 w-full h-full pointer-events-none"
            viewBox={imgRef.current && imgRef.current.naturalWidth ? `0 0 ${imgRef.current.naturalWidth} ${imgRef.current.naturalHeight}` : "0 0 1 1"}
            preserveAspectRatio="xMidYMid meet"
          >
            <g>
              {points.map((p, i) => {
                const isFg = p.label === 1;
                const nw = imgRef.current?.naturalWidth || 1;
                const nh = imgRef.current?.naturalHeight || 1;
                const cx = p.x * nw;
                const cy = p.y * nh;
                const r = Math.min(nw, nh) * 0.025;
                
                return (
                  <g key={i}>
                    <circle cx={cx} cy={cy} r={r} fill={isFg ? '#22dc50' : '#ff4444'} opacity={0.9} />
                    <circle cx={cx} cy={cy} r={r + (Math.min(nw, nh) * 0.005)} fill="none" stroke="white" strokeWidth={Math.max(1, Math.min(nw, nh) * 0.003)} opacity={0.8} />
                    <text x={cx} y={cy} dy={-(r + Math.min(nw, nh) * 0.015)} textAnchor="middle" fill="white" fontSize={Math.max(12, Math.min(nw, nh) * 0.025)} fontWeight="bold" className="drop-shadow-md" opacity={0.9}>{i+1}</text>
                  </g>
                );
              })}
            </g>
          </svg>
          <div className="absolute inset-0 bg-black/10 opacity-0 group-hover/pts:opacity-100 transition-all duration-300 flex items-center justify-center backdrop-blur-[2px]">
            <button onClick={(e) => { e.stopPropagation(); onOpenEditor?.(); }}
              className="bg-purple-600 hover:bg-purple-500 text-white px-5 py-2.5 rounded-xl shadow-2xl transition-all font-black text-[10px] uppercase tracking-widest scale-90 active:scale-95 flex items-center gap-2">
              <Crosshair size={12} /> Edit Points
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between px-2 py-1.5 bg-black/20 rounded-lg border border-white/5 text-[10px] font-mono">
          <span className="text-green-400/70">{points.filter(p => p.label === 1).length} FG</span>
          <span className="text-red-400/70">{points.filter(p => p.label === 0).length} BG</span>
        </div>
      </div>
    </BaseNode>
  );
});

// ── Geo Bbox Node ────────────────────────────────────────────────────────────

