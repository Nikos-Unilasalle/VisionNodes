import type { Node } from 'reactflow';

export type ParamType = 'int' | 'float' | 'number' | 'scalar' | 'string' | 'bool' | 'boolean' | 'toggle' | 'enum' | 'trigger' | 'code' | 'color';
export type PortColor = 'image' | 'mask' | 'any' | 'scalar' | 'list' | 'dict' | 'bool' | 'string';

export interface ParamSpec {
  id: string;
  label?: string;
  type?: ParamType;
  default?: unknown;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
}

export interface PortSpec {
  id: string;
  color: PortColor;
  label?: string;
}

export interface NodeSchema {
  type: string;
  label: string;
  category: string;
  icon: string;
  description?: string;
  inputs: PortSpec[];
  outputs: PortSpec[];
  params: ParamSpec[];
  resizable?: boolean;
  min_width?: number;
  min_height?: number;
  colorable?: boolean;
}

export interface NodeData {
  label: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  params: Record<string, any>;
  schema?: NodeSchema;
  description?: string;
}

export type VNNode = Node<NodeData>;
