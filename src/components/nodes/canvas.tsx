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

const _noteHash = (s: string) => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) | 0; } return Math.abs(h); };


export const CanvasNoteNode = memo(({ selected, data }: any) => {
  const [editing, setEditing] = useState(false);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const blurTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const text = data.params?.text ?? '';
  const palIdx = data?.activePaletteIndex ?? 6;
  const cIdx = data?.params?.color_index;
  const bgColor = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.bg : (data?.params?.bg_color || '#ffd4b8');
  const textColor = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.dark : (data?.params?.text_color || '#3a2010');

  // Deterministic tilt from node id — fixed per note, never changes
  const rotation = ((_noteHash(data.id || '') % 7) - 3) * 0.18; // -0.54° to +0.54°

  React.useEffect(() => {
    if (editing) textareaRef.current?.focus();
  }, [editing]);

  // Cancel pending close if pointer stays inside the editing area (toolbar clicks)
  const handleEditorMouseDown = () => {
    if (blurTimerRef.current) {
      clearTimeout(blurTimerRef.current);
      blurTimerRef.current = null;
    }
  };

  const handleTextareaBlur = () => {
    // Delay close so toolbar onMouseDown can cancel it first
    blurTimerRef.current = setTimeout(() => setEditing(false), 150);
  };

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditing(true);
  };

  const isMinified = !!(data as any)?.minified;

  // ── Note minifiée : adorable petite icône (post-it) ──────────────────────
  if (isMinified) {
    const firstLine = (text || '').split('\n').find((l: string) => l.trim()) || 'Note vide';
    return (
      <div
        className="relative w-full h-full flex items-center justify-center overflow-hidden cursor-grab active:cursor-grabbing transition-all duration-200 hover:scale-105"
        style={{
          background: bgColor,
          borderRadius: '6px',
          transform: `rotate(${rotation - 2}deg)`,
          boxShadow: selected
            ? `3px 5px 14px rgba(0,0,0,0.34), 0 0 0 2px rgba(0,0,0,0.25)`
            : `2px 4px 10px rgba(0,0,0,0.26)`,
        }}
        onDoubleClick={handleDoubleClick}
        title={firstLine}
      >
        {/* coin replié (dog-ear) pour l'effet post-it */}
        <div
          className="absolute top-0 right-0 w-2.5 h-2.5"
          style={{
            background: 'rgba(0,0,0,0.16)',
            borderRadius: '0 6px 0 4px',
          }}
        />
        <LucideIcons.StickyNote size={18} strokeWidth={2.2} style={{ color: textColor, opacity: 0.85 }} />
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      {/* Handles outside overflow-hidden so they aren't clipped */}
      <StyledHandle type="target" position={Position.Left}  id="text"     color="any"    top="40px" />
      <StyledHandle type="source" position={Position.Right} id="text_out" color="string" top="40px" />
    <div
      className="flex-1 w-full h-full flex flex-col overflow-hidden transition-all duration-200"
      style={{
        background: bgColor,
        borderRadius: '5px 5px 0 0',
        transform: `rotate(${rotation}deg)`,
        height: '100%',
        boxShadow: selected
          ? `5px 8px 24px rgba(0,0,0,0.38), 2px 3px 8px rgba(0,0,0,0.22), 0 0 0 2px rgba(0,0,0,0.25)`
          : `4px 6px 18px rgba(0,0,0,0.28), 2px 3px 6px rgba(0,0,0,0.16)`,
      }}
      onDoubleClick={handleDoubleClick}
    >
      <div
        className="flex items-center gap-1.5 px-2 py-1 select-none cursor-grab active:cursor-grabbing"
        style={{ background: 'rgba(0,0,0,0.13)', borderBottom: '1px solid rgba(0,0,0,0.10)' }}
      >
        <div
          className="w-2.5 h-2.5 rounded-[2px] flex-shrink-0"
          style={{ background: 'rgba(255,255,255,0.30)', border: '1px solid rgba(0,0,0,0.18)' }}
        />
        <span
          className="text-[8px] font-black uppercase tracking-[0.18em] truncate flex-1"
          style={{ color: `${textColor}88` }}
        >
          Note
        </span>
      </div>

      {!isMinified && (
        editing ? (
          <div className="flex-1 flex flex-col min-h-0 w-full h-full bg-black/10 nodrag nopan nowheel" onMouseDown={handleEditorMouseDown}>
            <MarkdownToolbar
              textareaRef={textareaRef}
              value={text}
              onChange={(val) => data.onChangeParams?.({ text: val })}
            />
            <textarea
              ref={textareaRef}
              value={text}
              onChange={e => data.onChangeParams?.({ text: e.target.value })}
              onBlur={handleTextareaBlur}
              onKeyDown={e => {
                if (e.key === 'Escape') setEditing(false);
                e.stopPropagation();
              }}
              className="nodrag nopan flex-1 w-full bg-transparent border-none outline-none resize-none px-3 py-2 leading-relaxed"
              style={{ color: textColor, fontSize: 13, fontFamily: 'inherit', fontWeight: 400, caretColor: textColor }}
              placeholder="Write your note here (Markdown supported)..."
            />
          </div>
        ) : (
          <div
            className="flex-1 nodrag nowheel px-3 py-2 overflow-y-auto select-none cursor-text markdown-body"
            style={{
              color: text ? textColor : `${textColor}55`,
              fontSize: 13,
              fontWeight: 400,
              lineHeight: '1.65',
              wordBreak: 'break-word',
              fontStyle: text ? 'normal' : 'italic',
            }}
          >
            {text ? (
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                {text}
              </ReactMarkdown>
            ) : (
              'Double-click to edit…'
            )}
          </div>
        )
      )}
    </div>
    </div>
  );
});


export const CanvasRerouteNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];
  const nodeHeight = useStore((s: any) => s.nodeInternals.get(nodeId)?.height ?? 48);

  useEffect(() => { updateNodeInternals(nodeId); }, [nodeHeight, ports.length, nodeId, updateNodeInternals]);

  // Evenly distribute output handles (ports + factory) across the full height, pixels only
  const total = ports.length + 1; // dynamic ports + factory
  const outTop = (i: number) => Math.round((i + 1) / (total + 1) * nodeHeight);

  return (
    <div
      style={{
        width: 8,
        height: '100%',
        minHeight: 48,
        borderRadius: 4,
        background: selected ? '#888' : '#444',
        border: selected ? '1px solid #aaa' : '1px solid #666',
        boxShadow: selected ? '0 0 0 2px #3b82f6' : '0 2px 6px rgba(0,0,0,0.5)',
        position: 'relative',
      }}
    >
      <NodeResizer
        isVisible={selected}
        minWidth={8}
        maxWidth={8}
        minHeight={24}
        onResize={() => updateNodeInternals(nodeId)}
        handleStyle={{ width: 6, height: 6 }}
        lineStyle={{ borderColor: '#3b82f6' }}
      />
      {/* Input fixed near top */}
      <StyledHandle type="target" position={Position.Left} id="in" color="any" top="10px" />
      {/* Dynamic outputs spread evenly */}
      {ports.map((p, i) => (
        <StyledHandle
          key={p.id}
          type="source"
          position={Position.Right}
          id={p.id.split('__').slice(1).join('__')}
          color={p.color}
          top={`${outTop(i)}px`}
        />
      ))}
      {/* Factory handle always at bottom of distribution */}
      <StyledHandle type="source" position={Position.Right} id="DYNAMIC_NEW_HANDLE" color="any" top={`${outTop(ports.length)}px`} />
    </div>
  );
});


export const CanvasFrameNode = memo(({ selected, data }: any) => {
  const [editing, setEditing] = useState(false);
  const title = data.params?.title ?? 'Frame';
  const isCollapsed = !!(data.params?.collapsed);
  const palIdx = data?.activePaletteIndex ?? 6;
  const cIdx = data?.params?.color_index;
  const bgColor = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.bg : (data?.params?.bg_color || '#6b8cb5');
  const textColor = cIdx !== undefined ? PALETTES[palIdx]?.colors[cIdx % 5]?.dark : (data?.params?.text_color || '#ffffff');

  return (
    <div
      className="w-full rounded-xl border-2 group/frame transition-all flex flex-col overflow-hidden"
      style={{ borderColor: bgColor, backgroundColor: isCollapsed ? bgColor : `${bgColor}15`, height: '100%' }}
    >
      <div
        className="px-3 py-2 font-black text-xs uppercase tracking-widest cursor-text select-none flex items-center gap-2 shrink-0"
        style={{ backgroundColor: bgColor, color: textColor }}
        onDoubleClick={(e) => { e.stopPropagation(); if (!isCollapsed) setEditing(true); }}
      >
        <span className="truncate flex-1 min-w-0">
          {editing ? (
            <input
              autoFocus
              className="bg-black/10 w-full outline-none px-1 py-0.5 rounded"
              style={{ color: textColor }}
              value={title}
              onChange={e => data.onChangeParams?.({ title: e.target.value })}
              onBlur={() => setEditing(false)}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === 'Escape') setEditing(false);
                e.stopPropagation();
              }}
            />
          ) : title}
        </span>
        <button
          className="shrink-0 opacity-0 group-hover/frame:opacity-60 hover:!opacity-100 transition-opacity"
          title={isCollapsed ? 'Expand' : 'Collapse'}
          onPointerDown={e => e.stopPropagation()}
          onDoubleClick={e => e.stopPropagation()}
          onClick={e => { e.stopPropagation(); data.onToggleCollapse?.(); }}
        >
          <ChevronDown size={12} style={{ transform: isCollapsed ? 'rotate(-90deg)' : 'none', transition: 'transform 0.15s' }} />
        </button>
      </div>
      {!isCollapsed && <div className="flex-1 pointer-events-none" />}
    </div>
  );
});

// ──────────────────────────────────────────────────────────────
// GROUP NODES
// ──────────────────────────────────────────────────────────────


export const GroupNode = memo(({ selected, data }: any) => {
  const rawInputs: { id: string; color: string }[] = data?.inputs ?? [];
  const rawOutputs: { id: string; color: string }[] = data?.outputs ?? [];
  const label = data?.params?.label || data?.label || 'Group';

  const splitPort = (p: { id: string; color: string }) => {
    const idx = p.id.indexOf('__');
    return { id: idx >= 0 ? p.id.slice(idx + 2) : p.id, color: idx >= 0 ? p.id.slice(0, idx) : 'any' };
  };

  const inputs = rawInputs.map(splitPort);
  const outputs = rawOutputs.map(splitPort);

  return (
    <BaseNode
      title={label}
      icon={Package}
      selected={selected}
      data={data}
      inputs={inputs}
      outputs={outputs}
      headerExtra={<span className="text-[8px] text-gray-600 font-mono">GROUP</span>}
    >
      <div className="text-[8px] text-gray-600 italic text-center py-0.5">⌥ double-click to enter</div>
    </BaseNode>
  );
});


export const GroupInputNode = memo(({ selected, data }: any) => {
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];
  const outputs = ports.map(p => {
    const idx = p.id.indexOf('__');
    return { id: idx >= 0 ? p.id.slice(idx + 2) : p.id, color: idx >= 0 ? p.id.slice(0, idx) : 'any' };
  });
  return (
    <BaseNode title="Group Input" icon={LogIn} selected={selected} data={data} outputs={outputs} inputs={[]}>
      {ports.length === 0 && <div className="text-[8px] text-gray-600 italic text-center">no inputs</div>}
    </BaseNode>
  );
});


export const GroupOutputNode = memo(({ selected, data }: any) => {
  const nodeId = useNodeId()!;
  const updateNodeInternals = useUpdateNodeInternals();
  const ports: { id: string; color: string; label: string }[] = data?.ports ?? [];

  // Force ReactFlow to recalculate handle positions when ports change
  useEffect(() => { updateNodeInternals(nodeId); }, [ports.length, nodeId, updateNodeInternals]);

  const inputs = [
    ...ports.map(p => {
      const idx = p.id.indexOf('__');
      return { id: idx >= 0 ? p.id.slice(idx + 2) : p.id, color: idx >= 0 ? p.id.slice(0, idx) : 'any' };
    }),
    { id: 'DYNAMIC_NEW_HANDLE', color: 'any' },
  ];
  return (
    <BaseNode title="Group Output" icon={LogOut} selected={selected} data={data} inputs={inputs} outputs={[]}>
      {ports.length === 0 && <div className="text-[8px] text-gray-600 italic text-center">connect outputs →</div>}
    </BaseNode>
  );
});



export const TeleportNode = memo(({ data, selected }: any) => {
  const { customBg } = useNodeColor();
  const nodeId = useNodeId();
  const updateNodeInternals = useUpdateNodeInternals();

  const sourceOutputs: Array<{ id: string; color: string; label?: string }> =
    data?.source_outputs ?? [];
  const label: string = data?.label ?? 'Téléport';
  const isBroken = !data?.params?.source_id;
  const isMinified = !!(data as any)?.minified;

  const START_Y = 40;
  const STEP = 28;

  useEffect(() => { if (nodeId) updateNodeInternals(nodeId); }, [nodeId, updateNodeInternals]);

  const borderColor = isBroken
    ? '#ef4444'
    : selected
    ? '#60a5fa'
    : customBg ?? '#60a5fa55';

  return (
    <div
      style={{
        minWidth: 160,
        opacity: 0.72,
        position: 'relative',
        borderRadius: 12,
        border: `2px dashed ${borderColor}`,
        background: customBg ? `${customBg}22` : '#1e2a3a99',
        boxShadow: selected ? `0 0 18px ${borderColor}55` : 'none',
        backdropFilter: 'blur(6px)',
        transition: 'box-shadow 0.2s, opacity 0.2s',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '7px 10px 5px', borderBottom: '1px solid rgba(255,255,255,0.07)',
        }}
      >
        <Zap size={11} color="#60a5fa" style={{ flexShrink: 0 }} />
        <span style={{
          fontSize: 10, fontWeight: 700, color: '#cbd5e1',
          flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {label}
        </span>
        <span style={{ fontSize: 8, color: '#60a5fa99', fontFamily: 'monospace', flexShrink: 0 }}>
          ⚡TP
        </span>
      </div>

      {/* Output rows — hidden when minified */}
      {!isMinified && <div style={{ padding: '4px 0 6px' }}>
        {isBroken ? (
          <div style={{ fontSize: 9, color: '#f87171', padding: '4px 10px', fontStyle: 'italic' }}>
            Source introuvable
          </div>
        ) : sourceOutputs.length === 0 ? (
          <div style={{ fontSize: 9, color: '#64748b', padding: '4px 10px', fontStyle: 'italic' }}>
            Aucune sortie
          </div>
        ) : (
          sourceOutputs.map((out, i) => (
            <div
              key={out.id}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
                padding: '1px 14px 1px 10px', height: STEP,
              }}
            >
              <span style={{ fontSize: 9, color: '#94a3b8', marginRight: 6 }}>
                {out.label ?? out.id}
              </span>
              <StyledHandle
                type="source"
                id={out.id}
                color={out.color as any}
                position={Position.Right}
                top={`${START_Y + i * STEP}px`}
              />
            </div>
          ))
        )}
      </div>}
    </div>
  );
});

