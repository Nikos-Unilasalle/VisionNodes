import { createContext, useContext } from 'react';

export const NodesDataContext = createContext<Record<string, any>>({});

export function useNodeData(nodeId: string | null): Record<string, any> {
  const nodesData = useContext(NodesDataContext);
  if (!nodeId) return {};
  const dataKeys = Object.keys(nodesData).filter(k => k.startsWith(`${nodeId}:`));
  return dataKeys.length > 0
    ? Object.fromEntries(dataKeys.map(k => [k.split(':')[1], nodesData[k]]))
    : (nodesData[nodeId] ?? {});
}
