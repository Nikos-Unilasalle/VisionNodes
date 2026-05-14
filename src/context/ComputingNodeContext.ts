import { createContext, useContext } from 'react';

export const ComputingNodeContext = createContext<string | null>(null);

export function useComputingNodeId(): string | null {
  return useContext(ComputingNodeContext);
}
