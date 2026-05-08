import type { Node, Edge } from 'reactflow';
import type { GroupEntry } from '../data/canvases';

export function getNestedSubGraph(
  canvasNodes: Node[],
  stack: GroupEntry[]
): { nodes: Node[]; edges: Edge[] } {
  if (stack.length === 0) return { nodes: [], edges: [] };
  const g = canvasNodes.find(n => n.id === stack[0].groupNodeId);
  const sub = (g?.data as any)?.subGraph ?? { nodes: [], edges: [] };
  if (stack.length === 1) return sub;
  return getNestedSubGraph(sub.nodes, stack.slice(1));
}

export function updateNestedSubGraph(
  canvasNodes: Node[],
  stack: GroupEntry[],
  field: 'nodes' | 'edges',
  updater: (items: any[]) => any[]
): Node[] {
  return canvasNodes.map(n => {
    if (n.id !== stack[0].groupNodeId) return n;
    const sub = (n.data as any)?.subGraph ?? { nodes: [], edges: [] };
    if (stack.length === 1) {
      return { ...n, data: { ...n.data, subGraph: { ...sub, [field]: updater(sub[field] ?? []) } } };
    }
    return { ...n, data: { ...n.data, subGraph: { ...sub, nodes: updateNestedSubGraph(sub.nodes, stack.slice(1), field, updater) } } };
  });
}
