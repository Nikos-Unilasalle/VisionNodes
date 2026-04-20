import React, { memo } from 'react';
import { Handle, Position, useNodeId, NodeResizeControl } from 'reactflow';
import { open, save } from '@tauri-apps/plugin-dialog';
import { 
  Camera, Waves, Ghost, Maximize, Search, User, Zap, Activity,
  Hash, Eye, Layout, PenTool, Database, Wind, Target, Palette, Scaling, Move, Layers, Box, Image, Film, Play, Pause,
  Plus, Info, Save, FolderOpen, BookOpen, Video, Type, Calculator, PlusSquare, Minus, Divide, Scissors, Keyboard, HelpCircle, ChevronDown, ChevronUp
} from 'lucide-react';
import * as LucideIcons from 'lucide-react';

const getIcon = (name: string, fallback = Box) => {
  if (!name) return fallback;
  const icon = (LucideIcons as any)[name];
  return icon || fallback;
};
import { 
  AreaChart, Area, ResponsiveContainer, YAxis, XAxis, Tooltip,
  BarChart, Bar, Cell
} from 'recharts';

export const HANDLE_COLORS = { image: '#3b82f6', data: '#22c55e', dict: '#22c55e', list: '#a855f7', scalar: '#eab308', string: '#7dd3fc', mask: '#d1d5db', flow: '#ef4444', boolean: '#22d3ee', any: '#ffffff' };

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

const BaseNode = ({ title, icon: Icon, children, selected, color = 'accent', inputs = [], outputs = [], var_count = 0, width = 'w-64', headerExtra }: any) => {
  const accentColor = color === 'accent' ? 'border-accent shadow-accent/20' : 
                      color === 'green' ? 'border-green-500 shadow-green-500/20' :
                      color === 'blue' ? 'border-blue-500 shadow-blue-500/20' :
                      color === 'red' ? 'border-red-500 shadow-red-500/20' :
                      'border-gray-500 shadow-gray-500/20';
                      
  const totalInputs = inputs.length + var_count;
  const totalOutputs = outputs.length;
  const maxPorts = Math.max(totalInputs, totalOutputs);
  
  const startOffset = 45;
  const spacing = 32;
  // Compact height: last port position + 35px padding
  const portsHeight = maxPorts > 0 ? (startOffset + (maxPorts - 1) * spacing + 35) : 90;
  const minHeight = Math.max(portsHeight, 90);

  // Offset ports downward by 45px to avoid title collision
  const getPortTop = (index: number, total: number) => {
    if (total === 0) return '50%';
    const startOffset = 45; // pixels from top
    const spacing = 32;
    return `${startOffset + index * spacing}px`;
  };

  return (
    <div 
        className={`rounded-xl bg-[#1a1a1a] border-2 transition-all duration-300 ${selected ? accentColor + ' shadow-lg scale-105' : 'border-[#333]'} w-52 shadow-2xl relative`}
        style={{ minHeight }}
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

      <div className="bg-[#222] px-4 py-2 flex items-center justify-between border-b border-[#333] rounded-t-xl overflow-hidden group/header">
        <div className="flex items-center gap-3 truncate">
          <Icon size={14} className="text-gray-400 group-hover:text-accent transition-colors shrink-0" />
          <span className="font-bold text-[10px] uppercase tracking-widest text-gray-200 truncate">{title}</span>
        </div>
        {headerExtra}
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
  );
};

// --- NODES ---
export const InputWebcamNode = memo(({ selected }: any) => (
  <BaseNode title="Webcam" icon={Camera} selected={selected} color="green" outputs={[{id: 'main', color: 'image'}]} />
));

export const InputImageNode = memo(({ selected, data }: any) => {
  const preview = data.node_data?.preview;
  
  const handleBrowse = async () => {
    try {
      const selectedFile = await open({
        multiple: false,
        filters: [{
          name: 'Image',
          extensions: ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff']
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
    <BaseNode title="Image File" icon={Image} selected={selected} color="green" outputs={[{id: 'main', color: 'image'}]}>
      {preview ? (
        <div className="relative group" onClick={handleBrowse}>
          <img 
            src={`data:image/jpeg;base64,${preview}`} 
            alt="Preview" 
            className="w-full h-32 object-cover rounded-lg border border-[#333] mb-1" 
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
          className="flex flex-col items-center justify-center border-2 border-dashed border-[#333] rounded-lg p-4 opacity-40 hover:opacity-100 transition-opacity cursor-pointer h-32"
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
          onClick={handleBrowse}
        >
          <Search size={20} className="text-gray-500 mb-2" />
          <div className="text-[7px] text-gray-500 uppercase font-black text-center">Click to Browse<br/>or Drop Image</div>
        </div>
      )}
    </BaseNode>
  );
});

export const InputMovieNode = memo(({ selected, data }: any) => {
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
    <BaseNode title="Movie File" icon={Film} selected={selected} color="green" outputs={[{id: 'main', color: 'image'}]}>
      <div className="p-4 space-y-4" onClick={handleBrowse} onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
        {data.node_data?.preview && (
          <div className="relative group/preview rounded-2xl overflow-hidden border border-white/5 bg-black/40 shadow-inner">
            <img 
              src={`data:image/jpeg;base64,${data.node_data.preview}`} 
              className="w-full h-auto object-cover opacity-80 group-hover/preview:opacity-100 transition-opacity duration-500"
              alt="Movie Preview"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
            <div className="absolute bottom-2 left-2 right-2">
                <div className="text-[10px] font-black text-white/90 truncate drop-shadow-md flex items-center gap-1.5">
                    <Film size={12} className="text-accent" />
                    {data.node_data.filename || "Movie Loaded"}
                </div>
            </div>
          </div>
        )}
        
        {!data.node_data?.preview && (
          <div className="py-8 flex flex-col items-center justify-center gap-3 bg-black/20 rounded-2xl border border-dashed border-white/10 opacity-40">
            <div className="p-3 bg-white/5 rounded-full">
                <Video size={24} className="text-gray-400" />
            </div>
            <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">No Media Loaded</div>
          </div>
        )}

        <div className="space-y-3">
          <div className="p-3 bg-white/5 rounded-2xl border border-white/5 group-hover:border-accent/20 transition-all duration-300">
            <div className="text-[9px] font-black text-gray-500 uppercase tracking-[0.2em] mb-1">Source Path</div>
            <div className="text-[11px] font-mono text-white/70 truncate">{data.params?.path || "No path selected..."}</div>
          </div>

          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2">
            <div className={`w-1.5 h-1.5 rounded-full ${data?.params?.playing ? 'bg-green-500 animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.5)]' : 'bg-gray-600'}`} />
            <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">
              {data?.params?.playing ? 'Playing' : 'Paused'}
            </span>
          </div>
            <div className="text-[10px] font-mono text-accent font-bold">
              {data.node_data?.current_frame || 0} / {data.node_data?.total_frames || 0}
            </div>
          </div>
        </div>
      </div>
    </BaseNode>
  );
});

export const SolidColorNode = memo(({ selected }: any) => (
  <BaseNode title="Solid Color" icon={Palette} selected={selected} color="green" outputs={[{id: 'main', color: 'image'}]} />
));

export const FilterCannyNode = memo(({ selected }: any) => (
  <BaseNode title="Canny Edge" icon={Waves} selected={selected} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const FilterBlurNode = memo(({ selected }: any) => (
  <BaseNode title="Blur" icon={Ghost} selected={selected} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const FilterThresholdNode = memo(({ selected }: any) => (
  <BaseNode title="Threshold" icon={Waves} selected={selected} color="blue" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'main', color: 'image'}, {id: 'mask', color: 'mask'}]} />
));

export const FilterColorMaskNode = memo(({ selected }: any) => (
  <BaseNode title="Color Mask" icon={Palette} selected={selected} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'mask', color: 'mask'}]}>
    <div className="text-[9px] text-gray-500 uppercase font-black">HSV Isolation</div>
  </BaseNode>
));

export const FilterGrayNode = memo(({ selected }: any) => (
  <BaseNode title="Grayscale" icon={Eye} selected={selected} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const FilterMorphologyNode = memo(({ selected }: any) => (
  <BaseNode title="Morphology" icon={Waves} selected={selected} color="accent" inputs={[{id: 'mask', color: 'mask'}, {id: 'image', color: 'image'}]} outputs={[{id: 'mask', color: 'mask'}]}>
    <div className="text-[9px] text-gray-500 uppercase font-black">Erode / Dilate</div>
  </BaseNode>
));

export const GeomFlipNode = memo(({ selected }: any) => (
  <BaseNode title="Flip" icon={Move} selected={selected} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const GeomResizeNode = memo(({ selected }: any) => (
  <BaseNode title="Resize" icon={Scaling} selected={selected} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const AnalysisFaceMPNode = memo(({ selected, data }: any) => {
  const max = data.params?.max_faces || 3;
  const outputs = [{id: 'main', color: 'image'}, {id: 'faces_list', color: 'list'}, ...Array.from({ length: max }).map((_, i) => ({ id: `face_${i}`, color: 'data' }))];
  return (
    <BaseNode title="Face Tracker" icon={User} selected={selected} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={outputs} />
  );
});

export const AnalysisHandMPNode = memo(({ selected, data }: any) => {
  const max = data.params?.max_hands || 2;
  const outputs = [{id: 'main', color: 'image'}, {id: 'hands_list', color: 'list'}, ...Array.from({ length: max }).map((_, i) => ({ id: `hand_${i}`, color: 'data' }))];
  return (
    <BaseNode title="Hand Tracker" icon={User} selected={selected} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={outputs} />
  );
});

export const AnalysisPoseMPNode = memo(({ selected }: any) => {
  const outputs = [
    {id: 'main', color: 'image'}, 
    {id: 'pose_list', color: 'list'},
    {id: 'data', color: 'dict'}
  ];
  return (
    <BaseNode title="Pose Tracker" icon={User} selected={selected} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={outputs} />
  );
});

export const AnalysisFlowNode = memo(({ selected }: any) => (
  <BaseNode title="Optical Flow" icon={Activity} selected={selected} color="red" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}, {id: 'data', color: 'flow'}]}>
    <div className="text-[9px] text-gray-500 uppercase font-black">Motion Vectors</div>
  </BaseNode>
));

export const AnalysisFlowVizNode = memo(({ selected }: any) => (
  <BaseNode title="Flow Viz" icon={Palette} selected={selected} color="accent" inputs={[{id: 'data', color: 'flow'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const AnalysisMonitorNode = memo(({ selected, data }: any) => {
  const nodeData = data.node_data || {};
  const val = nodeData.scalar ?? 0;
  const displayText = nodeData.display_text || `${val.toFixed(data.params?.precision ?? 3)}`;
  
  const parts = displayText.trim().split(/\s+/);
  const num = parts[0] || '0.000';
  const unit = parts[1] || '';

  // Simple normalization for the progress bar
  const mode = data.params?.mode ?? 0;
  let progress = 0;
  let themeColor = '#22c55e'; // Default data green

  if (mode === 1) { // Flow
    progress = (val / 5.0) * 100;
    themeColor = HANDLE_COLORS.flow;
  } else if (mode === 2) { // Area
    progress = (val / 100000) * 100;
    themeColor = HANDLE_COLORS.mask;
  } else if (mode >= 3 && mode <= 6) { // Image
    progress = (val / 255) * 100;
    themeColor = HANDLE_COLORS.image;
  } else if (mode === 7) { // Count
    progress = (val / 20) * 100;
    themeColor = HANDLE_COLORS.list;
  } else {
    progress = (val / 100) * 100;
  }

  return (
    <BaseNode 
      title={data.schema?.label || "Universal Monitor"} 
      icon={Target} 
      selected={selected} 
      color="blue" 
      inputs={[
        {id: 'data', color: 'data'},
        {id: 'image', color: 'image'}, 
        {id: 'mask', color: 'mask'}
      ]} 
      outputs={[
        {id: 'main', color: 'image'}, 
        {id: 'scalar', color: 'scalar'}
      ]}
    >
      <div className="flex flex-col items-center justify-center py-4 bg-black/40 rounded-xl border border-white/5 shadow-inner">
        <div className="text-[8px] font-black text-gray-500 uppercase tracking-widest mb-1 opacity-60">Live Monitor</div>
        
        <div className="flex items-baseline gap-1.5 px-4 truncate w-full justify-center">
           <span className="text-xl font-bold font-mono text-emerald-400 tracking-tighter drop-shadow-md truncate">
             {num}
           </span>
           {unit && <span className="text-[9px] font-black uppercase tracking-widest shrink-0" style={{ color: themeColor }}>{unit}</span>}
        </div>

        <div className="mt-3 w-3/4 h-1 bg-white/5 rounded-full overflow-hidden">
           <div 
             className="h-full shadow-[0_0_8px_rgba(34,197,94,0.3)] transition-all duration-300"
             style={{ width: `${Math.min(100, Math.max(2, progress))}%`, backgroundColor: themeColor }}
           />
        </div>
      </div>
    </BaseNode>
  );
});

export const ROIPolygonNode = memo(({ selected, data }: any) => {
  const [points, setPoints] = React.useState<any[]>([]);
  const frame = data.node_data?.main_preview || data.node_data?.main;
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
      title="ROI Polygon" 
      icon={Scaling} 
      selected={selected} 
      color="accent" 
      inputs={[{id: 'image', color: 'image'}]} 
      outputs={[
        {id: 'main', color: 'image'}, 
        {id: 'mask', color: 'mask'}, 
        {id: 'pts', color: 'list'}
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
            {/* Layer 1: Stretched Polygon */}
            <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 w-full h-full overflow-visible">
              {points.length >= 3 && (
                <polygon
                  points={points.map(p => `${p.x},${p.y}`).join(' ')}
                  className="fill-accent/30 stroke-accent"
                  style={{ strokeWidth: 0.012, vectorEffect: 'non-scaling-stroke' }}
                />
              )}
            </svg>

            {/* Layer 2: Circular Points */}
            {points.map((p, i) => (
              <circle 
                key={i} 
                cx={`${p.x * 100}%`} 
                cy={`${p.y * 100}%`} 
                r={4}
                className="fill-white stroke-accent" 
                style={{ strokeWidth: 1, vectorEffect: 'non-scaling-stroke' }} 
              />
            ))}
          </svg>
          
          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/roi:opacity-100 transition-all duration-300 flex items-center justify-center backdrop-blur-[2px]">
             <button 
               onClick={(e) => { e.stopPropagation(); onOpenEditor?.(); }}
               className="bg-accent hover:bg-blue-600 text-white px-5 py-2.5 rounded-xl shadow-2xl transition-all font-black text-[10px] uppercase tracking-widest scale-90 active:scale-95 flex items-center gap-2"
             >
               <Scaling size={12} /> Edit Region
             </button>
          </div>
        </div>

        <div className="flex items-center justify-between px-1">
           <div className="text-[8px] font-black text-gray-600 uppercase tracking-widest">
             {points.length} Vertices
           </div>
           <button 
             onClick={(e) => { e.stopPropagation(); onOpenEditor?.(); }}
             className="text-[8px] font-black text-accent uppercase tracking-widest hover:underline"
           >
             Modify Shape
           </button>
        </div>
      </div>
      <NodeResizeControl minWidth={200} minHeight={150}>
         <div className="absolute bottom-1 right-1 w-2 h-2 border-r-2 border-b-2 border-white/20" />
      </NodeResizeControl>
    </BaseNode>
  );
});

export const DrawOverlayNode = memo(({ selected }: any) => (
  <BaseNode title="Overlay" icon={PenTool} selected={selected} color="accent" inputs={[
    {id: 'image', color: 'image'}, 
    {id: 'data', color: 'data'}, 
    {id: 'data_2', color: 'data'}, 
    {id: 'data_3', color: 'data'}, 
    {id: 'data_4', color: 'data'}
  ]} outputs={[{id: 'main', color: 'image'}]} />
));

export const DataInspectorNode = memo(({ selected, data }: any) => {
  const d = data.node_data?.data_out;
  const isScalar = typeof d === 'number';
  const nodeId = useNodeId();
  
  return (
    <div className="relative group/node">
      <NodeResizeControl 
        minWidth={160} 
        minHeight={100} 
        style={{ background: 'transparent', border: 'none' }}
        onResize={(_, { width, height }) => {
          data.onChangeParams?.({ width, height });
        }}
      >
        <div className="absolute bottom-1 right-1 w-3 h-3 border-r-2 border-b-2 border-gray-600 rounded-br cursor-nwse-resize opacity-20 group-hover/node:opacity-100 transition-opacity" />
      </NodeResizeControl>
      
      <div style={{ width: data.params?.width || 208, height: data.params?.height || 'auto' }}>
        <BaseNode title="Inspector" icon={Eye} selected={selected} color="accent" inputs={[{id: 'data', color: 'data'}]}>
          {isScalar ? (
            <div className="text-xl font-mono text-center text-yellow-500 py-4">{d.toFixed(4)}</div>
          ) : (
            <pre className="text-[9px] font-mono bg-black/60 p-2 rounded h-full overflow-auto scrollbar-hide">
              {JSON.stringify(d, null, 2)}
            </pre>
          )}
        </BaseNode>
      </div>
    </div>
  );
});

export const DataListSelectorNode = memo(({ selected }: any) => (
  <BaseNode title="List Selector" icon={Database} selected={selected} color="green" inputs={[{id: 'list_in', color: 'list'}]} outputs={[{id: 'item_out', color: 'dict'}]} />
));

export const DataCoordSplitterNode = memo(({ selected }: any) => (
  <BaseNode title="Coord Splitter" icon={Database} selected={selected} color="green" inputs={[{id: 'dict_in', color: 'dict'}]} outputs={[
    {id: 'x', color: 'scalar'}, {id: 'y', color: 'scalar'}, {id: 'w', color: 'scalar'}, {id: 'h', color: 'scalar'}
  ]}>
    <div className="text-[9px] text-gray-500 uppercase font-black">Dict → 4 Scalars</div>
  </BaseNode>
));

export const DataCoordCombineNode = memo(({ selected }: any) => (
  <BaseNode title="Coord Combine" icon={Database} selected={selected} color="green" inputs={[
    {id: 'x', color: 'scalar'}, {id: 'y', color: 'scalar'}, {id: 'w', color: 'scalar'}, {id: 'h', color: 'scalar'}
  ]} outputs={[
    {id: 'dict_out', color: 'dict'}
  ]}>
    <div className="text-[9px] text-gray-500 uppercase font-black">4 Scalars → Dict</div>
  </BaseNode>
));

export const UtilCoordToMaskNode = memo(({ selected }: any) => (
  <BaseNode title="Coord To Mask" icon={Layers} selected={selected} color="accent" inputs={[{id: 'image', color: 'image'}, {id: 'data', color: 'dict'}]} outputs={[{id: 'mask', color: 'mask'}]}>
    <div className="text-[9px] text-gray-500 uppercase font-black">Dict → Raster Mask</div>
  </BaseNode>
));

export const UtilMaskBlendNode = memo(({ selected }: any) => (
  <BaseNode title="Mask Blend" icon={Layers} selected={selected} color="accent" inputs={[
    {id: 'image_a', color: 'image'}, 
    {id: 'image_b', color: 'image'}, 
    {id: 'mask', color: 'mask'}
  ]} outputs={[{id: 'main', color: 'image'}]}>
    <div className="text-[9px] text-gray-500 uppercase font-black">Alpha Compositing</div>
  </BaseNode>
));

export const OutputDisplayNode = memo(({ selected }: any) => (
  <BaseNode title="Final Out" icon={Maximize} selected={selected} color="green" inputs={[
    {id: 'main', color: 'image'},
    {id: 'mask_in', color: 'mask'},
    {id: 'flow_in', color: 'flow'}
  ]} />
));

// --- LOGIC & MATH ---

export const MathNode = memo(({ selected, data }: any) => {
  const schema = data.schema || { label: 'Math', icon: 'Calculator', inputs: [], outputs: [] };
  const IconCmp = getIcon(schema.icon, Calculator);
  return <BaseNode title={schema.label} icon={IconCmp} selected={selected} color="blue" inputs={schema.inputs} outputs={schema.outputs} />;
});

export const StringNode = memo(({ selected, data }: any) => {
  const schema = data.schema || { label: 'String', icon: 'Type', inputs: [], outputs: [] };
  const IconCmp = getIcon(schema.icon, Type);
  return (
    <BaseNode title={schema.label} icon={IconCmp} selected={selected} color="accent" inputs={schema.inputs} outputs={schema.outputs}>
       {data.node_data?.result && <div className="text-[9px] font-mono text-cyan-400 bg-black/40 p-2 rounded border border-white/5 truncate">{data.node_data.result}</div>}
    </BaseNode>
  );
});

export const PythonNode = memo(({ selected, data }: any) => {
  return (
    <BaseNode title="Python Script" icon={Zap} selected={selected} color="red" 
              inputs={[{id: 'a', color: 'any'}, {id: 'b', color: 'any'}, {id: 'c', color: 'any'}, {id: 'd', color: 'any'}]} 
              outputs={[{id: 'out_main', color: 'image'}, {id: 'out_scalar', color: 'scalar'}, {id: 'out_list', color: 'list'}, {id: 'out_dict', color: 'dict'}, {id: 'out_any', color: 'any'}]}>
      <div className="flex flex-col gap-1 opacity-60">
        <div className="text-[8px] font-bold text-red-500/80">DYNAMIC ENGINE</div>
        <div className="text-[7px] italic truncate">{data.params?.code?.substring(0, 30)}...</div>
      </div>
    </BaseNode>
  );
});

// --- SCIENTIFIC NODES ---

export const ScientificPlotterNode = memo(({ selected, data }: any) => {
  const [history, setHistory] = React.useState<any[]>([]);
  const val = data.node_data?.value;

  React.useEffect(() => {
    if (val !== undefined && val !== null) {
      setHistory(prev => {
        const next = [...prev, { time: Date.now(), v: val }];
        const limit = data.params?.buffer_size || 100;
        return next.slice(-limit);
      });
    }
  }, [val, data.params?.buffer_size]);

  return (
    <BaseNode title="Plotter" icon={Activity} selected={selected} color="blue" inputs={[{id: 'value', color: 'scalar'}]} outputs={[{id: 'value', color: 'scalar'}]}>
      <div className="h-20 w-full -mx-2 mt-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={history}>
            <defs>
              <linearGradient id="colorV" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#22d3ee" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <Area type="monotone" dataKey="v" stroke="#22d3ee" strokeWidth={2} fillOpacity={1} fill="url(#colorV)" isAnimationActive={false} />
            <YAxis hide domain={[data.params?.min_y ?? 'auto', data.params?.max_y ?? 'auto']} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </BaseNode>
  );
});

export const ScientificStatsNode = memo(({ selected, data }: any) => {
  const stats = data.node_data || {};
  const entries = [
    { label: 'Mean', v: stats.mean, color: 'text-cyan-400' },
    { label: 'Median', v: stats.median, color: 'text-blue-400' },
    { label: 'Std Dev', v: stats.std, color: 'text-purple-400' },
    { label: 'Range', v: (stats.max - stats.min), color: 'text-emerald-400' }
  ];

  return (
    <BaseNode title="Statistics" icon={Info} selected={selected} color="accent" inputs={[{id: 'data_list', color: 'list'}]} outputs={[
      {id: 'mean', color: 'scalar'}, {id: 'median', color: 'scalar'}, {id: 'std', color: 'scalar'}, {id: 'min', color: 'scalar'}, {id: 'max', color: 'scalar'}
    ]}>
      <div className="grid grid-cols-2 gap-2 mt-2">
        {entries.map(e => (
          <div key={e.label} className="bg-black/40 p-2 rounded-lg border border-white/5">
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
    <BaseNode title="Draw Text" icon={Type} selected={selected} inputs={schema.inputs} outputs={schema.outputs} var_count={varCount} width="w-80">
      <div className="flex flex-col gap-2 p-1 mx-6">
        <div className="flex items-center justify-between bg-black/20 p-2 rounded-lg border border-white/5">
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
        
        <div className="space-y-2">
          <div className="px-3 py-2 bg-black/40 rounded-xl border border-white/5">
            <div className="text-[7px] text-gray-500 uppercase font-black mb-1">Target Folder</div>
            <div className="text-[9px] font-mono text-gray-400 truncate">{data.params?.path || "Not selected"}</div>
          </div>
          <div className="px-3 py-2 bg-black/40 rounded-xl border border-white/5">
            <div className="text-[7px] text-gray-500 uppercase font-black mb-1">Base Filename</div>
            <div className="text-[9px] font-mono text-white/70 truncate">{data.params?.filename || "capture"}.csv</div>
          </div>
        </div>
      </div>
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

  const outputs = data.dynamicColor 
    ? schema.outputs.map((out: any) => ({ ...out, color: data.dynamicColor }))
    : schema.outputs;

  return (
    <BaseNode title={schema.label} icon={IconCmp} selected={selected} color="accent" inputs={schema.inputs} outputs={outputs}>
      {/* Minimalist: internal content moved to Inspector */}
    </BaseNode>
  );
});
