import React from 'react';
import { motion } from 'framer-motion';
import { 
  ArrowLeft, Microscope, Zap, Database, BarChart3, 
  CheckCircle2, ShieldCheck, Cpu, Layers, FileText 
} from 'lucide-react';

const BASE = import.meta.env.BASE_URL;

const NODE_DETAILS = [
  { title: "Root Isolation", desc: "Adaptive segmentation of the outer root boundary using morphological operations and edge detection." },
  { title: "Stele Segmentation", desc: "Otsu-based isolation of the vascular cylinder with radial spatial weighting to handle intensity gradients." },
  { title: "Xylem Detection", desc: "Identification of large metaxylem vessels using area and circularity constraints." },
  { title: "Protoxylem Analytics", desc: "Specialized detection of protoxylem poles in the outer stele periphery, filtering out pith cells." },
  { title: "Cortical Cell Analysis", desc: "Detection and measurement of cortical layers, cell wall thickness, and lacunae area." },
  { title: "Anatomy Report", desc: "Consolidated export of 20+ anatomical variables per RootScan standards." }
];

const RootAnatomyInfoPage = ({ onBack }: { onBack: () => void }) => {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }} 
      animate={{ opacity: 1, y: 0 }} 
      exit={{ opacity: 0, y: -20 }}
      className="bg-[var(--bg-main)] min-h-screen pb-20"
    >
      {/* Hero Section */}
      <section className="relative h-[60vh] overflow-hidden flex items-center">
        <div className="absolute inset-0 z-0">
          <img 
            src={`${BASE}marketplace/root_anatomy_hero.png`} 
            alt="Root Anatomy Hero" 
            className="w-full h-full object-cover opacity-40 blur-sm scale-110"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[var(--bg-main)] via-[var(--bg-main)]/80 to-transparent" />
        </div>

        <div className="container-lg relative z-10">
          <button 
            onClick={onBack}
            className="flex items-center gap-2 text-[var(--accent)] font-bold uppercase tracking-widest text-[11px] mb-8 hover:translate-x-[-4px] transition-transform"
          >
            <ArrowLeft size={14} /> Back to Marketplace
          </button>
          
          <div className="max-w-3xl">
            <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-[var(--accent)]/20 rounded-2xl text-[var(--accent)] shadow-2xl shadow-[var(--accent)]/20">
                    <Microscope size={32} />
                </div>
                <span className="text-[var(--text-xdim)] font-black uppercase tracking-[0.3em] text-[12px]">Research Grade Pack</span>
            </div>
            <h1 className="text-[48px] md:text-[64px] text-[var(--text-main)] font-bold leading-tight mb-6">
              Root Anatomy <span className="text-[var(--accent)]">Suite</span>
            </h1>
            <p className="text-[18px] text-[var(--text-dim)] leading-relaxed mb-8">
              A specialized high-throughput phenotyping pipeline developed for agroscience research. 
              Automate the complex task of quantifying root internal structures with precision and speed.
            </p>
          </div>
        </div>
      </section>

      {/* Main Comparison */}
      <section className="container-lg -mt-20 relative z-20 mb-24">
        <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-[40px] overflow-hidden shadow-2xl shadow-black/50">
            <div className="p-2">
                <img 
                    src={`${BASE}marketplace/root_anatomy_hero.png`} 
                    alt="Comparison" 
                    className="w-full rounded-[32px]"
                />
            </div>
            <div className="p-8 md:p-12 grid md:grid-cols-3 gap-10">
                <div className="space-y-4">
                    <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-500">
                        <Zap size={24} />
                    </div>
                    <h3 className="text-[20px] font-bold">Sub-pixel Accuracy</h3>
                    <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">
                        Optimized algorithms for detecting cell walls and vascular boundaries even in low-contrast microscopy images.
                    </p>
                </div>
                <div className="space-y-4">
                    <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-500">
                        <Database size={24} />
                    </div>
                    <h3 className="text-[20px] font-bold">Standardized Reporting</h3>
                    <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">
                        Outputs 20+ anatomical variables compliant with RootScan standards for direct integration into your research data.
                    </p>
                </div>
                <div className="space-y-4">
                    <div className="w-12 h-12 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-500">
                        <Cpu size={24} />
                    </div>
                    <h3 className="text-[20px] font-bold">Fully Automated</h3>
                    <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">
                        Replace hours of manual tracing with a single-click pipeline that processes entire batches of root sections.
                    </p>
                </div>
            </div>
        </div>
      </section>

      {/* Node Details */}
      <section className="container-lg mb-32 pt-24 border-t border-[var(--border)]">
        <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-[32px] font-bold mb-4">Inside the Suite</h2>
            <p className="text-[16px] text-[var(--text-dim)]">13 specialized nodes working in harmony to decode the secrets of root architecture.</p>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {NODE_DETAILS.map((node, i) => (
                <div key={i} className="bg-[var(--bg-alt)] border border-[var(--border)] p-8 rounded-3xl hover:border-[var(--accent)]/50 transition-colors group">
                    <h4 className="text-[18px] font-bold mb-3 group-hover:text-[var(--accent)] transition-colors">{node.title}</h4>
                    <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">{node.desc}</p>
                </div>
            ))}
        </div>
      </section>
    </motion.div>
  );
};

export default RootAnatomyInfoPage;
