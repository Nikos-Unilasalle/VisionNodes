import React, { useRef } from 'react';
import { Pause, Play, Pipette, Save, Activity } from 'lucide-react';
import { PALETTES } from './Nodes';
import type { ParamSpec, NodeData, VNNode } from '../types/NodeSchema';

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
        className="bg-white/5 border border-[#4f5b6b] rounded-lg px-3 py-1.5 text-accent font-black font-mono text-center w-28 outline-none focus:border-accent/60 transition-all text-[11px] shadow-sm"
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
export const NumberInput = ({ label, val, onChange }: NumberInputProps) => (
  <div className="space-y-4 group">
    <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
    <input
      type="number" step="any" value={val} onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
      className="w-full bg-black/20 border border-[#4f5b6b] group-hover:border-accent/40 rounded-xl px-4 py-2 text-[11px] text-white outline-none focus:border-accent transition-all font-mono"
    />
  </div>
);

interface SelectInputProps { label: string; val: number; options: string[]; onChange: (v: number) => void; }
export const SelectInput = ({ label, val, options, onChange }: SelectInputProps) => (
  <div className="space-y-4 group">
    <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{label}</label>
    <select
      value={val} onChange={(e) => onChange(parseInt(e.target.value))}
      className="w-full bg-black/20 border border-[#4f5b6b] group-hover:border-accent/40 rounded-xl px-4 py-2 text-[11px] text-white outline-none focus:border-accent transition-all appearance-none cursor-pointer"
    >
      {options.map((opt: string, i: number) => (
        <option key={i} value={i} className="bg-[#3d4452]">{opt}</option>
      ))}
    </select>
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

// ── Main panel ─────────────────────────────────────────────────────────────

interface NodeInspectorPanelProps {
  node: VNNode;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  liveData: Record<string, any>;
  activePaletteIndex: number;
  pickColorNodeId: string | null;
  onUpdateParams: (id: string, params: Record<string, unknown>) => void;
  onPickColorToggle: (id: string | null) => void;
  onRequestCapture: (id: string) => void;
}

export const NodeInspectorPanel: React.FC<NodeInspectorPanelProps> = ({
  node, liveData, activePaletteIndex,
  pickColorNodeId, onUpdateParams, onPickColorToggle, onRequestCapture,
}) => {
  const p = node.data.params;
  const up = (params: Record<string, unknown>) => onUpdateParams(node.id, params);

  // Skip manual types to avoid duplication with schema-driven loop below
  const MANUAL_TYPES = new Set([
    'canvas_note', 'canvas_frame', 'input_webcam', 'input_image', 'input_movie',
    'input_solid_color', 'filter_canny', 'filter_blur', 'filter_threshold',
    'geom_resize', 'geom_flip', 'filter_color_mask', 'filter_morphology',
    'analysis_face_mp', 'analysis_hand_mp', 'analysis_flow',
    'data_list_selector', 'list_region_select', 'output_display'
  ]);

  return (
    <div className="space-y-8 pb-32">

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

      {/* input_image */}
      {node.type === 'input_image' && (
        <TextInput label="Image Path" val={p.path || ''} onChange={(v: string) => up({ path: v })} />
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

      {/* input_solid_color */}
      {node.type === 'input_solid_color' && (
        <>
          <Slider label="Red"    val={p.r ?? 255} min={0}   max={255}  onChange={v => up({ r: v })} />
          <Slider label="Green"  val={p.g ?? 0}   min={0}   max={255}  onChange={v => up({ g: v })} />
          <Slider label="Blue"   val={p.b ?? 0}   min={0}   max={255}  onChange={v => up({ b: v })} />
          <Slider label="Width"  val={p.width  ?? 640} min={100} max={1920} onChange={v => up({ width: v })} />
          <Slider label="Height" val={p.height ?? 480} min={100} max={1080} onChange={v => up({ height: v })} />
        </>
      )}

      {/* filter_canny */}
      {node.type === 'filter_canny' && (
        <>
          <Slider label="Threshold Low"  val={p.low  || 100} min={1} max={500} onChange={v => up({ low: v })} />
          <Slider label="Threshold High" val={p.high || 200} min={1} max={500} onChange={v => up({ high: v })} />
        </>
      )}

      {/* filter_blur */}
      {node.type === 'filter_blur' && (
        <Slider label="Blur Kernel" val={p.size || 5} min={1} max={51} step={2} onChange={v => up({ size: v })} />
      )}

      {/* filter_threshold */}
      {node.type === 'filter_threshold' && (
        <Slider label="Threshold Value" val={p.threshold || 127} min={0} max={255} onChange={v => up({ threshold: v })} />
      )}

      {/* geom_resize */}
      {node.type === 'geom_resize' && (() => {
        const mode = p.mode ?? 0;
        return (
          <>
            <SelectInput label="Mode" val={mode} options={['Scale Factor', 'Fixed Size']} onChange={(v: number) => up({ mode: v })} />
            {mode === 0 ? (
              <Slider label="Scale Factor" val={p.scale ?? 1} min={0.05} max={4} step={0.05} onChange={v => up({ scale: v })} />
            ) : (
              <>
                <Slider label="Target Width (px)"  val={p.target_width  ?? 640} min={1} max={3840} step={1} onChange={v => up({ target_width: v })} />
                <Slider label="Target Height (px)" val={p.target_height ?? 480} min={1} max={2160} step={1} onChange={v => up({ target_height: v })} />
              </>
            )}
            <SelectInput label="Interpolation" val={p.interpolation ?? 1} options={['Nearest', 'Linear', 'Cubic', 'Lanczos']} onChange={(v: number) => up({ interpolation: v })} />
          </>
        );
      })()}

      {/* geom_flip */}
      {node.type === 'geom_flip' && (
        <Slider label="Flip Code (0,1,-1)" val={p.flip_mode || 1} min={-1} max={1} step={1} onChange={v => up({ flip_mode: v })} />
      )}

      {/* filter_color_mask */}
      {node.type === 'filter_color_mask' && (() => {
        const mode = p.mode ?? 0;
        const r = p.r ?? 128; const g = p.g ?? 128; const b = p.b ?? 128;
        return (
          <>
            <SelectInput label="Mode" val={mode} options={['HSV Range', 'RGB + Threshold']} onChange={(v: number) => up({ mode: v })} />
            {mode === 0 ? (
              <>
                <Slider label="Hue Min"   val={p.h_min ?? 0}   min={0} max={179} onChange={v => up({ h_min: v })} />
                <Slider label="Hue Max"   val={p.h_max ?? 179} min={0} max={179} onChange={v => up({ h_max: v })} />
                <Slider label="Sat Min"   val={p.s_min ?? 0}   min={0} max={255} onChange={v => up({ s_min: v })} />
                <Slider label="Value Min" val={p.v_min ?? 0}   min={0} max={255} onChange={v => up({ v_min: v })} />
              </>
            ) : (
              <>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-400">Target Color</span>
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded border border-[#333]" style={{ backgroundColor: `rgb(${r},${g},${b})` }} />
                      <button
                        className={`flex items-center gap-1 px-2 py-1 rounded text-xs border transition-colors ${pickColorNodeId === node.id ? 'bg-accent text-black border-accent' : 'border-[#333] text-gray-300 hover:border-accent/50'}`}
                        onClick={() => onPickColorToggle(pickColorNodeId === node.id ? null : node.id)}
                      >
                        <Pipette size={11} /> Pick
                      </button>
                    </div>
                  </div>
                </div>
                <Slider label="R"         val={r}                 min={0} max={255} onChange={v => up({ r: v })} />
                <Slider label="G"         val={g}                 min={0} max={255} onChange={v => up({ g: v })} />
                <Slider label="B"         val={b}                 min={0} max={255} onChange={v => up({ b: v })} />
                <Slider label="Threshold" val={p.threshold ?? 30} min={1} max={200} onChange={v => up({ threshold: v })} />
              </>
            )}
          </>
        );
      })()}

      {/* filter_morphology */}
      {node.type === 'filter_morphology' && (
        <>
          <Slider label="Operation (0=Dilate, 1=Erode)" val={p.operation || 0} min={0} max={1} step={1} onChange={v => up({ operation: v })} />
          <Slider label="Kernel Size" val={p.size || 5} min={3} max={21} step={2} onChange={v => up({ size: v })} />
        </>
      )}

      {/* analysis_face_mp */}
      {node.type === 'analysis_face_mp' && (
        <Slider label="Track Count" val={p.max_faces || 3} min={1} max={10} onChange={v => up({ max_faces: v })} />
      )}

      {/* analysis_hand_mp */}
      {node.type === 'analysis_hand_mp' && (
        <Slider label="Hand Count" val={p.max_hands || 2} min={1} max={4} onChange={v => up({ max_hands: v })} />
      )}

      {/* analysis_flow */}
      {node.type === 'analysis_flow' && (
        <>
          <Slider label="Pyr Scale" val={p.pyr_scale || 0.5} min={0.1} max={0.9} step={0.1} onChange={v => up({ pyr_scale: v })} />
          <Slider label="Levels"    val={p.levels    || 3}   min={1}   max={10}            onChange={v => up({ levels: v })} />
        </>
      )}

      {/* data_list_selector */}
      {node.type === 'data_list_selector' && (
        <Slider label="List Index" val={p.index || 0} min={0} max={10} onChange={v => up({ index: v })} />
      )}

      {/* list_region_select */}
      {node.type === 'list_region_select' && (() => {
        const sortBy = p.sort_by ?? 1;
        const byIndex = sortBy === 0;
        return (
          <>
            <SelectInput label="Sort By" val={sortBy} options={['Index', 'Largest area', 'Smallest area', 'Best confidence']} onChange={(v: number) => up({ sort_by: v })} />
            <div style={{ opacity: byIndex ? 1 : 0.35, pointerEvents: byIndex ? 'auto' : 'none' }}>
              <Slider label="Index" val={p.index ?? 0} min={0} max={100} step={1} onChange={v => up({ index: v })} />
            </div>
            <Slider label="Min Area (0–1)" val={p.min_area ?? 0} min={0} max={1} step={0.001} onChange={v => up({ min_area: v })} />
            <ToggleInput label="Require 4 pts" val={!!(p.require_pts ?? true)} onChange={v => up({ require_pts: v })} />
          </>
        );
      })()}

      {/* Schema-driven dynamic params (plugins) */}
      {!MANUAL_TYPES.has(node.type) && node.data.schema?.params?.map((sp: ParamSpec) => {
        const isEnum   = sp.type === 'enum' || sp.options;
        const isString = sp.type === 'string' || typeof (p[sp.id] ?? sp.default) === 'string';
        const isNumber = sp.type === 'number' || sp.type === 'float';
        const isBool   = sp.type === 'toggle' || sp.type === 'bool' || sp.type === 'boolean' || typeof (p[sp.id] ?? sp.default) === 'boolean';

        if (sp.type === 'trigger') {
          const isSnapshotSave = node.type === 'util_snapshot' && sp.id === 'save_to_disk';
          return (
            <div key={sp.id} className="space-y-4 group">
              <label className="text-[10px] text-gray-400 uppercase tracking-widest font-black group-hover:text-accent transition-all duration-300">{sp.label || sp.id}</label>
              <button
                onClick={() => {
                  if (isSnapshotSave) {
                    onRequestCapture(node.id);
                  } else {
                    up({ [sp.id]: 1 });
                    setTimeout(() => up({ [sp.id]: 0 }), 400);
                  }
                }}
                className="w-full bg-accent/5 border border-accent/20 text-accent font-black py-4 rounded-3xl hover:bg-accent hover:text-white transition-all duration-300 shadow-lg shadow-accent/5 flex items-center justify-center gap-2 active:scale-95"
              >
                <Save size={14} /> {sp.label || 'Execute'}
              </button>
            </div>
          );
        }

        if (isEnum)   return <SelectInput key={sp.id} label={sp.label || sp.id} val={Number(p[sp.id] ?? sp.default ?? 0)} options={sp.options || []} onChange={(v) => up({ [sp.id]: v })} />;
        if (isString) return sp.id === 'code'
          ? <CodeInput  key={sp.id} label={sp.label || sp.id} val={String(p[sp.id] ?? sp.default ?? '')} onChange={(v) => up({ [sp.id]: v })} />
          : <TextInput  key={sp.id} label={sp.label || sp.id} val={String(p[sp.id] ?? sp.default ?? '')} onChange={(v) => up({ [sp.id]: v })} />;
        if (isNumber) return <NumberInput key={sp.id} label={sp.label || sp.id} val={Number(p[sp.id] ?? sp.default ?? 0)} onChange={(v) => up({ [sp.id]: v })} />;
        if (isBool)   return <ToggleInput key={sp.id} label={sp.label || sp.id} val={!!(p[sp.id] ?? sp.default)} onChange={(v) => up({ [sp.id]: v })} />;

        return <Slider key={sp.id} label={sp.label || sp.id} val={Number(p[sp.id] ?? sp.default ?? 0)} min={sp.min || 0} max={sp.max || 100} step={sp.step || 1} onChange={(v) => up({ [sp.id]: v })} />;
      })}

    </div>
  );
};

export const AnalysisDataPanel = ({ liveData }: { liveData: any }) => {
  if (!liveData || Object.keys(liveData).length === 0) return null;
  return (
    <div className="p-6 bg-[#1a1f26]/80 backdrop-blur-md border-t border-[#4f5b6b] space-y-3 shadow-2xl h-full flex flex-col min-h-0">
      <div className="text-[9px] font-black text-cyan-400 uppercase tracking-[0.2em] flex items-center gap-2 bg-cyan-400/5 p-2 rounded-lg border border-cyan-400/10 shrink-0">
        <Activity size={10} /> Analysis Data
      </div>
      <pre className="text-[10px] font-mono text-green-400/90 flex-1 overflow-auto scrollbar-hide italic leading-relaxed">
        {JSON.stringify(liveData, null, 2)}
      </pre>
    </div>
  );
};

