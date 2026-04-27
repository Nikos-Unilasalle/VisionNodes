import React, { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { GlobalNav, SubNav, HomePage } from './components/Layout';
import WikiPage from './components/WikiPage';
import TutorialsPage from './components/TutorialsPage';
import CommunityPage from './components/CommunityPage';
import DownloadPage from './components/DownloadPage';
import type { Tab } from './components/Layout';

// ─── Footer ──────────────────────────────────────────────────────────────────

const Footer = ({ setActiveTab }: { setActiveTab: (t: Tab) => void }) => (
  <footer style={{ background: 'var(--bg-alt)', borderTop: '1px solid var(--border)' }}
          className="py-14 px-6">
    <div className="container-lg">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-10 mb-10 text-[12px]">
        <div className="space-y-3">
          <p className="font-bold text-[var(--text-main)] uppercase tracking-widest text-[10px]">Product</p>
          {[
            { label: 'Overview',  tab: 'home'      as Tab },
            { label: 'Node Wiki', tab: 'wiki'      as Tab },
            { label: 'Tutorials', tab: 'tutorials' as Tab },
            { label: 'Download',  tab: 'download'  as Tab },
          ].map(l => (
            <button key={l.label} onClick={() => setActiveTab(l.tab)}
                    className="block text-[var(--text-dim)] hover:text-[var(--text-main)] transition-colors">
              {l.label}
            </button>
          ))}
        </div>
        <div className="space-y-3">
          <p className="font-bold text-[var(--text-main)] uppercase tracking-widest text-[10px]">Community</p>
          {[
            { label: 'Share a Node / Pipeline', tab: 'community' as Tab },
          ].map(l => (
            <button key={l.label} onClick={() => setActiveTab(l.tab)}
                    className="block text-[var(--text-dim)] hover:text-[var(--text-main)] transition-colors">
              {l.label}
            </button>
          ))}
          <a href="https://github.com/Nikos-Unilasalle/VisionNodes/issues"
             target="_blank" rel="noreferrer"
             className="block text-[var(--text-dim)] hover:text-[var(--text-main)] transition-colors">
            GitHub Issues
          </a>
          <a href="https://github.com/Nikos-Unilasalle/VisionNodes/discussions"
             target="_blank" rel="noreferrer"
             className="block text-[var(--text-dim)] hover:text-[var(--text-main)] transition-colors">
            Discussions
          </a>
        </div>
        <div className="space-y-3">
          <p className="font-bold text-[var(--text-main)] uppercase tracking-widest text-[10px]">Research</p>
          <span className="block text-[var(--text-dim)]">UniLaSalle Polytechnic</span>
          <span className="block text-[var(--text-dim)]">Apex Research Team</span>
          <a href="https://github.com/Nikos-Unilasalle/VisionNodes"
             target="_blank" rel="noreferrer"
             className="block text-[var(--text-dim)] hover:text-[var(--text-main)] transition-colors">
            GitHub Source
          </a>
        </div>
        <div className="space-y-3">
          <p className="font-bold text-[var(--text-main)] uppercase tracking-widest text-[10px]">Legal</p>
          <span className="block text-[var(--text-dim)]">Open Source (MIT)</span>
          <span className="block text-[var(--text-dim)]">Privacy Policy</span>
        </div>
      </div>

      <div className="border-t border-[var(--border)] pt-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 text-[11px] text-[var(--text-xdim)]">
        <div className="flex items-center gap-3">
          <img src="/logo.svg" alt="VN" className="w-4 h-4 opacity-50" />
          <span>© 2026 VisionNodes Studio — An Apex · UniLaSalle initiative.</span>
        </div>
        <span>Free and open source software.</span>
      </div>
    </div>
  </footer>
);

// ─── App ──────────────────────────────────────────────────────────────────────

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('home');

  const goTo = (t: Tab) => {
    setActiveTab(t);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-main)', color: 'var(--text-main)' }}>
      <GlobalNav />
      <SubNav activeTab={activeTab} setActiveTab={goTo} />

      <main>
        <AnimatePresence mode="wait">
          {activeTab === 'home'      && <HomePage      key="home"      onDownload={() => goTo('download')} />}
          {activeTab === 'wiki'      && <WikiPage      key="wiki"      onCommunity={() => goTo('community')} />}
          {activeTab === 'tutorials' && <TutorialsPage key="tutorials" />}
          {activeTab === 'community' && <CommunityPage key="community" />}
          {activeTab === 'download'  && <DownloadPage  key="download"  />}
        </AnimatePresence>
      </main>

      <Footer setActiveTab={goTo} />
    </div>
  );
}
