import React, { memo } from 'react';
import { Handle, Position, useNodeId } from 'reactflow';
import { open } from '@tauri-apps/plugin-dialog';
import { 
  Camera, Waves, Ghost, Maximize, Search, User, Zap, Activity,
  Hash, Eye, Layout, PenTool, Database, Wind, Target, Palette, Scaling, Move, Layers, Box, Image, Film, Play, Pause,
  Plus, Info
} from 'lucide-react';
import * as LucideIcons from 'lucide-react';
import { 
  AreaChart, Area, ResponsiveContainer, YAxis, XAxis, Tooltip,
  BarChart, Bar, Cell
} from 'recharts';

export const HANDLE_COLORS = { image: '#3b82f6', data: '#22c55e', dict: '#22c55e', list: '#a855f7', scalar: '#eab308', mask: '#d1d5db', flow: '#ef4444', boolean: '#22d3ee', any: '#ffffff' };

const StyledHandle = ({ type, position, id, color = 'image', top }: any) => {
  const nodeId = useNodeId();
  const handleId = `${color}__${id}`;
  return (
    <Handle
      type={type}
      position={position}
      id={handleId}
      style={{ background: HANDLE_COLORS[color as keyof typeof HANDLE_COLORS] || color, width: 10, height: 10, border: '2px solid #111', top: top }}
      onClick={(e) => {
        e.stopPropagation();
        window.dispatchEvent(new CustomEvent('remove-handle-edge', { detail: { nodeId, handleId, type } }));
      }}
    />
  );
};

const BaseNode = ({ title, icon: Icon, children, selected, color = 'accent', inputs = [], outputs = [] }: any) => {
  const accentColor = color === 'accent' ? 'border-accent shadow-accent/20' : 
                      color === 'green' ? 'border-green-500 shadow-green-500/20' :
                      color === 'blue' ? 'border-blue-500 shadow-blue-500/20' :
                      color === 'red' ? 'border-red-500 shadow-red-500/20' :
                      'border-gray-500 shadow-gray-500/20';
                      
  return (
    <div className={`rounded-xl bg-[#1a1a1a] border-2 transition-all duration-300 ${selected ? accentColor + ' shadow-lg scale-105' : 'border-[#333]'} w-52 overflow-hidden shadow-2xl`}>
      {inputs.map((inp: any, i: number) => (
        <StyledHandle key={inp.id} type="target" position={Position.Left} id={inp.id} color={inp.color} top={`${(i + 1) * (100 / (inputs.length + 1))}%`} />
      ))}
      <div className="bg-[#222] px-4 py-2 flex items-center gap-3 border-b border-[#333]">
        <Icon size={14} className="text-gray-400" />
        <span className="font-bold text-[10px] uppercase tracking-widest text-gray-200">{title}</span>
      </div>
      <div className="p-2 text-[10px] text-gray-400 flex flex-col gap-2">
        {children}
      </div>
      {outputs.map((out: any, i: number) => (
        <StyledHandle key={out.id} type="source" position={Position.Right} id={out.id} color={out.color} top={`${(i + 1) * (100 / (outputs.length + 1))}%`} />
      ))}
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
      <div 
        className="flex flex-col items-center justify-center border-2 border-dashed border-[#333] rounded-lg p-4 opacity-40 hover:opacity-100 transition-opacity cursor-pointer"
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
        onClick={handleBrowse}
      >
        <Search size={20} className="text-gray-500 mb-2" />
        <div className="text-[7px] text-gray-500 uppercase font-black text-center">Click to Browse<br/>or Drop Movie</div>
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

export const AnalysisFlowNode = memo(({ selected }: any) => (
  <BaseNode title="Optical Flow" icon={Activity} selected={selected} color="red" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}, {id: 'data', color: 'flow'}]}>
    <div className="text-[9px] text-gray-500 uppercase font-black">Motion Vectors</div>
  </BaseNode>
));

export const AnalysisFlowVizNode = memo(({ selected }: any) => (
  <BaseNode title="Flow Viz" icon={Palette} selected={selected} color="accent" inputs={[{id: 'data', color: 'flow'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const AnalysisZoneMeanNode = memo(({ selected, data }: any) => (
  <BaseNode title="Area Monitor" icon={Target} selected={selected} color="blue" inputs={[{id: 'main', color: 'image'}, {id: 'data', color: 'flow'}]} outputs={[{id: 'main', color: 'image'}, {id: 'scalar', color: 'data'}]}>
    <div className="text-xl font-mono text-center text-white">{(data.node_data?.scalar || 0).toFixed(4)}</div>
  </BaseNode>
));

export const DrawOverlayNode = memo(({ selected }: any) => (
  <BaseNode title="Overlay" icon={PenTool} selected={selected} color="accent" inputs={[
    {id: 'image', color: 'image'}, 
    {id: 'data', color: 'any'}, 
    {id: 'data_2', color: 'any'}, 
    {id: 'data_3', color: 'any'}, 
    {id: 'data_4', color: 'any'}
  ]} outputs={[{id: 'main', color: 'image'}]} />
));

export const DataInspectorNode = memo(({ selected, data }: any) => {
  const d = data.node_data?.data_out;
  const isScalar = typeof d === 'number';
  
  return (
    <BaseNode title="Inspector" icon={Eye} selected={selected} color="accent" inputs={[{id: 'data', color: 'any'}]}>
      {isScalar ? (
        <div className="text-xl font-mono text-center text-yellow-500 py-4">{d.toFixed(4)}</div>
      ) : (
        <pre className="text-[9px] font-mono bg-black/60 p-2 rounded h-20 overflow-auto">{JSON.stringify(d, null, 2)}</pre>
      )}
    </BaseNode>
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

export const GenericCustomNode = memo(({ selected, data }: any) => {
  const schema = data.schema || { label: 'Unknown Plugin', icon: 'Box', inputs: [], outputs: [] };
  const IconCmp = (LucideIcons as any)[schema.icon] || Box;

  if (schema.type === 'sci_plotter') return <ScientificPlotterNode selected={selected} data={data} />;
  if (schema.type === 'sci_stats') return <ScientificStatsNode selected={selected} data={data} />;

  const outputs = data.dynamicColor 
    ? schema.outputs.map((out: any) => ({ ...out, color: data.dynamicColor }))
    : schema.outputs;

  return (
    <BaseNode title={schema.label} icon={IconCmp} selected={selected} color="accent" inputs={schema.inputs} outputs={outputs}>
      {/* Minimalist: internal content moved to Inspector */}
    </BaseNode>
  );
});
