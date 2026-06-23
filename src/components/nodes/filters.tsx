import React, { memo, useState, useMemo, useEffect } from 'react';
import { Handle, Position, useNodeId, useEdges, useUpdateNodeInternals, NodeResizer, useStore } from 'reactflow';
import { useNodeData } from '../../context/NodesDataContext';
import { useComputingNodeId } from '../../context/ComputingNodeContext';
import { open, save } from '@tauri-apps/plugin-dialog';
import { openPath } from '@tauri-apps/plugin-opener';
import {
  Camera, Waves, Ghost, Maximize, Search, User, Zap, Activity,
  Hash, Eye, Layout, PenTool, Database, Wind, Target, Palette, Scaling, Move, Layers, Box, Image, Film, Play, Pause,
  Plus, Info, Save, FolderOpen, BookOpen, Video, Type, Calculator, PlusSquare, Minus, Divide, Scissors, Keyboard, HelpCircle, ChevronDown, ChevronUp,
  Crosshair, Monitor, Lock, LockOpen, Crop, Filter, Package, LogIn, LogOut, BarChart2, Music, Volume2, RotateCcw, Repeat, Download, FileCode, ZapOff,
  Clipboard, FileText
} from 'lucide-react';
import * as LucideIcons from 'lucide-react';
import {
  AreaChart, Area, ResponsiveContainer, YAxis, XAxis, Tooltip,
  BarChart, Bar, Cell, LineChart, Line, CartesianGrid, ReferenceLine,
  ComposedChart,
} from 'recharts';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { MarkdownToolbar } from '../MarkdownToolbar';
import { getIcon, StyledHandle, BaseNode, HANDLE_COLORS, NodeColorContext, useNodeColor, NodeColorProvider, PALETTES } from './_shared';

export const FilterCannyNode = memo(({ selected, data }: any) => (
  <BaseNode title="Canny Edge" icon={Waves} selected={selected} data={data} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));


export const FilterGradientNode = memo(({ selected, data }: any) => (
  <BaseNode title="Image Gradient" icon={LucideIcons.ArrowUpRight} selected={selected} data={data} color="blue" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'magnitude', color: 'image'}, {id: 'angle', color: 'image'}, {id: 'dx', color: 'any'}, {id: 'dy', color: 'any'}]} />
));


export const FilterBlurNode = memo(({ selected, data }: any) => (
  <BaseNode title="Blur" icon={Ghost} selected={selected} data={data} color="blue" inputs={[{id: 'main', color: 'image'}, {id: 'mask', color: 'mask'}]} outputs={[{id: 'main', color: 'image'}]} />
));


export const FilterThresholdNode = memo(({ selected, data }: any) => (
  <BaseNode title="Threshold" icon={Waves} selected={selected} data={data} color="blue" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'main', color: 'image'}, {id: 'mask', color: 'mask'}]} />
));


export const FilterColorMaskNode = memo(({ selected, data }: any) => {
  const color = data.params?.color || '#FF0000';
  const mode = data.params?.mode === 1 ? 'RGB' : 'HSV';
  
  return (
    <BaseNode title="Color Mask" icon={Layers} selected={selected} data={data} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'mask', color: 'mask'}]}>
      <div className="px-3 py-2 space-y-2">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <div 
              className="w-5 h-5 rounded-full border border-white/20 shadow-inner" 
              style={{ backgroundColor: color, boxShadow: `0 0 10px ${color}44` }} 
            />
            <span className="text-[10px] font-mono font-bold text-gray-400">{color}</span>
          </div>
          <div className="px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-[8px] font-black text-accent uppercase tracking-tighter">
            {mode}
          </div>
        </div>
      </div>
    </BaseNode>
  );
});


export const FilterGrayNode = memo(({ selected, data }: any) => (
  <BaseNode title="Grayscale" icon={Eye} selected={selected} data={data} color="accent" inputs={[{id: 'image', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));


export const FilterMorphologyNode = memo(({ selected, data }: any) => (
  <BaseNode title="Morphology" icon={Waves} selected={selected} data={data} color="accent" inputs={[{id: 'mask', color: 'mask'}, {id: 'image', color: 'image'}]} outputs={[{id: 'mask', color: 'mask'}]} />
));


export const FilterMorphologySmartNode = memo(({ selected, data }: any) => (
  <BaseNode title="Smart Morphology" icon={Zap} selected={selected} data={data} color="accent" inputs={[{id: 'mask', color: 'mask'}]} outputs={[{id: 'mask', color: 'mask'}]} />
));


export const GeomFlipNode = memo(({ selected, data }: any) => (
  <BaseNode title="Flip" icon={Move} selected={selected} data={data} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]} />
));


export const GeomResizeNode = memo(({ selected, data }: any) => (
  <BaseNode title="Resize" icon={Scaling} selected={selected} data={data} color="blue" inputs={[{id: 'main', color: 'image'}]} outputs={[{id: 'main', color: 'image'}]}>
    {data.node_data?.width && (
      <div className="px-1 pt-1">
        <div className="text-[10px] font-mono text-blue-400 font-bold">{data.node_data.width}×{data.node_data.height}</div>
      </div>
    )}
  </BaseNode>
));

