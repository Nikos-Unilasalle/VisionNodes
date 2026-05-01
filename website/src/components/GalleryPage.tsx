import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Filter, Download, ExternalLink, Box, FileCode, Users } from 'lucide-react';
import communityData from '../data/community.json';

const BASE = import.meta.env.BASE_URL;

const DOMAINS = [
  'All Domains',
  'Satellite & Earth Observation', 'Medical & Health Sciences', 'Agricultural & Plant Sciences',
  'Material Sciences & Microscopy', 'Industrial Inspection & QC', 'Language & Text Sciences',
  'Environmental & Marine Sciences', 'Data Science & Analytics', 'Robotics & Autonomous Systems',
  'Signal Processing & Physics', 'Human-Computer Interaction', 'Research & Education',
];

const GalleryPage = () => {
  const [filterType, setFilterType] = useState<'all' | 'vn' | 'py'>('all');
  const [filterDomain, setFilterDomain] = useState('All Domains');
  const [search, setSearch] = useState('');

  const filtered = communityData.filter(item => {
    const matchesType = filterType === 'all' || item.type === filterType;
    const matchesDomain = filterDomain === 'All Domains' || item.domains.includes(filterDomain);
    const matchesSearch = item.title.toLowerCase().includes(search.toLowerCase()) || 
                         item.description.toLowerCase().includes(search.toLowerCase());
    return matchesType && matchesDomain && matchesSearch;
  });

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      {/* Header */}
      <section className="section-full section-alt" style={{ paddingTop: '4rem', paddingBottom: '3rem' }}>
        <div className="container-lg">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
            <div>
              <h1 className="text-[44px] md:text-[56px] text-[var(--text-main)] mb-4">Community Gallery</h1>
              <p className="text-[17px] text-[var(--text-dim)] max-w-2xl leading-relaxed">
                Explore pipelines and custom nodes created by the VisionNodes community. 
                Download and import them directly into your Studio.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Filters & Search */}
      <section className="sticky top-[105px] z-30 bg-[var(--bg-main)]/80 backdrop-blur-xl border-b border-[var(--border)] py-4">
        <div className="container-lg">
          <div className="flex flex-col lg:flex-row gap-4 items-center justify-between">
            <div className="flex flex-wrap gap-2 items-center">
              {/* Type Filter */}
              <div className="flex bg-[var(--bg-alt)] p-1 rounded-xl border border-[var(--border)]">
                {(['all', 'vn', 'py'] as const).map(t => (
                  <button
                    key={t}
                    onClick={() => setFilterType(t)}
                    className={`px-4 py-1.5 rounded-lg text-[13px] font-semibold transition-all ${
                      filterType === t ? 'bg-[var(--accent)] text-white shadow-lg' : 'text-[var(--text-dim)] hover:text-[var(--text-main)]'
                    }`}
                  >
                    {t === 'all' ? 'All' : t === 'vn' ? 'Pipelines' : 'Nodes'}
                  </button>
                ))}
              </div>

              {/* Domain Filter */}
              <select 
                value={filterDomain}
                onChange={(e) => setFilterDomain(e.target.value)}
                className="bg-[var(--bg-alt)] border border-[var(--border)] rounded-xl px-4 py-2 text-[13px] font-semibold text-[var(--text-main)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
              >
                {DOMAINS.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>

            {/* Search */}
            <div className="relative w-full lg:w-96">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-xdim)]" size={16} />
              <input
                type="text"
                placeholder="Search community creations..."
                className="w-full bg-[var(--bg-alt)] border border-[var(--border)] rounded-xl pl-11 pr-4 py-2.5 text-[14px] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] transition-all"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
          </div>
        </div>
      </section>

      {/* Gallery Grid */}
      <section className="section-full min-h-[60vh]">
        <div className="container-lg">
          {filtered.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              <AnimatePresence mode="popLayout">
                {filtered.map((item) => (
                  <motion.div
                    key={item.id}
                    layout
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    className="group bg-[var(--bg-card)] border border-[var(--border)] rounded-3xl overflow-hidden hover:border-[var(--accent)] transition-all hover:shadow-2xl hover:shadow-[var(--accent)]/10"
                  >
                    {/* Image Area */}
                    <div className="relative aspect-video overflow-hidden bg-[var(--bg-alt)]">
                      <img 
                        src={item.image.startsWith('http') ? item.image : `${BASE}${item.image}`} 
                        alt={item.title}
                        className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                      <div className="absolute top-4 left-4 flex gap-2">
                        <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest text-white shadow-lg ${
                          item.type === 'vn' ? 'bg-[#83b817]' : 'bg-[#60a5fa]'
                        }`}>
                          {item.type === 'vn' ? 'Pipeline' : 'Node'}
                        </span>
                      </div>
                    </div>

                    {/* Content */}
                    <div className="p-6">
                      <div className="flex items-center gap-2 text-[11px] text-[var(--accent)] font-bold uppercase tracking-wider mb-2">
                        {item.domains.slice(0, 2).map(d => (
                          <span key={d} className="flex items-center gap-1">
                            <div className="w-1 h-1 rounded-full bg-[var(--accent)]" /> {d}
                          </span>
                        ))}
                      </div>
                      <h3 className="text-[20px] font-bold text-[var(--text-main)] mb-2 group-hover:text-[var(--accent)] transition-colors">
                        {item.title}
                      </h3>
                      <p className="text-[14px] text-[var(--text-dim)] line-clamp-2 mb-6 leading-relaxed">
                        {item.description}
                      </p>

                      <div className="flex items-center justify-between border-t border-[var(--border)] pt-5">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 rounded-full bg-[var(--bg-alt)] border border-[var(--border)] flex items-center justify-center text-[12px] font-bold text-[var(--text-main)]">
                            {item.author[1].toUpperCase()}
                          </div>
                          <span className="text-[13px] font-medium text-[var(--text-dim)]">{item.author}</span>
                        </div>
                        {/* @ts-ignore */}
                        {item.integrated ? (
                          <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[var(--bg-alt)] border border-[var(--border)] text-[13px] font-bold text-[var(--accent)] opacity-80 cursor-default">
                            <Box size={14} /> Integrated
                          </div>
                        ) : (
                          <a 
                            href={item.fileUrl} 
                            download
                            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[var(--bg-alt)] border border-[var(--border)] text-[13px] font-bold text-[var(--text-main)] hover:bg-[var(--accent)] hover:text-white hover:border-[var(--accent)] transition-all active:scale-95"
                          >
                            <Download size={14} /> Download
                          </a>
                        )}
                      </div>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          ) : (
            <div className="text-center py-20">
              <div className="w-20 h-20 bg-[var(--bg-alt)] rounded-full flex items-center justify-center mx-auto mb-6 text-[var(--text-xdim)]">
                <Search size={32} />
              </div>
              <h3 className="text-[24px] text-[var(--text-main)] mb-2">No results found</h3>
              <p className="text-[var(--text-dim)]">Try adjusting your filters or search terms.</p>
            </div>
          )}
        </div>
      </section>
    </motion.div>
  );
};

export default GalleryPage;
