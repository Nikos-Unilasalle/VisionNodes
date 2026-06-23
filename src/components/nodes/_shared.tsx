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

export const getIcon = (name: string, fallback = Box) => {
  if (!name) return fallback;
  const icon = (LucideIcons as any)[name];
  return icon || fallback;
};


export const HANDLE_COLORS = { image: '#3b82f6', data: '#f97316', dict: '#22c55e', list: '#a855f7', scalar: '#eab308', string: '#7dd3fc', mask: '#d1d5db', flow: '#ef4444', boolean: '#22d3ee', any: '#ffffff', geotiff: '#059669', audio: '#818cf8', markers: '#f59e0b', regions: '#2dd4bf', contours: '#a3e635', coords: '#fb7185', points: '#e879f9', vectors: '#38bdf8' };


export const NodeColorContext = React.createContext<{ customBg?: string; customText?: string }>({});

export const useNodeColor = () => React.useContext(NodeColorContext);

export const NodeColorProvider = NodeColorContext.Provider;


export const StyledHandle = ({ type, position, id, color = 'image', top = '50%', left, noBorder = false }: any) => {
  const nodeId = useNodeId();
  const handleId = `${color}__${id}`;
  const isLeft = position === Position.Left;
  const isHoriz = position === Position.Top || position === Position.Bottom;

  const posStyle = isHoriz
    ? { left: left || '50%', transform: 'translateX(-50%)', top: position === Position.Top ? -5 : undefined, bottom: position === Position.Bottom ? -5 : undefined }
    : { top, [isLeft ? 'left' : 'right']: -5 };

  return (
    <Handle
      type={type}
      position={position}
      id={handleId}
      style={{
        background: HANDLE_COLORS[color as keyof typeof HANDLE_COLORS] || color,
        width: noBorder ? 5 : 10,
        height: noBorder ? 5 : 10,
        borderRadius: noBorder ? 0 : '50%',
        border: noBorder ? 'none' : '2px solid #111',
        zIndex: 50,
        position: 'absolute',
        ...posStyle,
      }}
      onClick={(e) => {
        e.stopPropagation();
        window.dispatchEvent(new CustomEvent('remove-handle-edge', { detail: { nodeId, handleId, type } }));
      }}
    />
  );
};




export const BaseNode = ({ 
  title, 
  icon: Icon, 
  selected, 
  data, 
  color = 'blue', 
  inputs = [], 
  outputs = [], 
  children, 
  width, 
  height,
  headerExtra, 
  className = "" 
}: any) => {
  const { customBg } = useNodeColor();
  const nodeId = useNodeId();
  const computingNodeId = useComputingNodeId();
  const isComputing = !!nodeId && computingNodeId === nodeId;
  const updateNodeInternals = useUpdateNodeInternals();
  // Externalized-param input handles — rendered natively on any node (see App.onExternalizeParam).
  const paramPorts: { id: string; color: string; label?: string }[] = (data as any)?.paramPorts ?? [];
  const allInputs = paramPorts.length ? [...inputs, ...paramPorts] : inputs;
  const totalInputs = allInputs.length + (data?.params?.var_count || 0);
  const totalOutputs = outputs.length;
  const maxPorts = Math.max(totalInputs, totalOutputs);

  const nodeNote = data?.params?.node_note;
  // Custom node label: when set, replaces the header title; the canonical type name
  // is shown small + blue in the header's right corner (see inspector "Label" field).
  const userLabel = ((data as any)?.userLabel || '').trim();
  const isLockedOut = !!(data as any)?.lockedOut;
  const isBypassed = !!(data as any)?.bypassed;
  const isMinified = !!(data as any)?.minified;
  const isRotated = !!(data as any)?.rotated;
  const startOffset = isMinified ? 10 : 45;
  const spacing = isMinified ? 5 : 32;

  useEffect(() => { if (nodeId) updateNodeInternals(nodeId); }, [isRotated, isMinified, nodeId, updateNodeInternals, totalInputs, totalOutputs]);

  const getPortTop = (index: number, total: number) => {
    if (total === 0) return '50%';
    return `${startOffset + index * spacing}px`;
  };

  const nodeWidth = typeof width === 'number' ? width : 208;
  const getPortLeft = (index: number, total: number) => {
    if (total <= 1) return `${nodeWidth / 2}px`;
    const margin = 16;
    const step = (nodeWidth - margin * 2) / (total - 1);
    return `${margin + index * step}px`;
  };
  const portsHeight = maxPorts > 0 ? (startOffset + (maxPorts - 1) * spacing + 12) : 24;
  const minHeight = Math.max(portsHeight, isMinified ? 18 : 90);

  const borderClass = isLockedOut
    ? 'border-red-500'
    : isBypassed
    ? 'border-gray-500'
    : selected ? (color === 'accent' ? 'border-accent' : `border-${color}-500`) : 'border-[#4f5b6b]';

  return (
    <div className={`relative ${className}`} style={{
        width: width || '13rem',
        height: height || 'auto'
    }}>
    <div
        className={`rounded-xl bg-[#2c333f] border-2 transition-all duration-300 ${borderClass} ${selected ? 'shadow-lg scale-105' : ''} shadow-2xl relative w-full h-full flex flex-col${isBypassed ? ' opacity-50 grayscale' : ''}`}
        style={{
          minHeight: height ? undefined : minHeight,
          ...(isLockedOut
            ? { boxShadow: '0 0 24px rgba(239,68,68,0.45), 0 0 8px rgba(239,68,68,0.25)' }
            : isBypassed
            ? { boxShadow: '0 0 12px rgba(107,114,128,0.3)' }
            : customBg ? { borderColor: customBg, boxShadow: selected ? `0 10px 15px -3px ${customBg}40` : `0 0 10px ${customBg}10` } : {}),
        }}
    >
      {isLockedOut && (
        <div className="absolute top-0 right-0 z-20 flex items-center gap-1 bg-red-500 text-white text-[7px] font-black px-2 py-1 rounded-bl-lg rounded-tr-[10px] uppercase tracking-widest shadow-lg select-none pointer-events-none">
          <Lock size={7} strokeWidth={3} />
          <span>LOCK OUT</span>
        </div>
      )}
      {isBypassed && (
        <div className="absolute top-0 right-0 z-20 flex items-center gap-1 bg-gray-600 text-white text-[7px] font-black px-2 py-1 rounded-bl-lg rounded-tr-[10px] uppercase tracking-widest shadow-lg select-none pointer-events-none">
          <span>BYPASS</span>
        </div>
      )}
      {/* Inputs with Labels */}
      {isRotated
        ? allInputs.map((inp: any, i: number) => {
            const portLeft = getPortLeft(i, totalInputs);
            return (
              <React.Fragment key={inp.id}>
                <StyledHandle type="target" position={Position.Top} id={inp.id} color={inp.color} left={portLeft} noBorder={isMinified} />
                {!isMinified && <span className="absolute text-[7px] font-medium text-gray-500 uppercase tracking-tighter opacity-80 pointer-events-none z-10 text-center" style={{ left: portLeft, top: 8, transform: 'translateX(-50%)' }}>{inp.label || inp.id}</span>}
              </React.Fragment>
            );
          })
        : allInputs.map((inp: any, i: number) => {
            const top = getPortTop(i, totalInputs);
            return (
              <div key={inp.id} className="absolute left-0 w-full flex items-center pointer-events-none z-10" style={{ top, transform: 'translateY(-50%)' }}>
                <StyledHandle type="target" position={Position.Left} id={inp.id} color={inp.color} top="50%" noBorder={isMinified} />
                {!isMinified && <span className="ml-[12px] text-[7px] font-medium text-gray-500 uppercase tracking-tighter opacity-80 max-w-[42%] truncate">{inp.label || inp.id}</span>}
              </div>
            );
          })
      }

      {/* Dynamic Variables with Labels */}
      {Array.from({ length: (data?.params?.var_count || 0) }).map((_, i) => {
        const char = String.fromCharCode(97 + i);
        if (isRotated) {
          const portLeft = getPortLeft(allInputs.length + i, totalInputs);
          return (
            <React.Fragment key={char}>
              <StyledHandle type="target" position={Position.Top} id={char} color="scalar" left={portLeft} noBorder={isMinified} />
              {!isMinified && <span className="absolute text-[8px] font-medium text-accent uppercase tracking-widest pointer-events-none z-10 text-center" style={{ left: portLeft, top: 8, transform: 'translateX(-50%)' }}>{char}</span>}
            </React.Fragment>
          );
        }
        const top = getPortTop(allInputs.length + i, totalInputs);
        return (
          <div key={char} className="absolute left-0 w-full flex items-center pointer-events-none z-10" style={{ top, transform: 'translateY(-50%)' }}>
            <StyledHandle type="target" position={Position.Left} id={char} color="scalar" top="50%" noBorder={isMinified} />
            {!isMinified && <span className="ml-[12px] text-[8px] font-medium text-accent uppercase tracking-widest">{char}</span>}
          </div>
        );
      })}
      
      {!isMinified && (
      <div className="bg-[#3d4452] px-4 py-2 flex items-center justify-between border-b border-[#4f5b6b] rounded-t-[10px] overflow-hidden group/header shrink-0"
           style={customBg ? { backgroundColor: `${customBg}20`, borderBottomColor: `${customBg}40` } : {}}>
        <div className="flex items-center gap-3 truncate min-w-0 flex-1">
          <Icon size={14} className="shrink-0 transition-colors" style={customBg ? { color: customBg } : {}} />
          <span className="font-bold text-[10px] uppercase tracking-widest truncate" style={customBg ? { color: customBg } : { color: '#e5e7eb' }}>{userLabel || title}</span>

          {data?.schema?.variable_inputs && (
            <div className="flex gap-1 ml-2 shrink-0">
              <button 
                onClick={(e) => { e.stopPropagation(); data.onChangeParams?.({ var_count: Math.max((data.params?.var_count || 0) - 1, 0) }); }}
                className="w-4 h-4 flex items-center justify-center bg-white/5 hover:bg-red-500/20 text-gray-400 hover:text-red-500 rounded border border-white/10 transition-all text-[10px] font-bold"
              >-</button>
              <button 
                onClick={(e) => { e.stopPropagation(); data.onChangeParams?.({ var_count: Math.min((data.params?.var_count || 0) + 1, 10) }); }}
                className="w-4 h-4 flex items-center justify-center bg-white/5 hover:bg-green-500/20 text-gray-400 hover:text-green-500 rounded border border-white/10 transition-all text-[10px] font-bold"
              >+</button>
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {userLabel && <span className="hidden group-hover/header:inline text-[8px] font-bold uppercase tracking-wider text-blue-400/80 truncate max-w-[120px]" title={title}>{title}</span>}
          {data?.isVisualized && <Eye size={11} className="text-yellow-400 animate-pulse" />}
          {headerExtra}
        </div>
      </div>
      )}
      
      {isMinified && (
        <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
          <span className="text-[8px] font-bold uppercase tracking-wider truncate max-w-[90%]" style={customBg ? { color: customBg } : { color: '#6b7280' }}>{userLabel || title}</span>
        </div>
      )}
      
      {!isMinified && (
      <div className="flex-1 p-2 text-[10px] text-gray-400 flex flex-col min-h-0 overflow-hidden rounded-b-[10px]">
        {children}
      </div>
      )}

      {/* Outputs with Labels */}
      {isRotated
        ? outputs.map((out: any, i: number) => {
            const portLeft = getPortLeft(i, totalOutputs);
            return (
              <React.Fragment key={out.id}>
                <StyledHandle type="source" position={Position.Bottom} id={out.id} color={out.color} left={portLeft} noBorder={isMinified} />
                {!isMinified && <span className="absolute text-[7px] font-medium text-gray-500 uppercase tracking-tighter opacity-80 pointer-events-none z-10 text-center" style={{ left: portLeft, bottom: 8, transform: 'translateX(-50%)' }}>{out.label || out.id}</span>}
              </React.Fragment>
            );
          })
        : outputs.map((out: any, i: number) => {
            const top = getPortTop(i, totalOutputs);
            return (
              <div key={out.id} className="absolute right-0 w-full flex items-center justify-end pointer-events-none z-10" style={{ top, transform: 'translateY(-50%)' }}>
                {!isMinified && <span className="mr-[12px] text-[7px] font-medium text-gray-500 uppercase tracking-tighter opacity-80 max-w-[42%] truncate text-right">{out.label || out.id}</span>}
                <StyledHandle type="source" position={Position.Right} id={out.id} color={out.color} top="50%" noBorder={isMinified} />
              </div>
            );
          })
      }
    </div>
    {nodeNote && (
      <div className="absolute left-0 right-0 top-full mt-1 text-center text-[9px] text-gray-400/80 truncate px-2 pointer-events-none select-none">
        {nodeNote}
      </div>
    )}
    {isComputing && (
      <div
        className="absolute pointer-events-none"
        style={{ bottom: '-5px', right: 0, width: '50%', height: '3px', borderRadius: '9999px' }}
      >
        <div style={{
          width: '100%',
          height: '100%',
          borderRadius: '9999px',
          background: 'linear-gradient(90deg, transparent, #4ade80 40%, #86efac 50%, #4ade80 60%, transparent)',
          backgroundSize: '200% 100%',
          animation: 'computing-sweep 1.2s linear infinite',
          boxShadow: '0 0 8px 2px rgba(74,222,128,0.6)',
        }} />
      </div>
    )}
    </div>
  );
};

// --- NODES ---

export const PALETTES = [
  {
    name: 'Astro',
    colors: [
      { bg: '#2B2B85', dark: '#ffffff' },
      { bg: '#5C5EDC', dark: '#ffffff' },
      { bg: '#8A8DF6', dark: '#111111' },
      { bg: '#BBAEFE', dark: '#111111' },
      { bg: '#FEADFE', dark: '#111111' }
    ]
  },
  {
    name: 'Moon',
    colors: [
      { bg: '#EAE9F5', dark: '#111111' },
      { bg: '#B3C3DE', dark: '#111111' },
      { bg: '#7698C3', dark: '#ffffff' },
      { bg: '#486B8E', dark: '#ffffff' },
      { bg: '#29405C', dark: '#ffffff' }
    ]
  },
  {
    name: 'Florest Moth',
    colors: [
      { bg: '#4A5D23', dark: '#ffffff' },
      { bg: '#8F994B', dark: '#111111' },
      { bg: '#C1C881', dark: '#111111' },
      { bg: '#EAE6AA', dark: '#111111' },
      { bg: '#E0AA90', dark: '#111111' }
    ]
  },
  {
    name: 'Cyberpunk Dreams',
    colors: [
      { bg: '#FF127B', dark: '#ffffff' },
      { bg: '#C21584', dark: '#ffffff' },
      { bg: '#741A8E', dark: '#ffffff' },
      { bg: '#3C1361', dark: '#ffffff' },
      { bg: '#1D0A35', dark: '#ffffff' }
    ]
  },
  {
    name: 'Night Winter',
    colors: [
      { bg: '#111F36', dark: '#ffffff' },
      { bg: '#234476', dark: '#ffffff' },
      { bg: '#406E9E', dark: '#ffffff' },
      { bg: '#7DABC6', dark: '#111111' },
      { bg: '#C8E2ED', dark: '#111111' }
    ]
  },
  {
    name: '90s Anime',
    colors: [
      { bg: '#FF645F', dark: '#ffffff' },
      { bg: '#FFAD48', dark: '#111111' },
      { bg: '#FFDE87', dark: '#111111' },
      { bg: '#6FA4D2', dark: '#111111' },
      { bg: '#5D4585', dark: '#ffffff' }
    ]
  },
  {
    name: 'Original VN',
    colors: [
      { bg: '#a8e6cf', dark: '#1a3d2e' },
      { bg: '#dcedbf', dark: '#2a3a1a' },
      { bg: '#ffd4b8', dark: '#3a2010' },
      { bg: '#ffa8a3', dark: '#3a1010' },
      { bg: '#ff667d', dark: '#1a0a0a' }
    ]
  }
];

