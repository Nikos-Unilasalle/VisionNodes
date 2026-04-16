import React, { useState, useCallback, useMemo, useEffect } from 'react';
import ReactFlow, { 
  addEdge, Background, Controls, applyEdgeChanges, applyNodeChanges,
  Node, Edge, Connection, EdgeChange, NodeChange, Panel
} from 'reactflow';
import 'reactflow/dist/style.css';
import { 
  Camera, Waves, Ghost, Maximize, Settings, Cpu, HardDrive, Info, 
  Plus, Layers, Search, User, Scaling, Zap, Activity, ChevronRight,
  Hash, Eye, Layout, PenTool, Database, Wind, Target, Move, Palette
} from 'lucide-react';
import * as N from './components/Nodes';
import { useVisionEngine } from './hooks/useVisionEngine';

const initialNodes: Node[] = [
  { id: 'node-1', type: 'input_webcam', position: { x: 50, y: 150 }, data: { label: 'Webcam', params: { device_index: 0 } } },
  { id: 'node-2', type: 'analysis_face_mp', position: { x: 300, y: 150 }, data: { label: 'Face Tracking', params: { max_faces: 3 } } },
  { id: 'node-4', type: 'output_display', position: { x: 600, y: 150 }, data: { label: 'Display Outlet', params: {} } },
];

const initialEdges: Edge[] = [
  { id: 'e1-2', source: 'node-1', target: 'node-2', sourceHandle: 'main', targetHandle: 'main' },
  { id: 'e2-4', source: 'node-2', target: 'node-4', sourceHandle: 'main', targetHandle: 'main' },
];

const nodeTypes = {
  input_webcam: N.InputWebcamNode,
  filter_canny: N.FilterCannyNode,
  filter_blur: N.FilterBlurNode,
  filter_gray: N.FilterGrayNode,
  filter_threshold: N.FilterThresholdNode,
  geom_flip: N.GeomFlipNode,
  geom_resize: N.GeomResizeNode,
  analysis_face_mp: N.AnalysisFaceMPNode,
  analysis_flow: N.AnalysisFlowNode,
  analysis_flow_viz: N.AnalysisFlowVizNode,
  analysis_zone_mean: N.AnalysisZoneMeanNode,
  draw_overlay: N.DrawOverlayNode,
  data_inspector: N.DataInspectorNode,
  output_display: N.OutputDisplayNode,
};

const CATEGORIES = [
  { id: 'src', label: 'Sources', icon: Camera, nodes: [{ type: 'input_webcam', label: 'Webcam' }] },
  { id: 'cv', label: 'Filters', icon: Waves, nodes: [
    { type: 'filter_canny', label: 'Canny Edge' },
    { type: 'filter_blur', label: 'Gaussian Blur' },
    { type: 'filter_gray', label: 'Grayscale' },
    { type: 'filter_threshold', label: 'Threshold' }
  ]},
  { id: 'geom', label: 'Geometric', icon: Move, nodes: [
    { type: 'geom_flip', label: 'Flip' },
    { type: 'geom_resize', label: 'Resize' }
  ]},
  { id: 'motion', label: 'Motion', icon: Wind, nodes: [
    { type: 'analysis_flow', label: 'Optical Flow' },
    { type: 'analysis_flow_viz', label: 'Flow Viz' },
    { type: 'analysis_zone_mean', label: 'Zone Mean' }
  ]},
  { id: 'ai', label: 'Tracking', icon: User, nodes: [{ type: 'analysis_face_mp', label: 'Face Tracker' }] },
  { id: 'util', label: 'Utilities', icon: PenTool, nodes: [
    { type: 'draw_overlay', label: 'Visual Overlay' },
    { type: 'data_inspector', label: 'Inspect Unit' }
  ]},
  { id: 'out', label: 'Terminal', icon: Maximize, nodes: [{ type: 'output_display', label: 'Final Display' }] }
];

function App() {
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState(CATEGORIES[1]);
  const { frame, nodesData, isConnected, updateGraph } = useVisionEngine();

  const nodesWithData = useMemo(() => {
    return nodes.map(node => {
      const dataKeys = Object.keys(nodesData).filter(k => k.startsWith(`${node.id}:`));
      const techData = dataKeys.length > 0 ? Object.fromEntries(dataKeys.map(k => [k.split(':')[1], nodesData[k]])) : nodesData[node.id];
      return { ...node, data: { ...node.data, node_data: techData } };
    });
  }, [nodes, nodesData]);

  const selectedNode = useMemo(() => nodesWithData.find((n) => n.id === selectedNodeId) || null, [nodesWithData, selectedNodeId]);

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => {
      const nextNodes = applyNodeChanges(changes, nds);
      updateGraph(nextNodes, edges);
      return nextNodes;
    });
  }, [edges, updateGraph]);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((eds) => {
      const nextEdges = applyEdgeChanges(changes, eds);
      updateGraph(nodes, nextEdges);
      return nextEdges;
    });
  }, [nodes, updateGraph]);

  const onConnect = useCallback((params: Connection) => {
    setEdges((eds) => {
      const nextEdges = addEdge({ ...params, id: `e-${Date.now()}` }, eds);
      updateGraph(nodes, nextEdges);
      return nextEdges;
    });
  }, [nodes, updateGraph]);

  const updateNodeParams = (id: string, params: any) => {
    setNodes((nds) => {
      const nextNodes = nds.map((node) => {
        if (node.id === id) return { ...node, data: { ...node.data, params: { ...node.data.params, ...params } } };
        return node;
      });
      updateGraph(nextNodes, edges);
      return nextNodes;
    });
  };

  const addNode = (type: string, label: string) => {
    const id = `node-${Date.now()}`;
    setNodes((nds) => {
      const nextNodes = [...nds, { id, type, position: { x: 350, y: 350 }, data: { label, params: {} } }];
      updateGraph(nextNodes, edges);
      return nextNodes;
    });
    setIsAddMenuOpen(false);
  };

  useEffect(() => { if (isConnected) updateGraph(nodes, edges); }, [isConnected]);

  return (
    <div className="w-full h-screen bg-[#0a0a0a] flex flex-col text-white font-sans overflow-hidden select-none">
      <header className="h-10 bg-[#151515] border-b border-[#222] flex items-center justify-between px-4 z-50">
        <div className="flex items-center gap-6">
           <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-accent rounded rotate-45 flex items-center justify-center shadow-lg shadow-accent/20 transition-transform hover:rotate-90">
                 <Cpu size={10} className="text-white" />
              </div>
              <h1 className="text-[10px] font-black tracking-[0.3em] text-white uppercase">VisionNodes Studio</h1>
           </div>
           <div className={`px-2 py-0.5 rounded text-[8px] font-bold ${isConnected ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'} border border-current opacity-60`}>
              {isConnected ? 'RUNTIME_CONNECTED' : 'WAITING_FOR_WS'}
           </div>
        </div>
      </header>

      <div className="flex-1 flex w-full relative">
        <div className="flex-1 relative overflow-hidden bg-[#080808]">
          <ReactFlow
            nodes={nodesWithData} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
            nodeTypes={nodeTypes} onNodeClick={(_, node) => setSelectedNodeId(node.id)} onPaneClick={() => setSelectedNodeId(null)}
            fitView
          >
            <Background color="#111" variant="lines" gap={40} size={1} />
            <Controls className="bg-[#1a1a1a] border-[#333] fill-white" />
            <Panel position="top-left">
              <button 
                onClick={() => setIsAddMenuOpen(!isAddMenuOpen)}
                className="bg-accent hover:bg-blue-600 text-white p-2 px-8 rounded-full shadow-2xl transition-all font-black text-[10px] tracking-widest uppercase flex items-center gap-2"
              >
                <Plus size={14} /> Add Module
              </button>
            </Panel>
          </ReactFlow>

          {isAddMenuOpen && (
            <div className="absolute inset-0 bg-black/80 backdrop-blur-md z-[100] flex items-center justify-center p-20" onClick={() => setIsAddMenuOpen(false)}>
              <div 
                className="bg-[#181818] border border-[#333] w-full max-w-[700px] h-[550px] rounded-3xl shadow-2xl flex overflow-hidden animate-in zoom-in-95 duration-200"
                onClick={e => e.stopPropagation()}
              >
                <div className="w-56 bg-[#111] border-r border-[#222] p-6 flex flex-col gap-2">
                  {CATEGORIES.map(cat => (
                    <button 
                      key={cat.id} onClick={() => setActiveCategory(cat)}
                      className={`flex items-center gap-4 px-4 py-3 rounded-2xl text-[11px] font-bold transition-all ${activeCategory.id === cat.id ? 'bg-accent text-white shadow-xl shadow-accent/20' : 'text-gray-500 hover:bg-white/5'}`}
                    >
                      <cat.icon size={18} /> {cat.label}
                    </button>
                  ))}
                </div>
                <div className="flex-1 p-12 overflow-y-auto overflow-x-hidden">
                  <h3 className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-10 border-b border-[#222] pb-2">Category :: {activeCategory.label}</h3>
                  <div className="grid grid-cols-2 gap-4">
                    {activeCategory.nodes.map(node => (
                      <button
                        key={node.type} onClick={() => addNode(node.type, node.label)}
                        className="p-6 bg-[#222] hover:bg-accent/10 border border-[#333] hover:border-accent/40 rounded-3xl text-left transition-all active:scale-95"
                      >
                        <div className="text-[11px] font-bold text-gray-200 uppercase tracking-tighter">{node.label}</div>
                        <div className="text-[8px] text-gray-600 font-mono mt-1 italic">cv::node</div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="absolute bottom-6 left-6 w-[400px] aspect-video bg-black border-2 border-[#222] rounded-3xl shadow-2xl overflow-hidden z-20 group hover:border-accent transition-all duration-700">
             {frame && <img src={frame} alt="Vision" className="w-full h-full object-contain" />}
          </div>
        </div>

        <aside className="w-85 bg-[#111] border-l border-[#222] flex flex-col z-30 shadow-2xl">
          <div className="h-10 border-b border-[#222] flex items-center px-4 bg-[#1a1a1a]">
            <Settings size={14} className="text-gray-500 mr-2" />
            <span className="text-[10px] font-black tracking-widest text-gray-400 uppercase">Unit Inspector</span>
          </div>
          
          <div className="p-10 flex flex-col gap-10 overflow-y-auto scrollbar-hide">
            {selectedNode ? (
              <div className="space-y-12 animate-in slide-in-from-right-10 duration-500">
                <div className="flex items-center gap-5">
                   <div className="w-16 h-16 bg-accent/5 rounded-3xl border border-accent/20 flex items-center justify-center text-accent shadow-inner">
                      <Cpu size={32} />
                   </div>
                   <div>
                      <h2 className="text-[14px] font-black text-white uppercase tracking-wider">{selectedNode.data.label}</h2>
                      <span className="text-[9px] text-gray-600 font-mono italic opacity-40">{selectedNode.id}</span>
                   </div>
                </div>

                <div className="space-y-8 pb-32">
                  {/* --- ALL SLIDERS FOR PERMANENT ACCESSIBILITY --- */}
                  {selectedNode.type === 'input_webcam' && (
                    <Slider label="Device Index" val={selectedNode.data.params.device_index || 0} min={0} max={5} onChange={v => updateNodeParams(selectedNode.id, {device_index: v})} />
                  )}
                  {selectedNode.type === 'filter_canny' && (
                    <>
                      <Slider label="Threshold Low" val={selectedNode.data.params.low || 100} min={1} max={500} onChange={v => updateNodeParams(selectedNode.id, {low: v})} />
                      <Slider label="Threshold High" val={selectedNode.data.params.high || 200} min={1} max={500} onChange={v => updateNodeParams(selectedNode.id, {high: v})} />
                    </>
                  )}
                  {selectedNode.type === 'filter_blur' && (
                    <Slider label="Blur Kernel" val={selectedNode.data.params.size || 5} min={1} max={51} step={2} onChange={v => updateNodeParams(selectedNode.id, {size: v})} />
                  )}
                  {selectedNode.type === 'filter_threshold' && (
                    <Slider label="Value" val={selectedNode.data.params.threshold || 127} min={0} max={255} onChange={v => updateNodeParams(selectedNode.id, {threshold: v})} />
                  )}
                  {selectedNode.type === 'geom_resize' && (
                    <Slider label="Scale Factor" val={selectedNode.data.params.scale || 1} min={0.1} max={3} step={0.1} onChange={v => updateNodeParams(selectedNode.id, {scale: v})} />
                  )}
                  {selectedNode.type === 'geom_flip' && (
                    <Slider label="Flip Code (0,1,-1)" val={selectedNode.data.params.flip_mode || 1} min={-1} max={1} step={1} onChange={v => updateNodeParams(selectedNode.id, {flip_mode: v})} />
                  )}
                  {selectedNode.type === 'analysis_face_mp' && (
                    <Slider label="Track Count" val={selectedNode.data.params.max_faces || 3} min={1} max={10} onChange={v => updateNodeParams(selectedNode.id, {max_faces: v})} />
                  )}
                  {selectedNode.type === 'analysis_flow' && (
                    <>
                       <Slider label="Pyr Scale" val={selectedNode.data.params.pyr_scale || 0.5} min={0.1} max={0.9} step={0.1} onChange={v => updateNodeParams(selectedNode.id, {pyr_scale: v})} />
                       <Slider label="Levels" val={selectedNode.data.params.levels || 3} min={1} max={10} onChange={v => updateNodeParams(selectedNode.id, {levels: v})} />
                       <Slider label="Iterations" val={selectedNode.data.params.iterations || 3} min={1} max={10} onChange={v => updateNodeParams(selectedNode.id, {iterations: v})} />
                    </>
                  )}
                  {selectedNode.type === 'draw_overlay' && (
                    <Slider label="Thickness" val={selectedNode.data.params.thickness || 2} min={1} max={10} onChange={v => updateNodeParams(selectedNode.id, {thickness: v})} />
                  )}

                  {selectedNode.data.node_data && (
                    <div className="p-6 bg-black/40 rounded-3xl border border-white/5 space-y-4 shadow-inner">
                       <div className="text-[9px] font-black text-gray-600 uppercase tracking-[0.3em] flex items-center gap-2"><Activity size={12}/> Analysis Data</div>
                       <pre className="text-[10px] font-mono text-accent/80 max-h-56 overflow-auto scrollbar-hide italic leading-relaxed">
                          {JSON.stringify(selectedNode.data.node_data, null, 2)}
                       </pre>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center opacity-5 py-20 grayscale pointer-events-none">
                <Layout size={120} />
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

const Slider = ({ label, val, min, max, step = 1, onChange }: any) => (
  <div className="space-y-4 group">
    <div className="flex justify-between text-[10px]">
      <label className="text-gray-500 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
      <span className="text-accent font-black font-mono bg-accent/10 px-3 py-1 rounded-lg border border-accent/20">{val}</span>
    </div>
    <input type="range" min={min} max={max} step={step} value={val} onChange={(e) => onChange(parseFloat(e.target.value))} className="w-full h-1.5 bg-[#222] rounded-full appearance-none cursor-pointer accent-accent" />
  </div>
);

export default App;
