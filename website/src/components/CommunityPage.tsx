import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Upload, ExternalLink, CheckCircle2, Github } from 'lucide-react';

const DOMAINS = [
  'Object Detection', 'Face Analysis', 'Hand Tracking', 'Pose Estimation',
  'OCR & Text', 'Motion & Tracking', 'Medical Imaging', 'Industrial Inspection',
  'Semantic Segmentation', 'Depth Estimation', 'Data Analysis', 'Signal Processing',
  'Creative Coding', 'Scientific Imaging', 'Robotics & Control',
];

const FILE_TYPES: Record<string, { label: string; color: string; ext: string }> = {
  vn:  { label: '.vn Pipeline',  color: '#83b817', ext: '.vn'  },
  py:  { label: '.py Node',      color: '#60a5fa', ext: '.py'  },
};

const CommunityPage = () => {
  const [fileType, setFileType] = useState<'vn' | 'py'>('vn');
  const [fileName, setFileName] = useState('');
  const [title, setTitle] = useState('');
  const [author, setAuthor] = useState('');
  const [description, setDescription] = useState('');
  const [domains, setDomains] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const toggleDomain = (d: string) =>
    setDomains(prev => prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d]);

  const handleFile = (f: File | null) => {
    if (!f) return;
    setFileName(f.name);
    if (f.name.endsWith('.py')) setFileType('py');
    else if (f.name.endsWith('.vn')) setFileType('vn');
  };

  const buildIssueURL = () => {
    const meta = FILE_TYPES[fileType];
    const body = [
      `**Title:** ${title}`,
      `**Author:** ${author}`,
      `**File type:** ${meta.ext}`,
      `**File name:** ${fileName}`,
      `**Domains:** ${domains.join(', ') || 'N/A'}`,
      '',
      '**Description:**',
      description,
      '',
      '> Attach your file to this issue.',
    ].join('\n');

    const params = new URLSearchParams({
      title: `[Community] ${meta.label}: ${title}`,
      body,
      labels: `community,${fileType}-submission`,
    });
    return `https://github.com/Nikos-Unilasalle/VisionNodes/issues/new?${params.toString()}`;
  };

  const canSubmit = title.trim() && description.trim() && fileName;

  const handleSubmit = () => {
    if (!canSubmit) return;
    window.open(buildIssueURL(), '_blank');
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <motion.div
        key="community"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="section-full"
        style={{ paddingTop: '6rem' }}
      >
        <div className="container-md text-center">
          <div className="w-16 h-16 rounded-full bg-[var(--accent)]/10 flex items-center justify-center text-[var(--accent)] mx-auto mb-6">
            <CheckCircle2 size={32} strokeWidth={1.5} />
          </div>
          <h2 className="text-[36px] text-[var(--text-main)] mb-4">Thank you!</h2>
          <p className="text-[16px] text-[var(--text-dim)] mb-8 leading-relaxed">
            Your GitHub Issue has been opened. Attach your file to the issue, and the community
            will review your contribution. Submissions that pass review are merged into the core library.
          </p>
          <button className="btn-secondary" onClick={() => { setSubmitted(false); setFileName(''); setTitle(''); setDescription(''); setDomains([]); }}>
            Submit another
          </button>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div key="community" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      {/* Header */}
      <section className="section-full section-alt" style={{ paddingTop: '4rem', paddingBottom: '3rem' }}>
        <div className="container-lg">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
            <div>
              <h1 className="text-[44px] md:text-[56px] text-[var(--text-main)] mb-4">Share Your Work</h1>
              <p className="text-[17px] text-[var(--text-dim)] max-w-2xl leading-relaxed">
                Share a custom node (<code className="bg-[var(--border)] px-1.5 py-0.5 rounded text-[13px]">.py</code>) or a
                pipeline (<code className="bg-[var(--border)] px-1.5 py-0.5 rounded text-[13px]">.vn</code>) with the VisionNodes community.
                Contributions are submitted via GitHub Issues and reviewed for inclusion in the core library.
              </p>
            </div>
            <a
              href="https://github.com/Nikos-Unilasalle/VisionNodes"
              target="_blank"
              rel="noreferrer"
              className="btn-secondary shrink-0"
            >
              <Github size={15} /> View on GitHub
            </a>
          </div>
        </div>
      </section>

      {/* Form */}
      <section className="section-full" style={{ paddingTop: '2.5rem' }}>
        <div className="container-md">
          <div className="space-y-6">

            {/* File type toggle */}
            <div>
              <label className="block text-[13px] font-semibold text-[var(--text-dim)] uppercase tracking-wider mb-3">
                Submission type
              </label>
              <div className="flex gap-3">
                {(Object.entries(FILE_TYPES) as [string, typeof FILE_TYPES['vn']][]).map(([key, meta]) => (
                  <button
                    key={key}
                    onClick={() => setFileType(key as 'vn' | 'py')}
                    className="flex items-center gap-2 px-5 py-3 rounded-xl border-2 font-semibold text-[14px] transition-all"
                    style={
                      fileType === key
                        ? { borderColor: meta.color, backgroundColor: meta.color + '15', color: meta.color }
                        : { borderColor: 'var(--border-strong)', color: 'var(--text-dim)' }
                    }
                  >
                    <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: meta.color }} />
                    {meta.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Drop zone */}
            <div>
              <label className="block text-[13px] font-semibold text-[var(--text-dim)] uppercase tracking-wider mb-3">
                File
              </label>
              <div
                className={`drop-zone ${dragging ? 'active' : ''}`}
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
                onClick={() => fileRef.current?.click()}
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept=".vn,.py"
                  className="hidden"
                  onChange={e => handleFile(e.target.files?.[0] || null)}
                />
                {fileName ? (
                  <div className="flex items-center justify-center gap-3">
                    <span
                      className="px-3 py-1 rounded-full text-[13px] font-bold"
                      style={{ backgroundColor: FILE_TYPES[fileType].color + '20', color: FILE_TYPES[fileType].color }}
                    >
                      {FILE_TYPES[fileType].ext}
                    </span>
                    <span className="text-[var(--text-main)] font-semibold">{fileName}</span>
                  </div>
                ) : (
                  <div>
                    <Upload size={28} className="mx-auto mb-3 text-[var(--text-xdim)]" strokeWidth={1.5} />
                    <p className="text-[15px] text-[var(--text-dim)]">Drop your file here, or click to browse</p>
                    <p className="text-[12px] text-[var(--text-xdim)] mt-1">Accepts .vn and .py files</p>
                  </div>
                )}
              </div>
              <p className="text-[12px] text-[var(--text-xdim)] mt-2">
                Note: the file will be attached to the GitHub Issue you create in the next step.
              </p>
            </div>

            {/* Title */}
            <div>
              <label className="block text-[13px] font-semibold text-[var(--text-dim)] uppercase tracking-wider mb-2">
                Title *
              </label>
              <input
                type="text"
                placeholder={fileType === 'py' ? 'e.g. Optical Flow Tracker' : 'e.g. Smile Detection Pipeline'}
                className="vn-input"
                value={title}
                onChange={e => setTitle(e.target.value)}
              />
            </div>

            {/* Author */}
            <div>
              <label className="block text-[13px] font-semibold text-[var(--text-dim)] uppercase tracking-wider mb-2">
                Author / GitHub username
              </label>
              <input
                type="text"
                placeholder="@your-github-handle"
                className="vn-input"
                value={author}
                onChange={e => setAuthor(e.target.value)}
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-[13px] font-semibold text-[var(--text-dim)] uppercase tracking-wider mb-2">
                Description *
              </label>
              <textarea
                rows={5}
                placeholder={
                  fileType === 'py'
                    ? 'Describe what this node does, its inputs, outputs, and any dependencies...'
                    : 'Describe this pipeline: what problem it solves, which nodes it uses, and any requirements...'
                }
                className="vn-input resize-none"
                value={description}
                onChange={e => setDescription(e.target.value)}
              />
            </div>

            {/* Domains */}
            <div>
              <label className="block text-[13px] font-semibold text-[var(--text-dim)] uppercase tracking-wider mb-3">
                Application domains
              </label>
              <div className="flex flex-wrap gap-2">
                {DOMAINS.map(d => (
                  <button
                    key={d}
                    onClick={() => toggleDomain(d)}
                    className={`vn-checkbox ${domains.includes(d) ? 'checked' : ''}`}
                  >
                    {domains.includes(d) && <CheckCircle2 size={13} strokeWidth={2} />}
                    {d}
                  </button>
                ))}
              </div>
            </div>

            {/* Submit */}
            <div className="pt-2">
              <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="btn-primary w-full sm:w-auto justify-center disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ExternalLink size={15} />
                Open GitHub Issue to submit
              </button>
              <p className="text-[12px] text-[var(--text-xdim)] mt-3">
                This will open a pre-filled GitHub Issue in a new tab. Attach your file there and submit.
              </p>
            </div>

          </div>
        </div>
      </section>
    </motion.div>
  );
};

export default CommunityPage;
