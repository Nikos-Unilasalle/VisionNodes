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

export const MLDfStatsNodeUI = ({ data, selected }: { data: any; selected: boolean }) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const [expanded, setExpanded] = React.useState(false);

  const sd   = (nd as any)?.stats_data || {};
  const mode = sd.mode as string | undefined;
  const shape: [number, number] | undefined = sd.shape;
  const hasData = !!mode;

  const fmt = (v: any, dec = 3): string => {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'number') return Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : v.toFixed(dec);
    return String(v);
  };

  // ── describe mode metrics ─────────────────────────────────────────────────
  const descStats = sd.stats as Record<string, Record<string, number>> | undefined;
  const numCols = descStats ? Object.keys(descStats).slice(0, expanded ? 8 : 4) : [];

  // ── dtypes mode ───────────────────────────────────────────────────────────
  const colInfo = sd.columns as Array<{name: string; dtype: string; nulls: number; null_pct: number}> | undefined;

  // ── value_counts mode ─────────────────────────────────────────────────────
  const vcCounts = sd.counts as Array<{value: string; count: number; pct: number}> | undefined;
  const vcMax = vcCounts ? Math.max(...vcCounts.map(c => c.count)) : 1;

  const dtypeColor = (dtype: string) =>
    dtype.startsWith('int') || dtype.startsWith('float') ? 'text-blue-400' :
    dtype.startsWith('bool') ? 'text-emerald-400' :
    dtype.startsWith('object') || dtype.startsWith('str') ? 'text-amber-400' :
    'text-gray-400';

  return (
    <BaseNode title="DF Stats" icon={BarChart2} selected={selected} data={data} color="orange"
      inputs={[{id: 'table', color: 'data', label: 'DataFrame'}]}
      outputs={[{id: 'preview', color: 'image', label: 'Stats'}, {id: 'stats_data', color: 'dict', label: 'Stats dict'}]}
      width={expanded ? '38rem' : '18rem'}>
      <div className="flex flex-col gap-2 mt-2 w-full">

        {/* Shape header */}
        {shape && (
          <div className="p-2 rounded-xl border border-white/5 bg-orange-500/5 flex items-center justify-between">
            <span className="text-[7px] text-orange-400/70 uppercase font-black tracking-widest">Shape</span>
            <span className="text-[13px] font-black font-mono text-orange-300">
              {shape[0].toLocaleString()} × {shape[1]}
            </span>
          </div>
        )}

        {/* Mode-specific content */}
        {mode === 'describe' && descStats && numCols.length > 0 && (
          <div className="p-2 rounded-xl border border-white/5 bg-white/3">
            <div className="text-[7px] text-gray-500 uppercase font-black mb-2 tracking-widest">Statistiques</div>
            {expanded ? (
              /* table header */
              <div>
                <div className="grid text-[7px] text-gray-600 font-black uppercase tracking-wider pb-1 border-b border-white/5 mb-1"
                  style={{ gridTemplateColumns: '1fr repeat(4, auto)' }}>
                  <span>Col</span>
                  <span className="text-right text-blue-400 w-14">Mean</span>
                  <span className="text-right text-orange-400 w-12">Std</span>
                  <span className="text-right w-14">Min</span>
                  <span className="text-right w-14">Max</span>
                </div>
                {numCols.map(col => {
                  const s = descStats[col];
                  return (
                    <div key={col} className="grid items-center text-[9px] py-0.5"
                      style={{ gridTemplateColumns: '1fr repeat(4, auto)' }}>
                      <span className="text-gray-300 font-medium truncate">{col}</span>
                      <span className="text-right font-mono text-blue-300 w-14">{fmt(s?.mean)}</span>
                      <span className="text-right font-mono text-orange-300 w-12">{fmt(s?.std)}</span>
                      <span className="text-right font-mono text-gray-400 w-14">{fmt(s?.min)}</span>
                      <span className="text-right font-mono text-gray-400 w-14">{fmt(s?.max)}</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              /* compact: mean ± std pill per col */
              <div className="space-y-1">
                {numCols.map(col => {
                  const s = descStats[col];
                  return (
                    <div key={col} className="flex items-center gap-2">
                      <span className="text-[8px] text-gray-400 w-20 truncate shrink-0">{col}</span>
                      <span className="text-[8px] font-mono text-blue-300 shrink-0">{fmt(s?.mean)}</span>
                      <span className="text-[7px] text-gray-600 shrink-0">±{fmt(s?.std, 2)}</span>
                      <span className="text-[7px] text-gray-600 ml-auto shrink-0">[{fmt(s?.min, 1)}, {fmt(s?.max, 1)}]</span>
                    </div>
                  );
                })}
                {Object.keys(descStats).length > 4 && (
                  <div className="text-[7px] text-gray-600 italic">+{Object.keys(descStats).length - 4} colonnes…</div>
                )}
              </div>
            )}
          </div>
        )}

        {mode === 'dtypes' && colInfo && (
          <div className="p-2 rounded-xl border border-white/5 bg-white/3">
            <div className="text-[7px] text-gray-500 uppercase font-black mb-1.5 tracking-widest">Colonnes</div>
            <div className="space-y-1">
              {(expanded ? colInfo : colInfo.slice(0, 6)).map(col => (
                <div key={col.name} className="flex items-center gap-2 text-[9px]">
                  <span className="text-gray-300 truncate flex-1">{col.name}</span>
                  <span className={`font-mono text-[8px] ${dtypeColor(col.dtype)} shrink-0`}>{col.dtype}</span>
                  {col.nulls > 0 && (
                    <span className="text-[7px] text-red-400 font-mono shrink-0">{col.null_pct}% null</span>
                  )}
                </div>
              ))}
              {!expanded && colInfo.length > 6 && (
                <div className="text-[7px] text-gray-600 italic">+{colInfo.length - 6} colonnes…</div>
              )}
            </div>
          </div>
        )}

        {mode === 'value_counts' && vcCounts && (
          <div className="p-2 rounded-xl border border-white/5 bg-white/3">
            <div className="text-[7px] text-gray-500 uppercase font-black mb-1.5 tracking-widest">
              {sd.column ? `value_counts(${sd.column})` : 'Fréquences'}
            </div>
            <div className="space-y-1">
              {(expanded ? vcCounts : vcCounts.slice(0, 6)).map(item => (
                <div key={item.value} className="flex items-center gap-2">
                  <span className="text-[8px] text-gray-400 w-20 truncate shrink-0">{item.value}</span>
                  <div className="flex-1 h-1 bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full rounded-full bg-blue-400 opacity-70"
                      style={{ width: `${(item.count / vcMax) * 100}%` }} />
                  </div>
                  <span className="text-[8px] font-mono text-blue-300 w-8 text-right shrink-0">{item.pct}%</span>
                </div>
              ))}
              {!expanded && vcCounts.length > 6 && (
                <div className="text-[7px] text-gray-600 italic">+{vcCounts.length - 6} valeurs…</div>
              )}
            </div>
          </div>
        )}

        {mode === 'head' && sd.columns && (
          <div className="p-2 rounded-xl border border-white/5 bg-white/3">
            <div className="text-[7px] text-gray-500 uppercase font-black mb-1.5 tracking-widest">Colonnes</div>
            <div className="flex flex-wrap gap-1">
              {(sd.columns as string[]).slice(0, expanded ? 30 : 10).map((col: string) => (
                <span key={col} className="text-[7px] bg-white/5 border border-white/10 rounded px-1.5 py-0.5 text-gray-300">{col}</span>
              ))}
              {(sd.columns as string[]).length > (expanded ? 30 : 10) && (
                <span className="text-[7px] text-gray-600 italic self-center">+{(sd.columns as string[]).length - (expanded ? 30 : 10)}</span>
              )}
            </div>
          </div>
        )}

        {!hasData && (
          <div className="text-[8px] text-gray-600 italic px-1">En attente de données…</div>
        )}

        <button
          onClick={() => setExpanded(e => !e)}
          className="w-full py-1.5 rounded-xl bg-white/5 border border-white/10 text-[8px] font-black uppercase tracking-widest text-gray-400 hover:bg-orange-500/20 hover:text-orange-300 hover:border-orange-500/30 transition-all flex items-center justify-center gap-1.5"
        >
          {expanded ? 'Vue compacte' : 'Vue complète'}
          <BarChart2 size={9} />
        </button>
      </div>
    </BaseNode>
  );
};


export const MLClassifierNodeUI = ({ data, selected }: { data: any; selected: boolean }) => {
  const nodeId = useNodeId();
  const nd = useNodeData(nodeId);
  const [expanded, setExpanded] = React.useState(false);

  const schema = data.schema || {};
  const NodeIcon = getIcon(schema.icon, Activity);
  const title = schema.label || 'Classifier';
  const inputs = schema.inputs || [];
  const outputs = schema.outputs || [];

  const accuracy   = (nd as any)?.accuracy   ?? null;
  const trainAcc   = (nd as any)?.train_acc   ?? null;
  const reportData = (nd as any)?.report_data || {};
  const classes    = Object.keys(reportData).filter(k => !['accuracy', 'macro avg', 'weighted avg'].includes(k));
  const hasData    = accuracy !== null;

  const fmtPct = (v: any) => typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—';
  const accColor = (v: number | null) =>
    v === null ? 'text-gray-500' : v >= 0.9 ? 'text-emerald-400' : v >= 0.7 ? 'text-amber-400' : 'text-red-400';

  return (
    <BaseNode title={title} icon={NodeIcon} selected={selected} data={data} color="violet"
      inputs={inputs} outputs={outputs} width={expanded ? '36rem' : '18rem'}>
      <div className="flex flex-col gap-2 mt-2 w-full">
        {/* Accuracy header */}
        <div className="p-2 rounded-xl border border-white/5 bg-violet-500/5">
          <div className="text-[7px] text-violet-400/70 uppercase font-black mb-1.5 tracking-widest">Performances</div>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col">
              <span className="text-[8px] text-gray-500">Test acc</span>
              <span className={`text-[15px] font-black font-mono ${accColor(accuracy)}`}>{fmtPct(accuracy)}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-[8px] text-gray-500">Train acc</span>
              <span className="text-[15px] font-black font-mono text-blue-400">{fmtPct(trainAcc)}</span>
            </div>
          </div>
        </div>

        {/* Per-class metrics */}
        {classes.length > 0 && (
          expanded ? (
            <div className="p-2 rounded-xl border border-white/5 bg-white/3">
              <div className="text-[7px] text-gray-500 uppercase font-black mb-2 tracking-widest">Par classe</div>
              <div className="grid grid-cols-5 text-[7px] text-gray-600 font-black uppercase tracking-wider pb-1 border-b border-white/5 mb-1">
                <span className="col-span-2">Classe</span>
                <span className="text-center">Prec</span>
                <span className="text-center">Recall</span>
                <span className="text-center">F1</span>
              </div>
              {classes.map((cls, i) => {
                const d = reportData[cls] || {};
                const f1 = d['f1-score'] ?? 0;
                const f1c = f1 >= 0.9 ? 'text-emerald-400' : f1 >= 0.7 ? 'text-amber-400' : 'text-red-400';
                return (
                  <div key={cls} className={`grid grid-cols-5 items-center text-[9px] py-0.5 rounded ${i % 2 === 0 ? 'bg-white/2' : ''}`}>
                    <span className="col-span-2 text-gray-300 font-medium truncate">{cls}</span>
                    <span className="text-center font-mono text-blue-300">{((d.precision ?? 0) * 100).toFixed(0)}%</span>
                    <span className="text-center font-mono text-purple-300">{((d.recall ?? 0) * 100).toFixed(0)}%</span>
                    <span className={`text-center font-mono font-bold ${f1c}`}>{(f1 * 100).toFixed(0)}%</span>
                  </div>
                );
              })}
              {reportData['weighted avg'] && (() => {
                const d = reportData['weighted avg'];
                return (
                  <div className="grid grid-cols-5 items-center text-[9px] py-0.5 pt-1 border-t border-white/5 mt-1">
                    <span className="col-span-2 text-gray-500 italic">w. avg</span>
                    <span className="text-center font-mono text-gray-400">{((d.precision ?? 0) * 100).toFixed(0)}%</span>
                    <span className="text-center font-mono text-gray-400">{((d.recall ?? 0) * 100).toFixed(0)}%</span>
                    <span className="text-center font-mono font-bold text-gray-300">{((d['f1-score'] ?? 0) * 100).toFixed(0)}%</span>
                  </div>
                );
              })()}
            </div>
          ) : (
            <div className="p-2 rounded-xl border border-white/5 bg-white/3">
              <div className="text-[7px] text-gray-500 uppercase font-black mb-1.5 tracking-widest">F1 par classe</div>
              <div className="space-y-1">
                {classes.slice(0, 5).map(cls => {
                  const d = reportData[cls] || {};
                  const f1 = d['f1-score'] ?? 0;
                  const f1c = f1 >= 0.9 ? 'text-emerald-400' : f1 >= 0.7 ? 'text-amber-400' : 'text-red-400';
                  const bgc  = f1 >= 0.9 ? 'bg-emerald-400' : f1 >= 0.7 ? 'bg-amber-400' : 'bg-red-400';
                  return (
                    <div key={cls} className="flex items-center gap-2">
                      <span className="text-[8px] text-gray-400 w-20 truncate shrink-0">{cls}</span>
                      <div className="flex-1 h-1 bg-white/5 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${bgc} opacity-70`} style={{ width: `${f1 * 100}%` }} />
                      </div>
                      <span className={`text-[8px] font-mono font-bold ${f1c} w-8 text-right`}>{(f1 * 100).toFixed(0)}%</span>
                    </div>
                  );
                })}
                {classes.length > 5 && (
                  <div className="text-[7px] text-gray-600 italic pl-1">+{classes.length - 5} classes…</div>
                )}
              </div>
            </div>
          )
        )}

        {!hasData && (
          <div className="text-[8px] text-gray-600 italic px-1">En attente de données…</div>
        )}

        <button
          onClick={() => setExpanded(e => !e)}
          className="w-full py-1.5 rounded-xl bg-white/5 border border-white/10 text-[8px] font-black uppercase tracking-widest text-gray-400 hover:bg-violet-500/20 hover:text-violet-300 hover:border-violet-500/30 transition-all flex items-center justify-center gap-1.5"
        >
          {expanded ? 'Vue compacte' : 'Rapport complet'}
          <BarChart2 size={9} />
        </button>
      </div>
    </BaseNode>
  );
};

// ── Raster Colorizer ─────────────────────────────────────────────────────────
