import React, { useRef, useState, useEffect } from 'react';
import { Pause, Play, Pipette, Save, Activity, Calculator, ChevronDown, Eye, EyeOff } from 'lucide-react';
import { PALETTES } from './Nodes';
import type { ParamSpec, NodeData, VNNode } from '../types/NodeSchema';
import { HexColorPicker } from 'react-colorful';

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
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
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
    setTempVal(s);
    const parsed = parseFloat(s);
    if (!isNaN(parsed)) {
      onChange(parsed);
    }
  };

  return (
    <div className="space-y-4 group">
      <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
      <input
        type="text" value={tempVal} onChange={(e) => handleChange(e.target.value)}
        onKeyDown={(e) => e.stopPropagation()}
        className="w-full bg-black/40 border border-[#4f5b6b] group-hover:border-accent/40 rounded-xl px-4 py-3 text-[13px] text-white outline-none focus:border-accent transition-all font-mono shadow-inner"
      />
    </div>
  );
};

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

interface CodeInputProps { label: string; val: string; onChange: (v: string) => void; }
export const CodeInput = ({ label, val, onChange }: CodeInputProps) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);
  const syncScroll = () => {
    if (textareaRef.current && highlightRef.current) {
      highlightRef.current.scrollTop  = textareaRef.current.scrollTop;
      highlightRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  };
  const lineCount = (val || '').split('\n').length;
  return (
    <div className="space-y-2 group">
      <div className="flex items-center justify-between">
        <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
        <div className="text-[8px] font-mono text-gray-600 bg-white/10 px-2 py-0.5 rounded">Python 3.x</div>
      </div>
      <div className="relative rounded-xl overflow-hidden border border-[#4f5b6b] group-hover:border-accent/40 transition-all shadow-inner bg-[#1e2530]">
        <div className="absolute inset-y-0 left-0 w-8 bg-black/15 border-r border-white/5 flex flex-col items-center pt-3 pb-3 text-[8px] font-mono text-gray-600 select-none pointer-events-none z-10 overflow-hidden">
          {Array.from({ length: lineCount }, (_, i) => (
            <div key={i} className="leading-relaxed h-[1.5em] flex items-center">{i + 1}</div>
          ))}
        </div>
        <div
          ref={highlightRef}
          aria-hidden="true"
          className="absolute inset-0 left-8 pt-3 pb-3 pr-4 text-[11px] font-mono leading-relaxed overflow-hidden pointer-events-none whitespace-pre select-none"
          dangerouslySetInnerHTML={{ __html: highlightPython(val || '') + '\n' }}
        />
        <textarea
          ref={textareaRef}
          value={val}
          onChange={(e) => onChange(e.target.value)}
          onScroll={syncScroll}
          spellCheck={false}
          className="relative w-full h-80 bg-transparent pl-10 pr-4 py-3 text-[11px] font-mono text-transparent caret-white outline-none resize-none scrollbar-hide leading-relaxed z-[1]"
          placeholder="Write your script here..."
          style={{ caretColor: '#fff' }}
        />
      </div>
      <div className="text-[8px] text-gray-500 italic px-1">
        Inputs: <span className="text-pink-400">a, b, c, d</span> · Persistence: <span className="text-pink-400">state['key']</span> · Outputs: <span className="text-blue-400">out_main, out_scalar, out_list, out_dict, out_any</span>
      </div>
    </div>
  );
};

interface ColorInputProps { label: string; val: string; onChange: (v: string) => void; }
export const ColorInput = ({ label, val, onChange }: ColorInputProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const currentVal = (val || '#ffffff').toUpperCase();

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
        <button 
          onClick={() => setIsOpen(!isOpen)}
          className="relative w-10 h-6 rounded-md border border-white/20 shadow-lg cursor-pointer hover:scale-105 transition-all overflow-hidden"
          style={{ backgroundColor: currentVal }}
        />
        
        {isOpen && (
          <div className="absolute right-0 top-full mt-2 z-[100] p-4 bg-[#1e2530] border border-white/10 rounded-2xl shadow-2xl space-y-3">
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
  exposedGroupParams?: ExposedParam[];
  onUpdateGroupChildParams?: (childNodeId: string, params: Record<string, unknown>) => void;
}

export const NodeInspectorPanel: React.FC<NodeInspectorPanelProps> = ({
  node, liveData, activePaletteIndex,
  pickColorNodeId, onUpdateParams, onPickColorToggle, onRequestCapture,
  isInsideGroup, onToggleExposed, exposedGroupParams, onUpdateGroupChildParams,
}) => {
  const p = node.data.params;
  const up = (params: Record<string, unknown>) => onUpdateParams(node.id, params);

  // Skip manual types to avoid duplication with schema-driven loop below
  const MANUAL_TYPES = new Set([
    'canvas_note', 'canvas_frame',
    'input_webcam', 'input_movie',
    'output_display',
    'geo_spectral_index', 'geo_band_calc',
    'plugin_audio_input', 'plugin_audio_to_spectrogram', 'plugin_audio_waveform',
    'plugin_audio_freq_filter', 'plugin_audio_pitch_shift', 'plugin_audio_time_stretch',
    'plugin_spectrogram_to_audio', 'plugin_audio_export', 'plugin_audio_info',
    'util_landmark_selector',
  ]);

  return (
    <div className="space-y-8 pb-32">

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
                  const lbl = sp.label || sp.id;
                  const isE2 = sp.type === 'enum' || sp.options;
                  const isColor2 = sp.type === 'color';
                  const isS2 = sp.type === 'string' || typeof (val ?? sp.default) === 'string';
                  const isN2 = sp.type === 'number' || sp.type === 'float';
                  const isB2 = sp.type === 'toggle' || sp.type === 'bool' || sp.type === 'boolean' || typeof (val ?? sp.default) === 'boolean';
                  if (isE2) return <SelectInput key={sp.id} label={lbl} val={Number(val ?? sp.default ?? 0)} options={sp.options || []} onChange={up2} />;
                  if (isColor2) return <ColorInput  key={sp.id} label={lbl} val={String(val ?? sp.default ?? '#ffffff')} onChange={up2} />;
                  if (isS2) return <TextInput   key={sp.id} label={lbl} val={String(val ?? sp.default ?? '')} onChange={v => up2(v)} />;
                  if (isN2) {
                    const v2 = Number(val ?? sp.default ?? 0);
                    const min2 = sp.min ?? -10;
                    const max2 = sp.max ?? (v2 > 100 ? v2 * 2 : 100);
                    return <Slider 
                      key={sp.id} 
                      label={lbl} 
                      val={v2} 
                      min={min2} 
                      max={max2} 
                      step={sp.step || (sp.type === 'float' ? 0.01 : 1)} 
                      onChange={up2} 
                    />;
                  }
                  if (isB2) return <ToggleInput key={sp.id} label={lbl} val={!!(val ?? sp.default)} onChange={up2} />;
                  return <Slider key={sp.id} label={lbl} val={Number(val ?? sp.default ?? 0)} min={sp.min || 0} max={sp.max || 100} step={sp.step || 1} onChange={up2} />;
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
              <div className="space-y-4 group mb-6">
                <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">Note Text</label>
                <textarea
                  value={p.text || ''}
                  onChange={e => up({ text: e.target.value })}
                  className="w-full border rounded-xl px-4 py-3 text-[13px] outline-none resize-none transition-all"
                  style={{ background: bgColor, color: textColor, borderColor: 'rgba(0,0,0,0.12)', fontFamily: 'Roboto, sans-serif', lineHeight: '1.65', minHeight: 120 }}
                  placeholder="Enter note text…"
                />
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
          <ColorInput label="Color" val={p.color ?? '#6366f1'} onChange={v => up({ color: v })} />
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
      {!MANUAL_TYPES.has(node.type) && node.data.schema?.params?.map((sp: ParamSpec) => {
        if (node.type === 'geom_resize' && sp.id !== 'mode' && sp.id !== 'interpolation') {
          const mode = Number(p.mode ?? 0);
          if (sp.id === 'scale'  && mode !== 0) return null;
          if (sp.id === 'width'  && mode !== 1 && mode !== 3) return null;
          if (sp.id === 'height' && mode !== 2 && mode !== 3) return null;
        }
        const isExposed = (node.data.exposedParams ?? []).includes(sp.id);
        const showEye   = !!(isInsideGroup && onToggleExposed && sp.type !== 'trigger' && sp.type !== 'code');
        const isEnum    = sp.type === 'enum' || sp.options;
        const isColor   = sp.type === 'color';
        const isString  = sp.type === 'string' || typeof (p[sp.id] ?? sp.default) === 'string';
        const isNumber  = sp.type === 'number' || sp.type === 'float' || typeof (p[sp.id] ?? sp.default) === 'number';
        const isBool    = sp.type === 'toggle' || sp.type === 'bool' || sp.type === 'boolean' || typeof (p[sp.id] ?? sp.default) === 'boolean';

        let inner: React.ReactNode;
        if (sp.type === 'trigger') {
          const isSnapshotSave = node.type === 'util_snapshot' && sp.id === 'save_to_disk';
          inner = (
            <div className="space-y-4 group">
              <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{sp.label || sp.id}</label>
              <button
                onClick={() => { if (isSnapshotSave) { onRequestCapture(node.id); } else { up({ [sp.id]: 1 }); setTimeout(() => up({ [sp.id]: 0 }), 400); } }}
                className="w-full bg-accent/5 border border-accent/20 text-accent font-black py-4 rounded-3xl hover:bg-accent hover:text-white transition-all duration-300 shadow-lg shadow-accent/5 flex items-center justify-center gap-2 active:scale-95"
              >
                <Save size={14} /> {sp.label || 'Execute'}
              </button>
            </div>
          );
        } else if (isEnum) {
          const isFlowPreset = node.type === 'analysis_flow' && sp.id === 'preset';
          inner = <SelectInput label={sp.label || sp.id} val={p[sp.id] ?? sp.default ?? 0} options={sp.options || []} onChange={(v) => {
            if (isFlowPreset) {
              const idx = Number(v);
              const pv = FLOW_PRESETS[idx];
              up(pv ? { preset: idx, ...pv } : { preset: idx });
            } else {
              up({ [sp.id]: v });
            }
          }} />;
        } else if (isColor) {
          inner = <ColorInput label={sp.label || sp.id} val={String(p[sp.id] ?? sp.default ?? '#ffffff')} onChange={(v) => up({ [sp.id]: v })} />;
        } else if (isString) {
          inner = sp.id === 'code'
            ? <CodeInput  label={sp.label || sp.id} val={String(p[sp.id] ?? sp.default ?? '')} onChange={(v) => up({ [sp.id]: v })} />
            : <TextInput  label={sp.label || sp.id} val={String(p[sp.id] ?? sp.default ?? '')} onChange={(v) => up({ [sp.id]: v })} />;
        } else if (isNumber) {
          const val = Number(p[sp.id] ?? sp.default ?? 0);
          const min = sp.min ?? -10;
          const max = sp.max ?? 100;
          inner = <Slider 
            label={sp.label || sp.id} 
            val={val} 
            min={min} 
            max={max} 
            step={sp.step || (sp.type === 'float' ? 0.01 : 1)} 
            onChange={(v) => up({ [sp.id]: v })} 
          />;
        } else if (isBool) {
          inner = <ToggleInput label={sp.label || sp.id} val={!!(p[sp.id] ?? sp.default)} onChange={(v) => up({ [sp.id]: v })} />;
        } else {
          inner = <Slider label={sp.label || sp.id} val={Number(p[sp.id] ?? sp.default ?? 0)} min={sp.min || 0} max={sp.max || 100} step={sp.step || 1} onChange={(v) => up({ [sp.id]: v })} />;
        }

        return (
          <div key={sp.id} className={showEye ? 'relative group/param' : undefined}>
            {inner}
            {showEye && (
              <button
                className={`absolute top-0 right-0 p-1 rounded transition-all duration-150 ${isExposed ? 'text-accent' : 'text-gray-600 opacity-0 group-hover/param:opacity-100'}`}
                onClick={(e) => { e.stopPropagation(); onToggleExposed!(node.id, sp.id); }}
                title={isExposed ? 'Retirer du groupe' : 'Exposer dans le groupe'}
              >
                {isExposed ? <Eye size={10} /> : <EyeOff size={10} />}
              </button>
            )}
          </div>
        );
      })}

    </div>
  );
};

export const AnalysisDataPanel = ({ liveData }: { liveData: any }) => {
  if (!liveData || Object.keys(liveData).length === 0) return null;
  return (
    <div className="p-6 bg-[#1a1f26]/80 backdrop-blur-md border-t border-[#4f5b6b] space-y-3 shadow-2xl shrink-0">
      <div className="text-[9px] font-black text-cyan-400 uppercase tracking-[0.2em] flex items-center gap-2 bg-cyan-400/5 p-2 rounded-lg border border-cyan-400/10">
        <Activity size={10} /> Analysis Data
      </div>
      <pre className="text-[10px] font-mono text-green-400/90 max-h-48 overflow-auto scrollbar-hide italic leading-relaxed">
        {JSON.stringify(liveData, null, 2)}
      </pre>
    </div>
  );
};

