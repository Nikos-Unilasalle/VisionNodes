import React, { useState } from 'react';
import { Search } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface CategoryNode {
  type: string;
  label: string;
  description?: string;
  schema?: any;
}

interface Category {
  id: string;
  label: string;
  icon: LucideIcon;
  nodes: CategoryNode[];
  section?: 'generic' | 'domain';
}

interface AddNodeMenuProps {
  isOpen: boolean;
  onClose: (e?: any) => void;
  dynamicCategories: Category[];
  activeCategoryId: string;
  setActiveCategoryId: (id: string) => void;
  addNode: (type: string, label: string, schema?: any) => void;
}

const AddNodeMenu: React.FC<AddNodeMenuProps> = ({
  isOpen,
  onClose,
  dynamicCategories,
  activeCategoryId,
  setActiveCategoryId,
  addNode,
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  const activeCategory = dynamicCategories.find(c => c.id === activeCategoryId) || dynamicCategories[0];

  const filteredNodes = (() => {
    if (!searchQuery) return activeCategory.nodes;
    const all = dynamicCategories.flatMap(c => c.nodes);
    const unique = Array.from(new Map(all.map(n => [n.type, n])).values());
    return unique.filter(n => n.label.toLowerCase().includes(searchQuery.toLowerCase()));
  })();

  if (!isOpen) return null;

  return (
    <div className="absolute inset-0 bg-black/80 backdrop-blur-md z-[100] flex items-center justify-center p-20" onClick={(e) => onClose(e)}>
      <div 
        className="bg-[#3d4452] border border-[#4f5b6b] w-full max-w-[700px] h-[85vh] rounded-3xl shadow-2xl flex overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={e => e.stopPropagation()}
      >
        <div className="w-56 bg-[#1e2530] border-r border-[#4f5b6b] p-6 flex flex-col gap-1 overflow-y-auto custom-scrollbar">
          {(() => {
            const sections: Array<{ key: string; label: string; cats: Category[] }> = [
              { key: 'generic', label: 'Generic', cats: dynamicCategories.filter(c => !c.section || c.section === 'generic') },
              { key: 'domain',  label: 'Domain',  cats: dynamicCategories.filter(c => c.section === 'domain') },
            ];
            return sections.map(({ key, label, cats }) => cats.length === 0 ? null : (
              <div key={key}>
                <div className="text-[8px] font-black uppercase tracking-[0.2em] text-gray-600 px-4 pt-4 pb-2">
                  {label}
                </div>
                {cats.map(cat => (
                  <button
                    key={cat.id} onClick={() => setActiveCategoryId(cat.id)}
                    className={`w-full flex items-center gap-4 px-4 py-3 rounded-2xl text-[11px] font-bold transition-all ${activeCategoryId === cat.id ? 'bg-accent text-white shadow-xl shadow-accent/20' : 'text-gray-500 hover:bg-white/5'}`}
                  >
                    <cat.icon size={18} /> {cat.label}
                  </button>
                ))}
              </div>
            ));
          })()}
        </div>
        <div className="flex-1 p-12 overflow-y-auto overflow-x-hidden flex flex-col">
          <div className="flex items-center justify-between mb-10 border-b border-[#4f5b6b] pb-4">
            <h3 className="text-[10px] font-black text-gray-400 uppercase tracking-widest">
              {searchQuery ? 'Search Results' : `Category :: ${activeCategory.label}`}
            </h3>
            <div className="relative group">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 group-focus-within:text-accent transition-colors" />
              <input 
                autoFocus
                type="text" 
                placeholder="Search modules..." 
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="bg-black/40 border border-[#4f5b6b] rounded-xl pl-10 pr-4 py-2 text-[11px] text-white outline-none focus:border-accent/50 w-64 transition-all"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {filteredNodes.map((node: any) => (
              <button
                key={node.type} onClick={() => { addNode(node.type, node.label, node.schema); setSearchQuery(''); }}
                className="p-6 bg-[#333942] hover:bg-accent/10 border border-[#4f5b6b] hover:border-accent/40 rounded-3xl text-left transition-all active:scale-95 group"
              >
                <div className="text-[11px] font-bold text-gray-200 uppercase tracking-tighter group-hover:text-accent transition-colors">{node.label}</div>
                <div className="text-[8px] text-gray-400 font-mono mt-1 italic">{node.schema ? 'cv::plugin' : 'cv::node'}</div>
              </button>
            ))}
          </div>
          {filteredNodes.length === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-700 gap-4 opacity-50 italic py-20">
              <Search size={48} strokeWidth={1} />
              <div className="text-[11px] font-bold uppercase tracking-widest">No modules found matching "{searchQuery}"</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AddNodeMenu;
