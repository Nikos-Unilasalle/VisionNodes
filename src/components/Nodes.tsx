import React, { memo } from 'react';
import { Handle, Position, useNodeId } from 'reactflow';
import { 
  Camera, Waves, Ghost, Maximize, Search, User, Zap, Activity,
  Hash, Eye, Layout, PenTool, Database, Wind, Target, Palette, Scaling, Move, Layers, Box
} from 'lucide-react';
import * as LucideIcons from 'lucide-react';

export const HANDLE_COLORS = { image: '#3b82f6', data: '#22c55e', dict: '#22c55e', list: '#a855f7', scalar: '#eab308', mask: '#d1d5db', flow: '#ef4444', any: '#ffffff' };

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
      <div className="p-4 text-[10px] text-gray-400 flex flex-col gap-2">
        {children}
      </div>
      {outputs.map((out: any, i: number) => (
        <StyledHandle key={out.id} type="source" position={Position.Right} id={out.id} color={out.color} top={`${(i + 1) * (100 / (outputs.length + 1))}%`} />
      ))}
    </div>
  );
};

// --- NODES ---
export const InputWebcamNode = memo(({ selected, data }: any) => (
  <BaseNode title="Webcam" icon={Camera} selected={selected} color="green" outputs={[{id: 'main', color: 'image'}]}>
    <div className="text-[10px] text-green-500 font-mono">ID: {data.params?.device_index || 0}</div>
  </BaseNode>
));

export const SolidColorNode = memo(({ selected, data }: any) => (
  <BaseNode title="Solid Color" icon={Palette} selected={selected} color="green" outputs={[{id: 'main', color: 'image'}]}>
    <div className="flex gap-2 text-[9px] font-black items-center justify-center pt-2 pb-1">
       <span className="text-red-500 bg-red-500/10 px-2 py-1 rounded">R:{data.params?.r ?? 255}</span>
       <span className="text-green-500 bg-green-500/10 px-2 py-1 rounded">G:{data.params?.g ?? 0}</span>
       <span className="text-blue-500 bg-blue-500/10 px-2 py-1 rounded">B:{data.params?.b ?? 0}</span>
    </div>
  </BaseNode>
));

export const FilterCannyNode = memo(({ selected }: any) => (
  <BaseNode title="Canny Edge" icon={Waves} selected={selected} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const FilterBlurNode = memo(({ selected }: any) => (
  <BaseNode title="Blur" icon={Ghost} selected={selected} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const FilterGrayNode = memo(({ selected }: any) => (
  <BaseNode title="Grayscale" icon={Eye} selected={selected} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));

export const FilterMorphologyNode = memo(({ selected }: any) => (
  <BaseNode title="Morphology" icon={Waves} selected={selected} color="accent" inputs={[{id: 'mask', color: 'mask'}, {id: 'image', color: 'image'}]} outputs={[{id: 'mask', color: 'mask'}]}>
    <div className="text-[9px] text-gray-500 uppercase font-black">Erode / Dilate</div>
  </BaseNode>
));

export const FilterColorMaskNode = memo(({ selected }: any) => (
  <BaseNode title="Color Mask" icon={Palette} selected={selected} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'mask', color: 'mask'}]}>
    <div className="text-[9px] text-gray-500 uppercase font-black">HSV Isolation</div>
  </BaseNode>
));

export const FilterThresholdNode = memo(({ selected }: any) => (
  <BaseNode title="Threshold" icon={Zap} selected={selected} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}, {id: 'mask', color: 'mask'}]} />
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
    <BaseNode title="Face Tracker" icon={User} selected={selected} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={outputs}>
      <div className="text-[9px] text-gray-500 uppercase font-black">MediaPipe Face ({max})</div>
    </BaseNode>
  );
});

export const AnalysisHandMPNode = memo(({ selected, data }: any) => {
  const max = data.params?.max_hands || 2;
  const outputs = [{id: 'main', color: 'image'}, {id: 'hands_list', color: 'list'}, ...Array.from({ length: max }).map((_, i) => ({ id: `hand_${i}`, color: 'data' }))];
  return (
    <BaseNode title="Hand Tracker" icon={User} selected={selected} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={outputs}>
      <div className="text-[9px] text-gray-500 uppercase font-black">MediaPipe Hands ({max})</div>
    </BaseNode>
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
  <BaseNode title="Zone Mean" icon={Target} selected={selected} color="blue" inputs={[{id: 'main', color: 'image'}, {id: 'data', color: 'flow'}]} outputs={[{id: 'main', color: 'image'}, {id: 'scalar', color: 'data'}]}>
    <div className="text-xl font-mono text-center text-white">{(data.node_data?.scalar || 0).toFixed(4)}</div>
  </BaseNode>
));

export const DrawOverlayNode = memo(({ selected }: any) => (
  <BaseNode title="Overlay" icon={PenTool} selected={selected} color="accent" inputs={[{id: 'image', color: 'image'}, {id: 'data', color: 'any'}]} outputs={[{id: 'main', color: 'image'}]} />
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

export const DataListSelectorNode = memo(({ selected, data }: any) => (
  <BaseNode title="List Selector" icon={Database} selected={selected} color="green" inputs={[{id: 'list_in', color: 'list'}]} outputs={[{id: 'item_out', color: 'dict'}]}>
    <div className="text-[10px] text-purple-400 font-mono">Index: {data.params?.index || 0}</div>
  </BaseNode>
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

export const GenericCustomNode = memo(({ selected, data }: any) => {
  const schema = data.schema || { label: 'Unknown Plugin', icon: 'Box', inputs: [], outputs: [] };
  const IconCmp = (LucideIcons as any)[schema.icon] || Box;

  return (
    <BaseNode title={schema.label} icon={IconCmp} selected={selected} color="accent" inputs={schema.inputs} outputs={schema.outputs}>
      <div className="text-[9px] text-gray-500 uppercase font-black">Dynamic Plugin</div>
      {data.node_data && data.node_data.display_text && (
        <div className="text-xl font-mono text-center text-yellow-500 py-2">{data.node_data.display_text}</div>
      )}
    </BaseNode>
  );
});
