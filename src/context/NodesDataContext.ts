import { createContext, useContext, useEffect, useRef, useState } from 'react';

// Ref-based store: mutations don't trigger React re-renders.
// Node components subscribe to their own slice and re-render only when their data changes.

export type NodesDataStore = {
  getAll: () => Record<string, any>;
  getNode: (nodeId: string) => Record<string, any>;
  subscribe: (nodeId: string, cb: () => void) => () => void;
  _update: (data: Record<string, any>) => void;
};

function createNodesDataStore(): NodesDataStore {
  let current: Record<string, any> = {};
  const listeners = new Map<string, Set<() => void>>();

  function getAll() {
    return current;
  }

  function getNode(nodeId: string): Record<string, any> {
    const prefix = `${nodeId}:`;
    const result: Record<string, any> = {};
    for (const k in current) {
      if (k.startsWith(prefix)) {
        result[k.slice(prefix.length)] = current[k];
      }
    }
    // Fallback: legacy flat key
    if (Object.keys(result).length === 0 && current[nodeId] !== undefined) {
      return current[nodeId];
    }
    return result;
  }

  function subscribe(nodeId: string, cb: () => void): () => void {
    if (!listeners.has(nodeId)) listeners.set(nodeId, new Set());
    listeners.get(nodeId)!.add(cb);
    return () => listeners.get(nodeId)?.delete(cb);
  }

  function _update(data: Record<string, any>) {
    // Find which node IDs changed
    const changed = new Set<string>();
    for (const k in data) {
      if (current[k] !== data[k]) {
        const nodeId = k.includes(':') ? k.split(':')[0] : k;
        changed.add(nodeId);
      }
    }
    // Also detect removed keys
    for (const k in current) {
      if (!(k in data)) {
        const nodeId = k.includes(':') ? k.split(':')[0] : k;
        changed.add(nodeId);
      }
    }
    current = data;
    // Notify only affected node subscribers
    for (const nodeId of changed) {
      listeners.get(nodeId)?.forEach(cb => cb());
    }
  }

  return { getAll, getNode, subscribe, _update };
}

export const NodesDataContext = createContext<NodesDataStore>(createNodesDataStore());

/**
 * Subscribe to a single node's live data. Re-renders only when that node's data changes.
 */
export function useNodeData(nodeId: string | null): Record<string, any> {
  const store = useContext(NodesDataContext);
  const [, forceRender] = useState(0);

  useEffect(() => {
    if (!nodeId) return;
    const unsub = store.subscribe(nodeId, () => forceRender(n => n + 1));
    return unsub;
  }, [store, nodeId]);

  return nodeId ? store.getNode(nodeId) : {};
}

export { createNodesDataStore };
