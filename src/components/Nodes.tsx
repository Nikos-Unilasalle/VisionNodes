import React, { memo, useState, useMemo, useEffect } from 'react';
import { Handle, Position, useNodeId, useEdges, useUpdateNodeInternals, NodeResizer, useStore } from 'reactflow';
import { useNodeData } from '../context/NodesDataContext';
import { useComputingNodeId } from '../context/ComputingNodeContext';
import { open, save } from '@tauri-apps/plugin-dialog';
import {
  Camera, Waves, Ghost, Maximize, Search, User, Zap, Activity,
  Hash, Eye, Layout, PenTool, Database, Wind, Target, Palette, Scaling, Move, Layers, Box, Image, Film, Play, Pause,
  Plus, Info, Save, FolderOpen, BookOpen, Video, Type, Calculator, PlusSquare, Minus, Divide, Scissors, Keyboard, HelpCircle, ChevronDown, ChevronUp,
  Crosshair, Monitor, Lock, LockOpen, Crop, Filter, Package, LogIn, LogOut, BarChart2, Music, Volume2, RotateCcw, Repeat, Download, FileCode, ZapOff,
  Clipboard, FileText
} from 'lucide-react';
import * as LucideIcons from 'lucide-react';

const getIcon = (name: string, fallback = Box) => {
  if (!name) return fallback;
  const icon = (LucideIcons as any)[name];
  return icon || fallback;
};
import {
  AreaChart, Area, ResponsiveContainer, YAxis, XAxis, Tooltip,
  BarChart, Bar, Cell, LineChart, Line, CartesianGrid, ReferenceLine,
  ComposedChart,
} from 'recharts';

export const HANDLE_COLORS = { image: '#3b82f6', data: '#f97316', dict: '#22c55e', list: '#a855f7', scalar: '#eab308', string: '#7dd3fc', mask: '#d1d5db', flow: '#ef4444', boolean: '#22d3ee', any: '#ffffff', geotiff: '#059669', audio: '#818cf8', markers: '#f59e0b', regions: '#2dd4bf', contours: '#a3e635', coords: '#fb7185', points: '#e879f9', vectors: '#38bdf8' };

const NodeColorContext = React.createContext<{ customBg?: string; customText?: string }>({});
export const useNodeColor = () => React.useContext(NodeColorContext);
export const NodeColorProvider = NodeColorContext.Provider;

const StyledHandle = ({ type, position, id, color = 'image', top = '50%', left, noBorder = false }: any) => {
  const nodeId = useNodeId();
  const handleId = `${color}__${id}`;
  const isLeft = position === Position.Left;
  const isHoriz = position === Position.Top || position === Position.Bottom;

  const posStyle = isHoriz
    ? { left: left || '50%', transform: 'translateX(-50%)', top: position === Position.Top ? -5 : undefined, bottom: position === Position.Bottom ? -5 : undefined }
    : { top, [isLeft ? 'left' : 'right']: -5 };

  return (
    <Handle
      type={type}
      position={position}
      id={handleId}
      style={{
        background: HANDLE_COLORS[color as keyof typeof HANDLE_COLORS] || color,
        width: noBorder ? 5 : 10,
        height: noBorder ? 5 : 10,
        borderRadius: noBorder ? 0 : '50%',
        border: noBorder ? 'none' : '2px solid #111',
        zIndex: 50,
        position: 'absolute',
        ...posStyle,
      }}
      onClick={(e) => {
        e.stopPropagation();
        window.dispatchEvent(new CustomEvent('remove-handle-edge', { detail: { nodeId, handleId, type } }));
      }}
    />
  );
};



export const BaseNode = ({ 
  title, 
  icon: Icon, 
  selected, 
  data, 
  color = 'blue', 
  inputs = [], 
  outputs = [], 
  children, 
  width, 
  height,
  headerExtra, 
  className = "" 
}: any) => {
  const { customBg } = useNodeColor();
  const nodeId = useNodeId();
  const computingNodeId = useComputingNodeId();
  const isComputing = !!nodeId && computingNodeId === nodeId;
  const updateNodeInternals = useUpdateNodeInternals();
  const totalInputs = inputs.length + (data?.params?.var_count || 0);
  const totalOutputs = outputs.length;
  const maxPorts = Math.max(totalInputs, totalOutputs);

  const nodeNote = data?.params?.node_note;
  const isLockedOut = !!(data as any)?.lockedOut;
  const isBypassed = !!(data as any)?.bypassed;
  const isMinified = !!(data as any)?.minified;
  const isRotated = !!(data as any)?.rotated;
  const startOffset = isMinified ? 10 : 45;
  const spacing = isMinified ? 5 : 32;

  useEffect(() => { if (nodeId) updateNodeInternals(nodeId); }, [isRotated, isMinified, nodeId, updateNodeInternals]);

  const getPortTop = (index: number, total: number) => {
    if (total === 0) return '50%';
    return `${startOffset + index * spacing}px`;
  };

  const nodeWidth = typeof width === 'number' ? width : 208;
  const getPortLeft = (index: number, total: number) => {
    if (total <= 1) return `${nodeWidth / 2}px`;
    const margin = 16;
    const step = (nodeWidth - margin * 2) / (total - 1);
    return `${margin + index * step}px`;
  };
  const portsHeight = maxPorts > 0 ? (startOffset + (maxPorts - 1) * spacing + 12) : 24;
  const minHeight = Math.max(portsHeight, isMinified ? 18 : 90);

  const borderClass = isLockedOut
    ? 'border-red-500'
    : isBypassed
    ? 'border-gray-500'
    : selected ? (color === 'accent' ? 'border-accent' : `border-${color}-500`) : 'border-[#4f5b6b]';

  return (
    <div className={`relative ${className}`} style={{
        width: width || '13rem',
        height: height || 'auto'
    }}>
    <div
        className={`rounded-xl bg-[#2c333f] border-2 transition-all duration-300 ${borderClass} ${selected ? 'shadow-lg scale-105' : ''} shadow-2xl relative w-full h-full flex flex-col${isBypassed ? ' opacity-50 grayscale' : ''}`}
        style={{
          minHeight: height ? undefined : minHeight,
          ...(isLockedOut
            ? { boxShadow: '0 0 24px rgba(239,68,68,0.45), 0 0 8px rgba(239,68,68,0.25)' }
            : isBypassed
            ? { boxShadow: '0 0 12px rgba(107,114,128,0.3)' }
            : customBg ? { borderColor: customBg, boxShadow: selected ? `0 10px 15px -3px ${customBg}40` : `0 0 10px ${customBg}10` } : {}),
        }}
    >
      {isLockedOut && (
        <div className="absolute top-0 right-0 z-20 flex items-center gap-1 bg-red-500 text-white text-[7px] font-black px-2 py-1 rounded-bl-lg rounded-tr-[10px] uppercase tracking-widest shadow-lg select-none pointer-events-none">
          <Lock size={7} strokeWidth={3} />
          <span>LOCK OUT</span>
        </div>
      )}
      {isBypassed && (
        <div className="absolute top-0 right-0 z-20 flex items-center gap-1 bg-gray-600 text-white text-[7px] font-black px-2 py-1 rounded-bl-lg rounded-tr-[10px] uppercase tracking-widest shadow-lg select-none pointer-events-none">
          <span>BYPASS</span>
        </div>
      )}
      {/* Inputs with Labels */}
      {isRotated
        ? inputs.map((inp: any, i: number) => {
            const portLeft = getPortLeft(i, totalInputs);
            return (
              <React.Fragment key={inp.id}>
                <StyledHandle type="target" position={Position.Top} id={inp.id} color={inp.color} left={portLeft} noBorder={isMinified} />
                {!isMinified && <span className="absolute text-[7px] font-medium text-gray-500 uppercase tracking-tighter opacity-80 pointer-events-none z-10 text-center" style={{ left: portLeft, top: 8, transform: 'translateX(-50%)' }}>{inp.id}</span>}
              </React.Fragment>
            );
          })
        : inputs.map((inp: any, i: number) => {
            const top = getPortTop(i, totalInputs);
            return (
              <div key={inp.id} className="absolute left-0 w-full flex items-center pointer-events-none z-10" style={{ top, transform: 'translateY(-50%)' }}>
                <StyledHandle type="target" position={Position.Left} id={inp.id} color={inp.color} top="50%" noBorder={isMinified} />
                {!isMinified && <span className="ml-[12px] text-[7px] font-medium text-gray-500 uppercase tracking-tighter opacity-80">{inp.id}</span>}
              </div>
            );
          })
      }

      {/* Dynamic Variables with Labels */}
      {Array.from({ length: (data?.params?.var_count || 0) }).map((_, i) => {
        const char = String.fromCharCode(97 + i);
        if (isRotated) {
          const portLeft = getPortLeft(inputs.length + i, totalInputs);
          return (
            <React.Fragment key={char}>
              <StyledHandle type="target" position={Position.Top} id={char} color="scalar" left={portLeft} noBorder={isMinified} />
              {!isMinified && <span className="absolute text-[8px] font-medium text-accent uppercase tracking-widest pointer-events-none z-10 text-center" style={{ left: portLeft, top: 8, transform: 'translateX(-50%)' }}>{char}</span>}
            </React.Fragment>
          );
        }
        const top = getPortTop(inputs.length + i, totalInputs);
        return (
          <div key={char} className="absolute left-0 w-full flex items-center pointer-events-none z-10" style={{ top, transform: 'translateY(-50%)' }}>
            <StyledHandle type="target" position={Position.Left} id={char} color="scalar" top="50%" noBorder={isMinified} />
            {!isMinified && <span className="ml-[12px] text-[8px] font-medium text-accent uppercase tracking-widest">{char}</span>}
          </div>
        );
      })}
      
      {!isMinified && (
      <div className="bg-[#3d4452] px-4 py-2 flex items-center justify-between border-b border-[#4f5b6b] rounded-t-[10px] overflow-hidden group/header shrink-0"
           style={customBg ? { backgroundColor: `${customBg}20`, borderBottomColor: `${customBg}40` } : {}}>
        <div className="flex items-center gap-3 truncate">
          <Icon size={14} className="shrink-0 transition-colors" style={customBg ? { color: customBg } : {}} />
          <span className="font-bold text-[10px] uppercase tracking-widest truncate" style={customBg ? { color: customBg } : { color: '#e5e7eb' }}>{title}</span>
          
          {data?.schema?.variable_inputs && (
            <div className="flex gap-1 ml-2 shrink-0">
              <button 
                onClick={(e) => { e.stopPropagation(); data.onChangeParams?.({ var_count: Math.max((data.params?.var_count || 0) - 1, 0) }); }}
                className="w-4 h-4 flex items-center justify-center bg-white/5 hover:bg-red-500/20 text-gray-400 hover:text-red-500 rounded border border-white/10 transition-all text-[10px] font-bold"
              >-</button>
              <button 
                onClick={(e) => { e.stopPropagation(); data.onChangeParams?.({ var_count: Math.min((data.params?.var_count || 0) + 1, 10) }); }}
                className="w-4 h-4 flex items-center justify-center bg-white/5 hover:bg-green-500/20 text-gray-400 hover:text-green-500 rounded border border-white/10 transition-all text-[10px] font-bold"
              >+</button>
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {data?.isVisualized && <Eye size={11} className="text-yellow-400 animate-pulse" />}
          {headerExtra}
        </div>
      </div>
      )}
      
      {isMinified && (
        <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
          <span className="text-[8px] font-bold uppercase tracking-wider truncate max-w-[90%]" style={customBg ? { color: customBg } : { color: '#6b7280' }}>{title}</span>
        </div>
      )}
      
      {!isMinified && (
      <div className="flex-1 p-2 text-[10px] text-gray-400 flex flex-col min-h-0 overflow-hidden rounded-b-[10px]">
        {children}
      </div>
      )}

      {/* Outputs with Labels */}
      {isRotated
        ? outputs.map((out: any, i: number) => {
            const portLeft = getPortLeft(i, totalOutputs);
            return (
              <React.Fragment key={out.id}>
                <StyledHandle type="source" position={Position.Bottom} id={out.id} color={out.color} left={portLeft} noBorder={isMinified} />
                {!isMinified && <span className="absolute text-[7px] font-medium text-gray-500 uppercase tracking-tighter opacity-80 pointer-events-none z-10 text-center" style={{ left: portLeft, bottom: 8, transform: 'translateX(-50%)' }}>{out.id}</span>}
              </React.Fragment>
            );
          })
        : outputs.map((out: any, i: number) => {
            const top = getPortTop(i, totalOutputs);
            return (
              <div key={out.id} className="absolute right-0 w-full flex items-center justify-end pointer-events-none z-10" style={{ top, transform: 'translateY(-50%)' }}>
                {!isMinified && <span className="mr-[12px] text-[7px] font-medium text-gray-500 uppercase tracking-tighter opacity-80">{out.id}</span>}
                <StyledHandle type="source" position={Position.Right} id={out.id} color={out.color} top="50%" noBorder={isMinified} />
              </div>
            );
          })
      }
    </div>
    {nodeNote && (
      <div className="absolute left-0 right-0 top-full mt-1 text-center text-[9px] text-gray-400/80 truncate px-2 pointer-events-none select-none">
        {nodeNote}
      </div>
    )}
    {isComputing && (
      <div
        className="absolute pointer-events-none"
        style={{ bottom: '-5px', right: 0, width: '50%', height: '3px', borderRadius: '9999px' }}
      >
        <div style={{
          width: '100%',
          height: '100%',
          borderRadius: '9999px',
          background: 'linear-gradient(90deg, transparent, #4ade80 40%, #86efac 50%, #4ade80 60%, transparent)',
          backgroundSize: '200% 100%',
          animation: 'computing-sweep 1.2s linear infinite',
          boxShadow: '0 0 8px 2px rgba(74,222,128,0.6)',
        }} />
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
  const hex = data.params?.color || '#ff0000';
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

export const FilterGradientNode = memo(({ selected, data }: any) => (
  <BaseNode title="Image Gradient" icon={LucideIcons.ArrowUpRight} selected={selected} data={data} color="blue" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'magnitude', color: 'image'}, {id: 'angle', color: 'image'}, {id: 'dx', color: 'any'}, {id: 'dy', color: 'any'}]} />
));

export const FilterBlurNode = memo(({ selected, data }: any) => (
  <BaseNode title="Blur" icon={Ghost} selected={selected} data={data} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const FilterThresholdNode = memo(({ selected, data }: any) => (
  <BaseNode title="Threshold" icon={Waves} selected={selected} data={data} color="blue" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'main', color: 'image'}, {id: 'mask', color: 'mask'}]} />
));

export const FilterColorMaskNode = memo(({ selected, data }: any) => {
  const color = data.params?.color || '#FF0000';
  const mode = data.params?.mode === 1 ? 'RGB' : 'HSV';
  
  return (
    <BaseNode title="Color Mask" icon={Layers} selected={selected} data={data} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'mask', color: 'mask'}]}>
      <div className="px-3 py-2 space-y-2">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div 
              className="w-5 h-5 rounded-full border border-white/20 shadow-inner" 
              style={{ backgroundColor: color, boxShadow: `0 0 10px ${color}44` }} 
            />
            <span className="text-[10px] font-mono font-bold text-gray-400">{color}</span>
          </div>
          <div className="px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-[8px] font-black text-accent uppercase tracking-tighter">
            {mode}
          </div>
        </div>
      </div>
    </BaseNode>
  );
});

export const FilterGrayNode = memo(({ selected, data }: any) => (
  <BaseNode title="Grayscale" icon={Eye} selected={selected} data={data} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const FilterMorphologyNode = memo(({ selected, data }: any) => (
  <BaseNode title="Morphology" icon={Waves} selected={selected} data={data} color="accent" inputs={[{id: 'mask', color: 'mask'}, {id: 'image', color: 'image'}]} outputs={[{id: 'mask', color: 'mask'}]} />
));

export const FilterMorphologySmartNode = memo(({ selected, data }: any) => (
  <BaseNode title="Smart Morphology" icon={Zap} selected={selected} data={data} color="accent" inputs={[{id: 'mask', color: 'mask'}]} outputs={[{id: 'mask', color: 'mask'}]} />
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
      outputs={[{id: 'factor', color: 'scalar', label: 'Px/Unit'}, {id: 'unit', color: 'scalar', label: 'Unit Name'}]}
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
          <div className="flex-1 overflow-auto scrollbar-hide p-2.5 min-h-0">
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



export const MaskPointQueryNode = memo(({ selected, data }: any) => (
  <BaseNode title="Mask Point Query" icon={Crosshair} selected={selected} data={data} color="accent"
    inputs={[{id: 'mask', color: 'mask'}, {id: 'x', color: 'scalar'}, {id: 'y', color: 'scalar'}]}
    outputs={[{id: 'inside', color: 'boolean'}]} />
));



// --- SCIENTIFIC NODES ---

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

  const [histories, setHistories] = React.useState<Record<string, number[]>>({});

  React.useEffect(() => {
    if (frozen) return;
    setHistories(prev => {
      const next: Record<string, number[]> = {};
      let changed = false;
      for (const k of portKeys) {
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
      return (changed || prevKeys.length !== portKeys.length || prevKeys.some(k => !portKeys.includes(k))) ? next : prev;
    });
  }, [nd, bufSize, frozen, portKeys]);

  const chartData = React.useMemo(() => {
    const maxLen = Math.max(0, ...portKeys.map(k => histories[k]?.length ?? 0));
    if (maxLen === 0) return [];
    return Array.from({ length: maxLen }, (_, i) => {
      const pt: any = { t: i };
      for (const k of portKeys) {
        const arr = histories[k];
        if (arr && i < arr.length) pt[k] = arr[i];
      }
      return pt;
    });
  }, [histories, portKeys]);

  const activeSeries = portKeys.filter(k => (histories[k]?.length ?? 0) > 0);
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
                 style={{ backgroundColor: SERIES_COLORS[portKeys.indexOf(k) % SERIES_COLORS.length] }} />
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
                    stroke={SERIES_COLORS[portKeys.indexOf(k) % SERIES_COLORS.length]} strokeWidth={1.5}
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

const PRO_COLORS = ['#ff6464', '#64ff64', '#ffb43c', '#64ffff', '#ff64ff', '#ffff64', '#c896ff', '#64c8ff'];

export const PlotterProNode = memo(({ selected, data }: any) => {
  const { customBg } = useNodeColor();
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  const nd = useNodeData(nodeId);
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];

  const bufSize = Number(data.params?.buffer_size ?? 300);
  const showGrid = data.params?.show_grid !== false;
  const lineWidth = Number(data.params?.line_width ?? 2);
  const showThresholds = !!data.params?.show_thresholds;
  const thMin = Number(data.params?.threshold_min ?? 0);
  const thMax = Number(data.params?.threshold_max ?? 255);
  const minY = data.params?.min_y;
  const maxY = data.params?.max_y;
  const autoScale = !!(data.params?.auto_scale ?? true);
  const yDomain: [any, any] = autoScale ? ['auto', 'auto'] : ((minY !== undefined && maxY !== undefined && minY !== maxY) ? [minY, maxY] : [0, 100]);

  useEffect(() => { updateNodeInternals(nodeId); }, [ports.length, nodeId, updateNodeInternals]);

  const portKeys = React.useMemo(() =>
    ports.map(p => p.id.split('__').pop() ?? p.id),
    [ports]
  );

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
      for (const k of portKeys) {
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
      return (changed || prevKeys.length !== portKeys.length || prevKeys.some(k => !portKeys.includes(k))) ? next : prev;
    });
  }, [nd, bufSize, portKeys]);

  const chartData = React.useMemo(() => {
    const maxLen = Math.max(0, ...portKeys.map(k => histories[k]?.length ?? 0));
    if (maxLen === 0) return [];
    return Array.from({ length: maxLen }, (_, i) => {
      const pt: any = { t: i };
      for (const k of portKeys) { const arr = histories[k]; if (arr && i < arr.length) pt[k] = arr[i]; }
      return pt;
    });
  }, [histories, portKeys]);

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

        {/* Output main */}
        <div className="absolute right-0 flex items-center justify-end pointer-events-none z-10"
             style={{ top: '22px', transform: 'translateY(-50%)' }}>
          <span className="mr-[12px] text-[7px] font-black text-white/40 uppercase tracking-widest">main</span>
          <StyledHandle type="source" position={Position.Right} id="main" color="image" top="50%" />
        </div>

        {/* Header */}
        <div className="bg-[#3d4452] px-3 py-1.5 flex items-center gap-2 border-b border-[#4f5b6b] rounded-t-xl shrink-0"
             style={customBg ? { backgroundColor: `${customBg}20`, borderBottomColor: `${customBg}40` } : {}}>
          <Activity size={12} className="shrink-0" style={customBg ? { color: customBg } : { color: '#a78bfa' }} />
          <span className="text-[10px] font-bold uppercase tracking-widest" style={customBg ? { color: customBg } : { color: '#ffffff' }}>Plotter Pro</span>
          <div className="ml-auto flex items-center gap-1.5">
            {portKeys.map((k, i) => (
              <div key={k} className="w-1.5 h-1.5 rounded-full opacity-80"
                   style={{ backgroundColor: PRO_COLORS[i % PRO_COLORS.length] }} />
            ))}
          </div>
        </div>

        {/* Chart */}
        <div className="flex-1 min-h-0 w-full px-1 py-1 overflow-hidden">
          {chartData.length === 0
            ? <div className="w-full h-full flex flex-col items-center justify-center gap-1">
                <span className="text-[8px] text-gray-600 uppercase tracking-widest">
                  {ports.length === 0 ? 'connect data' : `${ports.length} port${ports.length > 1 ? 's' : ''} — waiting`}
                </span>
              </div>
            : <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 2, right: 35, bottom: 0, left: 0 }}>
                  <YAxis hide domain={yDomain} />
                  {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#4a5568" vertical={false} />}
                  {showThresholds && <ReferenceLine y={thMin} stroke="#facc15" strokeDasharray="6 3" strokeWidth={1.5} label={{ position: 'insideRight', value: `${thMin.toFixed(1)}`, fill: '#facc15', fontSize: 7 }} />}
                  {showThresholds && <ReferenceLine y={thMax} stroke="#facc15" strokeDasharray="6 3" strokeWidth={1.5} label={{ position: 'insideRight', value: `${thMax.toFixed(1)}`, fill: '#facc15', fontSize: 7 }} />}
                  {portKeys.map((k, i) => (
                    <Line key={k} type="monotone" dataKey={k}
                      stroke={PRO_COLORS[i % PRO_COLORS.length]} strokeWidth={lineWidth}
                      dot={false} isAnimationActive={false} connectNulls />
                  ))}
                </LineChart>
              </ResponsiveContainer>
          }
        </div>
      </div>
    </div>
  );
});

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

const _noteHash = (s: string) => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) | 0; } return Math.abs(h); };

export const CanvasNoteNode = memo(({ selected, data }: any) => {
  const [editing, setEditing] = useState(false);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  const text = data.params?.text ?? '';
  const palIdx = data?.activePaletteIndex ?? 6;
  const cIdx = data?.params?.color_index;
  const bgColor = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.bg : (data?.params?.bg_color || '#ffd4b8');
  const textColor = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.dark : (data?.params?.text_color || '#3a2010');

  // Deterministic tilt from node id — fixed per note, never changes
  const rotation = ((_noteHash(data.id || '') % 7) - 3) * 0.18; // -0.54° to +0.54°

  React.useEffect(() => {
    if (editing) textareaRef.current?.focus();
  }, [editing]);

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditing(true);
  };

  const isMinified = !!(data as any)?.minified;

  return (
    <div
      className="w-full overflow-hidden transition-all duration-200"
      style={{
        background: bgColor,
        borderRadius: '5px 5px 0 0',
        transform: `rotate(${rotation}deg)`,
        height: isMinified ? 22 : undefined,
        boxShadow: selected
          ? `5px 8px 24px rgba(0,0,0,0.38), 2px 3px 8px rgba(0,0,0,0.22), 0 0 0 2px rgba(0,0,0,0.25)`
          : `4px 6px 18px rgba(0,0,0,0.28), 2px 3px 6px rgba(0,0,0,0.16)`,
      }}
      onDoubleClick={handleDoubleClick}
    >
      <div
        className="flex items-center gap-1.5 px-2 py-1 nodrag select-none"
        style={{ background: 'rgba(0,0,0,0.13)', borderBottom: isMinified ? 'none' : '1px solid rgba(0,0,0,0.10)' }}
      >
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

      {!isMinified && (
        editing ? (
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
        )
      )}
    </div>
  );
});

export const CanvasRerouteNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];
  const nodeHeight = useStore((s: any) => s.nodeInternals.get(nodeId)?.height ?? 48);

  useEffect(() => { updateNodeInternals(nodeId); }, [nodeHeight, ports.length, nodeId, updateNodeInternals]);

  // Evenly distribute output handles (ports + factory) across the full height, pixels only
  const total = ports.length + 1; // dynamic ports + factory
  const outTop = (i: number) => Math.round((i + 1) / (total + 1) * nodeHeight);

  return (
    <div
      style={{
        width: 8,
        height: '100%',
        minHeight: 48,
        borderRadius: 4,
        background: selected ? '#888' : '#444',
        border: selected ? '1px solid #aaa' : '1px solid #666',
        boxShadow: selected ? '0 0 0 2px #3b82f6' : '0 2px 6px rgba(0,0,0,0.5)',
        position: 'relative',
      }}
    >
      <NodeResizer
        isVisible={selected}
        minWidth={8}
        maxWidth={8}
        minHeight={24}
        onResize={() => updateNodeInternals(nodeId)}
        handleStyle={{ width: 6, height: 6 }}
        lineStyle={{ borderColor: '#3b82f6' }}
      />
      {/* Input fixed near top */}
      <StyledHandle type="target" position={Position.Left} id="in" color="any" top="10px" />
      {/* Dynamic outputs spread evenly */}
      {ports.map((p, i) => (
        <StyledHandle
          key={p.id}
          type="source"
          position={Position.Right}
          id={p.id.split('__').slice(1).join('__')}
          color={p.color}
          top={`${outTop(i)}px`}
        />
      ))}
      {/* Factory handle always at bottom of distribution */}
      <StyledHandle type="source" position={Position.Right} id="DYNAMIC_NEW_HANDLE" color="any" top={`${outTop(ports.length)}px`} />
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

const GeoSedimentLoaderNode = memo(({ selected, data }: any) => {
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

const GeoIndexNode = memo(({ selected, data }: any) => {
  const schema = data.schema;
  const IconCmp = getIcon(schema?.icon, Divide);

  return (
    <BaseNode title="Geophysics Index" icon={IconCmp} selected={selected} data={data} color="red" 
              inputs={schema?.inputs} outputs={schema?.outputs}>
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

export const GenericCustomNode = memo((props: any) => {
  const { data } = props;
  const schema = data.schema || { label: 'Unknown Plugin', icon: 'Box', inputs: [], outputs: [] };

  if (schema.type === 'sci_plotter') return <ScientificPlotterNode {...props} />;
  if (schema.type === 'plotter_pro') return <PlotterProNode {...props} />;
  if (schema.type === 'sci_histogram') return <ScientificHistogramNode {...props} />;
  if (schema.type === 'sci_stats') return <ScientificStatsNode {...props} />;
  if (schema.type === 'draw_text') return <DrawTextNode {...props} />;
  if (schema.type === 'util_csv_export') return <UtilCSVExportNode {...props} />;
  if (schema.type === 'geo_geotiff_reader') return <GeoTIFFReaderNode {...props} />;
  if (schema.type === 'geo_earth_engine') return <GeoEarthEngineNode {...props} />;
  if (schema.type === 'geo_band_info') return <GeoBandInfoNode {...props} />;
  if (schema.type === 'geo_land_cover') return <GeoLandCoverNode {...props} />;
  if (schema.type === 'sci_matrix_dist') return <MatrixDistNode {...props} />;
  if (schema.type === 'geo_sediment_loader') return <GeoSedimentLoaderNode {...props} />;
  if (schema.type === 'geo_index') return <GeoIndexNode {...props} />;
  if (schema.type === 'root_anatomy_report') return <RootAnatomyReportNodeUI {...props} />;
  if (schema.type === 'geo_turbidity_stats') return <TurbidityStatsNodeUI {...props} />;

  return <GenericCustomNodeInternal {...props} schema={schema} />;
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

const RootAnatomyReportNodeUI = ({ data, selected }: { data: any, selected: boolean }) => {
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
  { label: 'Cristal (0–1)',          short: 'Cristal',   color: 'text-blue-300',   bg: 'bg-blue-500/5'   },
  { label: 'Clair (1–5)',            short: 'Clair',     color: 'text-cyan-400',   bg: 'bg-cyan-500/5'   },
  { label: 'Légèrement turbide',     short: 'Légt.',     color: 'text-green-400',  bg: 'bg-green-500/5'  },
  { label: 'Turbide',                short: 'Turbide',   color: 'text-amber-400',  bg: 'bg-amber-500/5'  },
  { label: 'Très turbide',           short: 'Très T.',   color: 'text-orange-400', bg: 'bg-orange-500/5' },
  { label: 'Extrêmement turbide',    short: 'Extrême',   color: 'text-red-400',    bg: 'bg-red-500/5'    },
];

const TurbidityStatsNodeUI = ({ data, selected }: { data: any; selected: boolean }) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const [expanded, setExpanded] = React.useState(false);

  const stats = (nd as any)?.stats || {};
  const classes = stats.classes || {};
  const hasData = typeof stats.mean === 'number';

  const fmt = (v: any, dec = 2) =>
    typeof v === 'number' ? (v >= 1000 ? Math.round(v).toString() : v.toFixed(dec)) : '—';

  const metricsLeft = [
    { label: 'Moyenne', key: 'mean',   color: 'text-cyan-400' },
    { label: 'Médiane', key: 'median', color: 'text-cyan-400' },
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
              <div className="text-[7px] text-cyan-500/70 uppercase font-black mb-2 tracking-widest">Métriques NTU</div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                {metricsLeft.map(m => (
                  <div key={m.key} className="flex flex-col">
                    <span className="text-[8px] text-gray-500">{m.label}</span>
                    <span className={`text-[11px] font-bold font-mono ${m.color}`}>{fmt(stats[m.key])} NTU</span>
                  </div>
                ))}
              </div>
              <div className="mt-2 pt-1 border-t border-white/5 text-[8px] text-gray-400 flex justify-between">
                <span>Surface eau</span>
                <span className="text-emerald-400 font-mono font-bold">{fmt(stats.area_km2, 1)} km²</span>
              </div>
            </div>
            {/* Class distribution mini */}
            <div className="p-2 rounded-xl border border-white/5 bg-white/3">
              <div className="text-[7px] text-gray-500 uppercase font-black mb-1.5 tracking-widest">Distribution WFD</div>
              <div className="space-y-1">
                {TURB_CLASSES.filter(tc => {
                  const d = classes[tc.label];
                  return d && d.pct > 0.5;
                }).map(tc => {
                  const d = classes[tc.label] || {};
                  const pct = d.pct || 0;
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
                Métriques NTU
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
                  <span className="text-gray-400">Surface eau</span>
                  <span className="font-mono font-bold text-emerald-400 bg-black/20 px-1.5 py-0.5 rounded border border-white/5">{fmt(stats.area_km2, 1)} km²</span>
                </div>
                <div className="flex justify-between items-center text-[10px]">
                  <span className="text-gray-400">Pixels eau</span>
                  <span className="font-mono font-bold text-gray-300 bg-black/20 px-1.5 py-0.5 rounded border border-white/5">{stats.count ? stats.count.toLocaleString() : '—'}</span>
                </div>
              </div>
            </div>
            {/* WFD classes panel */}
            <div className="p-3 rounded-xl border border-white/5 bg-white/3">
              <h5 className="text-[9px] font-black uppercase tracking-wider text-amber-400 mb-3 border-b border-white/10 pb-1 flex justify-between items-center">
                Distribution WFD
                <div className="w-1.5 h-1.5 rounded-full bg-amber-400 opacity-50" />
              </h5>
              <div className="space-y-2">
                {TURB_CLASSES.map(tc => {
                  const d = classes[tc.label] || {};
                  const pct = d.pct || 0;
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
          {expanded ? 'Collapse View' : 'Distribution WFD'}
          <BarChart2 size={10} />
        </button>
      </div>
    </BaseNode>
  );
};

const GenericCustomNodeInternal = ({ selected, data, schema }: any) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const IconCmp = getIcon(schema.icon, Box);

  const outputs = data.dynamicColor 
    ? schema.outputs.map((out: any) => ({ ...out, color: data.dynamicColor }))
    : schema.outputs;

  const preview = nd?.preview_b64 || (typeof nd?.preview === 'string' ? nd.preview : null);

  return (
    <BaseNode title={data.label || schema.label} icon={IconCmp} selected={selected} data={data} color="accent" inputs={schema.inputs} outputs={outputs}>
      {preview && (
        <div className="px-2 pb-2">
          <img 
            src={`data:image/jpeg;base64,${preview}`} 
            alt="Node Preview" 
            className="w-full h-auto max-h-32 object-cover rounded-lg border border-white/10" 
          />
        </div>
      )}
    </BaseNode>
  );
};

export const CanvasFrameNode = memo(({ selected, data }: any) => {
  const [editing, setEditing] = useState(false);
  const title = data.params?.title ?? 'Frame';
  const isCollapsed = !!(data.params?.collapsed);
  const palIdx = data?.activePaletteIndex ?? 6;
  const cIdx = data?.params?.color_index;
  const bgColor = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.bg : (data?.params?.bg_color || '#333333');
  const textColor = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.dark : (data?.params?.text_color || '#ffffff');

  return (
    <div
      className="w-full rounded-xl border-2 group/frame transition-all flex flex-col overflow-hidden"
      style={{ borderColor: bgColor, backgroundColor: isCollapsed ? bgColor : `${bgColor}15`, height: '100%' }}
    >
      <div
        className="px-3 py-2 font-black text-xs uppercase tracking-widest cursor-text select-none flex items-center gap-2 shrink-0"
        style={{ backgroundColor: bgColor, color: textColor }}
        onDoubleClick={(e) => { e.stopPropagation(); if (!isCollapsed) setEditing(true); }}
      >
        <span className="truncate flex-1 min-w-0">
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
          ) : title}
        </span>
        <button
          className="shrink-0 opacity-0 group-hover/frame:opacity-60 hover:!opacity-100 transition-opacity"
          title={isCollapsed ? 'Déplier' : 'Replier'}
          onPointerDown={e => e.stopPropagation()}
          onDoubleClick={e => e.stopPropagation()}
          onClick={e => { e.stopPropagation(); data.onToggleCollapse?.(); }}
        >
          <ChevronDown size={12} style={{ transform: isCollapsed ? 'rotate(-90deg)' : 'none', transition: 'transform 0.15s' }} />
        </button>
      </div>
      {!isCollapsed && <div className="flex-1 pointer-events-none" />}
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
    <BaseNode title="Group Input" icon={LogIn} selected={selected} data={data} outputs={outputs} inputs={[]}>
      {ports.length === 0 && <div className="text-[8px] text-gray-600 italic text-center">no inputs</div>}
    </BaseNode>
  );
});

export const GroupOutputNode = memo(({ selected, data }: any) => {
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
    <BaseNode title="Group Output" icon={LogOut} selected={selected} data={data} inputs={inputs} outputs={[]}>
      {ports.length === 0 && <div className="text-[8px] text-gray-600 italic text-center">connect outputs →</div>}
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
              ['Neutrophils',  neu, 'text-blue-400'],
              ['Lymphocytes',  lym, 'text-cyan-400'],
              ['Monocytes',    mon, 'text-emerald-400'],
            ] as const).map(([label, val, cls]) => (
              <div key={label} className="flex items-center justify-between font-mono">
                <span className="text-[10px] text-gray-400">{label}</span>
                <div className="flex items-center gap-1">
                  <div className="h-1 rounded-full bg-white/5 w-16 overflow-hidden">
                    <div className={`h-full rounded-full opacity-60 ${cls.replace('text-', 'bg-')}`}
                         style={{ width: `${Math.min(100, parseFloat(val))}%` }} />
                  </div>
                  <span className={`text-[11px] font-black w-8 text-right ${cls}`}>{val}</span>
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

// ── Teleport Node ─────────────────────────────────────────────────────────────
// Ghost clone of a source node. Mirrors outputs without re-computing.
// Semi-transparent, dashed border, no input handles.
export const TeleportNode = memo(({ data, selected }: any) => {
  const { customBg } = useNodeColor();
  const nodeId = useNodeId();
  const updateNodeInternals = useUpdateNodeInternals();

  const sourceOutputs: Array<{ id: string; color: string; label?: string }> =
    data?.source_outputs ?? [];
  const label: string = data?.label ?? 'Téléport';
  const isBroken = !data?.params?.source_id;
  const isMinified = !!(data as any)?.minified;

  const START_Y = 40;
  const STEP = 28;

  useEffect(() => { if (nodeId) updateNodeInternals(nodeId); }, [nodeId, updateNodeInternals]);

  const borderColor = isBroken
    ? '#ef4444'
    : selected
    ? '#60a5fa'
    : customBg ?? '#60a5fa55';

  return (
    <div
      style={{
        minWidth: 160,
        opacity: 0.72,
        position: 'relative',
        borderRadius: 12,
        border: `2px dashed ${borderColor}`,
        background: customBg ? `${customBg}22` : '#1e2a3a99',
        boxShadow: selected ? `0 0 18px ${borderColor}55` : 'none',
        backdropFilter: 'blur(6px)',
        transition: 'box-shadow 0.2s, opacity 0.2s',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '7px 10px 5px', borderBottom: '1px solid rgba(255,255,255,0.07)',
        }}
      >
        <Zap size={11} color="#60a5fa" style={{ flexShrink: 0 }} />
        <span style={{
          fontSize: 10, fontWeight: 700, color: '#cbd5e1',
          flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {label}
        </span>
        <span style={{ fontSize: 8, color: '#60a5fa99', fontFamily: 'monospace', flexShrink: 0 }}>
          ⚡TP
        </span>
      </div>

      {/* Output rows — hidden when minified */}
      {!isMinified && <div style={{ padding: '4px 0 6px' }}>
        {isBroken ? (
          <div style={{ fontSize: 9, color: '#f87171', padding: '4px 10px', fontStyle: 'italic' }}>
            Source introuvable
          </div>
        ) : sourceOutputs.length === 0 ? (
          <div style={{ fontSize: 9, color: '#64748b', padding: '4px 10px', fontStyle: 'italic' }}>
            Aucune sortie
          </div>
        ) : (
          sourceOutputs.map((out, i) => (
            <div
              key={out.id}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
                padding: '1px 14px 1px 10px', height: STEP,
              }}
            >
              <span style={{ fontSize: 9, color: '#94a3b8', marginRight: 6 }}>
                {out.label ?? out.id}
              </span>
              <StyledHandle
                type="source"
                id={out.id}
                color={out.color as any}
                position={Position.Right}
                top={`${START_Y + i * STEP}px`}
              />
            </div>
          ))
        )}
      </div>}
    </div>
  );
});
