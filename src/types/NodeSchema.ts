import type { Node } from 'reactflow';

export type ParamType = 'int' | 'float' | 'number' | 'scalar' | 'string' | 'bool' | 'boolean' | 'toggle' | 'enum' | 'trigger' | 'code' | 'color' | 'file_path' | 'file_open' | 'date' | 'section';
export type PortColor = 'image' | 'mask' | 'any' | 'scalar' | 'list' | 'dict' | 'bool' | 'string' | 'geotiff';

export interface ParamSpec {
  id: string;
  label?: string;
  type?: ParamType;
  default?: unknown;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  /** Hide this param unless another param matches a given value. */
  show_if?: { param: string; value: number | string | boolean };
  /** Slot key ('a'–'h') — hide this param if the slot is not connected. */
  slot?: string;
  /** UI hint — 'df_columns' shows clickable column chips from live df_meta. */
  hints?: string;
}

export interface PortSpec {
  id: string;
  color: PortColor;
  label?: string;
}

export interface NodeSchema {
  type: string;
  label: string;
  category: string | string[];
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
  exposedParams?: string[];
}

export type VNNode = Node<NodeData>;
