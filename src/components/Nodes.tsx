import React, { memo, useState, useMemo, useEffect } from 'react';
import { Handle, Position, useNodeId, useEdges } from 'reactflow';
import { useNodeData } from '../context/NodesDataContext';
import { open, save } from '@tauri-apps/plugin-dialog';
import {
  Camera, Waves, Ghost, Maximize, Search, User, Zap, Activity,
  Hash, Eye, Layout, PenTool, Database, Wind, Target, Palette, Scaling, Move, Layers, Box, Image, Film, Play, Pause,
  Plus, Info, Save, FolderOpen, BookOpen, Video, Type, Calculator, PlusSquare, Minus, Divide, Scissors, Keyboard, HelpCircle, ChevronDown, ChevronUp,
  Crosshair, Monitor, Lock, LockOpen, Crop, Filter, Package, LogIn, LogOut, BarChart2, Music, Volume2, RotateCcw, Repeat, Download
} from 'lucide-react';
import * as LucideIcons from 'lucide-react';

const getIcon = (name: string, fallback = Box) => {
  if (!name) return fallback;
  const icon = (LucideIcons as any)[name];
  return icon || fallback;
};
import {
  AreaChart, Area, ResponsiveContainer, YAxis, XAxis, Tooltip,
  BarChart, Bar, Cell, LineChart, Line
} from 'recharts';

export const HANDLE_COLORS = { image: '#3b82f6', data: '#f97316', dict: '#22c55e', list: '#a855f7', scalar: '#eab308', string: '#7dd3fc', mask: '#d1d5db', flow: '#ef4444', boolean: '#22d3ee', any: '#ffffff', geotiff: '#059669', audio: '#818cf8' };

const NodeColorContext = React.createContext<{ customBg?: string; customText?: string }>({});
export const useNodeColor = () => React.useContext(NodeColorContext);
export const NodeColorProvider = NodeColorContext.Provider;

const StyledHandle = ({ type, position, id, color = 'image', top = '50%' }: any) => {
  const nodeId = useNodeId();
  const handleId = `${color}__${id}`;
  const isLeft = position === Position.Left;
  
  return (
    <Handle
      type={type}
      position={position}
      id={handleId}
      style={{ 
        background: HANDLE_COLORS[color as keyof typeof HANDLE_COLORS] || color, 
        width: 10, 
        height: 10, 
        border: '2px solid #111', 
        top: top,
        [isLeft ? 'left' : 'right']: -5,
        zIndex: 50,
        position: 'absolute'
      }}
      onClick={(e) => {
        e.stopPropagation();
        window.dispatchEvent(new CustomEvent('remove-handle-edge', { detail: { nodeId, handleId, type } }));
      }}
    />
  );
};

const BaseNode = ({ title, icon: Icon, children, selected, data, color = 'accent', inputs = [], outputs = [], var_count = 0, width, headerExtra }: any) => {
  const { customBg: ctxBg, customText: ctxText } = useNodeColor();
  const palIdx = data?.activePaletteIndex ?? 6;
  const cIdx = data?.params?.color_index;
  const computedBg = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.bg : data?.params?.bg_color;
  const computedText = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.dark : data?.params?.text_color;
  const customBg = ctxBg ?? computedBg;
  const customText = ctxText ?? computedText;

  const accentColor = color === 'accent' ? 'border-accent shadow-accent/20' : 
                      color === 'green' ? 'border-green-500 shadow-green-500/20' :
                      color === 'blue' ? 'border-blue-500 shadow-blue-500/20' :
                      color === 'red' ? 'border-red-500 shadow-red-500/20' :
                      color === 'indigo' ? 'border-indigo-500 shadow-indigo-500/20' :
                      'border-gray-500 shadow-gray-500/20';
                      
  const borderClass = customBg ? '' : (selected ? accentColor : 'border-[#4f5b6b]');

  const totalInputs = inputs.length + var_count;
  const totalOutputs = outputs.length;
  const maxPorts = Math.max(totalInputs, totalOutputs);
  
  const startOffset = 45;
  const spacing = 32;
  const portsHeight = maxPorts > 0 ? (startOffset + (maxPorts - 1) * spacing + 35) : 90;
  const minHeight = Math.max(portsHeight, 90);

  const getPortTop = (index: number, total: number) => {
    if (total === 0) return '50%';
    return `${45 + index * 32}px`;
  };

  const nodeNote = data?.params?.node_note;

  return (
    <div className="relative" style={width ? { width: typeof width === 'number' ? `${width}px` : width } : { width: '13rem' }}>
    <div
        className={`rounded-xl bg-[#2c333f] border-2 transition-all duration-300 ${borderClass} ${selected ? 'shadow-lg scale-105' : ''} shadow-2xl relative w-full`}
        style={{
          minHeight,
          ...(customBg ? { borderColor: customBg, boxShadow: selected ? `0 10px 15px -3px ${customBg}40` : `0 0 10px ${customBg}10` } : {}),
        }}
    >
      {/* Inputs with Labels */}
      {inputs.map((inp: any, i: number) => {
        const top = getPortTop(i, totalInputs);
        return (
          <div key={inp.id} className="absolute left-0 w-full flex items-center pointer-events-none" style={{ top, transform: 'translateY(-50%)' }}>
            <StyledHandle type="target" position={Position.Left} id={inp.id} color={inp.color} top="50%" />
            <span className="ml-[12px] text-[7px] font-medium text-gray-500 uppercase tracking-tighter opacity-80">{inp.id}</span>
          </div>
        );
      })}
      
      {/* Dynamic Variables with Labels */}
      {Array.from({ length: var_count }).map((_, i) => {
        const char = String.fromCharCode(97 + i);
        const top = getPortTop(inputs.length + i, totalInputs);
        return (
          <div key={char} className="absolute left-0 w-full flex items-center pointer-events-none" style={{ top, transform: 'translateY(-50%)' }}>
            <StyledHandle type="target" position={Position.Left} id={char} color="scalar" top="50%" />
            <span className="ml-[12px] text-[8px] font-medium text-accent uppercase tracking-widest">{char}</span>
          </div>
        );
      })}

      <div className="bg-[#3d4452] px-4 py-2 flex items-center justify-between border-b border-[#4f5b6b] rounded-t-[10px] overflow-hidden group/header"
           style={customBg ? { backgroundColor: `${customBg}20`, borderBottomColor: `${customBg}40` } : {}}>
        <div className="flex items-center gap-3 truncate">
          <Icon size={14} className="shrink-0 transition-colors" style={customBg ? { color: customBg } : {}} />
          <span className="font-bold text-[10px] uppercase tracking-widest truncate" style={customBg ? { color: customBg } : { color: '#e5e7eb' }}>{title}</span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {data?.isVisualized && <Eye size={11} className="text-yellow-400 animate-pulse" />}
          {headerExtra}
        </div>
      </div>
      
      <div className="p-2 text-[10px] text-gray-400 flex flex-col gap-2">
        {children}
      </div>

      {/* Outputs with Labels */}
      {outputs.map((out: any, i: number) => {
        const top = getPortTop(i, totalOutputs);
        return (
          <div key={out.id} className="absolute right-0 w-full flex items-center justify-end pointer-events-none" style={{ top, transform: 'translateY(-50%)' }}>
            <span className="mr-[12px] text-[7px] font-medium text-gray-500 uppercase tracking-tighter opacity-80">{out.id}</span>
            <StyledHandle type="source" position={Position.Right} id={out.id} color={out.color} top="50%" />
          </div>
        );
      })}
    </div>
    {nodeNote && (
      <div className="absolute left-0 right-0 top-full mt-1 text-center text-[9px] text-gray-400/80 truncate px-2 pointer-events-none select-none">
        {nodeNote}
      </div>
    )}
    </div>
  );
};

// --- NODES ---
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

export const SolidColorNode = memo(({ selected, data }: any) => {
  const r = data.params?.r ?? 255;
  const g = data.params?.g ?? 0;
  const b = data.params?.b ?? 0;
  const hex = `rgb(${r},${g},${b})`;
  return (
    <BaseNode title="Solid Color" icon={Palette} selected={selected} data={data} color="green" outputs={[{id: 'main', color: 'image'}]}>
      <div className="flex justify-center py-1 nodrag">
        <div className="w-10 h-10 rounded-full border-2 border-white/20 shadow-lg" style={{ background: hex, boxShadow: `0 0 16px 2px ${hex}55` }} />
      </div>
    </BaseNode>
  );
});

export const FilterCannyNode = memo(({ selected, data }: any) => (
  <BaseNode title="Canny Edge" icon={Waves} selected={selected} data={data} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const FilterBlurNode = memo(({ selected, data }: any) => (
  <BaseNode title="Blur" icon={Ghost} selected={selected} data={data} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const FilterThresholdNode = memo(({ selected, data }: any) => (
  <BaseNode title="Threshold" icon={Waves} selected={selected} data={data} color="blue" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'main', color: 'image'}, {id: 'mask', color: 'mask'}]} />
));

export const FilterColorMaskNode = memo(({ selected, data }: any) => (
  <BaseNode title="Color Mask" icon={Palette} selected={selected} data={data} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'mask', color: 'mask'}]} />
));

export const FilterGrayNode = memo(({ selected, data }: any) => (
  <BaseNode title="Grayscale" icon={Eye} selected={selected} data={data} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const FilterMorphologyNode = memo(({ selected, data }: any) => (
  <BaseNode title="Morphology" icon={Waves} selected={selected} data={data} color="accent" inputs={[{id: 'mask', color: 'mask'}, {id: 'image', color: 'image'}]} outputs={[{id: 'mask', color: 'mask'}]} />
));

export const GeomFlipNode = memo(({ selected, data }: any) => (
  <BaseNode title="Flip" icon={Move} selected={selected} data={data} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const GeomResizeNode = memo(({ selected, data }: any) => (
  <BaseNode title="Resize" icon={Scaling} selected={selected} data={data} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]}>
    {data.node_data?.width && (
      <div className="px-1 pt-1">
        <div className="text-[10px] font-mono text-blue-400 font-bold">{data.node_data.width}×{data.node_data.height}</div>
      </div>
    )}
  </BaseNode>
));

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
    inputs={[{id: '3Dvector', color: 'dict'}, {id: 'image', color: 'image'}]}
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

  return (
    <BaseNode
      title="Raster Stats"
      icon={Activity}
      selected={selected}
      data={data}
      color="blue"
      inputs={[{id: 'geotiff', color: 'geotiff'}]}
      outputs={[
        {id: 'geotiff', color: 'geotiff'},
        {id: 'min',     color: 'scalar'},
        {id: 'max',     color: 'scalar'},
        {id: 'mean',    color: 'scalar'}
      ]}
    >
      <div className="flex flex-col gap-3 p-1">
        <div className="text-[7px] font-black text-blue-400 uppercase tracking-[0.2em] px-1 flex justify-between">
            <span>Global Band Analysis</span>
            <span>Band {band}</span>
        </div>
        
        <div className="bg-blue-500/5 border border-blue-500/10 rounded-2xl p-4 flex flex-col items-center justify-center gap-1 shadow-inner relative overflow-hidden">
            <span className="text-[7px] font-black text-gray-500 uppercase tracking-widest z-10">Mean Value</span>
            <span className="text-3xl font-black text-blue-400 font-mono tracking-tighter z-10 drop-shadow-md">
                {mean.toFixed(4)}
            </span>
            <Activity size={48} className="absolute -right-4 -bottom-4 text-blue-500/5" />
        </div>

        <div className="grid grid-cols-3 gap-2">
            <div className="bg-black/20 border border-white/5 rounded-xl p-2 flex flex-col items-center shadow-inner">
                <span className="text-[6px] text-gray-600 uppercase font-black">Min</span>
                <span className="text-[10px] font-bold text-white/60 font-mono">{min.toFixed(2)}</span>
            </div>
            <div className="bg-black/20 border border-white/5 rounded-xl p-2 flex flex-col items-center shadow-inner">
                <span className="text-[6px] text-gray-600 uppercase font-black">Max</span>
                <span className="text-[10px] font-bold text-white/60 font-mono">{max.toFixed(2)}</span>
            </div>
            <div className="bg-black/20 border border-white/5 rounded-xl p-2 flex flex-col items-center shadow-inner">
                <span className="text-[6px] text-gray-600 uppercase font-black">Std</span>
                <span className="text-[10px] font-bold text-blue-400/60 font-mono">{std.toFixed(2)}</span>
            </div>
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
      outputs={[{ id: 'main', color: 'image' }, { id: 'width', color: 'scalar' }, { id: 'height', color: 'scalar' }]}
    >
      <div className="flex flex-col gap-3 nodrag">
        <div className="relative bg-black rounded-xl overflow-hidden border border-white/5 group/crop shadow-inner">
          {frame ? (
            <img src={`data:image/jpeg;base64,${frame}`} className="w-full h-auto block opacity-60 grayscale-[50%]" alt="Crop Preview" />
          ) : (
            <div className="w-full aspect-video flex items-center justify-center text-gray-800">
              <Crop size={24} className="opacity-10" />
            </div>
          )}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 w-full h-full overflow-visible">
              <rect x={rect.x} y={rect.y} width={rect.w} height={rect.h}
                className="fill-accent/20 stroke-accent" style={{ strokeWidth: 0.012, vectorEffect: 'non-scaling-stroke' }} />
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

export const DrawOverlayNode = memo(({ selected, data }: any) => (
  <BaseNode title="Overlay" icon={PenTool} selected={selected} data={data} color="accent" inputs={[
    {id: 'image', color: 'image'},
    {id: 'data', color: 'any'},
    {id: 'data_2', color: 'any'},
    {id: 'data_3', color: 'any'},
    {id: 'data_4', color: 'any'}
  ]} outputs={[{id: 'main', color: 'image'}]} />
));

// Recursive Component to render JSON with colors
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
  const d = useNodeData(useNodeId())?.data_out;
  const [filterKey, setFilterKey] = useState<string | null>(data?.params?.filter_key ?? null);
  const { customBg } = useNodeColor();
  const accentBorder = customBg ? '' : (selected ? 'border-accent shadow-accent/20 shadow-lg' : 'border-[#4f5b6b]');

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

  return (
    <div
      className={`w-full h-full rounded-xl bg-[#2c333f] border-2 ${accentBorder} shadow-2xl flex flex-col overflow-hidden transition-all duration-300`}
      style={{ position: 'relative', zIndex: 0, ...(customBg ? { borderColor: customBg, boxShadow: selected ? `0 10px 15px -3px ${customBg}40` : `0 0 10px ${customBg}10` } : {}) }}
    >
      <div className="absolute left-0 flex items-center pointer-events-none" style={{ top: '50%', transform: 'translateY(-50%)' }}>
        <StyledHandle type="target" position={Position.Left} id="data" color="any" top="50%" />
      </div>

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
      <div className="flex-1 overflow-auto scrollbar-hide p-2.5 min-h-0">
        <JsonTreeView data={displayData} />
      </div>
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
    {id: 'x', color: 'scalar'}, {id: 'y', color: 'scalar'}, {id: 'w', color: 'scalar'}, {id: 'h', color: 'scalar'}
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

export const UtilMaskBlendNode = memo(({ selected, data }: any) => (
  <BaseNode title="Mask Blend" icon={Layers} selected={selected} data={data} color="accent" inputs={[
    {id: 'image_a', color: 'image'},
    {id: 'image_b', color: 'image'},
    {id: 'mask', color: 'mask'}
  ]} outputs={[{id: 'main', color: 'image'}]} />
));

export const OutputDisplayNode = memo(({ selected, data }: any) => (
  <BaseNode title="Display" icon={Maximize} selected={selected} data={data} color="green" inputs={[
    {id: 'main', color: 'image'},
    {id: 'mask_in', color: 'mask'},
    {id: 'flow_in', color: 'flow'}
  ]} />
));

// --- LOGIC & MATH ---

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
  const code = data.params?.code || '';
  const lines = code.split('\n').map(l => l.trim());
  const firstComment = lines.find(l => l.startsWith('#'));
  const displayLine = firstComment || lines.find(l => l !== '') || '';

  return (
    <BaseNode title="Python Script" icon={Zap} selected={selected} data={data} color="red"
              inputs={[{id: 'a', color: 'any'}, {id: 'b', color: 'any'}, {id: 'c', color: 'any'}, {id: 'd', color: 'any'}]}
              outputs={[{id: 'main', color: 'image'}, {id: 'out_scalar', color: 'scalar'}, {id: 'out_list', color: 'list'}, {id: 'out_dict', color: 'dict'}, {id: 'out_any', color: 'any'}]}>
      {displayLine && (
        <div className="self-center w-fit max-w-[140px] flex items-center justify-center bg-black/10 rounded-lg px-3 py-2 border border-white/5 shadow-inner">
          <div className="text-[7px] font-mono text-emerald-400/70 truncate text-center italic">{displayLine}</div>
        </div>
      )}
    </BaseNode>
  );
});



// --- SCIENTIFIC NODES ---

export const ScientificPlotterNode = memo(({ selected, data }: any) => {
  const { customBg } = useNodeColor();
  const palIdx = data?.activePaletteIndex ?? 6;
  const SERIES_COLORS = PALETTES[palIdx].colors.map((c: any) => c.bg);
  const KEYS = ['v0', 'v1', 'v2', 'v3', 'v4'];
  const nd = useNodeData(useNodeId());
  const bufSize = Number(data.params?.buffer_size ?? 100);
  const frozen = !!data.params?.freeze;

  const [histories, setHistories] = React.useState<Record<string, number[]>>({});

  React.useEffect(() => {
    if (frozen) return;
    setHistories(prev => {
      const next: Record<string, number[]> = { ...prev };
      let changed = false;
      for (const k of KEYS) {
        const v = (nd as any)[k];
        if (v === undefined || v === null) continue;
        if (typeof v === 'number') {
          const cur = prev[k] ?? [];
          if (cur.length === 0 || cur[cur.length - 1] !== v) {
            next[k] = [...cur, v].slice(-bufSize);
            changed = true;
          }
        } else if (Array.isArray(v)) {
          next[k] = (v as any[]).map(Number).filter((n: number) => !isNaN(n)).slice(-bufSize);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [nd.v0, nd.v1, nd.v2, nd.v3, nd.v4, bufSize, frozen]);

  const chartData = React.useMemo(() => {
    const maxLen = Math.max(0, ...KEYS.map(k => histories[k]?.length ?? 0));
    if (maxLen === 0) return [];
    return Array.from({ length: maxLen }, (_, i) => {
      const pt: any = { t: i };
      for (const k of KEYS) {
        const arr = histories[k];
        if (arr && i < arr.length) pt[k] = arr[i];
      }
      return pt;
    });
  }, [histories]);

  const activeSeries = KEYS.filter(k => (histories[k]?.length ?? 0) > 0);
  const PORT_TOPS = ['20%', '35%', '50%', '65%', '80%'];
  const minY = data.params?.min_y;
  const maxY = data.params?.max_y;
  const yDomain: [any, any] = (minY !== undefined && maxY !== undefined && minY !== maxY) ? [minY, maxY] : ['auto', 'auto'];

  return (
    <div
      className={`w-full h-full rounded-xl bg-[#3d4452] border-2 shadow-2xl flex flex-col overflow-hidden transition-all duration-300 ${customBg ? '' : (selected ? 'border-accent shadow-accent/20 shadow-lg' : 'border-[#4f5b6b]')}`}
      style={customBg ? { borderColor: customBg, boxShadow: selected ? `0 10px 15px -3px ${customBg}40` : `0 0 10px ${customBg}10` } : {}}
    >
        {KEYS.map((k, i) => (
          <div key={`in-${k}`} className="absolute left-0 pointer-events-none"
               style={{ top: PORT_TOPS[i], transform: 'translateY(-50%)' }}>
            <StyledHandle type="target" position={Position.Left} id={k} color="any" top="50%" />
          </div>
        ))}
        {KEYS.map((k, i) => (
          <div key={`out-${k}`} className="absolute right-0 flex items-center justify-end pointer-events-none"
               style={{ top: PORT_TOPS[i], transform: 'translateY(-50%)' }}>
            <span className="mr-[12px] text-[7px] font-bold uppercase" style={{ color: SERIES_COLORS[i] }}>{k}</span>
            <StyledHandle type="source" position={Position.Right} id={k} color="any" top="50%" />
          </div>
        ))}
        <div className="bg-[#3d4452] px-3 py-1.5 flex items-center gap-2 border-b border-[#4f5b6b] rounded-t-xl shrink-0"
             style={customBg ? { backgroundColor: `${customBg}20`, borderBottomColor: `${customBg}40` } : {}}>
          <Activity size={12} className="shrink-0" style={customBg ? { color: customBg } : { color: '#22d3ee' }} />
          <span className="text-[10px] font-bold uppercase tracking-widest" style={customBg ? { color: customBg } : { color: '#ffffff' }}>Plotter</span>
          <div className="ml-auto flex items-center gap-2">
            {activeSeries.map(k => (
              <div key={k} className="w-1.5 h-1.5 rounded-full opacity-80"
                   style={{ backgroundColor: SERIES_COLORS[KEYS.indexOf(k)] }} />
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
        <div className="flex-1 min-h-0 w-full px-1 py-1">
          {chartData.length === 0
            ? <div className="w-full h-full flex items-center justify-center">
                <span className="text-[8px] text-gray-700 uppercase tracking-widest">connect data</span>
              </div>
            : <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 2, right: 18, bottom: 0, left: 0 }}>
                  <YAxis hide domain={yDomain} />
                  {activeSeries.map(k => (
                    <Line key={k} type="monotone" dataKey={k}
                      stroke={SERIES_COLORS[KEYS.indexOf(k)]} strokeWidth={1.5}
                      dot={false} isAnimationActive={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
          }
        </div>
      </div>
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

export const UtilCSVExportNode = memo(({ selected, data }: any) => {
  const handleBrowse = async () => {
    try {
      const selected = await save({
        filters: [{ name: 'CSV', extensions: ['csv'] }]
      });
      if (selected && typeof selected === 'string') {
        const lastSlash = Math.max(selected.lastIndexOf('/'), selected.lastIndexOf('\\'));
        const path = selected.substring(0, lastSlash);
        let filename = selected.substring(lastSlash + 1);
        if (filename.toLowerCase().endsWith('.csv')) {
          filename = filename.substring(0, filename.length - 4);
        }
        data.onChangeParams?.({ path, filename });
      }
    } catch (err) {
      console.error('Failed to open dialog:', err);
    }
  };

  const statusDot = (
    <div className={`w-2.5 h-2.5 rounded-full ${data.params?.record ? 'bg-red-500 animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.6)]' : 'bg-gray-600'}`} />
  );

  return (
    <BaseNode 
      title="CSV Export" 
      icon={Database} 
      selected={selected} 
      data={data}
      color="accent" 
      inputs={data.schema?.inputs || []}
      headerExtra={statusDot}
    >
      <div className="p-3 space-y-3 mx-6">
        <button 
          onClick={handleBrowse}
          className="w-full py-4 bg-accent/10 hover:bg-accent/20 border border-dashed border-accent/30 rounded-2xl flex flex-col items-center justify-center gap-2 transition-all group"
        >
          <FolderOpen size={20} className="text-accent group-hover:scale-110 transition-transform" />
          <div className="text-[10px] font-black text-accent uppercase tracking-widest text-center">Select Export Path</div>
        </button>
        
        <div className="space-y-4">
          <div className="px-3 py-2.5 bg-black/10 rounded-xl border border-white/5 flex flex-col gap-1 shadow-inner">
            <div className="text-[9px] font-mono text-gray-400 truncate">{data.params?.path || "Not selected"}</div>
          </div>
          <div className="px-3 py-2.5 bg-black/10 rounded-xl border border-white/5 flex flex-col gap-1 shadow-inner">
            <div className="text-[9px] font-mono text-white/70 truncate">{data.params?.filename || "capture"}.csv</div>
          </div>
        </div>
      </div>
    </BaseNode>
  );
});

export const PALETTES = [
  {
    name: 'Astro',
    colors: [
      { bg: '#2B2B85', dark: '#ffffff' },
      { bg: '#5C5EDC', dark: '#ffffff' },
      { bg: '#8A8DF6', dark: '#111111' },
      { bg: '#BBAEFE', dark: '#111111' },
      { bg: '#FEADFE', dark: '#111111' }
    ]
  },
  {
    name: 'Moon',
    colors: [
      { bg: '#EAE9F5', dark: '#111111' },
      { bg: '#B3C3DE', dark: '#111111' },
      { bg: '#7698C3', dark: '#ffffff' },
      { bg: '#486B8E', dark: '#ffffff' },
      { bg: '#29405C', dark: '#ffffff' }
    ]
  },
  {
    name: 'Florest Moth',
    colors: [
      { bg: '#4A5D23', dark: '#ffffff' },
      { bg: '#8F994B', dark: '#111111' },
      { bg: '#C1C881', dark: '#111111' },
      { bg: '#EAE6AA', dark: '#111111' },
      { bg: '#E0AA90', dark: '#111111' }
    ]
  },
  {
    name: 'Cyberpunk Dreams',
    colors: [
      { bg: '#FF127B', dark: '#ffffff' },
      { bg: '#C21584', dark: '#ffffff' },
      { bg: '#741A8E', dark: '#ffffff' },
      { bg: '#3C1361', dark: '#ffffff' },
      { bg: '#1D0A35', dark: '#ffffff' }
    ]
  },
  {
    name: 'Night Winter',
    colors: [
      { bg: '#111F36', dark: '#ffffff' },
      { bg: '#234476', dark: '#ffffff' },
      { bg: '#406E9E', dark: '#ffffff' },
      { bg: '#7DABC6', dark: '#111111' },
      { bg: '#C8E2ED', dark: '#111111' }
    ]
  },
  {
    name: '90s Anime',
    colors: [
      { bg: '#FF645F', dark: '#ffffff' },
      { bg: '#FFAD48', dark: '#111111' },
      { bg: '#FFDE87', dark: '#111111' },
      { bg: '#6FA4D2', dark: '#111111' },
      { bg: '#5D4585', dark: '#ffffff' }
    ]
  },
  {
    name: 'Original VN',
    colors: [
      { bg: '#a8e6cf', dark: '#1a3d2e' },
      { bg: '#dcedbf', dark: '#2a3a1a' },
      { bg: '#ffd4b8', dark: '#3a2010' },
      { bg: '#ffa8a3', dark: '#3a1010' },
      { bg: '#ff667d', dark: '#1a0a0a' }
    ]
  }
];

const _noteHash = (s: string) => { let h = 0; for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0; return Math.abs(h); };

export const CanvasNoteNode = memo(({ selected, data }: any) => {
  const [editing, setEditing] = useState(false);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  const text = data.params?.text ?? '';
  const palIdx = data?.activePaletteIndex ?? 6;
  const cIdx = data?.params?.color_index;
  const bgColor = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.bg : (data?.params?.bg_color || '#ffd4b8');
  const textColor = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.dark : (data?.params?.text_color || '#3a2010');

  // Deterministic tilt from node id — fixed per note, never changes
  const rotation = ((_noteHash(data.id || '') % 9) - 4) * 0.35; // -1.4° to +1.4°

  React.useEffect(() => {
    if (editing) textareaRef.current?.focus();
  }, [editing]);

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditing(true);
  };

  return (
    <div
      className="w-full h-full overflow-hidden transition-all duration-200"
      style={{
        background: bgColor,
        borderRadius: '5px 5px 0 0',
        transform: `rotate(${rotation}deg)`,
        boxShadow: selected
          ? `5px 8px 24px rgba(0,0,0,0.38), 2px 3px 8px rgba(0,0,0,0.22), 0 0 0 2px rgba(0,0,0,0.25)`
          : `4px 6px 18px rgba(0,0,0,0.28), 2px 3px 6px rgba(0,0,0,0.16)`,
      }}
      onDoubleClick={handleDoubleClick}
    >
      {/* Header — chapeau style + macOS square button */}
      <div
        className="flex items-center gap-1.5 px-2 py-1 nodrag select-none"
        style={{ background: 'rgba(0,0,0,0.13)', borderBottom: '1px solid rgba(0,0,0,0.10)' }}
      >
        {/* Old macOS square window button */}
        <div
          className="w-2.5 h-2.5 rounded-[2px] flex-shrink-0"
          style={{ background: 'rgba(255,255,255,0.30)', border: '1px solid rgba(0,0,0,0.18)' }}
        />
        <span
          className="text-[8px] font-black uppercase tracking-[0.18em] truncate flex-1"
          style={{ color: `${textColor}88` }}
        >
          Note
        </span>
      </div>

      {/* Body */}
      {editing ? (
        <textarea
          ref={textareaRef}
          value={text}
          onChange={e => data.onChangeParams?.({ text: e.target.value })}
          onBlur={() => setEditing(false)}
          onKeyDown={e => {
            if (e.key === 'Escape') setEditing(false);
            e.stopPropagation();
          }}
          className="nodrag nopan w-full bg-transparent border-none outline-none resize-none px-3 py-2 leading-relaxed"
          style={{ color: textColor, fontSize: 13, fontFamily: 'inherit', fontWeight: 400, caretColor: textColor, height: 'calc(100% - 26px)' }}
          placeholder="Write your note here..."
        />
      ) : (
        <div
          className="px-3 py-2 overflow-hidden select-none cursor-text"
          style={{
            color: text ? textColor : `${textColor}55`,
            fontSize: 13,
            fontWeight: 400,
            lineHeight: '1.65',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontStyle: text ? 'normal' : 'italic',
            height: 'calc(100% - 26px)',
          }}
        >
          {text || 'Double-click to edit…'}
        </div>
      )}
    </div>
  );
});

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

const GeoTIFFReaderNode = memo(({ selected, data }: any) => {
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

const GeoEarthEngineNode = memo(({ selected, data }: any) => {
  const nd = useNodeData(useNodeId());
  const thumbRef = React.useRef<string>('');
  if (nd?._thumb) thumbRef.current = nd._thumb;
  const thumb = thumbRef.current;
  const schema = data.schema;
  const IconCmp = getIcon('Map', Box);
  const outputs = schema?.outputs || [{ id: 'geotiff', color: 'geotiff' }, { id: 'preview', color: 'image' }, { id: 'meta', color: 'dict' }];

  return (
    <BaseNode title="Earth Engine Source" icon={IconCmp} selected={selected} data={data} color="green" inputs={[]} outputs={outputs}>
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

const GeoBandInfoNode = memo(({ selected, data }: any) => {
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

export const GenericCustomNode = memo(({ selected, data }: any) => {
  const schema = data.schema || { label: 'Unknown Plugin', icon: 'Box', inputs: [], outputs: [] };
  const IconCmp = getIcon(schema.icon, Box);

  if (schema.type === 'sci_plotter') return <ScientificPlotterNode selected={selected} data={data} />;
  if (schema.type === 'sci_stats') return <ScientificStatsNode selected={selected} data={data} />;
  if (schema.type === 'draw_text') return <DrawTextNode selected={selected} data={data} />;
  if (schema.type === 'util_csv_export') return <UtilCSVExportNode selected={selected} data={data} />;
  if (schema.type === 'geo_geotiff_reader') return <GeoTIFFReaderNode selected={selected} data={data} />;
  if (schema.type === 'geo_earth_engine') return <GeoEarthEngineNode selected={selected} data={data} />;
  if (schema.type === 'geo_band_info') return <GeoBandInfoNode selected={selected} data={data} />;
  if (schema.type === 'geo_land_cover') return <GeoLandCoverNode selected={selected} data={data} />;

  const outputs = data.dynamicColor 
    ? schema.outputs.map((out: any) => ({ ...out, color: data.dynamicColor }))
    : schema.outputs;

  return (
    <BaseNode title={data.label || schema.label} icon={IconCmp} selected={selected} data={data} color="accent" inputs={schema.inputs} outputs={outputs}>
    </BaseNode>
  );
});

export const CanvasFrameNode = memo(({ selected, data }: any) => {
  const [editing, setEditing] = useState(false);
  const title = data.params?.title ?? 'Frame Layer';
  const palIdx = data?.activePaletteIndex ?? 6;
  const cIdx = data?.params?.color_index;
  const bgColor = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.bg : (data?.params?.bg_color || '#333333');
  const textColor = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.dark : (data?.params?.text_color || '#ffffff');

  return (
    <div
      className="w-full h-full rounded-xl border-2 group/frame transition-all flex flex-col overflow-hidden"
      style={{ borderColor: bgColor, backgroundColor: `${bgColor}15` }}
    >
      <div
        className="px-4 py-2 font-black text-xs uppercase tracking-widest truncate cursor-text select-none"
        style={{ backgroundColor: bgColor, color: textColor }}
        onDoubleClick={(e) => { e.stopPropagation(); setEditing(true); }}
      >
        {editing ? (
          <input
            autoFocus
            className="bg-black/10 w-full outline-none px-1 py-0.5 rounded"
            style={{ color: textColor }}
            value={title}
            onChange={e => data.onChangeParams?.({ title: e.target.value })}
            onBlur={() => setEditing(false)}
            onKeyDown={e => {
              if (e.key === 'Enter' || e.key === 'Escape') setEditing(false);
              e.stopPropagation();
            }}
          />
        ) : (
          title
        )}
      </div>
      <div className="flex-1 pointer-events-none" />
    </div>
  );
});

// ──────────────────────────────────────────────────────────────
// GROUP NODES
// ──────────────────────────────────────────────────────────────

export const GroupNode = memo(({ selected, data }: any) => {
  const rawInputs: { id: string; color: string }[] = data?.inputs ?? [];
  const rawOutputs: { id: string; color: string }[] = data?.outputs ?? [];
  const label = data?.params?.label || data?.label || 'Group';

  const splitPort = (p: { id: string; color: string }) => {
    const idx = p.id.indexOf('__');
    return { id: idx >= 0 ? p.id.slice(idx + 2) : p.id, color: idx >= 0 ? p.id.slice(0, idx) : 'any' };
  };

  const inputs = rawInputs.map(splitPort);
  const outputs = rawOutputs.map(splitPort);

  return (
    <BaseNode
      title={label}
      icon={Package}
      selected={selected}
      data={data}
      inputs={inputs}
      outputs={outputs}
      headerExtra={<span className="text-[8px] text-gray-600 font-mono">GROUP</span>}
    >
      <div className="text-[8px] text-gray-600 italic text-center py-0.5">⌥ double-click to enter</div>
    </BaseNode>
  );
});

export const GroupInputNode = memo(({ selected, data }: any) => {
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];
  const outputs = ports.map(p => {
    const idx = p.id.indexOf('__');
    return { id: idx >= 0 ? p.id.slice(idx + 2) : p.id, color: idx >= 0 ? p.id.slice(0, idx) : 'any' };
  });
  return (
    <BaseNode title="Group IN" icon={LogIn} selected={selected} data={data} outputs={outputs} inputs={[]}>
      {ports.length === 0 && <div className="text-[8px] text-gray-600 italic text-center">no inputs</div>}
    </BaseNode>
  );
});

export const GroupOutputNode = memo(({ selected, data }: any) => {
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];
  const inputs = [
    ...ports.map(p => {
      const idx = p.id.indexOf('__');
      return { id: idx >= 0 ? p.id.slice(idx + 2) : p.id, color: idx >= 0 ? p.id.slice(0, idx) : 'any' };
    }),
    { id: 'new', color: 'any' },
  ];
  return (
    <BaseNode title="Group OUT" icon={LogOut} selected={selected} data={data} inputs={inputs} outputs={[]}>
      {ports.length === 0 && <div className="text-[8px] text-gray-600 italic text-center">connect outputs →</div>}
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
