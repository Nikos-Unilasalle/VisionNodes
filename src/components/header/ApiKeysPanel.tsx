import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Settings, Eye, EyeOff, Save, Check, AlertCircle } from 'lucide-react';
import { readTextFile, writeTextFile, mkdir } from '@tauri-apps/plugin-fs';
import { BaseDirectory } from '@tauri-apps/api/path';

// ── Secret field definitions ──────────────────────────────────────────────────

interface FieldDef {
  key: string;
  label: string;
  placeholder?: string;
  isPassword?: boolean;
}

interface SectionDef {
  title: string;
  fields: FieldDef[];
}

const SECTIONS: SectionDef[] = [
  {
    title: 'LLM Providers',
    fields: [
      { key: 'llm_OpenAI_key',         label: 'OpenAI',         placeholder: 'sk-…',          isPassword: true },
      { key: 'llm_Anthropic_key',       label: 'Anthropic',      placeholder: 'sk-ant-…',      isPassword: true },
      { key: 'llm_Groq_key',            label: 'Groq',           placeholder: 'gsk_…',         isPassword: true },
      { key: 'llm_DeepSeek_key',        label: 'DeepSeek',       placeholder: 'sk-…',          isPassword: true },
      { key: 'llm_Ollama (cloud)_key',  label: 'Ollama Cloud',   placeholder: 'API key',       isPassword: true },
      { key: 'llm_Custom_key',          label: 'Custom LLM',     placeholder: 'API key',       isPassword: true },
      { key: 'hf_token',                label: 'HuggingFace',    placeholder: 'hf_…',          isPassword: true },
    ],
  },
  {
    title: 'Google Earth Engine',
    fields: [
      { key: 'gcp_project', label: 'GCP Project ID', placeholder: 'my-project-123456' },
    ],
  },
  {
    title: 'Copernicus (CDS)',
    fields: [
      { key: 'copernicus_client_id',     label: 'Client ID',     placeholder: '…' },
      { key: 'copernicus_client_secret', label: 'Client Secret', placeholder: '…', isPassword: true },
    ],
  },
  {
    title: 'Copernicus Marine',
    fields: [
      { key: 'copernicus_marine_username', label: 'Username', placeholder: 'email or login' },
      { key: 'copernicus_marine_password', label: 'Password', placeholder: '…', isPassword: true },
    ],
  },
];

const SECRETS_FILE = '.vnstudio/secrets.json';

// ── Panel component ───────────────────────────────────────────────────────────

const ApiKeysPanel: React.FC = () => {
  const [open, setOpen]       = useState(false);
  const [values, setValues]   = useState<Record<string, string>>({});
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [status, setStatus]   = useState<'idle' | 'saved' | 'error'>('idle');
  const [errMsg, setErrMsg]   = useState('');
  const [loading, setLoading] = useState(false);

  // Load secrets whenever panel opens
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setStatus('idle');
    readTextFile(SECRETS_FILE, { baseDir: BaseDirectory.Home })
      .then(raw => setValues(JSON.parse(raw) as Record<string, string>))
      .catch(() => setValues({}))   // file absent = no keys yet
      .finally(() => setLoading(false));
  }, [open]);

  const handleSave = useCallback(async () => {
    // Ensure ~/.vnstudio/ exists — non-fatal (engine may have created it already)
    try {
      await mkdir('.vnstudio', { baseDir: BaseDirectory.Home, recursive: true });
    } catch { /* dir likely exists */ }

    try {
      const clean: Record<string, string> = {};
      Object.entries(values).forEach(([k, v]) => { if (v.trim()) clean[k] = v.trim(); });
      await writeTextFile(SECRETS_FILE, JSON.stringify(clean, null, 2), { baseDir: BaseDirectory.Home });
      setStatus('saved');
      setTimeout(() => setStatus('idle'), 2500);
    } catch (e: unknown) {
      setErrMsg(e instanceof Error ? e.message : String(e));
      setStatus('error');
      setTimeout(() => setStatus('idle'), 5000);
    }
  }, [values]);

  const set = (key: string, val: string) =>
    setValues(prev => ({ ...prev, [key]: val }));

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        title="API Keys & Secrets"
        className={`p-1.5 rounded-lg border transition-all ${
          open
            ? 'bg-accent/20 border-accent/40 text-accent'
            : 'bg-white/5 hover:bg-white/10 border-white/5 text-gray-400'
        }`}
      >
        <Settings size={14} />
      </button>

      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              className="absolute right-0 mt-2 w-80 bg-[#2c333f] border border-[#4f5b6b] rounded-xl shadow-2xl z-50 overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3 bg-[#3d4452] border-b border-[#4f5b6b]">
                <span className="text-[10px] font-black uppercase tracking-widest text-gray-200">
                  API Keys &amp; Secrets
                </span>
                <span className="text-[8px] text-gray-500">~/.vnstudio/secrets.json</span>
              </div>

              {/* Fields */}
              <div className="p-3 flex flex-col gap-4 max-h-[70vh] overflow-y-auto nowheel">
                {loading && (
                  <div className="text-center text-[9px] text-gray-500 py-4">Loading…</div>
                )}
                {!loading && SECTIONS.map(sec => (
                  <div key={sec.title}>
                    <div className="text-[8px] font-black uppercase tracking-widest text-gray-500 mb-2 px-1">
                      {sec.title}
                    </div>
                    <div className="flex flex-col gap-1.5">
                      {sec.fields.map(field => {
                        const filled = !!(values[field.key]?.trim());
                        return (
                          <div key={field.key} className="flex items-center gap-2">
                            <label className="text-[8px] w-28 shrink-0 truncate flex items-center gap-1"
                              style={{ color: filled ? '#a8e6cf' : '#6b7280' }}
                              title={field.label}>
                              {filled && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />}
                              {field.label}
                            </label>
                            <div className="flex-1 flex items-center gap-1 bg-black/30 border border-white/10 rounded-lg px-2 py-1 focus-within:border-accent/40 transition-all">
                              <input
                                type={field.isPassword && !visible[field.key] ? 'password' : 'text'}
                                value={values[field.key] ?? ''}
                                onChange={e => set(field.key, e.target.value)}
                                placeholder={field.placeholder}
                                className="flex-1 bg-transparent text-[9px] text-gray-200 placeholder-gray-600 outline-none font-mono"
                                autoComplete="off"
                                spellCheck={false}
                              />
                              {field.isPassword && (
                                <button
                                  onClick={() => setVisible(v => ({ ...v, [field.key]: !v[field.key] }))}
                                  className="text-gray-600 hover:text-gray-300 transition-colors shrink-0"
                                  tabIndex={-1}
                                >
                                  {visible[field.key] ? <EyeOff size={10} /> : <Eye size={10} />}
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>

              {/* Save bar */}
              <div className="px-3 py-2.5 bg-[#3d4452] border-t border-[#4f5b6b] flex items-center justify-between gap-2">
                {status === 'error' && (
                  <div className="flex items-center gap-1 text-[8px] text-red-400 truncate flex-1">
                    <AlertCircle size={10} className="shrink-0" />
                    <span className="truncate">{errMsg}</span>
                  </div>
                )}
                {status === 'saved' && (
                  <div className="flex items-center gap-1 text-[9px] text-emerald-400 font-bold flex-1">
                    <Check size={11} /> Keys saved successfully
                  </div>
                )}
                {status === 'idle' && <div className="flex-1" />}
                <button
                  onClick={handleSave}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all shrink-0 ${
                    status === 'saved'
                      ? 'bg-emerald-500/20 border border-emerald-500/40 text-emerald-400'
                      : status === 'error'
                      ? 'bg-red-500/15 border border-red-500/30 text-red-400'
                      : 'bg-accent/15 hover:bg-accent/25 border border-accent/30 text-accent'
                  }`}
                >
                  {status === 'saved' ? <><Check size={10} /> Saved</> : <><Save size={10} /> Save</>}
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ApiKeysPanel;
