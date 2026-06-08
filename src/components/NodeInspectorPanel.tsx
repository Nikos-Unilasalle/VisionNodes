import React, { useRef, useState, useEffect } from 'react';
import { Pause, Play, Pipette, Save, Activity, Calculator, ChevronDown, Eye, EyeOff, FolderOpen, Pencil, Check, Maximize2, PlugZap } from 'lucide-react';
import { save as tauriSaveDialog } from '@tauri-apps/plugin-dialog';
import { PALETTES } from './Nodes';
import type { ParamSpec, NodeData, VNNode } from '../types/NodeSchema';
import { HexColorPicker } from 'react-colorful';
import { MarkdownToolbar } from './MarkdownToolbar';
const PythonEditorModal = React.lazy(() =>
  import('./PythonEditorModal').then(m => ({ default: m.PythonEditorModal }))
);

const FLOW_PRESETS: Record<number, Record<string, number>> = {
  0: { pyr_scale: 0.5, levels: 3, winsize: 15, iterations: 3, poly_n: 5, poly_sigma: 1.2 },
  1: { pyr_scale: 0.5, levels: 5, winsize: 31, iterations: 7, poly_n: 7, poly_sigma: 1.5 },
  2: { pyr_scale: 0.5, levels: 2, winsize: 7, iterations: 3, poly_n: 5, poly_sigma: 1.1 },
  3: { pyr_scale: 0.5, levels: 5, winsize: 25, iterations: 5, poly_n: 7, poly_sigma: 1.5 },
  4: { pyr_scale: 0.5, levels: 2, winsize: 10, iterations: 2, poly_n: 5, poly_sigma: 1.1 },
};

// ── Form primitives ────────────────────────────────────────────────────────

interface SliderProps { label: string; val: number; min: number; max: number; step?: number; onChange: (v: number) => void; }
export const Slider = ({ label, val, min, max, step = 1, onChange }: SliderProps) => (
  <div className="space-y-4 group">
    <div className="flex justify-between items-center text-[10px]">
      <label className="text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
      <input
        type="number"
        min={min} max={max} step={step} value={val}
        onChange={(e) => { const v = parseFloat(e.target.value); if (!isNaN(v)) onChange(v); }}
        className="bg-black/40 border border-[#4f5b6b] rounded-lg px-3 py-2 text-accent font-black font-mono text-center w-32 outline-none focus:border-accent/60 transition-all text-[13px] shadow-inner"
      />
    </div>
    <input type="range" min={min} max={max} step={step} value={val} onChange={(e) => onChange(parseFloat(e.target.value))} className="w-full h-1 bg-[#4f5b6b]/40 rounded-full appearance-none cursor-pointer accent-accent transition-all hover:bg-[#4f5b6b]/60" />
  </div>
);

interface TextInputProps { label: string; val: string; onChange: (v: string) => void; }
export const TextInput = ({ label, val, onChange }: TextInputProps) => (
  <div className="space-y-4 group">
    <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
    <input
      type="text" value={val} onChange={(e) => onChange(e.target.value)}
      onKeyDown={(e) => e.stopPropagation()}
      className="w-full bg-black/20 border border-[#4f5b6b] group-hover:border-accent/40 rounded-xl px-4 py-2 text-[11px] text-white outline-none focus:border-accent transition-all"
      placeholder={`Enter ${label.toLowerCase()}...`}
    />
  </div>
);

interface FilePathInputProps { label: string; val: string; onChange: (v: string) => void; filters?: { name: string; extensions: string[] }[]; }
export const FilePathInput = ({ label, val, onChange, filters }: FilePathInputProps) => {
  const browse = async () => {
    const chosen = await tauriSaveDialog({ defaultPath: val || undefined, filters });
    if (chosen) onChange(chosen);
  };
  return (
    <div className="space-y-4 group">
      <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
      <div className="flex gap-2">
        <input
          type="text" value={val} onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => e.stopPropagation()}
          className="flex-1 bg-black/20 border border-[#4f5b6b] group-hover:border-accent/40 rounded-xl px-4 py-2 text-[11px] text-white outline-none focus:border-accent transition-all"
          placeholder={`Enter ${label.toLowerCase()}...`}
        />
        <button
          onClick={browse}
          className="shrink-0 bg-black/20 border border-[#4f5b6b] hover:border-accent/60 hover:bg-accent/10 rounded-xl px-3 py-2 text-gray-400 hover:text-accent transition-all"
          title="Browse…"
        >
          <FolderOpen size={14} />
        </button>
      </div>
    </div>
  );
};

interface NumberInputProps { label: string; val: number; onChange: (v: number) => void; }
export const NumberInput = ({ label, val, onChange }: NumberInputProps) => {
  const [tempVal, setTempVal] = useState(val.toString());
  
  // Sync local state when external value changes
  useEffect(() => {
    if (parseFloat(tempVal) !== val) {
      setTempVal(val.toString());
    }
  }, [val]);

  const handleChange = (s: string) => {
    const normalized = s.replace(/,/g, '.');
    setTempVal(normalized);
    if (normalized === '' || normalized === '-' || normalized === '.') {
      return;
    }
    const parsed = parseFloat(normalized);
    if (!isNaN(parsed)) {
      onChange(parsed);
    }
  };

  const handleBlur = () => {
    if (tempVal === '' || tempVal === '-' || tempVal === '.') {
      setTempVal(val.toString());
    }
  };

  return (
    <div className="space-y-4 group">
      <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
      <input
        type="text" value={tempVal} onChange={(e) => handleChange(e.target.value)}
        onBlur={handleBlur}
        onKeyDown={(e) => e.stopPropagation()}
        className="w-full bg-black/40 border border-[#4f5b6b] group-hover:border-accent/40 rounded-xl px-4 py-3 text-[13px] text-white outline-none focus:border-accent transition-all font-mono shadow-inner"
      />
    </div>
  );
};

interface DateInputProps { label: string; val: string; onChange: (v: string) => void; }
export const DateInput = ({ label, val, onChange }: DateInputProps) => (
  <div className="space-y-4 group">
    <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
    <input
      type="date" value={val} onChange={(e) => onChange(e.target.value)}
      onKeyDown={(e) => e.stopPropagation()}
      className="w-full bg-black/40 border border-[#4f5b6b] group-hover:border-accent/40 rounded-xl px-4 py-3 text-[13px] text-white outline-none focus:border-accent transition-all cursor-pointer font-mono shadow-inner"
    />
  </div>
);

interface SelectInputProps { label: string; val: any; options: (string | { label: string; value: any })[]; onChange: (v: any) => void; }
export const SelectInput = ({ label, val, options, onChange }: SelectInputProps) => (
  <div className="space-y-4 group">
    <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
    <div className="relative">
      <select
        value={val} onChange={(e) => {
          const v = e.target.value;
          onChange(isNaN(Number(v)) ? v : Number(v));
        }}
        className="w-full bg-black/20 border border-[#4f5b6b] group-hover:border-accent/40 rounded-xl px-4 py-3 text-[12px] text-white outline-none focus:border-accent transition-all appearance-none cursor-pointer font-bold"
      >
        {options.map((opt: any, i: number) => {
          const isObj = typeof opt === 'object';
          const l = isObj ? opt.label : opt;
          const v = isObj ? opt.value : i;
          return <option key={i} value={v} className="bg-[#3d4452]">{l}</option>;
        })}
      </select>
      <ChevronDown size={14} className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
    </div>
  </div>
);

interface ToggleInputProps { label: string; val: boolean; onChange: (v: boolean) => void; }
export const ToggleInput = ({ label, val, onChange }: ToggleInputProps) => (
  <div className="flex items-center justify-between py-2 group">
    <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
    <button
      onClick={() => onChange(!val)}
      className={`w-10 h-5 rounded-full transition-all duration-300 relative ${val ? 'bg-accent shadow-[0_0_10px_rgba(var(--color-accent),0.3)]' : 'bg-[#3d4452]'}`}
    >
      <div className={`absolute top-1 w-3 h-3 rounded-full bg-white transition-all duration-300 ${val ? 'left-6' : 'left-1'}`} />
    </button>
  </div>
);

// ── Python syntax highlighter ──────────────────────────────────────────────

const highlightPython = (code: string): string => {
  const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const tokens = [
    { name: 'comment',   regex: /#.*/,                                                                                                                                                      color: '#6b7280', italic: true },
    { name: 'string',    regex: /(['"])(?:(?!\1|\\).|\\.)*\1/,                                                                                                                              color: '#a7f3d0' },
    { name: 'keyword',   regex: /\b(def|class|return|if|elif|else|for|while|in|not|and|or|import|from|as|pass|break|continue|try|except|finally|with|yield|lambda|global|nonlocal|raise|del|assert|True|False|None)\b/, color: '#c084fc', bold: true },
    { name: 'builtin',   regex: /\b(print|len|range|list|dict|set|tuple|int|float|str|bool|type|isinstance|enumerate|zip|map|filter|sorted|reversed|min|max|sum|abs|round|open|input|super)\b/, color: '#60a5fa' },
    { name: 'state',     regex: /\b(self|state)\b/,                                                                                                                                        color: '#f472b6' },
    { name: 'decorator', regex: /@\w+/,                                                                                                                                                     color: '#f472b6' },
    { name: 'number',    regex: /\b\d+\.?\d*/,                                                                                                                                              color: '#fb923c' },
    { name: 'operator',  regex: /[=+\-*/%&|^<>!]+/,                                                                                                                                        color: '#06b6d4' },
  ];
  const processLine = (line: string) => {
    let result = ''; let pos = 0;
    while (pos < line.length) {
      let match = null; let bestToken = null;
      for (const token of tokens) {
        const m = token.regex.exec(line.slice(pos));
        if (m && m.index === 0) { match = m[0]; bestToken = token; break; }
      }
      if (match && bestToken) {
        const style = `color: ${(bestToken as any).color};${(bestToken as any).italic ? ' font-style: italic;' : ''}${(bestToken as any).bold ? ' font-weight: 600;' : ''}`;
        result += `<span style="${style}">${esc(match)}</span>`;
        pos += match.length;
      } else {
        result += esc(line[pos]); pos++;
      }
    }
    return result;
  };
  return code.split('\n').map(processLine).join('\n');
};

interface CodeInputProps { label: string; val: string; onChange: (v: string) => void; liveError?: string; }
const CODE_GUTTER = 32;  // px — matches w-8
const CODE_PAD_Y  = 12;  // px — matches py-3
const CODE_PAD_R  = 16;  // px — matches pr-4
const CODE_LINE_H = 18;  // px — explicit so textarea & highlight stay in sync
const CODE_FONT   = 11;  // px

const codeAreaStyle: React.CSSProperties = {
  paddingTop:    CODE_PAD_Y,
  paddingBottom: CODE_PAD_Y,
  paddingLeft:   CODE_GUTTER,
  paddingRight:  CODE_PAD_R,
  lineHeight:    `${CODE_LINE_H}px`,
  fontSize:      `${CODE_FONT}px`,
  fontFamily:    'ui-monospace, SFMono-Regular, Menlo, monospace',
};

export const CodeInput = ({ label, val, onChange, liveError }: CodeInputProps) => {
  const [modalOpen, setModalOpen] = useState(false);

  // Preview: first 8 lines
  const previewLines = (val || '').split('\n').slice(0, 8);
  const totalLines   = (val || '').split('\n').length;
  const hasMore      = totalLines > 8;
  const hasError     = !!liveError;

  return (
    <div className="space-y-2">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black">{label}</label>
        <div className="flex items-center gap-1.5">
          {hasError && (
            <span className="text-[8px] text-red-400 bg-red-950/60 border border-red-900/40 px-2 py-0.5 rounded truncate max-w-[140px]" title={liveError}>
              Error
            </span>
          )}
          <span className="text-[8px] font-mono text-gray-600 bg-white/10 px-2 py-0.5 rounded">Python 3.x</span>
          <button
            onClick={() => setModalOpen(true)}
            className="flex items-center gap-1 text-[9px] text-gray-400 hover:text-accent bg-white/5 hover:bg-accent/10 border border-white/10 hover:border-accent/40 px-2 py-1 rounded transition-all duration-200"
            title="Open full-screen editor"
          >
            <Maximize2 size={10} />
            <span>Open</span>
          </button>
        </div>
      </div>

      {/* ── Code preview ───────────────────────────────────────────────── */}
      <div
        className={`relative rounded-xl overflow-hidden border transition-all shadow-inner bg-[#1e2530] cursor-pointer hover:border-accent/40 ${
          hasError ? 'border-red-900/50' : 'border-[#4f5b6b]'
        }`}
        onClick={() => setModalOpen(true)}
        title="Click to open editor"
      >
        {/* Line numbers */}
        <div
          className="absolute inset-y-0 left-0 bg-black/15 border-r border-white/5 flex flex-col items-center text-gray-600 select-none pointer-events-none z-10 overflow-hidden"
          style={{ width: CODE_GUTTER, paddingTop: CODE_PAD_Y, paddingBottom: CODE_PAD_Y, fontSize: 8, fontFamily: codeAreaStyle.fontFamily }}
        >
          {previewLines.map((_, i) => (
            <div key={i} style={{ height: CODE_LINE_H, lineHeight: `${CODE_LINE_H}px` }} className="flex items-center">{i + 1}</div>
          ))}
        </div>
        {/* Highlighted preview */}
        <div
          aria-hidden="true"
          className="overflow-hidden pointer-events-none whitespace-pre select-none"
          style={{ ...codeAreaStyle, paddingBottom: hasMore ? 0 : CODE_PAD_Y }}
          dangerouslySetInnerHTML={{ __html: previewLines.map(l => highlightPython(l)).join('\n') }}
        />
        {/* "N more lines" fade */}
        {hasMore && (
          <div className="flex items-end justify-center h-8 bg-gradient-to-t from-[#1e2530] to-transparent">
            <span className="text-[8px] text-gray-600 pb-1">{totalLines - 8} more lines…</span>
          </div>
        )}
      </div>

      {/* ── Error detail ───────────────────────────────────────────────── */}
      {hasError && (
        <div className="text-[8px] text-red-400 bg-red-950/30 border border-red-900/30 rounded-lg px-3 py-2 font-mono break-all">
          {liveError}
        </div>
      )}

      {/* ── Modal (lazy-loaded chunk — Monaco only loads on first open) ── */}
      {modalOpen && (
        <React.Suspense fallback={null}>
          <PythonEditorModal
            label={label}
            value={val}
            liveError={liveError}
            onChange={onChange}
            onClose={() => setModalOpen(false)}
          />
        </React.Suspense>
      )}
    </div>
  );
};

interface ColorInputProps { 
  label: string; 
  val: string; 
  onChange: (v: string) => void; 
  nodeId?: string;
  onPickColorToggle?: (id: string | null) => void;
  isPicking?: boolean;
}
export const ColorInput = ({ label, val, onChange, nodeId, onPickColorToggle, isPicking }: ColorInputProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [openUp, setOpenUp] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const swatchRef = useRef<HTMLButtonElement>(null);
  const currentVal = (val || '#ffffff').toUpperCase();

  // Popover height ~290px. Flip above the swatch if not enough room below.
  const POPOVER_H = 300;
  const togglePicker = () => {
    if (!isOpen && swatchRef.current) {
      const rect = swatchRef.current.getBoundingClientRect();
      setOpenUp(window.innerHeight - rect.bottom < POPOVER_H);
    }
    setIsOpen(v => !v);
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  return (
    <div className="flex items-center justify-between py-2 group" ref={containerRef}>
      <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
      <div className="flex items-center gap-3 relative">
        <div className="text-[10px] font-mono text-gray-500">{currentVal}</div>
        {onPickColorToggle && nodeId && (
          <button
            onClick={() => onPickColorToggle(isPicking ? null : nodeId)}
            className={`p-1.5 rounded-md transition-all ${isPicking ? 'bg-accent text-white shadow-[0_0_10px_rgba(var(--color-accent),0.5)]' : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}
            title="Pick color from preview"
          >
            <Pipette size={14} />
          </button>
        )}
        <button
          ref={swatchRef}
          onClick={togglePicker}
          className="relative w-10 h-6 rounded-md border border-white/20 shadow-lg cursor-pointer hover:scale-105 transition-all overflow-hidden"
          style={{ backgroundColor: currentVal }}
        />

        {isOpen && (
          <div className={`absolute right-0 ${openUp ? 'bottom-full mb-2' : 'top-full mt-2'} z-[100] p-4 bg-[#1e2530] border border-white/10 rounded-2xl shadow-2xl space-y-3`}>
            <div className="custom-color-wheel">
              <HexColorPicker color={currentVal} onChange={(newColor) => onChange(newColor.toUpperCase())} />
            </div>
            <div className="flex items-center gap-2 pt-2 border-t border-white/5">
              <div className="w-4 h-4 rounded-full border border-white/10" style={{ backgroundColor: currentVal }} />
              <input 
                type="text" 
                value={currentVal} 
                onChange={(e) => onChange(e.target.value.toUpperCase())}
                className="bg-black/20 border border-white/5 rounded px-2 py-1 text-[10px] font-mono text-gray-300 w-20 outline-none focus:border-accent/50"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ── Main panel ─────────────────────────────────────────────────────────────

export interface ExposedParam {
  nodeId: string;
  nodeLabel: string;
  paramId: string;
  paramSpec: ParamSpec;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  currentValue: any;
  customLabel?: string;
}

interface NodeInspectorPanelProps {
  node: VNNode;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  liveData: Record<string, any>;
  activePaletteIndex: number;
  pickColorNodeId: string | null;
  onUpdateParams: (id: string, params: Record<string, unknown>) => void;
  onPickColorToggle: (id: string | null) => void;
  onRequestCapture: (id: string) => void;
  isInsideGroup?: boolean;
  onToggleExposed?: (nodeId: string, paramId: string) => void;
  onExternalizeParam?: (nodeId: string, sp: ParamSpec, value: any) => void;
  onSetNodeLabel?: (nodeId: string, label: string) => void;
  exposedGroupParams?: ExposedParam[];
  onUpdateGroupChildParams?: (childNodeId: string, params: Record<string, unknown>) => void;
  onRenameExposedParam?: (childNodeId: string, paramId: string, newLabel: string) => void;
}

export const NodeInspectorPanel: React.FC<NodeInspectorPanelProps> = ({
  node, liveData, activePaletteIndex,
  pickColorNodeId, onUpdateParams, onPickColorToggle, onRequestCapture,
  isInsideGroup, onToggleExposed, onExternalizeParam, onSetNodeLabel, exposedGroupParams, onUpdateGroupChildParams,
  onRenameExposedParam,
}) => {
  const p = node.data.params;
  const up = (params: Record<string, unknown>) => onUpdateParams(node.id, params);
  const [editingLabel, setEditingLabel] = useState<{ nodeId: string; paramId: string; value: string } | null>(null);
  const [collapsedSlots, setCollapsedSlots] = useState<Set<string>>(new Set());
  const noteTextareaRef = useRef<HTMLTextAreaElement>(null);

  const toggleSlot = (slot: string) =>
    setCollapsedSlots(prev => { const s = new Set(prev); s.has(slot) ? s.delete(slot) : s.add(slot); return s; });

  // Skip manual types to avoid duplication with schema-driven loop below
  const MANUAL_TYPES = new Set([
    'canvas_note', 'canvas_frame', 'canvas_ribbon',
    'input_webcam', 'input_movie',
    'output_display',
    'geo_spectral_index', 'geo_band_calc',
    'plugin_audio_input', 'plugin_audio_to_spectrogram', 'plugin_audio_waveform',
    'plugin_audio_freq_filter', 'plugin_audio_pitch_shift', 'plugin_audio_time_stretch',
    'plugin_spectrogram_to_audio', 'plugin_audio_export', 'plugin_audio_info',
    'util_landmark_selector',
    'math_vec_to_screen',
  ]);

  return (
    <div className="space-y-8 pb-32">

      {/* Custom node label — overrides the header title (type name moves to the corner) */}
      {onSetNodeLabel && node.type !== 'canvas_note' && node.type !== 'canvas_frame' && (
        <div className="space-y-2 group">
          <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">Label</label>
          <input
            type="text"
            value={(node.data as any).userLabel || ''}
            onChange={e => onSetNodeLabel(node.id, e.target.value)}
            className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-[11px] text-blue-300 font-bold outline-none focus:border-accent/50 transition-all placeholder:text-gray-600 placeholder:font-normal"
            placeholder={node.data.label || node.type}
          />
        </div>
      )}

      {/* group_node — exposed params from child nodes */}
      {node.type === 'group_node' && (
        <div className="space-y-6">
          {(!exposedGroupParams || exposedGroupParams.length === 0) ? (
            <div className="text-center py-12 space-y-3 opacity-40">
              <EyeOff size={28} className="mx-auto text-gray-500" />
              <p className="text-[11px] text-gray-400 font-bold">Aucun paramètre exposé</p>
              <p className="text-[9px] text-gray-600 leading-relaxed">Entrez dans le groupe et cliquez sur<br/>l'icône œil d'un paramètre</p>
            </div>
          ) : (() => {
            const byNode: Record<string, { label: string; params: ExposedParam[] }> = {};
            for (const ep of exposedGroupParams) {
              if (!byNode[ep.nodeId]) byNode[ep.nodeId] = { label: ep.nodeLabel, params: [] };
              byNode[ep.nodeId].params.push(ep);
            }
            return Object.entries(byNode).map(([nid, { label, params }]) => (
              <div key={nid} className="space-y-5">
                <div className="flex items-center gap-2 text-[9px] font-black text-gray-500 uppercase tracking-[0.2em]">
                  <span className="w-2 h-2 rounded-full bg-accent/60 shrink-0" />
                  {label}
                </div>
                {params.map(ep => {
                  const sp = ep.paramSpec;
                  const val = ep.currentValue;
                  const up2 = (v: unknown) => onUpdateGroupChildParams?.(ep.nodeId, { [sp.id]: v });
                  const lbl = ep.customLabel || sp.label || sp.id;
                  const isEditingThis = editingLabel?.nodeId === ep.nodeId && editingLabel?.paramId === ep.paramId;
                  const isE2 = sp.type === 'enum' || sp.options;
                  const isColor2 = sp.type === 'color';
                  const isS2 = sp.type === 'string' || typeof (val ?? sp.default) === 'string';
                  const isN2 = sp.type === 'number' || sp.type === 'float';
                  const isB2 = sp.type === 'toggle' || sp.type === 'bool' || sp.type === 'boolean' || typeof (val ?? sp.default) === 'boolean';

                  const confirmRename = (newVal: string) => {
                    const trimmed = newVal.trim();
                    onRenameExposedParam?.(ep.nodeId, ep.paramId, trimmed || (sp.label ?? ep.paramId));
                    setEditingLabel(null);
                  };

                  let control: React.ReactNode;
                  if (isE2) control = <SelectInput label={lbl} val={Number(val ?? sp.default ?? 0)} options={sp.options || []} onChange={up2} />;
                  else if (isColor2) control = <ColorInput label={lbl} val={String(val ?? sp.default ?? '#ffffff')} onChange={up2} nodeId={ep.nodeId} onPickColorToggle={onPickColorToggle} isPicking={pickColorNodeId === ep.nodeId} />;
                  else if (sp.type === 'file_path') control = <FilePathInput label={lbl} val={String(val ?? sp.default ?? '')} onChange={up2} filters={(sp as any).filters} />;
                  else if (isS2) control = <TextInput label={lbl} val={String(val ?? sp.default ?? '')} onChange={v => up2(v)} />;
                  else if (isN2) {
                    const v2 = Number(val ?? sp.default ?? 0);
                    const min2 = sp.min ?? -10;
                    const max2 = sp.max ?? (v2 > 100 ? v2 * 2 : 100);
                    control = <Slider label={lbl} val={v2} min={min2} max={max2} step={sp.step || (sp.type === 'float' ? 0.01 : 1)} onChange={up2} />;
                  } else if (isB2) {
                    control = <ToggleInput label={lbl} val={!!(val ?? sp.default)} onChange={up2} />;
                  } else {
                    control = <Slider label={lbl} val={Number(val ?? sp.default ?? 0)} min={sp.min || 0} max={sp.max || 100} step={sp.step || 1} onChange={up2} />;
                  }

                  return (
                    <div key={ep.paramId} className="relative group/ep">
                      {control}
                      {/* Inline label rename — pencil appears on hover */}
                      {isEditingThis ? (
                        <div className="absolute top-0 left-0 right-0 z-20 flex items-center gap-1.5 bg-[#2a2f3a] border border-accent/40 rounded-lg px-2 py-1.5 shadow-xl">
                          <input
                            autoFocus
                            className="flex-1 bg-transparent text-accent text-[10px] uppercase tracking-widest outline-none font-black min-w-0"
                            value={editingLabel.value}
                            onChange={e => setEditingLabel({ ...editingLabel, value: e.target.value })}
                            onBlur={() => confirmRename(editingLabel.value)}
                            onKeyDown={e => {
                              e.stopPropagation();
                              if (e.key === 'Enter') confirmRename(editingLabel.value);
                              if (e.key === 'Escape') setEditingLabel(null);
                            }}
                          />
                          <button
                            onMouseDown={e => { e.preventDefault(); confirmRename(editingLabel.value); }}
                            className="text-accent/60 hover:text-accent shrink-0"
                          >
                            <Check size={11} />
                          </button>
                        </div>
                      ) : (
                        <button
                          title="Rename label"
                          className="absolute top-0 right-0 z-10 opacity-0 group-hover/ep:opacity-40 hover:!opacity-100 text-accent transition-opacity p-0.5"
                          onClick={() => setEditingLabel({ nodeId: ep.nodeId, paramId: ep.paramId, value: lbl })}
                        >
                          <Pencil size={9} />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            ));
          })()}
        </div>
      )}

      {/* canvas_note / canvas_frame */}
      {(node.type === 'canvas_note' || node.type === 'canvas_frame') && (() => {
        const currentPalette = PALETTES[activePaletteIndex].colors;
        const cIdx = p.color_index;
        const bgColor  = cIdx !== undefined ? currentPalette[cIdx % 5].bg   : (p.bg_color   || (node.type === 'canvas_frame' ? '#333333' : '#ffd4b8'));
        const textColor = cIdx !== undefined ? currentPalette[cIdx % 5].dark : (p.text_color || (node.type === 'canvas_frame' ? '#ffffff' : '#3a2010'));
        return (
          <>
            {node.type === 'canvas_note' ? (
              <div className="flex flex-col gap-4 mb-6">
                <div className="space-y-2 group">
                  <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">Note Text</label>
                  <div className="rounded-xl overflow-hidden border border-white/10 transition-all focus-within:border-accent/40" style={{ background: bgColor }}>
                    <MarkdownToolbar
                      textareaRef={noteTextareaRef}
                      value={p.text || ''}
                      onChange={val => up({ text: val })}
                    />
                    <textarea
                      ref={noteTextareaRef}
                      value={p.text || ''}
                      onChange={e => up({ text: e.target.value })}
                      className="w-full px-4 py-3 text-[13px] outline-none resize-y"
                      style={{ background: 'transparent', color: textColor, fontFamily: 'Roboto, sans-serif', lineHeight: '1.65', minHeight: 120 }}
                      placeholder="Enter note text (Markdown supported)..."
                    />
                  </div>
                </div>
                {/* Input port settings */}
                <div className="space-y-3 border border-white/5 rounded-xl px-3 py-3 bg-white/[0.02]">
                  <label className="text-[9px] text-gray-500 uppercase tracking-widest font-black">Text Input Port</label>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-gray-400">Mode</span>
                    <select
                      value={p.mode ?? 0}
                      onChange={e => up({ mode: Number(e.target.value) })}
                      className="bg-black/30 border border-white/10 rounded-lg px-2 py-1 text-[11px] text-white outline-none cursor-pointer"
                    >
                      <option value={0}>Append</option>
                      <option value={1}>Replace</option>
                    </select>
                  </div>
                  {(p.mode ?? 0) === 0 && (
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] text-gray-400 shrink-0">Separator</span>
                      <input
                        value={p.separator ?? '\n\n'}
                        onChange={e => up({ separator: e.target.value })}
                        className="flex-1 bg-black/30 border border-white/10 rounded-lg px-2 py-1 text-[11px] text-white outline-none font-mono min-w-0"
                        placeholder="\n\n"
                      />
                    </div>
                  )}
                  <button
                    onClick={() => up({ text: '', mode: p.mode ?? 0 })}
                    className="w-full text-[9px] font-black uppercase tracking-widest text-red-400/70 hover:text-red-400 border border-red-400/10 hover:border-red-400/30 rounded-lg py-1.5 transition-all"
                  >
                    Clear
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4 group mb-6">
                <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">Frame Title</label>
                <input
                  value={p.title || 'Frame Layer'}
                  onChange={e => up({ title: e.target.value })}
                  className="w-full border rounded-xl px-4 py-3 text-[13px] outline-none transition-all font-black text-center"
                  style={{ background: bgColor, color: textColor, borderColor: 'rgba(0,0,0,0.12)' }}
                  placeholder="Enter frame title…"
                />
              </div>
            )}
            <div className="space-y-4">
              <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black">Background Color</label>
              <div className="flex gap-3 flex-wrap">
                {currentPalette.map(({ bg, dark, label }: { bg: string; dark: string; label: string }, i: number) => (
                  <button key={bg} title={label} onClick={() => up({ color_index: i })} className="flex flex-col items-center gap-1.5 group/swatch">
                    <div
                      className="w-10 h-10 rounded-xl transition-all duration-150 group-hover/swatch:scale-110"
                      style={{
                        background: bg,
                        border:     (cIdx === i || (cIdx === undefined && bgColor === bg)) ? '3px solid rgba(0,0,0,0.4)' : '2px solid rgba(0,0,0,0.1)',
                        boxShadow:  (cIdx === i || (cIdx === undefined && bgColor === bg)) ? '0 0 0 2px rgba(255,255,255,0.6)' : 'none',
                      }}
                    />
                    <span className="text-[7px] font-bold text-gray-500 uppercase tracking-wider overflow-hidden max-w-[40px] text-ellipsis whitespace-nowrap">{label}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center justify-between py-2">
              <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black">Text Color</label>
              <div className="flex gap-2">
                {['#ffffff', currentPalette[(cIdx !== undefined ? cIdx : 0) % 5]?.dark || '#1a1a1a'].map(c => (
                  <button
                    key={c}
                    onClick={() => up({ text_color: c, color_index: undefined })}
                    className="w-7 h-7 rounded-full border-2 transition-all hover:scale-110"
                    style={{
                      background:  c,
                      borderColor: textColor === c ? 'rgba(0,0,0,0.5)' : 'rgba(0,0,0,0.15)',
                      boxShadow:   textColor === c ? '0 0 0 2px rgba(255,255,255,0.5)' : 'none',
                    }}
                  />
                ))}
              </div>
            </div>
          </>
        );
      })()}

      {/* input_webcam */}
      {node.type === 'input_webcam' && (
        <>
          <Slider label="Device Index"       val={p.device_index || 0}  min={0}   max={5}    onChange={v => up({ device_index: v })} />
          <Slider label="Width (0 = auto)"   val={p.width || 0}         min={0}   max={3840} step={160} onChange={v => up({ width: v })} />
          <Slider label="Height (0 = auto)"  val={p.height || 0}        min={0}   max={2160} step={120} onChange={v => up({ height: v })} />
          <Slider label="FPS (0 = auto)"     val={p.fps || 0}           min={0}   max={120}  step={5}   onChange={v => up({ fps: v })} />
        </>
      )}

      {/* input_movie */}
      {node.type === 'input_movie' && (
        <div className="space-y-6">
          <TextInput label="Movie Path" val={p.path || ''} onChange={(v: string) => up({ path: v })} />
          <div className="flex flex-col gap-4 p-4 bg-white/10 rounded-2xl border border-white/5">
            <label className="text-[10px] text-gray-500 uppercase tracking-widest font-black">Playback Control</label>
            <div className="flex items-center justify-between">
              <button
                onClick={() => up({ playing: !p.playing })}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-bold transition-all ${p.playing ? 'bg-red-500 text-white shadow-lg shadow-red-500/20' : 'bg-green-500 text-white shadow-lg shadow-green-500/20'}`}
              >
                {p.playing ? <><Pause size={14} /> Stop</> : <><Play size={14} /> Start</>}
              </button>
              <div className="text-[10px] font-mono text-gray-400">
                Frame: {liveData?.current_frame || 0} / {liveData?.total_frames || 0}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Slider label="Start" val={p.start_frame || 0} min={0} max={(liveData?.total_frames || 1) - 1} onChange={v => up({ start_frame: v })} />
              <Slider label="End"   val={p.end_frame ?? (liveData?.total_frames ? liveData.total_frames - 1 : 0)} min={0} max={(liveData?.total_frames || 1) - 1} onChange={v => up({ end_frame: v })} />
            </div>
            <Slider
              label="Scrub"
              val={p.playing ? (liveData?.current_frame || 0) : (p.scrub_index || 0)}
              min={0} max={(liveData?.total_frames || 1) - 1}
              onChange={v => up({ scrub_index: v, playing: false })}
            />
          </div>
        </div>
      )}

      {/* geo_spectral_index */}
      {node.type === 'geo_spectral_index' && (() => {
        const getIdx = (val: any, options: string[]) => {
          if (typeof val === 'number') return val;
          if (typeof val === 'string') {
            const i = options.indexOf(val);
            return i !== -1 ? i : 0;
          }
          return 0;
        };
        return (
          <div className="space-y-6">
            <div className="p-4 bg-black/20 rounded-2xl border border-white/5 space-y-6">
              <div className="text-[8px] font-black text-gray-500 uppercase tracking-[0.2em] mb-2 flex justify-between">
                <span>Band Configuration</span>
              </div>
              <Slider label="NIR Band"   val={p.nir_band   ?? 4} min={1} max={20} onChange={v => up({ nir_band: v })} />
              <Slider label="Red Band"   val={p.red_band   ?? 1} min={1} max={20} onChange={v => up({ red_band: v })} />
              <Slider label="Green Band" val={p.green_band ?? 2} min={1} max={20} onChange={v => up({ green_band: v })} />
              <Slider label="Blue Band"  val={p.blue_band  ?? 3} min={1} max={20} onChange={v => up({ blue_band: v })} />
              <Slider label="SWIR Band"  val={p.swir_band  ?? 5} min={1} max={20} onChange={v => up({ swir_band: v })} />
            </div>

            <SelectInput
              label="Colormap"
              val={getIdx(p.colormap, ['viridis', 'plasma', 'turbo', 'jet', 'hot'])}
              options={['viridis', 'plasma', 'turbo', 'jet', 'hot']}
              onChange={v => up({ colormap: v })}
            />
          </div>
        );
      })()}

      {/* geo_band_calc */}
      {node.type === 'geo_band_calc' && (() => {
        const sensorOptions = ['Manual', 'S2/L8 (RGB+NIR)', 'S2 (All Bands)', 'L8 (All Bands)'];
        const indexOptions  = ['None', 'NDVI (Vegetation)', 'NDWI (Water)', 'NBR (Burn)', 'EVI (Enhanced Vegetation)'];
        
        const sensorIdx = p.sensor ?? 0;
        const indexIdx  = p.preset ?? 0;

        const presets: Record<number, any> = {
          1: { nir: 4, red: 1, green: 2, blue: 3, swir: 5 }, // RGB+NIR
          2: { nir: 8, red: 4, green: 3, blue: 2, swir: 11 }, // S2 All
          3: { nir: 5, red: 4, green: 3, blue: 2, swir: 6 },  // L8 All
        };

        const updateExpr = (sIdx: number, iIdx: number) => {
          if (iIdx === 0) return; // None
          const b = presets[sIdx] || presets[1]; // Fallback to RGB+NIR
          let expr = "";
          const eps = "1e-10";
          
          if (iIdx === 1) expr = `(B${b.nir} - B${b.red}) / (B${b.nir} + B${b.red} + ${eps})`;
          if (iIdx === 2) expr = `(B${b.green} - B${b.nir}) / (B${b.green} + B${b.nir} + ${eps})`;
          if (iIdx === 3) expr = `(B${b.nir} - B${b.swir}) / (B${b.nir} + B${b.swir} + ${eps})`;
          if (iIdx === 4) expr = `2.5 * (B${b.nir} - B${b.red}) / (B${b.nir} + 6.0 * B${b.red} - 7.5 * B${b.blue} + 1.0 + ${eps})`;
          
          up({ expression: expr, sensor: sIdx, preset: iIdx });
        };

        return (
          <div className="space-y-6">
            <div className="p-4 bg-accent/5 rounded-2xl border border-accent/10 space-y-4">
              <div className="text-[8px] font-black text-accent uppercase tracking-[0.2em] mb-2 flex items-center gap-2">
                <Calculator size={10} /> Preset Generator
              </div>
              <SelectInput label="Sensor" val={sensorIdx} options={sensorOptions} onChange={v => updateExpr(v, indexIdx)} />
              <SelectInput label="Preset" val={indexIdx}  options={indexOptions}  onChange={v => updateExpr(sensorIdx, v)} />
            </div>

            <CodeInput label="Expression" val={p.expression ?? ""} onChange={v => up({ expression: v, preset: 0 })} />
            
            <div className="grid grid-cols-2 gap-4">
              <NumberInput label="Clamp Min" val={p.clamp_min ?? -1} onChange={v => up({ clamp_min: v })} />
              <NumberInput label="Clamp Max" val={p.clamp_max ?? 1}  onChange={v => up({ clamp_max: v })} />
            </div>

            <SelectInput
              label="Colormap"
              val={typeof p.colormap === 'number' ? p.colormap : 0}
              options={['viridis', 'plasma', 'turbo', 'jet', 'hot', 'gray']}
              onChange={v => up({ colormap: v })}
            />
          </div>
        );
      })()}

      {/* ── Audio nodes ───────────────────────────────────────────────────── */}

      {/* plugin_audio_input */}
      {node.type === 'plugin_audio_input' && (() => {
        const isPlaying = !!(p.playing);
        const duration  = Number(liveData?.duration ?? p.duration ?? 0);
        const position  = Number(liveData?.position ?? 0);
        const progress  = duration > 0 ? Math.min(position / duration, 1) : 0;
        return (
          <>
            <TextInput label="File Path" val={p.path || ''} onChange={v => up({ path: v })} />
            <ToggleInput label="Force Mono" val={!!(p.mono ?? true)} onChange={v => up({ mono: v })} />

            {/* Transport */}
            {p.path && (
              <div className="space-y-3 pt-2">
                <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black">Playback</label>

                {/* Progress bar */}
                <div>
                  <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden cursor-pointer"
                    onClick={e => {
                      const rect = (e.target as HTMLElement).getBoundingClientRect();
                      const ratio = (e.clientX - rect.left) / rect.width;
                      up({ _seek: ratio * duration, playing: false });
                    }}>
                    <div className="h-full bg-indigo-500/80 rounded-full transition-all duration-100"
                      style={{ width: `${progress * 100}%` }} />
                  </div>
                  <div className="flex justify-between mt-1">
                    <span className="text-[8px] text-gray-500 font-mono">{position.toFixed(1)}s</span>
                    <span className="text-[8px] text-gray-500 font-mono">{duration.toFixed(1)}s</span>
                  </div>
                </div>

                {/* Controls */}
                <div className="flex items-center gap-2">
                  <button onClick={() => up({ playing: false, _seek: 0 })}
                    className="flex-1 py-2 rounded-xl bg-white/5 hover:bg-indigo-500/20 border border-white/10 text-gray-400 hover:text-indigo-300 text-[9px] font-black uppercase tracking-wider transition-all flex items-center justify-center gap-1">
                    ⏮ Rewind
                  </button>
                  <button onClick={() => up({ playing: !isPlaying })}
                    className={`flex-1 py-2 rounded-xl border text-[9px] font-black uppercase tracking-wider transition-all flex items-center justify-center gap-1 ${
                      isPlaying
                        ? 'bg-indigo-500/30 border-indigo-400/50 text-indigo-200 hover:bg-red-500/20 hover:border-red-400/40'
                        : 'bg-indigo-500/20 border-indigo-500/40 text-indigo-300 hover:bg-indigo-500/40'
                    }`}>
                    {isPlaying ? '⏸ Stop' : '▶ Play'}
                  </button>
                  <button onClick={() => up({ loop: !p.loop })}
                    className={`px-3 py-2 rounded-xl border text-[9px] font-black transition-all ${
                      p.loop ? 'bg-indigo-500/30 border-indigo-400/50 text-indigo-200' : 'bg-white/5 border-white/10 text-gray-500 hover:text-gray-300'
                    }`} title="Loop">
                    🔁
                  </button>
                </div>
              </div>
            )}
          </>
        );
      })()}

      {/* plugin_audio_to_spectrogram */}
      {node.type === 'plugin_audio_to_spectrogram' && (
        <>
          <ToggleInput label="Full File" val={!!p.full_file} onChange={v => up({ full_file: v })} />
          {!p.full_file && <Slider label="Window (s)" val={p.window_sec ?? 5} min={0.5} max={60} step={0.5} onChange={v => up({ window_sec: v })} />}
          <Slider label="N-FFT"      val={p.n_fft      ?? 2048} min={256}  max={8192} step={256}  onChange={v => up({ n_fft: v })} />
          <Slider label="Hop Length" val={p.hop_length ?? 512}  min={64}   max={2048} step={64}   onChange={v => up({ hop_length: v })} />
          <Slider label="Mel Bands"  val={p.n_mels     ?? 128}  min={32}   max={256}  step={16}   onChange={v => up({ n_mels: v })} />
          <SelectInput label="Colormap" val={Number(p.colormap ?? 0)} options={['Magma','Viridis','Inferno','Hot','Jet']} onChange={v => up({ colormap: v })} />
        </>
      )}

      {/* plugin_audio_waveform */}
      {node.type === 'plugin_audio_waveform' && (
        <>
          <Slider label="Width"  val={p.width  ?? 640} min={128} max={2048} step={32} onChange={v => up({ width: v })} />
          <Slider label="Height" val={p.height ?? 200} min={64}  max={1024} step={16} onChange={v => up({ height: v })} />
          <ColorInput label="Color" val={p.color ?? '#6366f1'} onChange={v => up({ color: v })} nodeId={node.id} onPickColorToggle={onPickColorToggle} isPicking={pickColorNodeId === node.id} />
        </>
      )}

      {/* plugin_audio_freq_filter */}
      {node.type === 'plugin_audio_freq_filter' && (
        <>
          <SelectInput label="Filter Type" val={Number(p.filter_type ?? 0)} options={['Low-pass','High-pass','Band-pass','Band-stop']} onChange={v => up({ filter_type: v })} />
          <Slider label="Low Cut (Hz)"  val={p.low_hz  ?? 100}  min={1} max={20000} step={10} onChange={v => up({ low_hz: v })} />
          <Slider label="High Cut (Hz)" val={p.high_hz ?? 4000} min={1} max={20000} step={10} onChange={v => up({ high_hz: v })} />
          <Slider label="Filter Order"  val={p.order   ?? 5}    min={1} max={10}    step={1}  onChange={v => up({ order: v })} />
        </>
      )}

      {/* plugin_audio_pitch_shift */}
      {node.type === 'plugin_audio_pitch_shift' && (
        <Slider label="Semitones" val={p.semitones ?? 0} min={-24} max={24} step={0.5} onChange={v => up({ semitones: v })} />
      )}

      {/* plugin_audio_time_stretch */}
      {node.type === 'plugin_audio_time_stretch' && (
        <Slider label="Speed Rate" val={p.rate ?? 1.0} min={0.1} max={4.0} step={0.05} onChange={v => up({ rate: v })} />
      )}

      {/* plugin_spectrogram_to_audio */}
      {node.type === 'plugin_spectrogram_to_audio' && (
        <>
          <Slider label="Sample Rate"    val={p.sr         ?? 22050} min={8000}  max={48000} step={100} onChange={v => up({ sr: v })} />
          <Slider label="N-FFT"          val={p.n_fft      ?? 2048}  min={256}   max={8192}  step={256} onChange={v => up({ n_fft: v })} />
          <Slider label="Hop Length"     val={p.hop_length ?? 512}   min={64}    max={2048}  step={64}  onChange={v => up({ hop_length: v })} />
          <Slider label="GL Iterations"  val={p.iterations ?? 32}    min={4}     max={128}   step={4}   onChange={v => up({ iterations: v })} />
        </>
      )}

      {/* plugin_audio_export */}
      {node.type === 'plugin_audio_export' && (
        <>
          <TextInput label="Output Path" val={p.path || 'output.wav'} onChange={v => up({ path: v })} />
          <div className="space-y-4 group">
            <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black">Save Now</label>
            <button
              onClick={() => { up({ save_now: 1 }); setTimeout(() => up({ save_now: 0 }), 400); }}
              className="w-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 font-black py-4 rounded-3xl hover:bg-indigo-500 hover:text-white transition-all duration-300 shadow-lg shadow-accent/5 flex items-center justify-center gap-2 active:scale-95"
            >
              <Save size={14} /> Save Audio File
            </button>
          </div>
        </>
      )}

      {/* plugin_audio_info  — outputs only, no params */}

      {/* util_landmark_selector */}
      {node.type === 'util_landmark_selector' && (
        <div className="space-y-4">
          <TextInput 
            label="Landmark Indices" 
            val={p.indices || "11,12,24,23"} 
            onChange={v => up({ indices: v })} 
          />
          <div className="p-3 bg-blue-500/5 border border-blue-500/10 rounded-xl space-y-2">
            <div className="text-[8px] font-black text-blue-400 uppercase tracking-widest">Aide Mémoire (Pose)</div>
            <div className="text-[9px] text-gray-500 leading-relaxed font-mono">
              11, 12 : Épaules (L, R)<br/>
              23, 24 : Hanches (L, R)<br/>
              13, 14 : Coudes (L, R)<br/>
              15, 16 : Poignets (L, R)
            </div>
          </div>
        </div>
      )}

      {/* math_vec_to_screen calibration */}
      {node.type === 'math_vec_to_screen' && (
        <div className="space-y-6">
          <div className="bg-accent/5 border border-accent/20 rounded-2xl p-5 space-y-3">
            <div className="flex items-center gap-2">
              <Activity size={14} className="text-accent" />
              <span className="text-[9px] font-black text-accent uppercase tracking-widest">Calibration</span>
            </div>
            <p className="text-[9px] text-gray-400 leading-relaxed">
              Regardez chaque coin de l'écran pendant 1 seconde et cliquez sur le bouton correspondant.
              Réalisez les 4 coins, puis activez la calibration.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {[
              { key: 'calibrate_tl', label: '↖ Top-Left' },
              { key: 'calibrate_tr', label: '↗ Top-Right' },
              { key: 'calibrate_bl', label: '↙ Bottom-Left' },
              { key: 'calibrate_br', label: '↘ Bottom-Right' },
            ].map(corner => {
              const done = node.data.params?.[corner.key];
              return (
                <button key={corner.key}
                  onClick={() => up({ [corner.key]: true })}
                  className={`flex items-center justify-center gap-2 px-3 py-3 rounded-xl text-[10px] font-bold transition-all border ${
                    done
                      ? 'bg-green-500/10 border-green-500/30 text-green-400'
                      : 'bg-white/5 border-white/10 text-gray-400 hover:bg-accent/10 hover:border-accent/30 hover:text-accent'
                  }`}
                >
                  {corner.label}
                </button>
              );
            })}
          </div>

          <ToggleInput label="Activer Calibration" val={!!p.calibration_enabled} onChange={v => up({ calibration_enabled: v })} />

          {p.calibration_enabled && (
            <button onClick={() => up({ calibrate_reset: true })}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-[10px] font-bold transition-all bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20"
            >
              Reset Calibration
            </button>
          )}

          <hr className="border-white/5" />

          <Slider label="Scale X" val={p.scale_x ?? 1.0} min={0.1} max={10} step={0.05} onChange={v => up({ scale_x: v })} />
          <Slider label="Scale Y" val={p.scale_y ?? 1.0} min={0.1} max={10} step={0.05} onChange={v => up({ scale_y: v })} />
          <Slider label="Offset X" val={p.offset_x ?? 0.0} min={-1.0} max={1.0} step={0.01} onChange={v => up({ offset_x: v })} />
          <Slider label="Offset Y" val={p.offset_y ?? 0.0} min={-1.0} max={1.0} step={0.01} onChange={v => up({ offset_y: v })} />
          <Slider label="Smoothing" val={p.smooth ?? 0.7} min={0.0} max={0.99} step={0.01} onChange={v => up({ smooth: v })} />
          <ToggleInput label="Clamp" val={p.clamp ?? true} onChange={v => up({ clamp: v })} />
          <ToggleInput label="Flip X" val={!!p.flip_x} onChange={v => up({ flip_x: v })} />
          <ToggleInput label="Flip Y" val={!!p.flip_y} onChange={v => up({ flip_y: v })} />
          <ToggleInput label="Use Camera FOV" val={!!p.use_fov} onChange={v => up({ use_fov: v })} />
        </div>
      )}

      {/* Node note — always visible, displayed under the node when non-empty */}
      {node.type !== 'canvas_note' && node.type !== 'canvas_frame' && (
        <div className="space-y-2 group pt-2 border-t border-white/5">
          <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">Note</label>
          <input
            type="text"
            value={p.node_note || ''}
            onChange={e => up({ node_note: e.target.value || undefined })}
            className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-[11px] text-gray-300 outline-none focus:border-accent/50 transition-all placeholder:text-gray-600"
            placeholder="Annotation visible sous la node…"
          />
        </div>
      )}

      {/* Schema-driven dynamic params (plugins) */}
      {!MANUAL_TYPES.has(node.type) && (() => {
        const schemaParams: ParamSpec[] = node.data.schema?.params ?? [];
        const connectedCount = 1 + ((node.data as any).ports?.length ?? 0);

        // ── show_if checker ───────────────────────────────────────────────
        const passesShowIf = (sp: ParamSpec): boolean => {
          if (!sp.show_if) return true;
          const cur = p[sp.show_if.param] ?? schemaParams.find(
            (x: ParamSpec) => x.id === sp.show_if!.param
          )?.default ?? 0;
          return Number(cur) === Number(sp.show_if.value) || cur === sp.show_if.value;
        };

        // ── single param widget ───────────────────────────────────────────
        const renderWidget = (sp: ParamSpec): React.ReactNode => {
          const isExposed = (node.data.exposedParams ?? []).includes(sp.id);
          const showEye   = !!(isInsideGroup && onToggleExposed && sp.type !== 'trigger' && sp.type !== 'code');
          const isExternalized = ((node.data as any).externalizedParams ?? []).includes(sp.id);
          const isEnum    = sp.type === 'enum' || sp.options;
          const isColor   = sp.type === 'color';
          const isDate    = sp.type === 'date' || sp.id === 'date_start' || sp.id === 'date_end';
          const isString  = (sp.type === 'string' || typeof (p[sp.id] ?? sp.default) === 'string') && !isDate;
          const isNumber  = sp.type === 'number' || sp.type === 'float' || typeof (p[sp.id] ?? sp.default) === 'number';
          const isBool    = sp.type === 'toggle' || sp.type === 'bool' || sp.type === 'boolean' || typeof (p[sp.id] ?? sp.default) === 'boolean';

          let inner: React.ReactNode;
          if (sp.type === 'trigger') {
            const isSnapshotSave    = node.type === 'util_snapshot' && sp.id === 'save_to_disk';
            const isSnapshotCapture = node.type === 'util_snapshot' && sp.id === 'capture';
            inner = (
              <div className="space-y-4 group">
                <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{sp.label || sp.id}</label>
                <button
                  onClick={() => { if (isSnapshotSave) { onRequestCapture(node.id); } else if (isSnapshotCapture) { window.dispatchEvent(new CustomEvent('snapshot-to-node', { detail: { nodeId: node.id } })); } else { up({ [sp.id]: 1 }); setTimeout(() => up({ [sp.id]: 0 }), 400); } }}
                  className="w-full bg-accent/5 border border-accent/20 text-accent font-black py-4 rounded-3xl hover:bg-accent hover:text-white transition-all duration-300 shadow-lg shadow-accent/5 flex items-center justify-center gap-2 active:scale-95"
                >
                  <Save size={14} /> {sp.label || 'Execute'}
                </button>
              </div>
            );
          } else if (isEnum) {
            const isFlowPreset = node.type === 'analysis_flow' && sp.id === 'preset';
            inner = <SelectInput label={sp.label || sp.id} val={p[sp.id] ?? sp.default ?? 0} options={sp.options || []} onChange={(v) => {
              if (isFlowPreset) { const idx = Number(v); const pv = FLOW_PRESETS[idx]; up(pv ? { preset: idx, ...pv } : { preset: idx }); }
              else { up({ [sp.id]: v }); }
            }} />;
          } else if (isColor) {
            inner = <ColorInput label={sp.label || sp.id} val={String(p[sp.id] ?? sp.default ?? '#ffffff')} onChange={(v) => up({ [sp.id]: v })} nodeId={node.id} onPickColorToggle={onPickColorToggle} isPicking={pickColorNodeId === node.id} />;
          } else if (sp.type === 'file_path') {
            inner = <FilePathInput label={sp.label || sp.id} val={String(p[sp.id] ?? sp.default ?? '')} onChange={(v) => up({ [sp.id]: v })} filters={(sp as any).filters} />;
          } else if (isDate) {
            inner = <DateInput label={sp.label || sp.id} val={String(p[sp.id] ?? sp.default ?? '')} onChange={(v) => up({ [sp.id]: v })} />;
          } else if (isString) {
            if (sp.id === 'code') {
              inner = <CodeInput label={sp.label || sp.id} val={String(p[sp.id] ?? sp.default ?? '')} onChange={(v) => up({ [sp.id]: v })} liveError={liveData?.out_e || undefined} />;
            } else {
              const colHints: string[] | undefined =
                sp.hints === 'df_columns' ? (liveData?.df_meta?.columns as string[] | undefined) :
                sp.hints === 'item_keys'  ? (liveData?._available_keys as string[] | undefined) :
                undefined;
              const curVal = String(p[sp.id] ?? sp.default ?? '');
              const selected = new Set(curVal.split(',').map((s: string) => s.trim()).filter(Boolean));
              inner = (
                <div className="space-y-1.5">
                  <TextInput label={sp.label || sp.id} val={curVal} onChange={(v) => up({ [sp.id]: v })} />
                  {colHints?.length ? (
                    <div className="flex flex-wrap gap-1 pt-0.5">
                      {colHints.map((col: string) => {
                        const active = selected.has(col);
                        return (
                          <button
                            key={col}
                            onClick={() => {
                              const next = new Set(selected);
                              if (active) next.delete(col); else next.add(col);
                              up({ [sp.id]: Array.from(next).join(', ') });
                            }}
                            className={`text-[8px] font-mono px-1.5 py-0.5 rounded border transition-all ${active ? 'bg-accent/20 border-accent/50 text-accent' : 'bg-white/5 border-white/10 text-gray-400 hover:border-accent/30 hover:text-gray-200'}`}
                          >
                            {col}
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              );
            }
          } else if (isNumber) {
            const val = Number(p[sp.id] ?? sp.default ?? 0);
            let minVal = sp.min;
            let maxVal = sp.max;
            let stepVal = sp.step;

            if (node.type === 'scalar_input' && sp.id === 'value') {
              minVal = p.min !== undefined ? Number(p.min) : 0.0;
              maxVal = p.max !== undefined ? Number(p.max) : 100.0;
              stepVal = p.step !== undefined ? Number(p.step) : (p.format === 0 ? 1 : 0.01);
            }

            inner = (minVal === undefined || maxVal === undefined)
              ? <NumberInput label={sp.label || sp.id} val={val} onChange={(v) => up({ [sp.id]: v })} />
              : <Slider label={sp.label || sp.id} val={val} min={minVal} max={maxVal} step={stepVal || (sp.type === 'float' ? 0.01 : 1)} onChange={(v) => up({ [sp.id]: v })} />;
          } else if (isBool) {
            inner = <ToggleInput label={sp.label || sp.id} val={!!(p[sp.id] ?? sp.default)} onChange={(v) => up({ [sp.id]: v })} />;
          } else {
            inner = <Slider label={sp.label || sp.id} val={Number(p[sp.id] ?? sp.default ?? 0)} min={sp.min || 0} max={sp.max || 100} step={sp.step || 1} onChange={(v) => up({ [sp.id]: v })} />;
          }

          const showExternalize = !!(onExternalizeParam && (isNumber || isString) && !isEnum && sp.type !== 'trigger' && sp.type !== 'code');
          const hasOverlay = showEye || showExternalize;

          return (
            <div key={sp.id} className={hasOverlay ? 'relative group/param' : undefined}>
              <div className={isExternalized ? 'opacity-40 pointer-events-none' : undefined}>
                {inner}
              </div>
              <div className="absolute top-0 right-0 flex items-center gap-0.5">
                {showExternalize && (
                  <button
                    className={`p-1 rounded transition-all duration-150 ${isExternalized ? 'text-green-400' : 'text-gray-600 opacity-0 group-hover/param:opacity-100 hover:text-green-400'}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!isExternalized) {
                        const val = isString ? (p[sp.id] ?? sp.default ?? '') : Number(p[sp.id] ?? sp.default ?? 0);
                        onExternalizeParam!(node.id, sp, val);
                      }
                    }}
                    title={isExternalized ? `Paramètre externalisé (${isString ? 'String' : 'Number'} connecté)` : `Externaliser → créer une entrée + node ${isString ? 'String' : 'Number'}`}
                  >
                    <PlugZap size={10} />
                  </button>
                )}
                {showEye && (
                  <button
                    className={`p-1 rounded transition-all duration-150 ${isExposed ? 'text-accent' : 'text-gray-600 opacity-0 group-hover/param:opacity-100'}`}
                    onClick={(e) => { e.stopPropagation(); onToggleExposed!(node.id, sp.id); }}
                    title={isExposed ? 'Retirer du groupe' : 'Exposer dans le groupe'}
                  >
                    {isExposed ? <Eye size={10} /> : <EyeOff size={10} />}
                  </button>
                )}
              </div>
            </div>
          );
        };

        // ── non-slot params — with section collapsible support ───────────────
        // Group params into sections: a 'section' type param opens a new group.
        // Params before the first section are rendered flat (legacy behaviour).
        type ParamGroup = { section: ParamSpec | null; params: ParamSpec[] };
        const paramGroups: ParamGroup[] = [];
        let currentGroup: ParamGroup = { section: null, params: [] };
        for (const sp of schemaParams.filter(sp => !sp.slot)) {
          if (sp.type === 'section') {
            if (currentGroup.params.length > 0 || currentGroup.section) {
              paramGroups.push(currentGroup);
            }
            currentGroup = { section: sp, params: [] };
          } else {
            currentGroup.params.push(sp);
          }
        }
        paramGroups.push(currentGroup);

        const renderGroupParams = (params: ParamSpec[]) => params.map((sp: ParamSpec) => {
          // Skip internal/hidden params (underscore prefix = engine-only state)
          if (sp.id.startsWith('_')) return null;
          if (node.type === 'geom_resize' && sp.id !== 'mode' && sp.id !== 'interpolation') {
            const mode = Number(p.mode ?? 0);
            if (sp.id === 'scale'  && mode !== 0) return null;
            if (sp.id === 'width'  && mode !== 1 && mode !== 3) return null;
            if (sp.id === 'height' && mode !== 2 && mode !== 3) return null;
          }
          if (node.type === 'filter_color_mask') {
            const mode = Number(p.mode ?? 0);
            if (mode === 0 && sp.id === 'threshold') return null;
            if (mode !== 0 && ['h_tol', 's_tol', 'v_tol'].includes(sp.id)) return null;
          }
          if (!passesShowIf(sp)) return null;
          return renderWidget(sp);
        });

        const nonSlotNodes = paramGroups.map((group, gi) => {
          // No section header → flat (legacy)
          if (!group.section) {
            return <React.Fragment key={`flat-${gi}`}>{renderGroupParams(group.params)}</React.Fragment>;
          }
          const sec = group.section;
          // Section hidden by show_if → skip the whole group
          if (!passesShowIf(sec)) return null;
          const secKey = `section-${sec.id}`;
          const isCollapsed = collapsedSlots.has(secKey);
          const visibleParams = group.params.filter(passesShowIf);
          return (
            <div key={secKey} className="rounded-xl overflow-hidden border border-white/[0.07]">
              <button
                className="w-full flex items-center gap-2 px-3 py-2 bg-white/[0.04] hover:bg-white/[0.07] transition-colors text-left"
                onClick={() => toggleSlot(secKey)}
              >
                <span className="text-gray-400 text-[12px] font-mono w-3 shrink-0 leading-none">
                  {isCollapsed ? '›' : '∨'}
                </span>
                <span className="text-[9px] font-black uppercase tracking-widest text-gray-200 truncate flex-1">
                  {sec.label || sec.id}
                </span>
                {visibleParams.length > 0 && isCollapsed && (
                  <span className="text-[8px] text-gray-600 font-mono shrink-0">{visibleParams.length} params</span>
                )}
              </button>
              {!isCollapsed && (
                <div className="px-3 pb-3 pt-2 flex flex-col gap-4 border-t border-white/[0.05]">
                  {renderGroupParams(group.params)}
                </div>
              )}
            </div>
          );
        });

        // ── slot-grouped params (collapsible) ─────────────────────────────
        const hasSlotParams = schemaParams.some(sp => sp.slot);
        const slotGroupNodes = !hasSlotParams ? [] :
          Array.from('abcdefgh').slice(0, connectedCount).map(slot => {
            const group = schemaParams.filter(sp => sp.slot === slot);
            if (group.length === 0) return null;
            const isCollapsed = collapsedSlots.has(slot);
            const labelSp  = group.find(sp => sp.id === `${slot}_label`);
            const colorSp  = group.find(sp => sp.id === `${slot}_color`);
            const slotLabel = String(p[labelSp?.id ?? ''] ?? labelSp?.default ?? slot.toUpperCase());
            const slotColor = String(p[colorSp?.id ?? ''] ?? colorSp?.default ?? '#888888');

            return (
              <div key={slot} className="rounded-lg overflow-hidden border border-white/5">
                <button
                  className="w-full flex items-center gap-2 px-2 py-1.5 bg-white/[0.03] hover:bg-white/[0.06] transition-colors text-left"
                  onClick={() => toggleSlot(slot)}
                >
                  <span className="text-gray-500 text-[11px] font-mono w-3 shrink-0">
                    {isCollapsed ? '›' : '∨'}
                  </span>
                  <span className="w-3 h-3 rounded-sm shrink-0 border border-white/10" style={{ backgroundColor: slotColor }} />
                  <span className="text-[9px] font-black uppercase tracking-widest text-gray-300 truncate flex-1">
                    {slot.toUpperCase()} — {slotLabel}
                  </span>
                </button>
                {!isCollapsed && (
                  <div className="px-2 pb-2 pt-1 flex flex-col gap-3 border-t border-white/5">
                    {group.filter(passesShowIf).map(sp => renderWidget(sp))}
                  </div>
                )}
              </div>
            );
          });

        return <>{nonSlotNodes}{slotGroupNodes}</>;
      })()}

    </div>
  );
};

const DataFramePanel = ({ meta }: { meta: any }) => {
  const [showHead, setShowHead] = React.useState(false);
  const shape: [number, number] = meta.shape || [0, 0];
  const columns: string[] = meta.columns || [];
  const dtypes: Record<string, string> = meta.dtypes || {};
  const nulls: Record<string, number>  = meta.nulls  || {};
  const head: Record<string, any>[]    = meta.head   || [];

  const dtypeColor = (t: string) =>
    t.startsWith('int') || t.startsWith('float') || t.startsWith('complex') ? 'text-blue-400' :
    t.startsWith('bool') ? 'text-emerald-400' :
    t === 'object' || t.startsWith('str') ? 'text-amber-400' :
    t.startsWith('datetime') ? 'text-purple-400' :
    'text-gray-400';

  const totalNulls = Object.values(nulls).reduce((s, n) => s + n, 0);

  return (
    <div className="space-y-2">
      {/* Shape + quality bar */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-black font-mono text-orange-300">
          {shape[0].toLocaleString()} × {shape[1]}
        </span>
        {totalNulls > 0 && (
          <span className="text-[8px] text-red-400 font-mono">{totalNulls} nulls</span>
        )}
      </div>

      {/* Column list */}
      <div className="space-y-0.5 max-h-40 overflow-y-auto scrollbar-hide">
        {columns.map(col => {
          const n = nulls[col] ?? 0;
          const pct = shape[0] > 0 ? (n / shape[0]) * 100 : 0;
          return (
            <div key={col} className="flex items-center gap-1.5 text-[9px] py-0.5">
              <span className="text-gray-300 flex-1 truncate font-medium">{col}</span>
              <span className={`font-mono shrink-0 ${dtypeColor(dtypes[col] || '')}`}>{dtypes[col]}</span>
              {n > 0 && (
                <span className="text-[7px] font-mono text-red-400/80 shrink-0">{pct.toFixed(0)}%∅</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Head toggle */}
      {head.length > 0 && (
        <button
          onClick={() => setShowHead(h => !h)}
          className="w-full py-1 rounded-lg bg-white/5 border border-white/10 text-[7px] font-black uppercase tracking-widest text-gray-500 hover:text-orange-300 hover:border-orange-500/30 transition-all"
        >
          {showHead ? '▲ Masquer aperçu' : '▼ Aperçu données'}
        </button>
      )}
      {showHead && head.length > 0 && (
        <div className="overflow-x-auto scrollbar-hide rounded-lg border border-white/10">
          <table className="text-[8px] font-mono w-full">
            <thead>
              <tr className="border-b border-white/10 bg-white/5">
                {columns.slice(0, 6).map(c => (
                  <th key={c} className="px-1.5 py-1 text-left text-gray-500 font-black truncate max-w-16">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {head.map((row, i) => (
                <tr key={i} className={i % 2 === 0 ? '' : 'bg-white/3'}>
                  {columns.slice(0, 6).map(c => (
                    <td key={c} className="px-1.5 py-0.5 text-gray-400 truncate max-w-16">
                      {row[c] === null || row[c] === undefined ? <span className="text-red-400/60">∅</span> : String(row[c]).slice(0, 10)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export const AnalysisDataPanel = ({ liveData }: { liveData: any }) => {
  if (!liveData || Object.keys(liveData).length === 0) return null;

  const dfMeta = liveData.df_meta;
  const otherKeys = Object.keys(liveData).filter(k => k !== 'df_meta' && k !== 'preview' && k !== 'main');
  const hasOther = otherKeys.length > 0;

  if (!dfMeta && !hasOther) return null;

  return (
    <div className="p-6 bg-[#1a1f26]/80 backdrop-blur-md border-t border-[#4f5b6b] space-y-4 shadow-2xl shrink-0">
      {dfMeta && (
        <div className="space-y-2">
          <div className="text-[9px] font-black text-orange-400 uppercase tracking-[0.2em] flex items-center gap-2 bg-orange-400/5 p-2 rounded-lg border border-orange-400/10">
            <Activity size={10} /> DataFrame
          </div>
          <DataFramePanel meta={dfMeta} />
        </div>
      )}
      {hasOther && (
        <div className="space-y-2">
          <div className="text-[9px] font-black text-cyan-400 uppercase tracking-[0.2em] flex items-center gap-2 bg-cyan-400/5 p-2 rounded-lg border border-cyan-400/10">
            <Activity size={10} /> Analysis Data
          </div>
          <pre className="text-[9px] font-mono text-green-400/90 max-h-32 overflow-auto scrollbar-hide italic leading-relaxed">
            {JSON.stringify(Object.fromEntries(otherKeys.map(k => [k, liveData[k]])), null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};

