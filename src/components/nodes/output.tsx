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

export const OutputDisplayNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  const nd = useNodeData(nodeId) as any;
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];

  useEffect(() => { updateNodeInternals(nodeId); }, [ports.length, nodeId, updateNodeInternals]);

  const inputs = [
    { id: 'main', color: 'image' },
    ...ports.map(p => {
      const idx = p.id.indexOf('__');
      const shortId = idx >= 0 ? p.id.slice(idx + 2) : p.id;
      const color = idx >= 0 ? p.id.slice(0, idx) : (shortId.startsWith('img') ? 'image' : 'any');
      return { id: shortId, color };
    }),
    { id: 'DYNAMIC_NEW_HANDLE', color: 'any' },
    { id: 'mask_in', color: 'mask' },
    { id: 'flow_in', color: 'flow' }
  ];

  return (
    <BaseNode title="Display" icon={Maximize} selected={selected} data={data} color="green" inputs={inputs} outputs={[{id: 'main', color: 'image'}]} />
  );
});

// --- LOGIC & MATH ---


export const OutputMovieNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  const mode = data.params?.mode ?? 0;
  const recording = data.params?.recording ?? false;
  const outputPath = data.params?.output_path || '';
  const frameCount = nd?.frame_count ?? 0;

  const handleBrowse = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const { save: saveDialog } = await import('@tauri-apps/plugin-dialog');
      const selectedPath = await saveDialog({
        defaultPath: mode === 1 ? 'webcam_recording.mp4' : 'export.mp4',
        filters: [{ name: 'Video', extensions: ['mp4'] }]
      });
      if (selectedPath) data.onChangeParams?.({ output_path: selectedPath });
    } catch (err) {
      console.error('Browse error:', err);
    }
  };

  const inputs = mode === 0 ? [{ id: 'image', color: 'image' }] : [];

  return (
    <BaseNode
      title="Movie Export"
      icon={Film}
      selected={selected}
      data={data}
      color={recording ? 'red' : 'accent'}
      inputs={inputs}
      headerExtra={recording ? <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse shrink-0" /> : null}
    >
      <div className="p-2 space-y-2 nodrag">
        {/* Mode tabs */}
        <div className="flex gap-0.5 p-0.5 bg-black/30 rounded-lg">
          {['Stream', 'Webcam'].map((label, i) => (
            <button
              key={i}
              onClick={e => { e.stopPropagation(); data.onChangeParams?.({ mode: i, recording: false }); }}
              className={`flex-1 py-1 rounded text-[8px] font-black uppercase transition-all ${mode === i ? 'bg-accent text-white shadow' : 'text-gray-500 hover:text-gray-300'}`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Output path */}
        <button
          onClick={handleBrowse}
          className="w-full py-1.5 px-2 bg-white/5 hover:bg-white/10 border border-dashed border-white/20 hover:border-white/40 rounded-lg text-left transition-all"
        >
          <div className="text-[7px] text-gray-600 uppercase font-black mb-0.5">Output Path</div>
          <div className="text-[9px] font-mono text-gray-300 truncate">
            {outputPath ? outputPath.split(/[/\\]/).pop() : 'Click to select…'}
          </div>
        </button>

        {/* Record / Stop */}
        <button
          onClick={e => { e.stopPropagation(); data.onChangeParams?.({ recording: !recording }); }}
          className={`w-full py-2.5 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all flex items-center justify-center gap-2 ${
            recording
              ? 'bg-red-500 text-white shadow-lg shadow-red-500/20'
              : 'bg-white/5 border border-white/10 text-gray-400 hover:bg-white/10 hover:text-white'
          }`}
        >
          {recording
            ? <><div className="w-2.5 h-2.5 rounded-sm bg-white" /> Stop</>
            : <><div className="w-2.5 h-2.5 rounded-full bg-red-400" /> Record</>}
        </button>

        {recording && frameCount > 0 && (
          <div className="text-center text-[9px] font-mono text-red-400 animate-pulse">{frameCount} frames captured</div>
        )}
        {!recording && mode === 1 && (
          <div className="text-[8px] text-gray-600 italic text-center leading-tight">Webcam: a Movie node is created on stop</div>
        )}
      </div>
    </BaseNode>
  );
});


export const ExportPyNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];

  // Force ReactFlow to recalculate handle positions when ports change
  useEffect(() => { updateNodeInternals(nodeId); }, [ports.length, nodeId, updateNodeInternals]);

  const inputs = [
    ...ports.map(p => {
      const idx = p.id.indexOf('__');
      return { id: idx >= 0 ? p.id.slice(idx + 2) : p.id, color: idx >= 0 ? p.id.slice(0, idx) : 'any' };
    }),
    { id: 'DYNAMIC_NEW_HANDLE', color: 'any' },
  ];
  return (
    <BaseNode title="Export .py" icon={FileCode} selected={selected} data={data} inputs={inputs} outputs={[]}>
      {ports.length === 0 && (
        <div className="text-[8px] text-gray-600 italic text-center pb-1">connect outputs →</div>
      )}
      <div className="mx-2 mb-2 nodrag">
        <button
          onClick={() => data.onExportPy?.()}
          className="w-full text-[9px] bg-white/5 hover:bg-white/10 text-gray-300 rounded px-2 py-1 border border-white/10 transition-colors"
        >
          Save as…
        </button>
      </div>
    </BaseNode>
  );
});

