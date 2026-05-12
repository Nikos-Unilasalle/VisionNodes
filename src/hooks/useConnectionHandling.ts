import { useCallback } from 'react';
import { addEdge, Connection, Edge } from 'reactflow';
import { updateNestedSubGraph } from '../utils/groups';
import type { Node } from 'reactflow';

export function useConnectionHandling({
  setViewNodes,
  setViewEdges,
  pushSnapshot,
  nodesRef,
  edgesRef,
  groupStackRef,
  activeCanvasIdRef,
  setCanvases,
  connectionMadeRef,
  pluginSchemas,
}: any) {

  const onConnect = useCallback((params: Connection) => {
    connectionMadeRef.current = true;
    pushSnapshot();

    // SOURCE-dynamic: canvas_reroute factory output handle
    const sourceNode = nodesRef.current.find((n: Node) => n.id === params.source);
    if (sourceNode?.type === 'canvas_reroute' && params.sourceHandle?.endsWith('__DYNAMIC_NEW_HANDLE')) {
      const idx = (sourceNode.data as any)?.ports?.length ?? 0;
      const portId = `any__out_${idx}_${Math.random().toString(36).substr(2, 6)}`;
      const newPort = { id: portId, color: 'any', label: `out_${idx}` };
      const newHeight = Math.max(48, 14 + (idx + 1) * 20 + 20);
      setViewNodes((nds: Node[]) => nds.map((n: Node) => n.id === params.source ? {
        ...n,
        style: { ...n.style, height: Math.max((n.style?.height as number) || 48, newHeight) },
        data: { ...n.data, ports: [...((n.data as any)?.ports ?? []), newPort] },
      } : n));
      setViewEdges((eds: Edge[]) => addEdge({ ...params, id: `e-${Date.now()}`, sourceHandle: portId }, eds));
      return;
    }

    const targetNode = nodesRef.current.find((n: Node) => n.id === params.target);
    const targetSchema = pluginSchemas?.find((s: any) => s.type === targetNode?.type);
    
    // Check if node is dynamic via schema flags or known types
    const isDynamic = !!targetSchema?.dynamic_inputs || 
                     !!targetSchema?.dynamic_outputs || 
                     ['output_display', 'draw_overlay', 'util_csv_export', 'group_output', 'group_input'].includes(targetNode?.type || '');

    const createDynamicPort = (color: string, labelPrefix: string) => {
      const idx = (targetNode!.data as any)?.ports?.length ?? 0;
      // Ensure unique port ID by adding a random suffix
      const portId = `${color}__${idx}_${Math.random().toString(36).substr(2, 4)}`;
      const sh = params.sourceHandle!;
      const label = labelPrefix === 'img'
        ? `${labelPrefix}${idx}`
        : (sh.split('__').pop() || `${labelPrefix}${idx}`);
      const newPort = { id: portId, color, label };
      setViewNodes((nds: Node[]) => nds.map((n: Node) => n.id === params.target
        ? { ...n, data: { ...n.data, ports: [...((n.data as any)?.ports ?? []), newPort] } }
        : n));
      return { portId, newPort };
    };

    if (isDynamic && params.sourceHandle) {
      const isFactory = params.targetHandle?.endsWith('DYNAMIC_NEW_HANDLE');
      const isOccupied = !isFactory && edgesRef.current.some(
        (e: Edge) => e.target === params.target && e.targetHandle === params.targetHandle
      );

      if (isFactory || isOccupied) {
        const sh = params.sourceHandle;
        const color = sh.split('__')[0] || 'any';

        if (targetNode!.type === 'output_display' || targetNode!.type === 'draw_overlay') {
          const { portId } = createDynamicPort(color, color === 'image' ? 'img' : 'data');
          setViewEdges((eds: Edge[]) => addEdge({ ...params, id: `e-${Date.now()}`, targetHandle: portId }, eds));
        } else if (targetNode!.type === 'util_csv_export') {
          const idx = (targetNode!.data as any)?.ports?.length ?? 0;
          const sourceLabel = (params.sourceHandle || '').split('__').pop() || `col${idx}`;
          const portId = `${color}__${sourceLabel}_${idx}`;
          const newPort = { id: portId, color, label: sourceLabel };
          setViewNodes((nds: Node[]) => nds.map((n: Node) => n.id === params.target
            ? { ...n, data: { ...n.data, ports: [...((n.data as any)?.ports ?? []), newPort] } }
            : n));
          setViewEdges((eds: Edge[]) => addEdge({ ...params, id: `e-${Date.now()}`, targetHandle: portId }, eds));
        } else {
          const labelPrefix = (targetNode!.type === 'group_output' || targetSchema?.dynamic_outputs) ? 'out' : 'in';
          const { portId, newPort } = createDynamicPort(color, labelPrefix);
          setViewEdges((eds: Edge[]) => addEdge({ ...params, id: `e-${Date.now()}`, targetHandle: portId }, eds));

          if (targetNode!.type === 'group_output' && groupStackRef.current.length > 0) {
            const parentGroupId = groupStackRef.current[groupStackRef.current.length - 1].groupNodeId;
            const parentStack = groupStackRef.current.slice(0, -1);
            setCanvases(prev => prev.map((c: any) => c.id === activeCanvasIdRef.current ? {
              ...c,
              nodes: (parentStack.length > 0
                ? updateNestedSubGraph(c.nodes, parentStack, 'nodes', (nds: Node[]) => nds.map((n: Node) => n.id !== parentGroupId ? n : { ...n, data: { ...n.data, outputs: [...((n.data as any)?.outputs ?? []), newPort] } }))
                : c.nodes.map((n: Node) => n.id !== parentGroupId ? n : { ...n, data: { ...n.data, outputs: [...((n.data as any)?.outputs ?? []), newPort] } })
              )
            } : c));
          }
        }
        return;
      } else {
        // Just replace existing edge on that handle
        setViewEdges((eds: Edge[]) => addEdge({ ...params, id: `e-${Date.now()}` },
          eds.filter((e: any) => !(e.target === params.target && e.targetHandle === params.targetHandle))));
        return;
      }
    }

    setViewEdges((eds: any) => addEdge({ ...params, id: `e-${Date.now()}` }, eds));
  }, [pushSnapshot, setViewNodes, setViewEdges, nodesRef, edgesRef, groupStackRef, activeCanvasIdRef, setCanvases]);

  return { onConnect };
}
