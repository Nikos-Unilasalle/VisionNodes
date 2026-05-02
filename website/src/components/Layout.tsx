import React, { useState, useEffect, useRef } from 'react';
const BASE = import.meta.env.BASE_URL;
import { motion, AnimatePresence } from 'framer-motion';
import * as LucideIcons from 'lucide-react';
import {
  Download, Github, Book, Play, Search, ChevronRight, Menu, X,
  Zap, Cpu, Layers, Monitor, FileCode, DownloadCloud, Globe,
  ArrowRight, CheckCircle2, Upload, ExternalLink, GitBranch,
  Microscope, GraduationCap, Terminal, Code2, Users, Sun, Moon,
  Box, Image, Camera, ScanLine, Activity, Filter, Shuffle,
  BarChart2, Database, Scissors, Grid, Palette, Eye, RefreshCw,
  PlusCircle, Sparkles, MousePointer2
} from 'lucide-react';
import nodesData from '../data/nodes.json';

// ─── Types ──────────────────────────────────────────────────────────────────

type Tab = 'home' | 'about' | 'wiki' | 'tutorials' | 'community' | 'gallery' | 'admin' | 'download' | 'privacy';

interface Port {
  id: string;
  color: string;
  label?: string;
}

interface NodeDef {
  type: string;
  label: string;
  category: string;
  icon: string;
  description: string;
  inputs?: Port[];
  outputs?: Port[];
}

interface Category {
  id: string;
  label: string;
  nodes: NodeDef[];
}

// ─── Constants ───────────────────────────────────────────────────────────────

const PORT_COLORS: Record<string, string> = {
  image:   '#a3d154',
  scalar:  '#f87171',
  vector:  '#60a5fa',
  boolean: '#facc15',
  string:  '#c084fc',
  dict:    '#fb923c',
  list:    '#fb923c',
  any:     '#9ca3af',
  mask:    '#fbbf24',
  audio:   '#818cf8',
};

const CATEGORY_META: Record<string, { label: string; color: string }> = {
  src:       { label: 'Sources',      color: '#facc15' },
  cv:        { label: 'Vision',       color: '#a3d154' },
  mask:      { label: 'Masking',      color: '#fbbf24' },
  geom:      { label: 'Geometry',     color: '#2dd4bf' },
  track:     { label: 'Tracking',     color: '#60a5fa' },
  features:  { label: 'Features',     color: '#fb923c' },
  analysis:  { label: 'Analysis',     color: '#34d399' },
  visualize: { label: 'Visualize',    color: '#38bdf8' },
  draw:      { label: 'Drawing',      color: '#f472b6' },
  util:      { label: 'Utilities',    color: '#9ca3af' },
  math:      { label: 'Math',         color: '#f87171' },
  strings:   { label: 'Strings',      color: '#22d3ee' },
  logic:     { label: 'Logic',        color: '#c084fc' },
  blend:     { label: 'Blending',     color: '#a78bfa' },
  out:       { label: 'Output',       color: '#818cf8' },
  canvas:    { label: 'Canvas',       color: '#a3e635' },
  noise:     { label: 'Noise',        color: '#e879f9' },
  ocr:       { label: 'OCR',          color: '#4ade80' },
  data:      { label: 'Data',         color: '#f97316' },
  audio:     { label: 'Audio',        color: '#818cf8' },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getPortColor(type: string): string {
  const key = (type || 'any').toLowerCase().replace(/\s/g, '');
  for (const [k, v] of Object.entries(PORT_COLORS)) {
    if (key.includes(k)) return v;
  }
  return PORT_COLORS.any;
}

function getLucideIcon(name: string, size = 18, color = 'currentColor') {
  const Icon = (LucideIcons as any)[name];
  if (!Icon) return <Box size={size} color={color} strokeWidth={1.5} />;
  return <Icon size={size} color={color} strokeWidth={1.5} />;
}

// ─── MacOs Window Frame ──────────────────────────────────────────────────────

const MacOsWindow = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`macos-window ${className}`}>
    <div className="macos-header">
      <div className="macos-dots">
        <div className="macos-dot red" />
        <div className="macos-dot yellow" />
        <div className="macos-dot green" />
      </div>
    </div>
    <div className="macos-content">
      {children}
    </div>
  </div>
);

// ─── Global Nav ──────────────────────────────────────────────────────────────

const GlobalNav = ({ onTabChange }: { onTabChange?: (t: Tab) => void }) => (
  <nav className="global-nav">
    <div className="container-lg w-full flex items-center justify-between">
      <div className="flex items-center gap-8">
        <a href="https://www.unilasalle.fr/la-recherche-unilasalle" target="_blank" rel="noreferrer"
           className="hidden md:block text-white/50 hover:text-white/80 transition-colors text-xs no-underline">
          Research
        </a>
        <button onClick={() => onTabChange?.('community')}
                className="hidden md:block text-white/50 hover:text-white/80 transition-colors text-xs">
          Community
        </button>
        <a href="https://www.openaccess.nl/en" target="_blank" rel="noreferrer"
           className="hidden md:block text-white/50 hover:text-white/80 transition-colors text-xs no-underline">
          Open Source
        </a>
      </div>
      <div className="flex items-center gap-5">
        <a href="https://github.com/Nikos-Unilasalle/VisionNodes" target="_blank" rel="noreferrer"
           className="text-white/50 hover:text-white/80 transition-colors">
          <Github size={14} />
        </a>
      </div>
    </div>
  </nav>
);

// ─── Sub Nav ─────────────────────────────────────────────────────────────────

const TABS: { id: Tab; label: string }[] = [
  { id: 'home',      label: 'Overview'  },
  { id: 'about',     label: 'About'     },
  { id: 'wiki',      label: 'Node Wiki' },
  { id: 'gallery',   label: 'Gallery'   },
  { id: 'tutorials', label: 'Tutorials' },
  { id: 'community', label: 'Share'     },
  { id: 'download',  label: 'Download'  },
];

const SubNav = ({ activeTab, setActiveTab }: { activeTab: Tab; setActiveTab: (t: Tab) => void }) => {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="sub-nav">
      <div className="container-lg w-full flex items-center justify-between">
        {/* Brand */}
        <button
          onClick={() => setActiveTab('home')}
          className="flex items-center gap-3 text-[19px] font-semibold tracking-tight text-[var(--text-main)] hover:text-[var(--accent)] transition-colors group"
          style={{ fontFamily: 'Rubik, sans-serif' }}
        >
          <img src={`${BASE}logo.svg`} alt="VN" className="w-8 h-8 transition-transform group-hover:scale-110" />
          VisionNodes Studio
        </button>

        {/* Desktop tabs */}
        <div className="hidden sm:flex items-center gap-1">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-3 py-1.5 rounded-lg text-[13px] font-semibold transition-all ${
                activeTab === t.id
                  ? 'bg-[var(--accent)] text-white'
                  : 'text-[var(--text-dim)] hover:text-[var(--text-main)] hover:bg-[var(--border)]'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Mobile burger */}
        <button className="sm:hidden" onClick={() => setMobileOpen(!mobileOpen)}>
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="sm:hidden absolute top-full left-0 right-0 bg-[var(--bg-main)] border-b border-[var(--border)] px-4 py-3 flex flex-col gap-1 z-50"
          >
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => { setActiveTab(t.id); setMobileOpen(false); }}
                className={`px-3 py-2 rounded-lg text-[14px] text-left font-semibold transition-all ${
                  activeTab === t.id ? 'bg-[var(--accent)] text-white' : 'text-[var(--text-dim)]'
                }`}
              >
                {t.label}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
};

// ─── Port Dot ────────────────────────────────────────────────────────────────

const PortDot = ({ port, dir }: { port: Port; dir: 'in' | 'out' }) => {
  const color = getPortColor(port.color);
  const label = port.label || port.id;
  const typeLabel = port.color || 'any';

  return (
    <div className="port-dot" style={{ backgroundColor: color }} title={`${dir === 'in' ? '▶' : '◀'} ${label} (${typeLabel})`}>
      <span className="port-tooltip">{dir === 'in' ? '▶' : '◀'} {label} · {typeLabel}</span>
    </div>
  );
};

// ─── Node Card (Wiki) ─────────────────────────────────────────────────────────

const NodeCard = ({ node }: { node: NodeDef }) => {
  const meta = CATEGORY_META[node.category] || { label: node.category, color: '#9ca3af' };
  const iconColor = meta.color;

  return (
    <div className="node-card">
      {/* Header row */}
      <div className="flex items-start gap-3">
        <div
          className="node-icon-wrap"
          style={{ backgroundColor: iconColor + '22' }}
        >
          {getLucideIcon(node.icon, 18, iconColor)}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-[14px] font-semibold text-[var(--text-main)] leading-tight truncate"
              style={{ fontFamily: 'Rubik, sans-serif' }}>
            {node.label}
          </h4>
          <span
            className="cat-pill mt-1"
            style={{ backgroundColor: meta.color + '20', color: meta.color }}
          >
            {meta.label}
          </span>
        </div>
      </div>

      {/* Description */}
      <p className="text-[12px] leading-relaxed text-[var(--text-dim)] flex-1">
        {node.description}
      </p>

      {/* Ports */}
      {((node.inputs && node.inputs.length > 0) || (node.outputs && node.outputs.length > 0)) && (
        <div className="border-t border-[var(--border)] pt-2 flex items-center justify-between gap-2">
          <div className="port-row">
            {(node.inputs || []).map((p, i) => <PortDot key={i} port={p} dir="in" />)}
          </div>
          <span className="text-[9px] text-[var(--text-xdim)] font-mono tracking-widest">→</span>
          <div className="port-row">
            {(node.outputs || []).map((p, i) => <PortDot key={i} port={p} dir="out" />)}
          </div>
        </div>
      )}
    </div>
  );
};

// ─── Slideshow ───────────────────────────────────────────────────────────────

const SLIDES = [
  { src: `${BASE}slides/slide1.jpg`, alt: 'Face Detection Pipeline' },
  { src: `${BASE}slides/slide2.jpg`, alt: 'Geospatial Analysis' },
  { src: `${BASE}slides/slide3.jpg`, alt: 'Object Tracking' },
  { src: `${BASE}slides/slide4.jpg`, alt: 'Complex Graph Logic' },
  { src: `${BASE}slides/slide5.jpg`, alt: 'Real-time Camera Processing' },
];

const Slideshow = () => {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrent((prev) => (prev + 1) % SLIDES.length);
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="relative aspect-video overflow-hidden">
      <AnimatePresence initial={false}>
        <motion.img
          key={current}
          src={SLIDES[current].src}
          alt={SLIDES[current].alt}
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '-100%' }}
          transition={{ duration: 0.7, ease: [0.32, 0.72, 0, 1] }}
          className="absolute inset-0 w-full h-full object-cover"
        />
      </AnimatePresence>

      {/* Manual Navigation Dots */}
      <div className="absolute bottom-4 left-6 flex gap-2 z-20">
        {SLIDES.map((_, i) => (
          <button
            key={i}
            onClick={() => setCurrent(i)}
            className={`w-2 h-2 rounded-full transition-all ${
              current === i 
                ? 'bg-[var(--accent)] w-6' 
                : 'bg-white/30 hover:bg-white/60'
            }`}
            aria-label={`Go to slide ${i + 1}`}
          />
        ))}
      </div>
    </div>
  );
};

// ─── Hero Section ─────────────────────────────────────────────────────────────

const HeroSection = ({ onDownload }: { onDownload: () => void }) => (
  <section className="section-full" style={{ paddingTop: '5rem', paddingBottom: '4rem' }}>
    <div className="container-lg text-center">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: 'easeOut' }}
      >
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent)]/10 border border-[var(--accent)]/20 text-[var(--accent)] text-[11px] font-bold uppercase tracking-widest mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
          Version alpha 0.8
        </div>

        <div className="flex flex-col md:flex-row items-center justify-center gap-6 mb-4">
          <img src={`${BASE}logo.svg`} alt="VisionNodes Logo" className="w-20 h-20 md:w-28 md:h-28" />
          <h1 className="text-[52px] md:text-[72px] font-normal text-[var(--text-main)] leading-none">
            VisionNodes Studio
          </h1>
        </div>
        <p className="text-[20px] md:text-[24px] text-[var(--text-dim)] mb-3 font-normal">
          The node-based development environment for rapid prototyping<br className="hidden md:block" /> of Computer Vision &amp; AI pipelines.
        </p>
        <p className="text-[15px] text-[var(--text-xdim)] max-w-2xl mx-auto mb-10 leading-relaxed">
          Developed by the <strong className="text-[var(--text-dim)]">Apex team at UniLaSalle Polytechnic Institute</strong>.
          Free, open-source, and built for researchers, engineers and students.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-4 mb-16">
          <button onClick={onDownload} className="btn-primary text-[15px]">
            <Download size={16} /> Download for free
          </button>
          <a href="https://github.com/Nikos-Unilasalle/VisionNodes" target="_blank" rel="noreferrer"
             className="btn-secondary text-[15px]">
            <Github size={16} /> View on GitHub
          </a>
        </div>

        {/* Cover slideshow */}
        <div className="relative max-w-5xl mx-auto">
          <MacOsWindow className="relative z-10 overflow-hidden">
            <Slideshow />
          </MacOsWindow>
        </div>
      </motion.div>
    </div>
  </section>
);

// ─── Manifesto Section ────────────────────────────────────────────────────────

const ManifestoSection = () => (
  <section className="section-full section-alt">
    <div className="container-md text-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
      >
        <h2 className="text-[36px] md:text-[44px] text-[var(--text-main)] mb-8">
          From debugging boilerplate<br />to algorithmic discovery.
        </h2>
        <div className="space-y-5 text-[17px] text-[var(--text-dim)] leading-relaxed max-w-3xl mx-auto text-justify">
          <p>
            VisionNodes Studio eliminates the overhead of iterative code compilation and environment management,
            allowing researchers and engineers to focus entirely on the exploration and validation of computer vision algorithms.
            Every parameter change propagates through the execution graph in real time, providing immediate visual feedback
            that accelerates the hypothesis-to-result cycle.
          </p>
          <p>
            First and foremost, VisionNodes Studio is a <strong className="text-[var(--text-main)]">robust research environment</strong>.
            It allows scientists and engineers to give birth to sophisticated algorithms through direct, real-time practice,
            accelerating the path from hypothesis to discovery. Beyond its core research capabilities,
            it serves as an exceptional platform for <strong className="text-[var(--text-main)]">teaching complex sciences</strong> and
            delivering high-impact presentations at <strong className="text-[var(--text-main)]">international conferences and colloquia</strong>,
            transforming abstract theories into tangible, interactive results.
          </p>
        </div>
      </motion.div>
    </div>
  </section>
);

// ─── Features Section ─────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: <Layers size={22} strokeWidth={1.5} />,
    title: 'Modular Orchestration',
    text: 'Abstract complexity into atomic, composable units. Construct pipelines of arbitrary depth from a library of 200+ production-ready nodes spanning CV, ML inference, signal processing, and data utilities.',
  },
  {
    icon: <Zap size={22} strokeWidth={1.5} />,
    title: 'Deterministic Runtime',
    text: 'Stateful execution graphs with guaranteed reproducibility. Multi-modal inference with OpenCV, PyTorch, MediaPipe, and ONNX backends. Real-time throughput at camera frame rate.',
  },
  {
    icon: <Code2 size={22} strokeWidth={1.5} />,
    title: 'Native Extensibility',
    text: 'Extend the library with a single Python decorator. The plugin API exposes typed inputs/outputs, parameter definitions, and lifecycle hooks — no build step, no restart required.',
  },
  {
    icon: <Terminal size={22} strokeWidth={1.5} />,
    title: 'Python Export',
    text: 'Export visual pipelines into standalone Python scripts. VisionNodes automatically resolves dependencies and generates the necessary code, bridging the gap between prototyping and deployment.',
  },
];

const FeaturesSection = () => (
  <section className="section-full">
    <div className="container-lg">
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
        {FEATURES.map((f, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
            className="vn-card p-7"
          >
            <div className="w-10 h-10 rounded-xl bg-[var(--accent)]/10 flex items-center justify-center text-[var(--accent)] mb-5">
              {f.icon}
            </div>
            <h3 className="text-[18px] text-[var(--text-main)] mb-3">{f.title}</h3>
            <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">{f.text}</p>
          </motion.div>
        ))}
      </div>
    </div>
  </section>
);

// ─── Institutional Section ────────────────────────────────────────────────────

const InstitutionalSection = () => (
  <section className="section-full section-alt">
    <div className="container-lg">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="vn-card-flat overflow-hidden relative"
      >
        {/* Campus background */}
        <div className="absolute inset-0">
          <img src={`${BASE}campus.jpg`} alt="Campus" className="w-full h-full object-cover opacity-[0.12]" />
          <div className="absolute inset-0 bg-gradient-to-r from-[var(--bg-card)] via-[var(--bg-card)]/90 to-[var(--bg-card)]/60" />
        </div>

        {/* Content */}
        <div className="relative z-10 p-10 md:p-14">
          <p className="text-[11px] font-bold uppercase tracking-widest text-[var(--accent)] mb-4">Research Origin</p>
          <h2 className="text-[28px] md:text-[36px] text-[var(--text-main)] mb-4">
            Apex — UniLaSalle
          </h2>
          <p className="text-[16px] text-[var(--text-dim)] max-w-2xl leading-relaxed mb-10">
            VisionNodes Studio is an initiative born from the research and innovation of the Apex team
            at UniLaSalle Polytechnic Institute, dedicated to pushing the boundaries of real-time
            computer vision for scientific and industrial applications.
          </p>

          {/* Logos */}
          <div className="flex items-center gap-10 flex-wrap">
            <img src={`${BASE}unilasalle.png`} alt="UniLaSalle" className="h-14 md:h-16 object-contain" />
            <img
              src={`${BASE}apex.png`}
              alt="Apex"
              className="h-14 md:h-16 object-contain"
              style={{ filter: 'invert(40%) sepia(80%) saturate(2000%) hue-rotate(5deg) brightness(90%) contrast(100%)' }}
            />
          </div>
        </div>
      </motion.div>
    </div>
  </section>
);

// ─── Home Page ────────────────────────────────────────────────────────────────

const HomePage = ({ onDownload }: { onDownload: () => void }) => (
  <motion.div key="home" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
    <HeroSection onDownload={onDownload} />
    <ManifestoSection />
    <FeaturesSection />
    <InstitutionalSection />
  </motion.div>
);

export { HomePage, GlobalNav, SubNav, NodeCard, PortDot, MacOsWindow, CATEGORY_META, PORT_COLORS, getLucideIcon, getPortColor };
export type { Tab, NodeDef, Category, Port };
