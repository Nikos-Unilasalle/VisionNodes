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

export const InputWebcamNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  return (
    <BaseNode title="Webcam" icon={Camera} selected={selected} data={data} color="green" outputs={[{id: 'main', color: 'image'}]}>
      {nd.width ? (
        <div className="px-1 pb-1">
          <div className="text-[10px] font-mono text-accent font-bold">{nd.width}×{nd.height} · {nd.fps}fps · 8-bit BGR</div>
        </div>
      ) : null}
    </BaseNode>
  );
});


export const InputImageNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  const preview = nd?.preview;
  
  const handleBrowse = async () => {
    try {
      const selectedFile = await open({
        multiple: false,
        filters: [{
          name: 'Image',
          extensions: ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tif', 'tiff']
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
    <BaseNode title="Image File" icon={Image} selected={selected} data={data} color="green" outputs={[{id: 'main', color: 'image'}]}>
      {preview ? (
        <div className="relative group" onClick={handleBrowse}>
          <img 
            src={`data:image/jpeg;base64,${preview}`} 
            alt="Preview" 
            className="w-full h-32 object-cover rounded-lg border border-[#4f5b6b] mb-1" 
          />
          <div 
            className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer rounded-lg border-2 border-dashed border-green-500/50"
            onDragOver={(e) => e.preventDefault()}
            onDrop={onDrop}
          >
            <Search size={20} className="text-white mb-1" />
            <div className="text-[7px] text-white uppercase font-black">Browse / Drop</div>
          </div>
        </div>
      ) : (
        <div 
          className="flex flex-col items-center justify-center border-2 border-dashed border-[#4f5b6b] rounded-lg p-4 opacity-40 hover:opacity-100 transition-opacity cursor-pointer h-32"
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
          onClick={handleBrowse}
        >
          <Search size={20} className="text-gray-500 mb-2" />
          <div className="text-[7px] text-gray-500 uppercase font-black text-center">Click to Browse<br/>or Drop Image</div>
        </div>
      )}
      {nd?.width && (
        <div className="px-1 pt-1">
          <div className="text-[10px] font-mono text-accent font-bold">{nd.width}×{nd.height} · 8-bit BGR</div>
        </div>
      )}
    </BaseNode>
  );
});


export const InputMovieNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  const handleBrowse = async () => {
    try {
      const selectedFile = await open({
        multiple: false,
        filters: [{
          name: 'Video',
          extensions: ['mp4', 'mov', 'avi', 'mkv', 'webm']
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
    <BaseNode title="Movie File" icon={Film} selected={selected} data={data} color="green" outputs={[{id: 'main', color: 'image'}, {id: 'frame', label: 'Frame', color: 'scalar'}]}>
      <div className="p-4 space-y-4" onClick={handleBrowse} onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
        {nd?.preview && (
          <div className="relative group/preview rounded-2xl overflow-hidden border border-white/5 bg-black/10 shadow-inner">
            <img
              src={`data:image/jpeg;base64,${nd.preview}`}
              className="w-full h-auto object-cover opacity-80 group-hover/preview:opacity-100 transition-opacity duration-500"
              alt="Movie Preview"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
            <div className="absolute bottom-2 left-2 right-2">
                <div className="text-[10px] font-black text-white/90 truncate drop-shadow-md flex items-center gap-1.5">
                    <Film size={12} className="text-accent" />
                    {nd.filename || "Movie Loaded"}
                </div>
            </div>
          </div>
        )}

        {!nd?.preview && (
          <div className="py-8 flex flex-col items-center justify-center gap-3 bg-black/10 rounded-2xl border border-dashed border-white/10 opacity-40">
            <div className="p-3 bg-white/5 rounded-full">
                <Video size={24} className="text-gray-400" />
            </div>
            <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">No Media Loaded</div>
          </div>
        )}

        <div className="space-y-3">
          {(nd?.width || nd?.fps) && (
            <div className="p-3 bg-white/5 rounded-2xl border border-white/5">
              <div className="text-[9px] font-black text-gray-500 uppercase tracking-[0.2em] mb-1">Video Info</div>
              <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                {nd?.width && <span className="text-[10px] font-mono text-accent font-bold">{nd.width}×{nd.height}</span>}
                {nd?.fps   && <span className="text-[10px] font-mono text-white/60">{nd.fps} fps</span>}
                {nd?.duration && <span className="text-[10px] font-mono text-white/60">{nd.duration}s</span>}
                <span className="text-[10px] font-mono text-white/30">8-bit</span>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
            <div className={`w-1.5 h-1.5 rounded-full ${data?.params?.playing ? 'bg-green-500 animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.5)]' : 'bg-gray-600'}`} />
            <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">
              {data?.params?.playing ? 'Playing' : 'Paused'}
            </span>
          </div>
            <div className="text-[10px] font-mono text-accent font-bold">
              {nd?.current_frame || 0} / {nd?.total_frames || 0}
            </div>
          </div>
        </div>
      </div>
    </BaseNode>
  );
});


export const ObjDepthMapNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  const thumb: string | undefined = nd?._thumb;
  const error: string | undefined = nd?._error;
  const filePath: string = nd?.path || data.params?.obj_path || '';
  const filename = filePath ? filePath.split(/[\\/]/).pop() : '';

  const handleBrowse = async () => {
    try {
      const file = await open({
        multiple: false,
        filters: [{ name: 'OBJ 3D', extensions: ['obj'] }],
      });
      if (file && typeof file === 'string') data.onChangeParams?.({ obj_path: file });
    } catch {}
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) data.onChangeParams?.({ obj_path: (file as any).path || file.name });
  };

  return (
    <BaseNode title="OBJ Depth Map" icon={Box} selected={selected} data={data} color="accent"
      inputs={[]} outputs={[{ id: 'depth', color: 'image', label: 'Depth' }, { id: 'path', color: 'string', label: 'Path' }]}>
      {thumb ? (
        <div className="relative group" onClick={handleBrowse}>
          <img
            src={`data:image/jpeg;base64,${thumb}`}
            alt="Depth preview"
            className="w-full h-32 object-cover rounded-lg border border-[#4f5b6b] mb-1"
          />
          <div
            className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer rounded-lg border-2 border-dashed border-accent/50"
            onDragOver={e => e.preventDefault()} onDrop={onDrop}
          >
            <Search size={20} className="text-white mb-1" />
            <div className="text-[7px] text-white uppercase font-black">Browse / Drop .obj</div>
          </div>
        </div>
      ) : (
        <div
          className="flex flex-col items-center justify-center border-2 border-dashed border-[#4f5b6b] rounded-lg p-4 opacity-40 hover:opacity-100 transition-opacity cursor-pointer h-32"
          onDragOver={e => e.preventDefault()} onDrop={onDrop} onClick={handleBrowse}
        >
          <Box size={20} className="text-gray-500 mb-2" />
          <div className="text-[7px] text-gray-500 uppercase font-black text-center">Click to Browse<br/>or Drop .obj</div>
        </div>
      )}
      {error && !thumb && (
        <div className="px-1 pt-1">
          <div className="text-[8px] font-mono text-red-400 break-all leading-tight">{error}</div>
        </div>
      )}
      {filename && (
        <div className="px-1 pt-1">
          <div className="text-[9px] font-mono text-accent truncate">{filename}</div>
        </div>
      )}
    </BaseNode>
  );
});


export const SolidColorNode = memo(({ selected, data }: any) => {
  const hex = data.params?.color || '#ff0000';
  return (
    <BaseNode title="Solid Color" icon={Palette} selected={selected} data={data} color="green" outputs={[{id: 'main', color: 'image'}]}>
      <div className="flex justify-center py-1 nodrag">
        <div className="w-10 h-10 rounded-full border-2 border-white/20 shadow-lg" style={{ background: hex, boxShadow: `0 0 16px 2px ${hex}55` }} />
      </div>
    </BaseNode>
  );
});

