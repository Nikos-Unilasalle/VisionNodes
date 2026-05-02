import React from 'react';
import { motion } from 'framer-motion';
import { Download, Github, ExternalLink, Apple, Monitor } from 'lucide-react';

const PLATFORMS = [
  {
    id: 'mac',
    label: 'macOS',
    sub: 'Apple Silicon & Intel',
    icon: <Apple size={28} strokeWidth={1.5} />,
    accent: '#1a1917',
    href: 'https://github.com/Nikos-Unilasalle/VisionNodes/releases/latest',
    badge: '',
  },
  {
    id: 'win',
    label: 'Windows',
    sub: 'Windows 10 / 11',
    icon: <Monitor size={28} strokeWidth={1.5} />,
    accent: '#60a5fa',
    href: 'https://github.com/Nikos-Unilasalle/VisionNodes/releases/latest',
    badge: '',
  },
  {
    id: 'linux',
    label: 'Linux',
    sub: 'Ubuntu 22.04+, Debian',
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
        <path d="M12 8v4l3 3"/>
      </svg>
    ),
    accent: '#f87171',
    href: 'https://github.com/Nikos-Unilasalle/VisionNodes/releases/latest',
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
        {/* Coming soon banner */}
        <div className="vn-card-flat max-w-md mx-auto mb-12 p-6 text-center border-dashed border-2 border-[var(--accent)]/30 bg-[var(--accent)]/[0.03] rounded-2xl">
          <div className="text-[32px] mb-2">✨🦦</div>
          <h3 className="text-[18px] font-semibold text-[var(--text-main)] mb-1">Coming Soon!</h3>
          <p className="text-[14px] text-[var(--text-dim)]">
            We are putting the final touches on our standalone executables.<br/> Check back very soon!
          </p>
        </div>
        
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
