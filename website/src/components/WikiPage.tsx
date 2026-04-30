import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Search, PlusCircle } from 'lucide-react';
import nodesData from '../data/nodes.json';
import { NodeCard, CATEGORY_META } from './Layout';
import type { NodeDef, Category } from './Layout';

const ALL_CATS = Object.keys(CATEGORY_META);

const WikiPage = ({ onCommunity }: { onCommunity: () => void }) => {
  const [search, setSearch] = useState('');
  const [activeCat, setActiveCat] = useState<string>('all');

  const categories = nodesData as Category[];

  const filteredCategories = categories
    .filter(c => activeCat === 'all' || c.id === activeCat)
    .map(c => ({
      ...c,
      nodes: c.nodes.filter((n: NodeDef) =>
        (n.label || '').toLowerCase().includes(search.toLowerCase()) ||
        (n.description || '').toLowerCase().includes(search.toLowerCase())
      ),
    }))
    .filter(c => c.nodes.length > 0);

  const totalNodes = categories.reduce((sum, c) => sum + c.nodes.length, 0);

  return (
    <motion.div key="wiki" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      {/* Header */}
      <section className="section-full section-alt" style={{ paddingTop: '4rem', paddingBottom: '3rem' }}>
        <div className="container-lg text-center">
          <h1 className="text-[44px] md:text-[56px] text-[var(--text-main)] mb-4">
            The Node Registry.
          </h1>
          <p className="text-[17px] text-[var(--text-dim)] max-w-2xl mx-auto mb-10">
            A comprehensive catalog of {totalNodes}+ computational units for modular pipeline synthesis.
            Each node exposes typed input/output ports and configurable parameters.
          </p>

          {/* Search */}
          <div className="relative max-w-lg mx-auto mb-8">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-xdim)]" size={17} />
            <input
              type="text"
              placeholder="Search nodes..."
              className="vn-input pl-11 rounded-full text-[15px]"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          {/* Category filter pills */}
          <div className="flex flex-wrap justify-center gap-2">
            <button
              onClick={() => setActiveCat('all')}
              className={`cat-pill transition-all ${
                activeCat === 'all'
                  ? 'bg-[var(--text-main)] text-[var(--bg-main)]'
                  : 'bg-[var(--border)] text-[var(--text-dim)] hover:text-[var(--text-main)]'
              }`}
            >
              All
            </button>
            {categories.map(c => {
              const meta = CATEGORY_META[c.id] || { label: c.id, color: '#9ca3af' };
              return (
                <button
                  key={c.id}
                  onClick={() => setActiveCat(activeCat === c.id ? 'all' : c.id)}
                  className="cat-pill transition-all"
                  style={
                    activeCat === c.id
                      ? { backgroundColor: meta.color, color: '#fff' }
                      : { backgroundColor: meta.color + '22', color: meta.color }
                  }
                >
                  {meta.label}
                  <span className="opacity-60 text-[10px]">{c.nodes.length}</span>
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {/* Nodes grid */}
      <section className="section-full" style={{ paddingTop: '3rem' }}>
        <div className="container-lg space-y-12">
          {filteredCategories.map(cat => {
            const meta = CATEGORY_META[cat.id] || { label: cat.id, color: '#9ca3af' };
            return (
              <div key={cat.id}>
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: meta.color }} />
                  <h2 className="text-[22px] text-[var(--text-main)]">{meta.label}</h2>
                  <span className="text-[13px] text-[var(--text-xdim)] ml-1">{cat.nodes.length} nodes</span>
                  <div className="flex-1 h-px bg-[var(--border)] ml-2" />
                </div>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {cat.nodes.map((node: NodeDef) => (
                    <NodeCard key={node.type} node={node} />
                  ))}
                </div>
              </div>
            );
          })}

          {filteredCategories.length === 0 && (
            <div className="text-center py-20 text-[var(--text-xdim)]">
              <Search size={40} className="mx-auto mb-4 opacity-30" />
              <p>No nodes found for "{search}"</p>
            </div>
          )}
        </div>
      </section>

      {/* CTA */}
      <section className="section-full section-alt">
        <div className="container-md text-center">
          <div className="vn-card-flat p-10 border-dashed border-2 border-[var(--accent)]/30 bg-[var(--accent)]/[0.03]">
            <div className="w-12 h-12 rounded-full bg-[var(--accent)]/10 flex items-center justify-center text-[var(--accent)] mx-auto mb-5">
              <PlusCircle size={22} strokeWidth={1.5} />
            </div>
            <h3 className="text-[22px] text-[var(--text-main)] mb-3">Missing a node?</h3>
            <p className="text-[15px] text-[var(--text-dim)] mb-6 max-w-md mx-auto">
              VisionNodes is built to be extended. Write your own node in Python and share it with the community
              — no C++ compilation, no build system required.
            </p>
            <div className="flex flex-wrap gap-3 justify-center">
              <button
                onClick={onCommunity}
                className="btn-primary"
              >
                Share a Node
              </button>
              <a
                href="https://github.com/Nikos-Unilasalle/VisionNodes"
                target="_blank"
                rel="noreferrer"
                className="btn-secondary"
              >
                Contribution Guide
              </a>
            </div>
          </div>
        </div>
      </section>
    </motion.div>
  );
};

export default WikiPage;
