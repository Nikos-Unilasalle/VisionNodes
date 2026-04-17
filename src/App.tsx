import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import ReactFlow, { 
  addEdge, Background, Controls, applyEdgeChanges, applyNodeChanges,
  Node, Edge, Connection, EdgeChange, NodeChange, Panel
} from 'reactflow';
import 'reactflow/dist/style.css';
import { 
  Camera, Waves, Ghost, Maximize, Settings, Cpu, HardDrive, Info, 
  Plus, Layers, Search, User, Scaling, Zap, Activity, ChevronRight,
  Hash, Eye, Layout, PenTool, Database, Wind, Target, Move, Palette, Box, Image, Film
} from 'lucide-react';
import * as N from './components/Nodes';
import { useVisionEngine } from './hooks/useVisionEngine';

const initialNodes: Node[] = [
  { id: 'node-1', type: 'input_webcam', position: { x: 50, y: 150 }, data: { label: 'Webcam', params: { device_index: 0 } } },
  { id: 'node-2', type: 'analysis_face_mp', position: { x: 300, y: 150 }, data: { label: 'Face Tracking', params: { max_faces: 3 } } },
  { id: 'node-4', type: 'output_display', position: { x: 600, y: 150 }, data: { label: 'Display Outlet', params: {} } },
];

const initialEdges: Edge[] = [
  { id: 'e1-2', source: 'node-1', target: 'node-2', sourceHandle: 'image__main', targetHandle: 'image__image' },
  { id: 'e2-4', source: 'node-2', target: 'node-4', sourceHandle: 'image__main', targetHandle: 'image__main' },
];

const nodeTypes = {
  input_webcam: N.InputWebcamNode,
  input_image: N.InputImageNode,
  input_movie: N.InputMovieNode,
  input_solid_color: N.SolidColorNode,
  filter_canny: N.FilterCannyNode,
  filter_blur: N.FilterBlurNode,
  filter_gray: N.FilterGrayNode,
  filter_threshold: N.FilterThresholdNode,
  filter_morphology: N.FilterMorphologyNode,
  filter_color_mask: N.FilterColorMaskNode,
  geom_flip: N.GeomFlipNode,
  geom_resize: N.GeomResizeNode,
  analysis_face_mp: N.AnalysisFaceMPNode,
  analysis_hand_mp: N.AnalysisHandMPNode,
  analysis_flow: N.AnalysisFlowNode,
  analysis_flow_viz: N.AnalysisFlowVizNode,
  analysis_zone_mean: N.AnalysisZoneMeanNode,
  draw_overlay: N.DrawOverlayNode,
  draw_point: N.GenericCustomNode,
  draw_line: N.GenericCustomNode,
  draw_rect: N.GenericCustomNode,
  util_coord_to_mask: N.UtilCoordToMaskNode,
  util_mask_blend: N.UtilMaskBlendNode,
  data_list_selector: N.DataListSelectorNode,
  data_coord_splitter: N.DataCoordSplitterNode,
  data_coord_combine: N.DataCoordCombineNode,
  data_inspector: N.DataInspectorNode,
  output_display: N.OutputDisplayNode,
};

const CATEGORIES = [
  { id: 'src', label: 'Sources', icon: Camera, nodes: [
    { type: 'input_webcam', label: 'Webcam' },
    { type: 'input_image', label: 'Image File' },
    { type: 'input_movie', label: 'Movie File' },
    { type: 'input_solid_color', label: 'Solid Color' }
  ]},
  { id: 'cv', label: 'Filters', icon: Waves, nodes: [
    { type: 'filter_canny', label: 'Canny Edge' },
    { type: 'filter_blur', label: 'Gaussian Blur' },
    { type: 'filter_gray', label: 'Grayscale' },
    { type: 'filter_threshold', label: 'Threshold' }
  ]},
  { id: 'mask', label: 'Masks', icon: Layers, nodes: [
    { type: 'filter_color_mask', label: 'Color Mask' },
    { type: 'filter_morphology', label: 'Morphology' },
    { type: 'util_coord_to_mask', label: 'Coord To Mask' }
  ]},
  { id: 'blend', label: 'Blending', icon: Box, nodes: [
    { type: 'util_mask_blend', label: 'Mask Blend' }
  ]},
  { id: 'geom', label: 'Geometric', icon: Move, nodes: [
    { type: 'geom_flip', label: 'Flip' },
    { type: 'geom_resize', label: 'Resize' }
  ]},
  { id: 'track', label: 'Tracking', icon: User, nodes: [
    { type: 'analysis_face_mp', label: 'Face Tracker' },
    { type: 'analysis_hand_mp', label: 'Hand Tracker' },
    { type: 'analysis_flow', label: 'Optical Flow' }
  ]},
  { id: 'features', label: 'Features', icon: Target, nodes: [] },
  { id: 'visualize', label: 'Visualizers', icon: Eye, nodes: [
    { type: 'data_inspector', label: 'Inspect Unit' },
    { type: 'analysis_zone_mean', label: 'Area Monitor' },
    { type: 'analysis_flow_viz', label: 'Flow Viz' }
  ]},
  { id: 'draw', label: 'Drawing', icon: PenTool, nodes: [
    { type: 'draw_overlay', label: 'Visual Overlay' }
  ]},
  { id: 'util', label: 'Utilities', icon: Box, nodes: [
    { type: 'data_list_selector', label: 'List Selector' },
    { type: 'data_coord_splitter', label: 'Coord Splitter' },
    { type: 'data_coord_combine', label: 'Coord Combine' }
  ]},
  { id: 'logic', label: 'Logic', icon: Zap, nodes: [] },
  { id: 'scientific', label: 'Scientific', icon: Activity, nodes: [] },
  { id: 'out', label: 'Output', icon: Maximize, nodes: [
    { type: 'output_display', label: 'Final Display' }
  ] }
];

function App() {
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false);
  const [pendingConnection, setPendingConnection] = useState<any>(null);
  const [activeCategoryId, setActiveCategoryId] = useState(CATEGORIES[1].id);
  const [rightPanelWidth, setRightPanelWidth] = useState(340);
  const isResizing = useRef(false);
  const { frame, nodesData, pluginSchemas, isConnected, updateGraph } = useVisionEngine();

  const dynamicCategories = useMemo(() => {
    const cats = CATEGORIES.map(c => ({...c, nodes: [...c.nodes]}));
    // Collect all statically-defined node types to avoid duplicates
    const staticTypes = new Set(CATEGORIES.flatMap(c => c.nodes.map(n => n.type)));
    (pluginSchemas || []).forEach(schema => {
      if (staticTypes.has(schema.type)) return; // skip already registered
      let targetCat = cats.find((c: any) => c.id === schema.category);
      if (!targetCat) {
         targetCat = {
            id: schema.category,
            label: schema.category.charAt(0).toUpperCase() + schema.category.slice(1),
            icon: Layers,
            nodes: []
         } as any;
         cats.splice(cats.length - 1, 0, targetCat as any);
      }
      targetCat!.nodes.push({ type: schema.type, label: schema.label, schema: schema } as any);
    });
    return cats;
  }, [pluginSchemas]);

  const activeCategory: any = dynamicCategories.find(c => c.id === activeCategoryId) || dynamicCategories[0];

  const dynamicNodeTypes = useMemo(() => {
    const types: any = { ...nodeTypes };
    (pluginSchemas || []).forEach(schema => {
      types[schema.type] = N.GenericCustomNode;
    });
    return types;
  }, [pluginSchemas]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing.current) return;
      const newWidth = Math.max(250, Math.min(800, document.body.clientWidth - e.clientX));
      setRightPanelWidth(newWidth);
    };
    const handleMouseUp = () => { isResizing.current = false; };
    
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsAddMenuOpen(false);
        setPendingConnection(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const nodesWithData = useMemo(() => {
    return nodes.map(node => {
      const dataKeys = Object.keys(nodesData).filter(k => k.startsWith(`${node.id}:`));
      const techData = dataKeys.length > 0 ? Object.fromEntries(dataKeys.map(k => [k.split(':')[1], nodesData[k]])) : nodesData[node.id];
      
      let dynamicColor = null;
      if (node.type === 'logic_switch') {
        const edge = edges.find(e => e.target === node.id && (e.targetHandle?.endsWith('if_true') || e.targetHandle?.endsWith('if_false')));
        if (edge) dynamicColor = edge.sourceHandle?.split('__')[0];
      }

      return { 
        ...node, 
        data: { 
          ...node.data, 
          node_data: techData,
          dynamicColor,
          onChangeParams: (p: any) => updateNodeParams(node.id, p)
        } 
      };
    });
  }, [nodes, nodesData, edges]);

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

  const onConnectEnd = useCallback((event: any, connectionState?: any) => {
    if (connectionState && connectionState.isValid === false) {
      const containerBounds = document.querySelector('.react-flow')?.getBoundingClientRect();
      const x = event.clientX - (containerBounds?.left || 0);
      const y = event.clientY - (containerBounds?.top || 0);
      setPendingConnection({
        sourceNode: connectionState.fromNode?.id,
        sourceHandle: connectionState.fromHandle?.id,
        type: connectionState.fromHandle?.type,
        x, y
      });
      setIsAddMenuOpen(true);
    }
  }, []);

  const isValidConnection = useCallback((connection: Connection) => {
    if (!connection.sourceHandle || !connection.targetHandle) return false;
    const sourceType = connection.sourceHandle.split('__')[0];
    const targetType = connection.targetHandle.split('__')[0];
    
    if (targetType === 'any' || sourceType === 'any') return true;
    
    const sourceColor = N.HANDLE_COLORS[sourceType as keyof typeof N.HANDLE_COLORS] || sourceType;
    const targetColor = N.HANDLE_COLORS[targetType as keyof typeof N.HANDLE_COLORS] || targetType;
    
    return sourceColor === targetColor;
  }, []);

  const onNodeDragStop = useCallback((_: any, node: Node) => {
    const distToSq = (p: any, v: any, w: any) => {
      const l2 = Math.pow(v.x - w.x, 2) + Math.pow(v.y - w.y, 2);
      if (l2 === 0) return Math.pow(p.x - v.x, 2) + Math.pow(p.y - v.y, 2);
      let t = ((p.x - v.x) * (w.x - v.x) + (p.y - v.y) * (w.y - v.y)) / l2;
      t = Math.max(0, Math.min(1, t));
      return Math.pow(p.x - (v.x + t * (w.x - v.x)), 2) + Math.pow(p.y - (v.y + t * (w.y - v.y)), 2);
    };

    const nodeCenter = { x: node.position.x + 100, y: node.position.y + 50 };
    
    const edgeToInsert = edges.find(edge => {
      const sourceNode = nodes.find(n => n.id === edge.source);
      const targetNode = nodes.find(n => n.id === edge.target);
      if (!sourceNode || !targetNode) return false;
      const sx = sourceNode.position.x + 200, sy = sourceNode.position.y + 50;
      const tx = targetNode.position.x, ty = targetNode.position.y + 50;
      return Math.sqrt(distToSq(nodeCenter, {x:sx, y:sy}, {x:tx, y:ty})) < 30;
    });

    if (edgeToInsert && edgeToInsert.source !== node.id && edgeToInsert.target !== node.id) {
      setEdges((eds) => {
        const nextEdges = eds.filter(e => e.id !== edgeToInsert.id).concat([
          { id: `e-${Date.now()}-1`, source: edgeToInsert.source, target: node.id, sourceHandle: edgeToInsert.sourceHandle, targetHandle: 'main' },
          { id: `e-${Date.now()}-2`, source: node.id, target: edgeToInsert.target, sourceHandle: 'main', targetHandle: edgeToInsert.targetHandle }
        ]);
        setTimeout(() => updateGraph(nodes, nextEdges), 10);
        return nextEdges;
      });
    }
  }, [nodes, edges, updateGraph]);

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

  const copyNodes = useCallback(() => {
    const selectedNodes = nodes.filter(n => n.selected);
    if (selectedNodes.length === 0) return;
    const clipboardData = {
      nodes: selectedNodes.map(n => ({...n, id: `node-copy-${Date.now()}-${Math.random()}`})),
      edges: edges.filter(e => selectedNodes.some(n => n.id === e.source) && selectedNodes.some(n => n.id === e.target))
    };
    localStorage.setItem('vision-nodes-clipboard', JSON.stringify(clipboardData));
  }, [nodes, edges]);

  const pasteNodes = useCallback((mousePos?: {x: number, y: number}) => {
    const raw = localStorage.getItem('vision-nodes-clipboard');
    if (!raw) return;
    const { nodes: copiedNodes, edges: copiedEdges } = JSON.parse(raw);
    const idMap: Record<string, string> = {};
    const newNodes = copiedNodes.map((n: any) => {
      const newId = `node-${Date.now()}-${Math.random()}`;
      idMap[n.id] = newId;
      return { 
        ...n, 
        id: newId, 
        selected: true,
        position: mousePos ? { x: mousePos.x + (n.position.x - copiedNodes[0].position.x), y: mousePos.y + (n.position.y - copiedNodes[0].position.y) } : { x: n.position.x + 50, y: n.position.y + 50 }
      };
    });
    const newEdges = copiedEdges.map((e: any) => ({
      ...e,
      id: `e-${Date.now()}-${Math.random()}`,
      source: idMap[e.source],
      target: idMap[e.target]
    }));
    setNodes(nds => [...nds.map(n => ({...n, selected: false})), ...newNodes]);
    setEdges(eds => [...eds, ...newEdges]);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'c') copyNodes();
      if ((e.metaKey || e.ctrlKey) && e.key === 'v') pasteNodes();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [copyNodes, pasteNodes]);

  const addNode = (type: string, label: string, schema?: any) => {
    const id = `node-${Date.now()}`;
    const position = pendingConnection ? { x: pendingConnection.x, y: pendingConnection.y } : { x: 350, y: 350 };
    setNodes((nds) => {
      const nextNodes = [...nds, { id, type, position, data: { label, params: {}, schema } }];
      if (pendingConnection && pendingConnection.sourceNode) {
        setTimeout(() => {
          const newEl = document.querySelector(`[data-id="${id}"]`);
          if (!newEl) return;
          const expectedColor = pendingConnection.sourceHandle.split('__')[0];
          const targetClass = pendingConnection.type === 'source' ? 'target' : 'source';
          const handles = Array.from(newEl.querySelectorAll(`.react-flow__handle-${targetClass}`));
          const match = handles.find(h => h.getAttribute('data-handleid')?.startsWith(`${expectedColor}__`)) || handles[0];
          
          if (match) {
            const matchedHandleId = match.getAttribute('data-handleid');
            if (matchedHandleId) {
              setEdges(eds => {
                const newEdges = [...eds, {
                  id: `e-${Date.now()}`,
                  source: pendingConnection.type === 'source' ? pendingConnection.sourceNode : id,
                  target: pendingConnection.type === 'source' ? id : pendingConnection.sourceNode,
                  sourceHandle: pendingConnection.type === 'source' ? pendingConnection.sourceHandle : matchedHandleId,
                  targetHandle: pendingConnection.type === 'source' ? matchedHandleId : pendingConnection.sourceHandle
                }];
                updateGraph(nextNodes, newEdges);
                return newEdges;
              });
            }
          }
        }, 50);
      } else {
        updateGraph(nextNodes, edges);
      }
      return nextNodes;
    });
    setIsAddMenuOpen(false);
    setPendingConnection(null);
  };

  useEffect(() => { if (isConnected) updateGraph(nodes, edges); }, [isConnected]);

  const [searchQuery, setSearchQuery] = useState('');
  const filteredNodes = useMemo(() => {
    if (!searchQuery) return activeCategory.nodes;
    const all = dynamicCategories.flatMap(c => c.nodes);
    return all.filter(n => n.label.toLowerCase().includes(searchQuery.toLowerCase()));
  }, [searchQuery, activeCategory, dynamicCategories]);

  useEffect(() => {
    const handleRemoveEdge = (e: any) => {
      const { nodeId, handleId, type } = e.detail;
      setEdges((eds) => {
        const nextEdges = eds.filter(edge => {
          if (type === 'target') return !(edge.target === nodeId && edge.targetHandle === handleId);
          if (type === 'source') return !(edge.source === nodeId && edge.sourceHandle === handleId);
          return true;
        });
        if (nextEdges.length !== eds.length) setTimeout(() => updateGraph(nodes, nextEdges), 10);
        return nextEdges;
      });
    };
    window.addEventListener('remove-handle-edge', handleRemoveEdge);
    return () => window.removeEventListener('remove-handle-edge', handleRemoveEdge);
  }, [nodes, updateGraph]);

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
        <div className="flex-1 relative overflow-hidden bg-[#080808]" onContextMenu={e => e.preventDefault()}>
          <ReactFlow
            nodes={nodesWithData} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} 
            onConnect={onConnect} onConnectEnd={onConnectEnd} isValidConnection={isValidConnection}
            onNodeDragStop={onNodeDragStop}
            onEdgeClick={(_, edge) => setEdges(eds => { const n = eds.filter(e => e.id !== edge.id); updateGraph(nodes, n); return n; })}
            nodeTypes={dynamicNodeTypes} onNodeClick={(_, node) => setSelectedNodeId(node.id)} onPaneClick={() => setSelectedNodeId(null)}
            panOnDrag={[1, 2]} panOnScroll={true} selectionOnDrag={true}
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
            <div className="absolute inset-0 bg-black/80 backdrop-blur-md z-[100] flex items-center justify-center p-20" onClick={() => { setIsAddMenuOpen(false); setPendingConnection(null); }}>
              <div 
                className="bg-[#181818] border border-[#333] w-full max-w-[700px] h-[85vh] rounded-3xl shadow-2xl flex overflow-hidden animate-in zoom-in-95 duration-200"
                onClick={e => e.stopPropagation()}
              >
                <div className="w-56 bg-[#111] border-r border-[#222] p-6 flex flex-col gap-2">
                  {dynamicCategories.map(cat => (
                    <button 
                      key={cat.id} onClick={() => setActiveCategoryId(cat.id)}
                      className={`flex items-center gap-4 px-4 py-3 rounded-2xl text-[11px] font-bold transition-all ${activeCategoryId === cat.id ? 'bg-accent text-white shadow-xl shadow-accent/20' : 'text-gray-500 hover:bg-white/5'}`}
                    >
                      <cat.icon size={18} /> {cat.label}
                    </button>
                  ))}
                </div>
                <div className="flex-1 p-12 overflow-y-auto overflow-x-hidden flex flex-col">
                  <div className="flex items-center justify-between mb-10 border-b border-[#222] pb-4">
                    <h3 className="text-[10px] font-black text-gray-400 uppercase tracking-widest">
                      {searchQuery ? 'Search Results' : `Category :: ${activeCategory.label}`}
                    </h3>
                    <div className="relative group">
                      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 group-focus-within:text-accent transition-colors" />
                      <input 
                        autoFocus
                        type="text" 
                        placeholder="Search modules..." 
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        className="bg-black/40 border border-[#222] rounded-xl pl-10 pr-4 py-2 text-[11px] text-white outline-none focus:border-accent/50 w-64 transition-all"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    {filteredNodes.map((node: any) => (
                      <button
                        key={node.type} onClick={() => { addNode(node.type, node.label, node.schema); setSearchQuery(''); }}
                        className="p-6 bg-[#222] hover:bg-accent/10 border border-[#333] hover:border-accent/40 rounded-3xl text-left transition-all active:scale-95 group"
                      >
                        <div className="text-[11px] font-bold text-gray-200 uppercase tracking-tighter group-hover:text-accent transition-colors">{node.label}</div>
                        <div className="text-[8px] text-gray-600 font-mono mt-1 italic">{node.schema ? 'cv::plugin' : 'cv::node'}</div>
                      </button>
                    ))}
                  </div>
                  {filteredNodes.length === 0 && (
                    <div className="flex-1 flex flex-col items-center justify-center text-gray-700 gap-4 opacity-50 italic py-20">
                      <Search size={48} strokeWidth={1} />
                      <div className="text-[11px] font-bold uppercase tracking-widest">No modules found matching "{searchQuery}"</div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          <div className="absolute bottom-6 left-6 w-[400px] aspect-video bg-black border-2 border-[#222] rounded-3xl shadow-2xl overflow-hidden z-20 group hover:border-accent transition-all duration-700">
             {frame && <img src={frame} alt="Vision" className="w-full h-full object-contain" />}
          </div>
        </div>

        {/* Right Panel */}
        <div 
          className="bg-[#0a0a0a] border-l border-[#1a1a1a] flex flex-col relative shrink-0 transition-all duration-300 h-full overflow-hidden"
          style={{ width: selectedNodeId ? rightPanelWidth : 0, opacity: selectedNodeId ? 1 : 0 }}
        >
          {/* Resize Handle */}
          <div 
            className="absolute left-0 top-0 bottom-0 w-1.5 -ml-[3px] cursor-col-resize hover:bg-accent/50 z-20 transition-colors duration-150"
            onMouseDown={() => isResizing.current = true}
          />

          <div className="h-full flex flex-col">
            <div className="h-10 border-b border-[#222] flex items-center px-4 bg-[#1a1a1a] shrink-0">
              <Settings size={14} className="text-gray-500 mr-2" />
              <span className="text-[10px] font-black tracking-widest text-gray-400 uppercase">Unit Inspector</span>
            </div>
            
            <div className="flex-1 overflow-y-auto scrollbar-hide p-10">
              {selectedNode ? (
                <div className="space-y-12 animate-in slide-in-from-right-10 duration-500">
                  <div className="flex items-center gap-5">
                     <div className="w-16 h-16 bg-accent/5 rounded-3xl border border-accent/20 flex items-center justify-center text-accent shadow-inner">
                        <Cpu size={32} />
                     </div>
                     <div>
                        <h2 className="text-[14px] font-black text-white uppercase tracking-wider">{selectedNode.data.label}</h2>
                        <span className="text-[9px] text-gray-600 font-mono italic opacity-40 leading-none">{selectedNode.id}</span>
                     </div>
                  </div>

                  <div className="space-y-8 pb-32">
                    {/* --- ALL SLIDERS --- */}
                    {selectedNode.type === 'input_webcam' && (
                      <Slider label="Device Index" val={selectedNode.data.params.device_index || 0} min={0} max={5} onChange={v => updateNodeParams(selectedNode.id, {device_index: v})} />
                    )}
                    {selectedNode.type === 'input_image' && (
                      <TextInput label="Image Path" val={selectedNode.data.params.path || ''} onChange={v => updateNodeParams(selectedNode.id, {path: v})} />
                    )}
                    {selectedNode.type === 'input_movie' && (
                      <div className="space-y-6">
                        <TextInput label="Movie Path" val={selectedNode.data.params.path || ''} onChange={v => updateNodeParams(selectedNode.id, {path: v})} />
                        <div className="flex flex-col gap-4 p-4 bg-white/5 rounded-2xl border border-white/5">
                          <label className="text-[10px] text-gray-500 uppercase tracking-widest font-black">Playback Control</label>
                          <div className="flex items-center justify-between">
                            <button 
                              onClick={() => updateNodeParams(selectedNode.id, { playing: !selectedNode.data.params.playing })}
                              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-bold transition-all ${selectedNode.data.params.playing ? 'bg-red-500 text-white shadow-lg shadow-red-500/20' : 'bg-green-500 text-white shadow-lg shadow-green-500/20'}`}
                            >
                              {selectedNode.data.params.playing ? <><Pause size={14} /> Stop</> : <><Play size={14} /> Start</>}
                            </button>
                            <div className="text-[10px] font-mono text-gray-400">
                              Frame: {selectedNode.data.node_data?.current_frame || 0} / {selectedNode.data.node_data?.total_frames || 0}
                            </div>
                          </div>
                          <Slider 
                            label="Scrub" 
                            val={selectedNode.data.params.playing ? (selectedNode.data.node_data?.current_frame || 0) : (selectedNode.data.params.scrub_index || 0)} 
                            min={0} 
                            max={(selectedNode.data.node_data?.total_frames || 1) - 1} 
                            onChange={v => updateNodeParams(selectedNode.id, { scrub_index: v, playing: false })} 
                          />
                        </div>
                      </div>
                    )}
                    {selectedNode.type === 'input_solid_color' && (
                      <>
                        <Slider label="Red" val={selectedNode.data.params.r ?? 255} min={0} max={255} onChange={v => updateNodeParams(selectedNode.id, {r: v})} />
                        <Slider label="Green" val={selectedNode.data.params.g ?? 0} min={0} max={255} onChange={v => updateNodeParams(selectedNode.id, {g: v})} />
                        <Slider label="Blue" val={selectedNode.data.params.b ?? 0} min={0} max={255} onChange={v => updateNodeParams(selectedNode.id, {b: v})} />
                        <Slider label="Width" val={selectedNode.data.params.width ?? 640} min={100} max={1920} onChange={v => updateNodeParams(selectedNode.id, {width: v})} />
                        <Slider label="Height" val={selectedNode.data.params.height ?? 480} min={100} max={1080} onChange={v => updateNodeParams(selectedNode.id, {height: v})} />
                      </>
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
                      <Slider label="Threshold Value" val={selectedNode.data.params.threshold || 127} min={0} max={255} onChange={v => updateNodeParams(selectedNode.id, {threshold: v})} />
                    )}
                    {selectedNode.type === 'geom_resize' && (
                      <Slider label="Scale Factor" val={selectedNode.data.params.scale || 1} min={0.1} max={3} step={0.1} onChange={v => updateNodeParams(selectedNode.id, {scale: v})} />
                    )}
                    {selectedNode.type === 'geom_flip' && (
                      <Slider label="Flip Code (0,1,-1)" val={selectedNode.data.params.flip_mode || 1} min={-1} max={1} step={1} onChange={v => updateNodeParams(selectedNode.id, {flip_mode: v})} />
                    )}
                    {selectedNode.type === 'filter_color_mask' && (
                      <>
                        <Slider label="Hue Min" val={selectedNode.data.params.h_min || 0} min={0} max={179} onChange={v => updateNodeParams(selectedNode.id, {h_min: v})} />
                        <Slider label="Hue Max" val={selectedNode.data.params.h_max || 179} min={0} max={179} onChange={v => updateNodeParams(selectedNode.id, {h_max: v})} />
                        <Slider label="Sat Min" val={selectedNode.data.params.s_min || 0} min={0} max={255} onChange={v => updateNodeParams(selectedNode.id, {s_min: v})} />
                        <Slider label="Value Min" val={selectedNode.data.params.v_min || 0} min={0} max={255} onChange={v => updateNodeParams(selectedNode.id, {v_min: v})} />
                      </>
                    )}
                    {selectedNode.type === 'filter_morphology' && (
                      <>
                        <Slider label="Operation (0=Dilate, 1=Erode)" val={selectedNode.data.params.operation || 0} min={0} max={1} step={1} onChange={v => updateNodeParams(selectedNode.id, {operation: v})} />
                        <Slider label="Kernel Size" val={selectedNode.data.params.size || 5} min={3} max={21} step={2} onChange={v => updateNodeParams(selectedNode.id, {size: v})} />
                      </>
                    )}
                    {selectedNode.type === 'analysis_face_mp' && (
                      <Slider label="Track Count" val={selectedNode.data.params.max_faces || 3} min={1} max={10} onChange={v => updateNodeParams(selectedNode.id, {max_faces: v})} />
                    )}
                    {selectedNode.type === 'analysis_hand_mp' && (
                      <Slider label="Hand Count" val={selectedNode.data.params.max_hands || 2} min={1} max={4} onChange={v => updateNodeParams(selectedNode.id, {max_hands: v})} />
                    )}
                    {selectedNode.type === 'analysis_flow' && (
                      <>
                         <Slider label="Pyr Scale" val={selectedNode.data.params.pyr_scale || 0.5} min={0.1} max={0.9} step={0.1} onChange={v => updateNodeParams(selectedNode.id, {pyr_scale: v})} />
                         <Slider label="Levels" val={selectedNode.data.params.levels || 3} min={1} max={10} onChange={v => updateNodeParams(selectedNode.id, {levels: v})} />
                      </>
                    )}

                    {selectedNode.type === 'data_list_selector' && (
                      <Slider label="List Index" val={selectedNode.data.params.index || 0} min={0} max={10} onChange={v => updateNodeParams(selectedNode.id, {index: v})} />
                    )}

                    {selectedNode.data.schema && selectedNode.data.schema.params && selectedNode.data.schema.params.map((p: any) => {
                      const isEnum = p.type === 'enum' || p.options;
                      const isString = p.type === 'string' || typeof (selectedNode.data.params[p.id] ?? p.default) === 'string';
                      
                      if (isEnum) {
                        return <SelectInput 
                          key={p.id} 
                          label={p.label || p.id} 
                          val={selectedNode.data.params[p.id] ?? p.default ?? 0} 
                          options={p.options || []}
                          onChange={(v: any) => updateNodeParams(selectedNode.id, {[p.id]: v})} 
                        />;
                      }
                      
                      if (isString) {
                        return <TextInput key={p.id} label={p.label || p.id} val={selectedNode.data.params[p.id] ?? p.default ?? ''} onChange={(v: any) => updateNodeParams(selectedNode.id, {[p.id]: v})} />;
                      }
                      return <Slider key={p.id} label={p.id} val={selectedNode.data.params[p.id] ?? p.default ?? 0} min={p.min || 0} max={p.max || 100} step={p.step || 1} onChange={(v: any) => updateNodeParams(selectedNode.id, {[p.id]: v})} />;
                    })}

                    {selectedNode.data.node_data && (
                      <div className="p-4 bg-black/40 rounded-2xl border border-white/5 space-y-3 shadow-inner">
                         <div className="text-[9px] font-black text-gray-600 uppercase tracking-[0.2em] flex items-center gap-2 bg-black/20 p-2 rounded-lg"><Activity size={10}/> Analysis Data</div>
                         <pre className="text-[10px] font-mono text-accent/80 max-h-32 overflow-auto scrollbar-hide italic leading-relaxed">
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
          </div>
        </div>
      </div>
    </div>
  );
}

const Slider = ({ label, val, min, max, step = 1, onChange }: any) => (
  <div className="space-y-4 group">
    <div className="flex justify-between text-[10px]">
      <label className="text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
      <span className="text-accent font-black font-mono bg-accent/10 px-3 py-1 rounded-lg border border-accent/20">{val}</span>
    </div>
    <input type="range" min={min} max={max} step={step} value={val} onChange={(e) => onChange(parseFloat(e.target.value))} className="w-full h-1.5 bg-[#222] rounded-full appearance-none cursor-pointer accent-accent" />
  </div>
);

const TextInput = ({ label, val, onChange }: any) => (
  <div className="space-y-4 group">
    <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
    <input 
      type="text" 
      value={val} 
      onChange={(e) => onChange(e.target.value)} 
      className="w-full bg-black/40 border border-[#222] group-hover:border-accent/40 rounded-xl px-4 py-2 text-[11px] text-white outline-none focus:border-accent transition-all"
      placeholder={`Enter ${label.toLowerCase()}...`}
    />
  </div>
);

const SelectInput = ({ label, val, options, onChange }: any) => (
  <div className="space-y-4 group">
    <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
    <select 
      value={val} 
      onChange={(e) => onChange(parseInt(e.target.value))} 
      className="w-full bg-black/40 border border-[#222] group-hover:border-accent/40 rounded-xl px-4 py-2 text-[11px] text-white outline-none focus:border-accent transition-all appearance-none cursor-pointer"
    >
      {options.map((opt: string, i: number) => (
        <option key={i} value={i} className="bg-[#1a1a1a]">{opt}</option>
      ))}
    </select>
  </div>
);

export default App;
