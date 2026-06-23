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

export const AnalysisFaceMPNode = memo(({ selected, data }: any) => {
  const max = data.params?.max_faces || 3;
  const outputs = [{id: 'main', color: 'image'}, {id: 'faces_list', color: 'list'}, ...Array.from({ length: max }).map((_, i) => ({ id: `face_${i}`, color: 'dict' }))];
  return (
    <BaseNode title="Face Tracker" icon={User} selected={selected} data={data} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={outputs} />
  );
});


export const AnalysisHandMPNode = memo(({ selected, data }: any) => {
  const max = data.params?.max_hands || 2;
  const outputs = [{id: 'main', color: 'image'}, {id: 'hands_list', color: 'list'}, ...Array.from({ length: max }).map((_, i) => ({ id: `hand_${i}`, color: 'dict' }))];
  return (
    <BaseNode title="Hand Tracker" icon={User} selected={selected} data={data} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={outputs} />
  );
});


export const AnalysisPoseMPNode = memo(({ selected, data }: any) => {
  const outputs = [
    {id: 'main', color: 'image'},
    {id: 'pose_list', color: 'list'},
    {id: 'data', color: 'dict'}
  ];
  return (
    <BaseNode title="Pose Tracker" icon={User} selected={selected} data={data} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={outputs} />
  );
});


export const AnalysisHeadPoseNode = memo(({ selected, data }: any) => (
  <BaseNode title="Head Pose" icon={Crosshair} selected={selected} data={data} color="accent"
    inputs={[{id: 'image', color: 'image'}, {id: 'face', color: 'dict'}]}
    outputs={[{id: 'main', color: 'image'}, {id: 'pose', color: 'dict'}]} />
));


export const TransformEyeCropNode = memo(({ selected, data }: any) => (
  <BaseNode title="Eye Crop" icon={Eye} selected={selected} data={data} color="blue"
    inputs={[{id: 'image', color: 'image'}, {id: 'face', color: 'dict'}]}
    outputs={[{id: 'eye_left', color: 'image'}, {id: 'eye_right', color: 'image'}, {id: 'meta', color: 'dict'}]} />
));


export const AnalysisGazeNode = memo(({ selected, data }: any) => (
  <BaseNode title="Gaze Estimator" icon={Eye} selected={selected} data={data} color="green"
    inputs={[{id: 'image', color: 'image'}]}
    outputs={[{id: 'main', color: 'image'}, {id: 'gaze', color: 'dict'}, {id: 'yaw', color: 'scalar'}, {id: 'pitch', color: 'scalar'}]} />
));


export const MathVecToScreenNode = memo(({ selected, data }: any) => (
  <BaseNode title="Vec → Screen" icon={Monitor} selected={selected} data={data} color="green"
    inputs={[{id: '3dvector', color: 'dict'}, {id: 'image', color: 'image'}]}
    outputs={[{id: 'main', color: 'image'}, {id: 'x', color: 'scalar'}, {id: 'y', color: 'scalar'}, {id: 'point', color: 'dict'}]} />
));


export const AnalysisFlowNode = memo(({ selected, data }: any) => (
  <BaseNode title="Optical Flow" icon={Activity} selected={selected} data={data} color="red" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}, {id: 'data', color: 'flow'}]} />
));


export const AnalysisFlowVizNode = memo(({ selected, data }: any) => (
  <BaseNode title="Flow Viz" icon={Palette} selected={selected} data={data} color="accent" inputs={[{id: 'data', color: 'flow'}]} outputs={[{id: 'main', color: 'image'}]} />
));


export const AnalysisMonitorNode = memo(({ selected, data }: any) => {
  const nodeData = useNodeData(useNodeId());
  const val = nodeData.scalar ?? 0;
  const displayText = nodeData.display_text || `${val.toFixed(data.params?.precision ?? 3)}`;
  
  const parts = displayText.trim().split(/\s+/);
  const num = parts[0] || '0.000';
  const unit = parts.slice(1).join(' ') || '';

  const mode = data.params?.mode ?? 0;
  let progress = 0;
  let themeColor = '#22c55e';

  if (mode === 1) { progress = (val / 5.0) * 100; themeColor = HANDLE_COLORS.flow; }
  else if (mode === 2) { progress = (val / 100000) * 100; themeColor = HANDLE_COLORS.mask; }
  else if (mode >= 3 && mode <= 6) { progress = (val / 255) * 100; themeColor = HANDLE_COLORS.image; }
  else if (mode === 7) { progress = (val / 20) * 100; themeColor = HANDLE_COLORS.list; }
  else { progress = (val / 100) * 100; }

  return (
    <BaseNode
      title={data.schema?.label || "Universal Monitor"}
      icon={Target}
      selected={selected}
      data={data}
      color="blue"
      inputs={[
        {id: 'data', color: 'any'},
        {id: 'image', color: 'image'},
        {id: 'mask', color: 'mask'}
      ]}
      outputs={[
        {id: 'main', color: 'image'},
        {id: 'scalar', color: 'scalar'}
      ]}
    >
      <div className="flex flex-col items-center justify-center py-3 bg-black/10 rounded-xl border border-white/5 shadow-inner gap-1">
        <div className="text-[7px] font-black text-gray-600 uppercase tracking-widest">Live Monitor</div>
        <div className="flex items-baseline gap-1 px-2 w-full justify-center">
          <span className="text-2xl font-bold font-mono tracking-tighter drop-shadow-md" style={{ color: themeColor }}>
            {num}
          </span>
          {unit && <span className="text-[9px] font-black uppercase tracking-wider shrink-0 text-gray-400">{unit}</span>}
        </div>
        <div className="w-4/5 h-1 bg-white/5 rounded-full overflow-hidden mt-1">
          <div 
            className="h-full transition-all duration-300"
            style={{ width: `${Math.min(100, Math.max(2, progress))}%`, backgroundColor: themeColor, boxShadow: `0 0 6px ${themeColor}80` }}
          />
        </div>
      </div>
    </BaseNode>
  );
});


export const MatrixDistNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const hist = nd?.hist_0 || [];
  const stats = nd?.stats || {};

  const chartData = useMemo(() => {
    return hist.map((v: number, i: number) => ({ x: i, v }));
  }, [hist]);

  const entries = [
    { label: 'Mean',   v: (stats as any).mean,  color: 'text-cyan-400' },
    { label: 'Std Dev', v: (stats as any).std,   color: 'text-purple-400' },
    { label: 'Min',    v: (stats as any).min,   color: 'text-blue-400' },
    { label: 'Max',    v: (stats as any).max,   color: 'text-emerald-400' },
  ];

  const isMinified = !!(data as any)?.minified;

  return (
    <BaseNode
      title="Matrix Distribution"
      icon={BarChart2}
      selected={selected}
      data={data}
      color="accent"
      inputs={[{id: 'data', color: 'any'}]}
      outputs={[
        {id: 'main',   color: 'image'},
        {id: 'bins',   color: 'any'},
        {id: 'counts', color: 'any'},
        {id: 'stats',  color: 'any'},
      ]}
      width="100%"
      height={isMinified ? undefined : "100%"}
      className="w-full h-full"
    >
      <div className="flex-1 min-h-0 w-full flex flex-col p-1">
        <div className="flex-1 min-h-0 w-full">
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                <defs>
                  <linearGradient id="distGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00d4aa" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#00d4aa" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '10px' }}
                  labelStyle={{ display: 'none' }}
                  formatter={(value: any) => [Number(value).toFixed(1), 'Count']}
                />
                <Bar dataKey="v" fill="url(#distGrad)" stroke="#00d4aa" strokeWidth={1} isAnimationActive={false} minPointSize={1} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center opacity-40 gap-2 min-h-[80px]">
              <BarChart2 size={20} className="text-gray-500 animate-pulse" />
              <span className="text-[7px] font-black uppercase tracking-widest text-gray-600">Waiting for Data...</span>
            </div>
          )}
        </div>

        {(stats as any).mean !== undefined && (
          <div className="grid grid-cols-2 gap-1 border-t border-white/5 pt-2 mt-1 shrink-0 px-2 pb-1">
            {entries.map(e => (
              <div key={e.label} className="flex flex-col">
                <span className="text-[7px] text-gray-500 uppercase font-bold tracking-tighter">{e.label}</span>
                <span className={`text-[10px] font-mono ${e.color} tabular-nums`}>{typeof e.v === 'number' ? e.v.toFixed(3) : '---'}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </BaseNode>
  );
});

