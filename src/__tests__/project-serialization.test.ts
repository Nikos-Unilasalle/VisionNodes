import { describe, it, expect } from 'vitest';

// ── Project serialization contract ──────────────────────────────────────────
// Mirrors the load/save logic in App.tsx to catch schema drift.

interface NodeData {
  label?: string;
  params?: Record<string, unknown>;
}

interface SerializedProject {
  nodes: Array<{ id: string; type: string; position: { x: number; y: number }; data: NodeData }>;
  edges: Array<{ id: string; source: string; target: string }>;
  ui?: Record<string, unknown>;
}

function serializeProject(nodes: SerializedProject['nodes'], edges: SerializedProject['edges']): string {
  return JSON.stringify({ nodes, edges });
}

function deserializeProject(content: string): SerializedProject {
  const data = JSON.parse(content);
  const nodes = (data.nodes || []) as SerializedProject['nodes'];
  const edges = (data.edges || []) as SerializedProject['edges'];
  const ui = data.ui as Record<string, unknown> | undefined;
  return { nodes, edges, ui };
}

const SAMPLE_NODES: SerializedProject['nodes'] = [
  { id: 'n1', type: 'input_webcam', position: { x: 0, y: 0 }, data: { label: 'Webcam', params: { device_index: 0 } } },
  { id: 'n2', type: 'output_display', position: { x: 400, y: 0 }, data: { label: 'Display', params: {} } },
];

const SAMPLE_EDGES: SerializedProject['edges'] = [
  { id: 'e1', source: 'n1', target: 'n2' },
];

describe('Project serialization', () => {
  it('round-trips nodes and edges', () => {
    const json = serializeProject(SAMPLE_NODES, SAMPLE_EDGES);
    const { nodes, edges } = deserializeProject(json);
    expect(nodes).toHaveLength(2);
    expect(edges).toHaveLength(1);
    expect(nodes[0].id).toBe('n1');
    expect(edges[0].source).toBe('n1');
  });

  it('preserves node params', () => {
    const json = serializeProject(SAMPLE_NODES, SAMPLE_EDGES);
    const { nodes } = deserializeProject(json);
    expect(nodes[0].data.params?.device_index).toBe(0);
  });

  it('missing nodes/edges defaults to empty arrays', () => {
    const { nodes, edges } = deserializeProject('{}');
    expect(nodes).toEqual([]);
    expect(edges).toEqual([]);
  });

  it('preserves ui field', () => {
    const json = JSON.stringify({ nodes: [], edges: [], ui: { zoom: 0.8 } });
    const { ui } = deserializeProject(json);
    expect(ui?.zoom).toBe(0.8);
  });

  it('throws on invalid JSON', () => {
    expect(() => deserializeProject('not json')).toThrow();
  });
});
