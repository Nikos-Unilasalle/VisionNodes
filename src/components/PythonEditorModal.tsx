import React, { useEffect, useRef, useCallback, useState } from 'react';
import ReactDOM from 'react-dom';
import Editor, { OnMount, loader } from '@monaco-editor/react';
import { X, AlertCircle, CheckCircle2 } from 'lucide-react';

// Monaco local setup — runs once when this chunk is loaded (i.e. only when modal opens)
import * as monaco from 'monaco-editor';
import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';
(window as any).MonacoEnvironment = { getWorker: () => new editorWorker() };
loader.config({ monaco });

// ── VNStudio Python completions ────────────────────────────────────────────

const VNSTUDIO_COMPLETIONS = [
  { label: 'a', detail: 'Input A (any type)', doc: 'First input — image, scalar, list, dict, DataFrame…' },
  { label: 'b', detail: 'Input B (any type)', doc: 'Second input' },
  { label: 'c', detail: 'Input C (any type)', doc: 'Third input' },
  { label: 'd', detail: 'Input D (any type)', doc: 'Fourth input' },
  { label: 'e', detail: 'Input E (any type)', doc: 'Fifth input' },
  { label: 'np',  detail: 'numpy', doc: 'NumPy always available' },
  { label: 'cv2', detail: 'OpenCV', doc: 'OpenCV always available' },
  { label: 'pd',  detail: 'pandas (if installed)', doc: 'Pandas — check with isinstance(a, pd.DataFrame)' },
  { label: 'state', detail: 'dict — persists between frames', doc: 'state[\'counter\'] = state.get(\'counter\', 0) + 1' },
  { label: 'out_main',   detail: '→ image output', doc: 'np.ndarray (BGR image)' },
  { label: 'out_scalar', detail: '→ scalar output', doc: 'float' },
  { label: 'out_list',   detail: '→ list output',   doc: 'list' },
  { label: 'out_dict',   detail: '→ dict output',   doc: 'dict' },
  { label: 'out_any',    detail: '→ any output',    doc: 'any type' },
  { label: 'out_data',   detail: '→ DataFrame output', doc: 'pd.DataFrame' },
  { label: 'out_e',      detail: '→ error string',  doc: 'Set automatically on exception' },
];

const SNIPPETS = [
  {
    label: 'if isinstance image',
    insertText: 'if isinstance(a, np.ndarray):\n    ${1:pass}',
    doc: 'Check if input is an image',
  },
  {
    label: 'state counter',
    insertText: 'state[\'counter\'] = state.get(\'counter\', 0) + 1',
    doc: 'Persist counter across frames',
  },
  {
    label: 'DataFrame filter',
    insertText: 'if isinstance(a, pd.DataFrame):\n    out_data = a[a[\'${1:column}\'] == ${2:value}]',
    doc: 'Filter DataFrame rows',
  },
  {
    label: 'BGR to Gray',
    insertText: 'out_main = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)',
    doc: 'Convert image to grayscale',
  },
  {
    label: 'resize image',
    insertText: 'out_main = cv2.resize(a, (${1:640}, ${2:480}))',
    doc: 'Resize image to fixed dimensions',
  },
];

function registerVNCompletions(monaco: typeof import('monaco-editor')) {
  monaco.languages.registerCompletionItemProvider('python', {
    provideCompletionItems: (model, position) => {
      const word = model.getWordUntilPosition(position);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber:   position.lineNumber,
        startColumn:     word.startColumn,
        endColumn:       word.endColumn,
      };
      const kind = monaco.languages.CompletionItemKind;

      const varItems = VNSTUDIO_COMPLETIONS.map(c => ({
        label:         c.label,
        kind:          kind.Variable,
        detail:        c.detail,
        documentation: c.doc,
        insertText:    c.label,
        range,
      }));

      const snippetItems = SNIPPETS.map(s => ({
        label:            s.label,
        kind:             kind.Snippet,
        detail:           'VNStudio snippet',
        documentation:    s.doc,
        insertText:       s.insertText,
        insertTextRules:  monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
        range,
      }));

      return { suggestions: [...varItems, ...snippetItems] };
    },
  });
}

// ── Component ──────────────────────────────────────────────────────────────

interface PythonEditorModalProps {
  label:      string;
  value:      string;
  liveError?: string;
  onChange:   (v: string) => void;
  onClose:    () => void;
}

export function PythonEditorModal({ label, value, liveError, onChange, onClose }: PythonEditorModalProps) {
  const editorRef = useRef<import('monaco-editor').editor.IStandaloneCodeEditor | null>(null);
  const completionsRegistered = useRef(false);
  const [statusLine, setStatusLine] = useState({ line: 1, col: 1 });
  const [wordWrap, setWordWrap] = useState<'on' | 'off'>('on');

  // Keyboard: Escape → close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const handleMount: OnMount = useCallback((editor, monaco) => {
    editorRef.current = editor;

    // Register VNStudio completions once
    if (!completionsRegistered.current) {
      registerVNCompletions(monaco);
      completionsRegistered.current = true;
    }

    // Cursor position → status bar
    editor.onDidChangeCursorPosition((e) => {
      setStatusLine({ line: e.position.lineNumber, col: e.position.column });
    });

    // Cmd+S → focus stays in editor (code already live)
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      onClose();
    });

    editor.focus();
  }, [onClose]);

  const hasError = !!liveError;

  const modal = (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-6 md:p-12 pointer-events-none select-none">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm pointer-events-auto cursor-pointer"
        onClick={onClose}
      />
      
      {/* Modal Content */}
      <div
        className="w-full h-full max-w-[1400px] max-h-[900px] flex flex-col bg-[#0d1117] rounded-2xl border border-white/10 shadow-2xl overflow-hidden pointer-events-auto relative z-10"
        style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' }}
      >
        {/* ── Top bar ────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-4 h-11 bg-[#161b22] border-b border-white/10 shrink-0 select-none">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-purple-400 shadow-[0_0_8px_rgba(192,132,252,0.6)]" />
            <span className="text-[11px] text-gray-300 font-semibold tracking-wide">{label}</span>
            <span className="text-[9px] text-gray-600 bg-white/5 border border-white/10 px-2 py-0.5 rounded">Python 3.x · Sandboxed</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setWordWrap(w => w === 'on' ? 'off' : 'on')}
              className="text-[10px] text-gray-500 hover:text-gray-300 transition-colors px-2 py-1 rounded hover:bg-white/5"
              title="Toggle word wrap (Alt+Z)"
            >
              wrap: {wordWrap}
            </button>
            <span className="text-[9px] text-gray-600 px-2">Cmd+S or Esc → close</span>
            <button
              onClick={onClose}
              className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-white/10 transition-all"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* ── Editor ─────────────────────────────────────────────────────── */}
        <div className="flex-1 overflow-hidden">
          <Editor
            language="python"
            theme="vs-dark"
            value={value}
            onChange={(v) => onChange(v ?? '')}
            onMount={handleMount}
            options={{
              minimap:             { enabled: true },
              fontSize:            13,
              lineHeight:          22,
              fontFamily:          'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
              fontLigatures:       true,
              tabSize:             4,
              insertSpaces:        true,
              wordWrap,
              scrollBeyondLastLine: false,
              automaticLayout:     true,
              padding:             { top: 16, bottom: 16 },
              cursorBlinking:      'smooth',
              cursorSmoothCaretAnimation: 'on',
              smoothScrolling:     true,
              bracketPairColorization: { enabled: true },
              guides: {
                bracketPairs:  true,
                indentation:   true,
              },
              suggest: {
                showKeywords:  true,
                showSnippets:  true,
              },
              quickSuggestions: { strings: false, comments: false, other: true },
              parameterHints:  { enabled: true },
              formatOnPaste:   true,
              formatOnType:    false,
              renderWhitespace: 'boundary',
              renderLineHighlight: 'gutter',
            }}
          />
        </div>

        {/* ── Status bar ──────────────────────────────────────────────────── */}
        <div className={`flex items-center justify-between px-4 h-7 shrink-0 border-t text-[10px] transition-colors ${
          hasError
            ? 'bg-red-950/60 border-red-900/40'
            : 'bg-[#161b22] border-white/10'
        }`}>
          <div className="flex items-center gap-3">
            {hasError ? (
              <div className="flex items-center gap-1.5 text-red-400">
                <AlertCircle size={11} />
                <span className="truncate max-w-[600px]">{liveError}</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-green-500">
                <CheckCircle2 size={11} />
                <span>No errors</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-4 text-gray-600">
            <span>Ln {statusLine.line}, Col {statusLine.col}</span>
            <span>·</span>
            <span>np · cv2 · pd · state · out_*</span>
          </div>
        </div>
      </div>
    </div>
  );

  return ReactDOM.createPortal(modal, document.body);
}
