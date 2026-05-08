import type { Node, Edge } from 'reactflow';

export type GroupEntry = { groupNodeId: string };

export interface Canvas {
  id: string;
  name: string;
  nodes: Node[];
  edges: Edge[];
  filePath: string | null;
}

export const CANVAS_IDS = ['c1', 'c2', 'c3', 'c4'];
export const CANVAS_NAMES = ['Scene 1', 'Scene 2', 'Scene 3', 'Scene 4'];

export const makeInitialCanvases = (): Canvas[] => CANVAS_IDS.map((id, i) => ({
  id,
  name: CANVAS_NAMES[i],
  nodes: [],
  edges: [],
  filePath: null,
}));
