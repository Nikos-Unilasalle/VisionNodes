import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Filter, ShoppingBag, ExternalLink, Box, Heart, ShieldCheck, Microscope, Info } from 'lucide-react';
import marketplaceData from '../data/marketplace.json';

const BASE = import.meta.env.BASE_URL;

const DOMAINS = [
  'All Domains',
  'Veterinary', 'Agroscience', 'Geology', 'Health', 'Nutrition', 'Security', 'Electronics'
];

const MarketplacePage = ({ onProductClick }: { onProductClick: (link: string) => void }) => {
  const [filterDomain, setFilterDomain] = useState('All Domains');
  const [search, setSearch] = useState('');

  const filtered = marketplaceData.filter(item => {
    const matchesDomain = filterDomain === 'All Domains' || item.domains.includes(filterDomain);
    const matchesSearch = item.title.toLowerCase().includes(search.toLowerCase()) || 
                         item.description.toLowerCase().includes(search.toLowerCase());
    return matchesDomain && matchesSearch;
  });

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      {/* Hero / Banner Section */}
      <section className="section-full relative overflow-hidden" style={{ paddingTop: '5rem', paddingBottom: '4rem', background: 'linear-gradient(135deg, var(--bg-alt) 0%, var(--bg-main) 100%)' }}>
        <div className="absolute top-0 right-0 w-1/3 h-full opacity-10 pointer-events-none">
            <ShoppingBag size={400} className="text-[var(--accent)] translate-x-1/2 -translate-y-1/4 rotate-12" />
        </div>
        
        <div className="container-lg relative z-10">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent)]/10 border border-[var(--accent)]/20 text-[var(--accent)] text-[11px] font-bold uppercase tracking-widest mb-6">
              <ShoppingBag size={12} /> Marketplace
            </div>
            <h1 className="text-[44px] md:text-[64px] text-[var(--text-main)] mb-6 leading-tight">
              Specialized AI <span className="text-[var(--accent)]">Solutions</span>
            </h1>
            <p className="text-[18px] text-[var(--text-dim)] mb-8 leading-relaxed">
              Explore high-precision AI nodes developed by UniLaSalle's research units and industry partners. 
              Acquire specialized intelligence for your specific scientific or industrial needs.
            </p>
          </div>

          {/* Impact Banner */}
          <div className="bg-[var(--bg-card)] border border-[var(--accent)]/30 rounded-3xl p-6 md:p-8 flex flex-col md:flex-row items-center gap-6 shadow-2xl shadow-[var(--accent)]/5">
            <div className="w-16 h-16 rounded-2xl bg-[var(--accent)]/10 flex items-center justify-center text-[var(--accent)] shrink-0">
              <Heart size={32} />
            </div>
            <div>
              <h3 className="text-[18px] font-bold text-[var(--text-main)] mb-2">Supporting Research & Education</h3>
              <p className="text-[14px] text-[var(--text-dim)] leading-relaxed">
                UniLaSalle is a <strong>non-profit association</strong>. By acquiring these models, you are directly contributing 
                to financing our research units and supporting the next generation of engineers and PhD students across our 
                campuses in veterinary science, agroscience, geology, health, and electronics.
              </p>
            </div>
            <div className="shrink-0 flex gap-4">
                <img src={`${BASE}unilasalle.png`} alt="UniLaSalle" className="h-10 opacity-80" />
            </div>
          </div>
        </div>
      </section>

      {/* Filters & Search */}
      <section className="sticky top-[105px] z-30 bg-[var(--bg-main)]/80 backdrop-blur-xl border-b border-[var(--border)] py-4">
        <div className="container-lg">
          <div className="flex flex-col lg:flex-row gap-4 items-center justify-between">
            <div className="flex flex-wrap gap-3 items-center">
              <span className="text-[12px] font-bold uppercase tracking-widest text-[var(--text-xdim)] flex items-center gap-2">
                <Filter size={14} /> Filter by field:
              </span>
              <div className="flex flex-wrap gap-2">
                {DOMAINS.map(d => (
                  <button
                    key={d}
                    onClick={() => setFilterDomain(d)}
                    className={`px-4 py-1.5 rounded-xl text-[13px] font-semibold transition-all border ${
                      filterDomain === d 
                        ? 'bg-[var(--accent)] text-white border-[var(--accent)] shadow-lg shadow-[var(--accent)]/20' 
                        : 'bg-[var(--bg-alt)] text-[var(--text-dim)] border-[var(--border)] hover:text-[var(--text-main)] hover:border(--text-dim)]'
                    }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>

            {/* Search */}
            <div className="relative w-full lg:w-80">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-xdim)]" size={16} />
              <input
                type="text"
                placeholder="Search models..."
                className="w-full bg-[var(--bg-alt)] border border-[var(--border)] rounded-xl pl-11 pr-4 py-1.5 text-[14px] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] transition-all"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
          </div>
        </div>
      </section>

      {/* Marketplace Grid */}
      <section className="section-full min-h-[60vh]">
        <div className="container-lg">
          {filtered.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              <AnimatePresence mode="popLayout">
                {filtered.map((item) => (
                  <motion.div
                    key={item.id}
                    layout
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    onClick={() => item.link && onProductClick(item.link)}
                    className={`group bg-[var(--bg-card)] border border-[var(--border)] rounded-3xl overflow-hidden hover:border-[var(--accent)] transition-all hover:shadow-2xl hover:shadow-[var(--accent)]/10 flex flex-col ${item.link ? 'cursor-pointer' : ''}`}
                  >
                    {/* Image Area */}
                    <div className="relative aspect-[16/10] overflow-hidden bg-[var(--bg-alt)]">
                      <img 
                        src={item.image.startsWith('http') ? item.image : `${BASE}${item.image}`} 
                        alt={item.title}
                        className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-[var(--bg-card)] via-transparent to-transparent opacity-60" />
                      
                      <div className="absolute top-4 left-4">
                        <span className="px-3 py-1 rounded-full bg-black/50 backdrop-blur-md text-[10px] font-black uppercase tracking-widest text-white border border-white/10">
                          {item.type === 'vn' ? 'Pipeline Bundle' : 'Custom Node'}
                        </span>
                      </div>

                      <div className="absolute top-4 right-4">
                        <div className="bg-[var(--accent)] text-white px-3 py-1 rounded-lg text-[14px] font-bold shadow-lg">
                          {item.price}
                        </div>
                      </div>
                    </div>

                    {/* Content */}
                    <div className="p-6 flex-1 flex flex-col">
                      <div className="flex items-center gap-2 text-[11px] text-[var(--accent)] font-bold uppercase tracking-wider mb-2">
                        {item.domains.map(d => (
                          <span key={d} className="flex items-center gap-1">
                            <ShieldCheck size={12} /> {d}
                          </span>
                        ))}
                      </div>
                      <h3 className="text-[22px] font-bold text-[var(--text-main)] mb-3 group-hover:text-[var(--accent)] transition-colors">
                        {item.title}
                      </h3>
                      <p className="text-[14px] text-[var(--text-dim)] mb-6 leading-relaxed flex-1">
                        {item.description}
                      </p>

                      {/* Features mini-list */}
                      <div className="flex flex-wrap gap-2 mb-6">
                          {item.features.map((f: string) => (
                              <span key={f} className="text-[10px] bg-[var(--bg-alt)] text-[var(--text-xdim)] px-2 py-1 rounded-md border border-[var(--border)]">
                                  {f}
                              </span>
                          ))}
                      </div>

                      <div className="flex items-center justify-between border-t border-[var(--border)] pt-5">
                        <div className="flex flex-col max-w-[60%]">
                          <span className="text-[10px] text-[var(--text-xdim)] uppercase font-bold tracking-widest">Provider</span>
                          <span className="text-[12px] font-semibold text-[var(--text-dim)] truncate" title={item.author}>{item.author}</span>
                        </div>
                        
                        <div className="flex gap-2">
                          <button 
                            onClick={(e) => { e.stopPropagation(); }}
                            className="relative group/btn flex items-center justify-center px-5 py-2.5 rounded-xl bg-[var(--bg-alt)] border border-[var(--border)] text-[var(--text-xdim)] text-[14px] font-bold transition-all overflow-hidden cursor-not-allowed grayscale"
                          >
                            <span className="group-hover/btn:opacity-0 transition-opacity duration-200">Acquire</span>
                            <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover/btn:opacity-100 transition-opacity duration-200 text-[var(--accent)]">
                              Coming soon!
                            </span>
                          </button>
                        </div>
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
              <h3 className="text-[24px] text-[var(--text-main)] mb-2">No models found</h3>
              <p className="text-[var(--text-dim)]">Try adjusting your filters or search terms.</p>
            </div>
          )}
        </div>
      </section>

      {/* Partner Section */}
      <section className="section-full section-alt">
          <div className="container-md text-center">
              <div className="w-16 h-16 rounded-full bg-[var(--bg-alt)] border border-[var(--border)] flex items-center justify-center mx-auto mb-6">
                  <Info size={24} className="text-[var(--accent)]" />
              </div>
              <h2 className="text-[32px] text-[var(--text-main)] mb-6">Want to sell your models?</h2>
              <p className="text-[17px] text-[var(--text-dim)] mb-10 leading-relaxed">
                  Are you another school, a research laboratory or a company? 
                  Join our marketplace and reach a community of scientists and engineers worldwide. 
                  VisionNodes Studio is the perfect platform to distribute your specialized AI expertise.
              </p>
              <button className="btn-secondary">
                  Contact the Apex Team
              </button>
          </div>
      </section>
    </motion.div>
  );
};

export default MarketplacePage;
