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

export const AudioInputNode = memo(({ selected, data }: any) => {
  const nd       = useNodeData(useNodeId());
  const isPlaying = !!(data.params?.playing);
  const duration  = Number(nd?.duration ?? data.params?.duration ?? 0);
  const position  = Number(nd?.position ?? 0);
  const progress  = duration > 0 ? Math.min(position / duration, 1) : 0;

  const handleBrowse = async () => {
    try {
      const selectedFile = await open({
        multiple: false,
        filters: [{ name: 'Audio', extensions: ['wav', 'mp3', 'flac', 'ogg', 'aac', 'm4a', 'aiff'] }]
      });
      if (selectedFile && typeof selectedFile === 'string') {
        data.onChangeParams?.({ path: selectedFile, playing: false, position: 0 });
      }
    } catch (err) {
      console.error('Failed to open audio dialog:', err);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) data.onChangeParams?.({ path: (file as any).path || file.name, playing: false, position: 0 });
  };

  const fileName = data.params?.path?.split('/').pop() || data.params?.path?.split('\\').pop() || '';
  const hasFile  = !!fileName;

  return (
    <BaseNode title="Audio File" icon={Music} selected={selected} data={data} color="indigo"
      outputs={[
        {id: 'audio', color: 'audio', label: 'Audio'},
        {id: 'left',  color: 'audio', label: 'Left'},
        {id: 'right', color: 'audio', label: 'Right'},
        {id: 'mono',  color: 'audio', label: 'Mono'},
        {id: 'sr',       color: 'scalar'},
        {id: 'duration', color: 'scalar'},
        {id: 'position', color: 'scalar'},
      ]}>

      {/* File picker zone ... (unchanged) */}

      {/* File picker zone */}
      {hasFile ? (
        <div className="relative group cursor-pointer mx-2 mb-1" onClick={handleBrowse}
          onDragOver={e => e.preventDefault()} onDrop={onDrop}>
          <div className="flex items-center gap-2 bg-indigo-500/10 px-3 py-2 rounded-xl border border-indigo-500/30 group-hover:border-indigo-400/60 transition-colors">
            <Music size={13} className="text-indigo-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-[9px] text-white/80 font-semibold truncate">{fileName}</div>
              {nd?.sr
                ? <div className="text-[7px] text-indigo-400/60 font-mono">{nd.sr} Hz · {Number(nd.duration ?? 0).toFixed(2)}s</div>
                : <div className="text-[7px] text-gray-600 animate-pulse">Loading…</div>
              }
            </div>
          </div>
          <div className="absolute inset-0 bg-black/60 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity rounded-xl border-2 border-dashed border-indigo-400/50">
            <Search size={14} className="text-white mr-1" />
            <span className="text-[7px] text-white uppercase font-black">Browse / Drop</span>
          </div>
        </div>
      ) : (
        <div className="mx-2 mb-2 flex flex-col items-center justify-center border-2 border-dashed border-indigo-500/30 rounded-xl p-4 opacity-50 hover:opacity-100 transition-opacity cursor-pointer"
          onDragOver={e => e.preventDefault()} onDrop={onDrop} onClick={handleBrowse}>
          <Music size={20} className="text-indigo-400 mb-1.5" />
          <div className="text-[7px] text-indigo-300 uppercase font-black text-center">Click to Browse<br/>or Drop Audio</div>
          <div className="text-[6px] text-gray-600 mt-1">wav · mp3 · flac · ogg · aac</div>
        </div>
      )}

      {/* Progress bar */}
      {hasFile && (
        <div className="mx-2 mb-2">
          <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
            <div className="h-full bg-indigo-500/70 rounded-full transition-all duration-300"
              style={{ width: `${progress * 100}%` }} />
          </div>
          {duration > 0 && (
            <div className="flex justify-between mt-0.5">
              <span className="text-[6px] text-gray-600 font-mono">{position.toFixed(1)}s</span>
              <span className="text-[6px] text-gray-600 font-mono">{duration.toFixed(1)}s</span>
            </div>
          )}
        </div>
      )}

      {/* Transport controls */}
      {hasFile && (
        <div className="mx-2 mb-2 flex items-center justify-center gap-2 nodrag">
          {/* Rewind */}
          <button
            onClick={() => {
              data.onChangeParams?.({ playing: false, rewind: 1 });
              setTimeout(() => data.onChangeParams?.({ rewind: 0 }), 400);
            }}
            className="w-7 h-7 rounded-lg bg-white/5 hover:bg-indigo-500/20 border border-white/10 hover:border-indigo-500/40 flex items-center justify-center transition-all active:scale-95"
            title="Rewind"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" className="text-gray-300">
              <path d="M1 2v6l3.5-3L1 8V2zm4 0v6l3.5-3L5 8V2z"/>
            </svg>
          </button>

          {/* Play / Stop */}
          <button
            onClick={() => data.onChangeParams?.({ playing: !isPlaying })}
            className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all active:scale-95 border font-bold ${
              isPlaying
                ? 'bg-indigo-500/30 border-indigo-400/50 hover:bg-red-500/30 hover:border-red-400/50'
                : 'bg-indigo-500/20 border-indigo-500/40 hover:bg-indigo-500/40'
            }`}
            title={isPlaying ? 'Stop' : 'Play'}
          >
            {isPlaying
              ? <Pause size={14} className="text-indigo-300" />
              : <Play  size={14} className="text-indigo-300" />
            }
          </button>

          {/* Loop toggle */}
          <button
            onClick={() => data.onChangeParams?.({ loop: !data.params?.loop })}
            className={`w-7 h-7 rounded-lg border flex items-center justify-center transition-all active:scale-95 ${
              data.params?.loop
                ? 'bg-indigo-500/30 border-indigo-400/50 text-indigo-300'
                : 'bg-white/5 border-white/10 text-gray-600 hover:text-gray-300 hover:border-white/20'
            }`}
            title="Loop"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M1.5 3.5 C1.5 2.4 2.4 1.5 3.5 1.5 H7 L8.5 3"/>
              <path d="M8.5 6.5 C8.5 7.6 7.6 8.5 6.5 8.5 H3 L1.5 7"/>
              <polyline points="6.5,1.5 8.5,3 6.5,4.5" fill="currentColor" stroke="none"/>
              <polyline points="3.5,8.5 1.5,7 3.5,5.5"  fill="currentColor" stroke="none"/>
            </svg>
          </button>
        </div>
      )}
    </BaseNode>
  );
});


export const AudioToSpectroNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  return (
    <BaseNode title="Audio to Spectro" icon={Waves} selected={selected} data={data} color="indigo" inputs={[{id: 'audio', color: 'audio'}, {id: 'sr', color: 'scalar'}]} outputs={[{id: 'image', color: 'image', label: 'Image'}, {id: 'raw', color: 'image', label: 'Raw'}, {id: 'sr', color: 'scalar', label: 'SR'}]}>
      {nd?.preview && (
        <div className="px-2 pb-2">
          <img src={`data:image/jpeg;base64,${nd.preview}`} className="w-full h-20 object-cover rounded border border-white/10" alt="Spectrogram" />
        </div>
      )}
    </BaseNode>
  );
});


export const SpectroToAudioNode = memo(({ selected, data }: any) => (
  <BaseNode title="Spectro to Audio" icon={Music} selected={selected} data={data} color="indigo"
    inputs={[
      {id: 'image', color: 'image', label: 'Image'},
      {id: 'raw',   color: 'image', label: 'Raw'},
      {id: 'sr',    color: 'scalar', label: 'SR'},
    ]}
    outputs={[
      {id: 'audio', color: 'audio', label: 'Audio'},
      {id: 'left',  color: 'audio', label: 'Left'},
      {id: 'right', color: 'audio', label: 'Right'},
      {id: 'mono',  color: 'audio', label: 'Mono'},
      {id: 'sr',    color: 'scalar'},
    ]}>
    <div className="mx-2 mb-2 nodrag">
      <button
        onClick={() => { data.onChangeParams?.({ run: 1 }); setTimeout(() => data.onChangeParams?.({ run: 0 }), 400); }}
        className="w-full bg-indigo-500/10 hover:bg-indigo-500/30 border border-indigo-500/30 hover:border-indigo-400/60 text-indigo-300 text-[8px] font-black uppercase tracking-widest py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition-all active:scale-95"
      >
        <Play size={9} /> Reconstruct Audio
      </button>
    </div>
  </BaseNode>
));


export const AudioExportNode = memo(({ selected, data }: any) => (
  <BaseNode title="Audio Export" icon={Save} selected={selected} data={data} color="indigo" inputs={[{id: 'audio', color: 'audio'}, {id: 'sr', color: 'scalar'}]} />
));

/** Generic indigo node for audio plugin nodes that don't need a custom UI. */

export const AudioGenericNode = memo(({ selected, data }: any) => {
  const schema = data.schema || { label: 'Audio Node', icon: 'Music', inputs: [], outputs: [] };
  const IconCmp = getIcon(schema.icon, Music);
  return (
    <BaseNode title={data.label || schema.label} icon={IconCmp} selected={selected} data={data} color="indigo" inputs={schema.inputs} outputs={schema.outputs} />
  );
});


export const AudioWaveformNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  return (
    <BaseNode title="Waveform View" icon={Waves} selected={selected} data={data} color="indigo" inputs={[{id: 'audio', color: 'audio'}]} outputs={[{id: 'image', color: 'image'}]}>
      {nd?.preview && (
        <div className="px-2 pb-2">
          <img src={`data:image/jpeg;base64,${nd.preview}`} className="w-full h-16 object-cover rounded border border-indigo-500/20" alt="Waveform" />
        </div>
      )}
    </BaseNode>
  );
});


export const AudioPlaybackNode = memo(({ selected, data }: any) => {
  const nd        = useNodeData(useNodeId());
  const isPlaying = !!(data.params?.playing);
  const duration  = Number(nd?.duration ?? 0);
  const position  = Number(nd?.position ?? 0);
  const progress  = duration > 0 ? Math.min(position / duration, 1) : 0;

  return (
    <BaseNode title="Speaker Out" icon={Volume2} selected={selected} data={data} color="indigo"
      inputs={[{id: 'audio', color: 'audio'}, {id: 'sr', color: 'scalar'}]}
      outputs={[{id: 'position', color: 'scalar'}, {id: 'duration', color: 'scalar'}]}>

      {/* Progress bar */}
      <div className="mx-2 mb-1">
        <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
          <div className="h-full bg-indigo-500/70 rounded-full transition-all duration-300"
            style={{ width: `${progress * 100}%` }} />
        </div>
        {duration > 0 && (
          <div className="flex justify-between mt-0.5">
            <span className="text-[6px] text-gray-600 font-mono">{position.toFixed(1)}s</span>
            <span className="text-[6px] text-gray-600 font-mono">{duration.toFixed(1)}s</span>
          </div>
        )}
      </div>

      {/* Transport controls */}
      <div className="mx-2 mb-2 flex items-center justify-center gap-2 nodrag">
        {/* Rewind */}
        <button
          onClick={() => {
            data.onChangeParams?.({ playing: false, rewind: 1 });
            setTimeout(() => data.onChangeParams?.({ rewind: 0 }), 400);
          }}
          className="w-7 h-7 rounded-lg bg-white/5 hover:bg-indigo-500/20 border border-white/10 hover:border-indigo-500/40 flex items-center justify-center transition-all active:scale-95"
          title="Rewind"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" className="text-gray-300">
            <path d="M1 2v6l3.5-3L1 8V2zm4 0v6l3.5-3L5 8V2z"/>
          </svg>
        </button>

        {/* Play / Pause */}
        <button
          onClick={() => data.onChangeParams?.({ playing: !isPlaying })}
          className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all active:scale-95 border font-bold ${
            isPlaying
              ? 'bg-indigo-500/30 border-indigo-400/50 hover:bg-red-500/30 hover:border-red-400/50'
              : 'bg-indigo-500/20 border-indigo-500/40 hover:bg-indigo-500/40'
          }`}
          title={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying
            ? <Pause size={14} className="text-indigo-300" />
            : <Play  size={14} className="text-indigo-300" />
          }
        </button>

        {/* Loop toggle */}
        <button
          onClick={() => data.onChangeParams?.({ loop: !data.params?.loop })}
          className={`w-7 h-7 rounded-lg border flex items-center justify-center transition-all active:scale-95 ${
            data.params?.loop
              ? 'bg-indigo-500/30 border-indigo-400/50 text-indigo-300'
              : 'bg-white/5 border-white/10 text-gray-600 hover:text-gray-300 hover:border-white/20'
          }`}
          title="Loop"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <path d="M1.5 3.5 C1.5 2.4 2.4 1.5 3.5 1.5 H7 L8.5 3"/>
            <path d="M8.5 6.5 C8.5 7.6 7.6 8.5 6.5 8.5 H3 L1.5 7"/>
            <polyline points="6.5,1.5 8.5,3 6.5,4.5" fill="currentColor" stroke="none"/>
            <polyline points="3.5,8.5 1.5,7 3.5,5.5"  fill="currentColor" stroke="none"/>
          </svg>
        </button>
      </div>
    </BaseNode>
  );
});
