import type { Edge, Node } from 'reactflow';

/**
 * Rebuilds the dynamic ports a saved graph's edges rely on.
 *
 * Nodes with growable inputs (Display, CSV Export, Plotter, Python…) do not draw
 * their extra ports from the schema: they draw `data.ports` — and the Python
 * node its outputs from `data.outPorts`, the Reroute from `data.ports` — which
 * the editor appends to as each edge is connected (useConnectionHandling.ts).
 * A graph written or edited outside the editor can carry the edges without
 * those entries. The engine still runs them (it reads the port id off the edge),
 * but the node draws no handle, so React Flow drops the edge from the canvas.
 *
 * Each port is `{ id: "{color}__{name}", color, label }` and is drawn under that
 * same id, so it can be restored from the edge that names it. An edge aimed at a
 * port that exists under another colour is pointed at the existing one instead,
 * and one aimed at the "+" factory handle itself gets a port of its own.
 */

const FACTORY = 'DYNAMIC_NEW_HANDLE';

/** Dynamic-input types with no schema here, as listed in useConnectionHandling.ts. */
const SCHEMALESS_DYNAMIC_INPUTS = new Set(['group_output', 'export_py', 'raster_colorizer']);

const split = (handle: string) => {
  const i = handle.indexOf('__');
  return i < 0 ? { color: 'any', name: handle } : { color: handle.slice(0, i), name: handle.slice(i + 2) };
};

export function restoreDynamicPorts<N extends Node, E extends Edge>(
  nodes: N[],
  edges: E[],
  schemas: any[] | undefined,
): { nodes: N[]; edges: E[] } {
  const byType = new Map((schemas ?? []).map((s: any) => [s.type, s]));
  const added = new Map<string, { ports?: any[]; outPorts?: any[] }>();

  const portsOf = (node: N, field: 'ports' | 'outPorts'): any[] => {
    let entry = added.get(node.id);
    if (!entry) added.set(node.id, (entry = {}));
    if (!entry[field]) entry[field] = [...(((node.data as any)?.[field] as any[]) ?? [])];
    return entry[field]!;
  };

  /** Which list holds `node`'s dynamic ports on that side, or null if it has none there. */
  const dynamicField = (node: N, side: 'target' | 'source'): 'ports' | 'outPorts' | null => {
    if (side === 'source') {
      if (node.type === 'logic_python') return 'outPorts';
      if (node.type === 'canvas_reroute') return 'ports';
      return null;
    }
    if (node.type === 'canvas_reroute') return null;
    const schema = byType.get(node.type);
    return schema?.dynamic_inputs || SCHEMALESS_DYNAMIC_INPUTS.has(node.type ?? '') ? 'ports' : null;
  };

  /** Inputs the component draws on its own; the Python node draws only its dynamic ones. */
  const staticInputs = (node: N): Set<string> => {
    if (node.type === 'logic_python') return new Set();
    return new Set((byType.get(node.type)?.inputs ?? []).map((p: any) => p.id).filter((id: string) => id !== FACTORY));
  };

  const byId = new Map(nodes.map(n => [n.id, n]));
  let changed = false;

  const resolve = (edge: E, side: 'target' | 'source'): string | null | undefined => {
    const handle = side === 'target' ? edge.targetHandle : edge.sourceHandle;
    const node = byId.get(side === 'target' ? edge.target : edge.source);
    if (!handle || !node) return handle;
    const field = dynamicField(node, side);
    if (!field) return handle;
    const { color, name } = split(handle);
    if (side === 'target' && staticInputs(node).has(name)) return handle;

    const ports = portsOf(node, field);
    if (name === FACTORY) {
      // Wired to the "+" itself: give it the port connecting would have made.
      const otherHandle = side === 'target' ? edge.sourceHandle : edge.targetHandle;
      const portColor = otherHandle ? split(otherHandle).color : color;
      const id = `${portColor}__${ports.length}_${edge.id.replace(/[^a-zA-Z0-9]/g, '').slice(-4) || 'p'}`;
      ports.push({ id, color: portColor, label: `in${ports.length}` });
      changed = true;
      return id;
    }
    const existing = ports.find(p => split(p.id).name === name);
    if (existing) {
      if (existing.id !== handle) changed = true;
      return existing.id;
    }
    ports.push({ id: handle, color, label: name });
    changed = true;
    return handle;
  };

  const newEdges = edges.map(edge => {
    const targetHandle = resolve(edge, 'target');
    const sourceHandle = resolve(edge, 'source');
    return targetHandle === edge.targetHandle && sourceHandle === edge.sourceHandle
      ? edge
      : { ...edge, targetHandle, sourceHandle };
  });

  const newNodes = nodes.map(node => {
    let data: any = node.data;
    const extra = added.get(node.id);
    if (extra) {
      data = { ...data };
      if (extra.ports) data.ports = extra.ports;
      if (extra.outPorts) data.outPorts = extra.outPorts;
    }
    const sub = data?.subGraph;
    if (sub?.nodes && sub?.edges) {
      const inner = restoreDynamicPorts(sub.nodes, sub.edges, schemas);
      if (inner.nodes !== sub.nodes || inner.edges !== sub.edges) {
        data = { ...data, subGraph: { ...sub, ...inner } };
        changed = true;
      }
    }
    return data === node.data ? node : { ...node, data };
  });

  return changed ? { nodes: newNodes, edges: newEdges } : { nodes, edges };
}
