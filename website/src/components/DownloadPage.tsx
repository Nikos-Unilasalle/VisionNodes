import React from 'react';
import { motion } from 'framer-motion';
import { Download, Github, ExternalLink, Apple, Monitor, ImageIcon } from 'lucide-react';

// Release version that the direct-download asset filenames are pinned to.
// Bump this single constant when publishing a new release.
const VERSION = '0.1.3';
const ASSET_BASE = `https://github.com/Nikos-Unilasalle/VisionNodes/releases/download/v${VERSION}`;

const PLATFORMS = [
  {
    id: 'mac',
    label: 'macOS',
    sub: 'Apple Silicon (M1–M4)',
    icon: <Apple size={28} strokeWidth={1.5} />,
    accent: '#1a1917',
    href: `${ASSET_BASE}/VNStudio_${VERSION}_aarch64.dmg`,
    badge: '',
  },
  {
    id: 'win',
    label: 'Windows',
    sub: 'Windows 10 / 11',
    icon: <Monitor size={28} strokeWidth={1.5} />,
    accent: '#60a5fa',
    href: `${ASSET_BASE}/VNStudio_${VERSION}_x64-setup.exe`,
    badge: '',
  },
  {
    id: 'linux',
    label: 'Linux',
    sub: 'Ubuntu 22.04+, Debian (.deb)',
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
        <path d="M12 8v4l3 3"/>
      </svg>
    ),
    accent: '#f87171',
    href: `${ASSET_BASE}/VNStudio_${VERSION}_amd64.deb`,
    badge: '',
  },
];

const DownloadPage = () => (
  <motion.div key="download" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
    {/* Header */}
    <section className="section-full section-alt" style={{ paddingTop: '4rem', paddingBottom: '3rem' }}>
      <div className="container-lg text-center">
        <h1 className="text-[44px] md:text-[56px] text-[var(--text-main)] mb-4">Download</h1>
        <p className="text-[17px] text-[var(--text-dim)] max-w-xl mx-auto">
          VisionNodes Studio is free and open source. Download for your platform below,
          or build from source.
        </p>
      </div>
    </section>

    {/* Platform cards */}
    <section className="section-full" style={{ paddingTop: '2.5rem' }}>
      <div className="container-lg">
        <div className="grid md:grid-cols-3 gap-5 mb-12">
          {PLATFORMS.map((p, i) => (
            <motion.a
              key={p.id}
              href={p.href}
              target="_blank"
              rel="noreferrer"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              className="vn-card p-8 text-center block no-underline group"
            >
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-5 transition-transform group-hover:scale-110"
                style={{ backgroundColor: p.accent + '15', color: p.accent }}
              >
                {p.icon}
              </div>
              {p.badge && (
                <span className="inline-block text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full bg-[var(--accent)]/10 text-[var(--accent)] mb-3">
                  {p.badge}
                </span>
              )}
              <h3 className="text-[22px] text-[var(--text-main)] mb-1">{p.label}</h3>
              <p className="text-[13px] text-[var(--text-dim)] mb-6">{p.sub}</p>
              <div className="btn-primary justify-center" style={{ display: 'flex' }}>
                <Download size={15} /> Download
              </div>
            </motion.a>
          ))}
        </div>

        {/* macOS Gatekeeper notice */}
        <div className="vn-card-flat max-w-2xl mx-auto mb-12 p-6 rounded-2xl border border-[#1a1917]/15 bg-[#1a1917]/[0.03]">
          <div className="flex items-start gap-3">
            <Apple size={20} strokeWidth={1.5} className="mt-0.5 shrink-0 text-[var(--text-main)]" />
            <div>
              <h4 className="text-[15px] font-semibold text-[var(--text-main)] mb-1">
                macOS: “VNStudio is damaged and can’t be opened”?
              </h4>
              <p className="text-[13px] text-[var(--text-dim)] mb-3">
                The app is not yet signed with an Apple Developer certificate, so macOS
                Gatekeeper quarantines it. The app is <em>not</em> damaged. Drag it to{' '}
                <span className="font-medium text-[var(--text-main)]">Applications</span>, then
                run this once in Terminal to clear the quarantine flag:
              </p>
              <pre className="text-[12.5px] bg-[var(--bg-alt)] rounded-lg p-3 overflow-x-auto font-mono text-[var(--text-main)] mb-2">
xattr -cr /Applications/VNStudio.app
              </pre>
              <p className="text-[12.5px] text-[var(--text-dim)]">
                Then open it normally. Alternatively: right-click the app →{' '}
                <span className="font-medium">Open</span> → <span className="font-medium">Open</span>.
              </p>
            </div>
          </div>
        </div>

        {/* Sample images */}
        <div className="vn-card-flat p-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 mb-5">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 bg-[var(--accent)]/10 text-[var(--accent)]">
              <ImageIcon size={20} strokeWidth={1.5} />
            </div>
            <div>
              <h3 className="text-[18px] text-[var(--text-main)] mb-1">Demo Images</h3>
              <p className="text-[14px] text-[var(--text-dim)]">
                Sample images used in the built-in templates — rocks, blood cells, roots, portraits and more.
                Drop them in your <code className="text-[var(--text-main)] bg-[var(--bg-alt)] px-1.5 py-0.5 rounded text-[12px]">samples/</code> folder next to the app.
              </p>
            </div>
          </div>
          <a
            href={`${ASSET_BASE}/samples.zip`}
            target="_blank"
            rel="noreferrer"
            className="btn-secondary shrink-0"
          >
            <Download size={15} /> samples.zip
          </a>
        </div>

        {/* Source */}
        <div className="vn-card-flat p-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 bg-[var(--bg-alt)]">
          <div>
            <h3 className="text-[18px] text-[var(--text-main)] mb-1">Build from Source</h3>
            <p className="text-[14px] text-[var(--text-dim)]">
              Full source code on GitHub. Requires Python 3.10+, Node 18+, and Rust for the Tauri shell.
            </p>
          </div>
          <a
            href="https://github.com/Nikos-Unilasalle/VisionNodes"
            target="_blank"
            rel="noreferrer"
            className="btn-secondary shrink-0"
          >
            <Github size={15} /> GitHub Repository <ExternalLink size={12} />
          </a>
        </div>

        {/* Requirements */}
        <div className="mt-8 grid sm:grid-cols-2 gap-4">
          <div className="vn-card p-6">
            <h4 className="text-[15px] text-[var(--text-main)] mb-3">System Requirements</h4>
            <ul className="space-y-1.5 text-[13px] text-[var(--text-dim)]">
              <li>• macOS 12+, Windows 10+, Ubuntu 22.04+</li>
              <li>• 8 GB RAM (16 GB recommended for ML models)</li>
              <li>• 2 GB disk space (+ model files)</li>
              <li>• Camera for live capture nodes (optional)</li>
            </ul>
          </div>
          <div className="vn-card p-6">
            <h4 className="text-[15px] text-[var(--text-main)] mb-3">Bundled Dependencies</h4>
            <ul className="space-y-1.5 text-[13px] text-[var(--text-dim)]">
              <li>• Python 3.10 runtime (self-contained)</li>
              <li>• OpenCV, NumPy, PyTorch (CPU)</li>
              <li>• MediaPipe, EasyOCR auto-install on first use</li>
              <li>• ONNX Runtime for model inference</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  </motion.div>
);

export default DownloadPage;
