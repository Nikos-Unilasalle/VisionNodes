import { describe, it, expect } from 'vitest';

// ── useNodeData logic ────────────────────────────────────────────────────────
// Tests the extraction logic from NodesDataContext without React rendering.

function extractNodeData(nodesData: Record<string, unknown>, nodeId: string): Record<string, unknown> {
  const dataKeys = Object.keys(nodesData).filter(k => k.startsWith(`${nodeId}:`));
  return dataKeys.length > 0
    ? Object.fromEntries(dataKeys.map(k => [k.split(':')[1], nodesData[k]]))
    : ((nodesData[nodeId] as Record<string, unknown>) ?? {});
}

describe('extractNodeData', () => {
  it('extracts colon-prefixed keys for node', () => {
    const nodesData = {
      'node-1:width': 640,
      'node-1:height': 480,
      'node-2:width': 1280,
    };
    const result = extractNodeData(nodesData, 'node-1');
    expect(result).toEqual({ width: 640, height: 480 });
  });

  it('falls back to flat key when no colon-prefixed keys', () => {
    const nodesData = {
      'node-1': { scalar: 42, label: 'test' },
    };
    const result = extractNodeData(nodesData, 'node-1');
    expect(result).toEqual({ scalar: 42, label: 'test' });
  });

  it('returns empty object for unknown node', () => {
    expect(extractNodeData({}, 'ghost')).toEqual({});
  });

  it('does not mix keys from different nodes', () => {
    const nodesData = {
      'node-1:fps': 30,
      'node-2:fps': 60,
    };
    expect(extractNodeData(nodesData, 'node-1')).toEqual({ fps: 30 });
    expect(extractNodeData(nodesData, 'node-2')).toEqual({ fps: 60 });
  });

  it('colon-prefixed keys take priority over flat key', () => {
    const nodesData = {
      'node-1': { old: true },
      'node-1:new': true,
    };
    const result = extractNodeData(nodesData, 'node-1');
    expect(result).toEqual({ new: true });
    expect(result).not.toHaveProperty('old');
  });
});
