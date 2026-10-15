import type { Edge, Node } from 'reactflow';

/**
 * Brings saved edge handles in line with the current node schemas.
 *
 * A handle id is "{portColor}__{portId}", and a schema-driven node draws its
 * handles from the schema's port colours. When the desktop retypes a port —
 * `labels_map` went from `any` to `markers`, `regions` from `list` to
 * `regions` — every graph saved before still names the old colour. The engine
 * only reads the port id, so the graph keeps computing, but React Flow finds no
 * handle under the old id and silently drops the edge from the canvas: the
 * nodes look unconnected while their data still flows.
 *
 * Only nodes drawn from their schema are touched (`customTypes` lists the ones
 * with a hand-written component, whose handles may not follow the schema), and
 * only ports the schema declares; group sub-graphs are walked too.
 */
export function normalizeEdgeHandles<N extends Node, E extends Edge>(
  nodes: N[],
  edges: E[],
  schemas: any[] | undefined,
  customTypes: ReadonlySet<string>,
): { nodes: N[]; edges: E[] } {
  if (!schemas?.length) return { nodes, edges };
  const byType = new Map(schemas.map((s: any) => [s.type, s]));

  const portColor = (node: N | undefined, side: 'inputs' | 'outputs', portId: string): string | null => {
    if (!node?.type || customTypes.has(node.type)) return null;
    const schema = byType.get(node.type);
    if (!schema || schema.dynamic_inputs || schema.dynamic_outputs || schema.variable_inputs) return null;
    const color = schema[side]?.find((p: any) => p.id === portId)?.color;
    if (!color) return null;
    // The generic node repaints every output in `dynamicColor` when it is set.
    return side === 'outputs' ? ((node.data as any)?.dynamicColor ?? color) : color;
  };

  /**
   * The port a `main` stands for on a node that has none. An input: `image`,
   * which the engine fills from a `main` edge (see executor.ts), else the first
   * input. An output: the first image output — read as `main`, a node like
   * Colormap that names its output `image` would pass nothing at all.
   */
  const mainFallback = (node: N | undefined, side: 'inputs' | 'outputs'): string | null => {
    if (!node?.type || customTypes.has(node.type)) return null;
    const ports: any[] = byType.get(node.type)?.[side] ?? [];
    if (side === 'inputs') return (ports.find(p => p.id === 'image') ?? ports[0])?.id ?? null;
    return (ports.find(p => p.color === 'image') ?? ports[0])?.id ?? null;
  };

  const fix = (handle: string | null | undefined, node: N | undefined, side: 'inputs' | 'outputs') => {
    if (!handle) return handle;
    // Bare ids ("main") are what Shift-dropping a node onto an edge used to write.
    const index = handle.indexOf('__');
    const portId = index < 0 ? handle : handle.slice(index + 2);
    const port = portColor(node, side, portId) ? portId : portId === 'main' ? mainFallback(node, side) : null;
    const color = port ? portColor(node, side, port) : null;
    return color ? `${color}__${port}` : handle;
  };

  const byId = new Map(nodes.map(n => [n.id, n]));
  let changed = false;
  const newEdges = edges.map(edge => {
    const sourceHandle = fix(edge.sourceHandle, byId.get(edge.source), 'outputs');
    const targetHandle = fix(edge.targetHandle, byId.get(edge.target), 'inputs');
    if (sourceHandle === edge.sourceHandle && targetHandle === edge.targetHandle) return edge;
    changed = true;
    return { ...edge, sourceHandle, targetHandle };
  });

  const newNodes = nodes.map(node => {
    const sub = (node.data as any)?.subGraph;
    if (!sub?.nodes || !sub?.edges) return node;
    const inner = normalizeEdgeHandles(sub.nodes, sub.edges, schemas, customTypes);
    if (inner.nodes === sub.nodes && inner.edges === sub.edges) return node;
    changed = true;
    return { ...node, data: { ...(node.data as any), subGraph: { ...sub, ...inner } } };
  });

  return changed ? { nodes: newNodes, edges: newEdges } : { nodes, edges };
}
