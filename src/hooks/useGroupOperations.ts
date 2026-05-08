import { useCallback } from 'react';
import type { Node, Edge } from 'reactflow';

export function useGroupOperations({
  nodesRef,
  edgesRef,
  pushSnapshot,
  setViewNodes,
  setViewEdges,
}: any) {

  const groupSelectedNodes = useCallback(() => {
    const selected = nodesRef.current.filter((n: Node) => n.selected);
    if (selected.length < 1) return;
    pushSnapshot();

    const selectedIds = new Set(selected.map(n => n.id));
    const allEdges = edgesRef.current;

    const innerEdges = allEdges.filter((e: Edge) => selectedIds.has(e.source) && selectedIds.has(e.target));
    const incomingEdges = allEdges.filter((e: Edge) => !selectedIds.has(e.source) && selectedIds.has(e.target));
    const outgoingEdges = allEdges.filter((e: Edge) => selectedIds.has(e.source) && !selectedIds.has(e.target));

    // Terminal nodes: selected nodes that produce no output to other selected nodes
    const innerSourceIds = new Set(innerEdges.map((e: Edge) => e.source));
    const terminalNodes = selected.filter(n => !innerSourceIds.has(n.id));

    const inputPorts: { id: string; color: string; label: string }[] = [];
    const outputPorts: { id: string; color: string; label: string }[] = [];

    const inPortIdMap = new Map<string, string>();
    const usedInIds = new Set<string>();
    for (const e of incomingEdges) {
      const th = e.targetHandle || 'any__in';
      const key = `${e.target}::${th}`;
      if (inPortIdMap.has(key)) continue;
      let portId = th;
      if (usedInIds.has(portId)) portId = `${th.split('__')[0] || 'any'}__in${inputPorts.length}`;
      usedInIds.add(portId);
      inPortIdMap.set(key, portId);
      inputPorts.push({ id: portId, color: portId.split('__')[0] || 'any', label: `in${inputPorts.length}` });
    }

    const outPortIdMap = new Map<string, string>();
    const usedOutIds = new Set<string>();
    for (const e of outgoingEdges) {
      const sh = e.sourceHandle || 'any__out';
      const key = `${e.source}::${sh}`;
      if (outPortIdMap.has(key)) continue;
      let portId = sh;
      if (usedOutIds.has(portId)) portId = `${sh.split('__')[0] || 'any'}__out${outputPorts.length}`;
      usedOutIds.add(portId);
      outPortIdMap.set(key, portId);
      outputPorts.push({ id: portId, color: portId.split('__')[0] || 'any', label: `out${outputPorts.length}` });
    }

    const ts = Date.now();
    const ginId = `gin-${ts}`;
    const goutId = `gout-${ts + 1}`;
    const groupId = `group-${ts + 2}`;

    // Auto-wire terminal node outputs not already covered by outgoingEdges
    const extraGoutEdges: Edge[] = [];
    for (const termNode of terminalNodes) {
      const schemaOuts: { id: string; color: string; label: string }[] =
        (termNode.data as any)?.schema?.outputs || [];
      let handles: { handleId: string; color: string; label: string }[];
      if (schemaOuts.length > 0) {
        handles = schemaOuts.map(o => ({ handleId: `${o.color}__${o.id}`, color: o.color, label: o.label || o.id }));
      } else {
        // Try edges first (node has existing connections)
        const seen = new Set<string>();
        const edgeHandles = allEdges
          .filter((e: Edge) => e.source === termNode.id && e.sourceHandle)
          .flatMap((e: Edge) => {
            const sh = e.sourceHandle!;
            if (seen.has(sh)) return [];
            seen.add(sh);
            return [{ handleId: sh, color: sh.split('__')[0] || 'any', label: sh.split('__').slice(1).join('__') || sh }];
          });
        if (edgeHandles.length > 0) {
          handles = edgeHandles;
        } else {
          // DOM query fallback for static nodes without schema and without edges
          const nodeEl = document.querySelector(`[data-id="${termNode.id}"]`);
          handles = Array.from(nodeEl?.querySelectorAll('.react-flow__handle.source') ?? [])
            .flatMap((h: any) => {
              const hid = h.getAttribute('data-handleid');
              if (!hid) return [];
              return [{ handleId: hid, color: hid.split('__')[0] || 'any', label: hid.split('__').slice(1).join('__') || hid }];
            });
        }
      }
      for (const { handleId, color, label } of handles) {
        const key = `${termNode.id}::${handleId}`;
        if (outPortIdMap.has(key) || usedOutIds.has(handleId)) continue;
        usedOutIds.add(handleId);
        outPortIdMap.set(key, handleId);
        outputPorts.push({ id: handleId, color, label });
        extraGoutEdges.push({
          id: `sg-${ts}-${Math.random()}`, source: termNode.id, sourceHandle: handleId,
          target: goutId, targetHandle: handleId,
        });
      }
    }

    const xs = selected.map(n => n.position.x);
    const ys = selected.map(n => n.position.y);
    const minX = Math.min(...xs), minY = Math.min(...ys), maxX = Math.max(...xs) + 200;

    const ginNode: Node = {
      id: ginId, type: 'group_input',
      position: { x: minX - 240, y: minY },
      data: { label: 'Group IN', params: {}, ports: inputPorts }
    };
    const goutNode: Node = {
      id: goutId, type: 'group_output',
      position: { x: maxX + 60, y: minY },
      data: { label: 'Group OUT', params: {}, ports: outputPorts }
    };

    const seenGinKeys = new Set<string>();
    const seenGoutKeys = new Set<string>();
    const subEdges: Edge[] = [
      ...innerEdges,
      ...incomingEdges.flatMap(e => {
        const key = `${e.target}::${e.targetHandle || 'any__in'}`;
        if (seenGinKeys.has(key)) return [];
        seenGinKeys.add(key);
        const portId = inPortIdMap.get(key) ?? e.targetHandle;
        return [{ id: `sg-${ts}-${Math.random()}`, source: ginId, sourceHandle: portId, target: e.target, targetHandle: e.targetHandle }];
      }),
      ...outgoingEdges.flatMap(e => {
        const key = `${e.source}::${e.sourceHandle || 'any__out'}`;
        if (seenGoutKeys.has(key)) return [];
        seenGoutKeys.add(key);
        const portId = outPortIdMap.get(key) ?? e.sourceHandle;
        return [{ id: `sg-${ts}-${Math.random()}`, source: e.source, sourceHandle: e.sourceHandle, target: goutId, targetHandle: portId }];
      }),
      ...extraGoutEdges,
    ];

    const groupNode: Node = {
      id: groupId, type: 'group_node',
      position: { x: (minX + maxX) / 2 - 95, y: minY - 30 },
      data: {
        label: 'Group', params: {},
        inputs: inputPorts,
        outputs: outputPorts,
        subGraph: {
          nodes: [...selected.map(n => ({ ...n, selected: false })), ginNode, goutNode],
          edges: subEdges,
        }
      }
    };

    const seenOuterInPorts = new Set<string>();
    const outerEdges = allEdges
      .filter(e => !selectedIds.has(e.source) && !selectedIds.has(e.target))
      .concat(
        incomingEdges
          .filter(e => {
            const portId = inPortIdMap.get(`${e.target}::${e.targetHandle || 'any__in'}`);
            if (!portId || seenOuterInPorts.has(portId)) return false;
            seenOuterInPorts.add(portId);
            return true;
          })
          .map(e => {
            const portId = inPortIdMap.get(`${e.target}::${e.targetHandle || 'any__in'}`) ?? e.targetHandle;
            return { ...e, id: `oe-${ts}-${Math.random()}`, target: groupId, targetHandle: portId };
          })
      )
      .concat(
        outgoingEdges.map(e => {
          const portId = outPortIdMap.get(`${e.source}::${e.sourceHandle || 'any__out'}`) ?? e.sourceHandle;
          return { ...e, id: `oe-${ts}-${Math.random()}`, source: groupId, sourceHandle: portId };
        })
      );

    setViewNodes((nds: Node[]) => [...nds.filter(n => !selectedIds.has(n.id)), groupNode]);
    setViewEdges((_: Edge[]) => outerEdges);
  }, [pushSnapshot, setViewNodes, setViewEdges, nodesRef, edgesRef]);

  const ungroupNode = useCallback((groupNodeId: string) => {
    const groupNode = nodesRef.current.find((n: Node) => n.id === groupNodeId);
    if (!groupNode || groupNode.type !== 'group_node') return;
    pushSnapshot();

    const sub = (groupNode.data as any)?.subGraph ?? { nodes: [], edges: [] };
    const innerNodes: Node[] = sub.nodes.filter((n: Node) => n.type !== 'group_input' && n.type !== 'group_output');
    const innerEdges: Edge[] = sub.edges.filter((e: Edge) => {
      const inIds = new Set(innerNodes.map(n => n.id));
      return inIds.has(e.source) && inIds.has(e.target);
    });

    const sub_nodes: Node[] = sub.nodes;
    const sub_edges: Edge[] = sub.edges;
    const ginNode = sub_nodes.find((n: Node) => n.type === 'group_input');
    const goutNode = sub_nodes.find((n: Node) => n.type === 'group_output');
    const ginId = ginNode?.id;
    const goutId = goutNode?.id;

    const outerEdges = edgesRef.current.filter((e: Edge) => e.source !== groupNodeId && e.target !== groupNodeId);

    const reconnectedIn: Edge[] = edgesRef.current
      .filter((e: Edge) => e.target === groupNodeId)
      .flatMap(outerE => {
        const th = outerE.targetHandle || '';
        return sub_edges
          .filter(se => se.source === ginId && se.sourceHandle === th)
          .map(se => ({ ...outerE, id: `ug-${Date.now()}-${Math.random()}`, target: se.target, targetHandle: se.targetHandle }));
      });

    const reconnectedOut: Edge[] = edgesRef.current
      .filter((e: Edge) => e.source === groupNodeId)
      .flatMap(outerE => {
        const sh = outerE.sourceHandle || '';
        return sub_edges
          .filter(se => se.target === goutId && se.targetHandle === sh)
          .map(se => ({ ...outerE, id: `ug-${Date.now()}-${Math.random()}`, source: se.source, sourceHandle: se.sourceHandle }));
      });

    setViewNodes((nds: Node[]) => [...nds.filter(n => n.id !== groupNodeId), ...innerNodes.map(n => ({ ...n, position: { x: n.position.x + groupNode.position.x, y: n.position.y + groupNode.position.y } }))]);
    setViewEdges((_: Edge[]) => [...outerEdges, ...innerEdges, ...reconnectedIn, ...reconnectedOut]);
  }, [pushSnapshot, setViewNodes, setViewEdges, nodesRef, edgesRef]);

  return { groupSelectedNodes, ungroupNode };
}
