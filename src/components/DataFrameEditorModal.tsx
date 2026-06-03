import React, { useEffect, useRef, useState, useMemo } from 'react';
import ReactDOM from 'react-dom';
import { X, Search, ChevronLeft, ChevronRight, RotateCcw, Edit2, AlertCircle } from 'lucide-react';

interface DataFrameEditorModalProps {
  label: string;
  dfMeta?: {
    shape: [number, number];
    columns: string[];
    dtypes: Record<string, string>;
    nulls: Record<string, number>;
    rows: Record<string, any>[];
    truncated?: boolean;
  };
  edits: any[];
  onChange: (newEdits: any[]) => void;
  onClose: () => void;
}

export function DataFrameEditorModal({ label, dfMeta, edits, onChange, onClose }: DataFrameEditorModalProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [editingCell, setEditingCell] = useState<{ rowIndex: any; colName: string } | null>(null);
  const [tempValue, setTempValue] = useState('');
  
  const itemsPerPage = 15;
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input on edit start
  useEffect(() => {
    if (editingCell && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingCell]);

  // Keyboard: Escape to close modal (if not editing a cell)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (editingCell) {
          setEditingCell(null);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose, editingCell]);

  // Handle cell edit save
  const handleSaveCell = (rowIndex: any, colName: string, value: string) => {
    const existingIdx = edits.findIndex(e => e.index === rowIndex && e.col === colName);
    let newEdits = [...edits];
    if (existingIdx >= 0) {
      newEdits[existingIdx] = { index: rowIndex, col: colName, val: value };
    } else {
      newEdits.push({ index: rowIndex, col: colName, val: value });
    }
    onChange(newEdits);
    setEditingCell(null);
  };

  const handleResetAll = () => {
    if (confirm("Voulez-vous vraiment réinitialiser toutes les modifications sur ce DataFrame ?")) {
      onChange([]);
    }
  };

  const columns = dfMeta?.columns || [];
  const rows = dfMeta?.rows || [];
  const dtypes = dfMeta?.dtypes || {};
  const shape = dfMeta?.shape || [0, 0];

  // Client-side search filtering
  const filteredRows = useMemo(() => {
    if (!searchQuery) return rows;
    const query = searchQuery.toLowerCase();
    return rows.filter(row => {
      return Object.entries(row).some(([key, val]) => {
        if (key === '__row_index__') return false;
        return String(val ?? '').toLowerCase().includes(query);
      });
    });
  }, [rows, searchQuery]);

  // Pagination calculation
  const totalPages = Math.max(1, Math.ceil(filteredRows.length / itemsPerPage));
  
  // Reset page when search query changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  const paginatedRows = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredRows.slice(start, start + itemsPerPage);
  }, [filteredRows, currentPage]);

  const dtypeColor = (t: string) => {
    if (!t) return 'text-gray-500';
    if (t.startsWith('int') || t.startsWith('float') || t.startsWith('complex')) return 'text-blue-400';
    if (t.startsWith('bool')) return 'text-emerald-400';
    if (t === 'object' || t.startsWith('str')) return 'text-amber-400';
    if (t.startsWith('datetime')) return 'text-purple-400';
    return 'text-gray-400';
  };

  const modal = (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-6 md:p-12 pointer-events-none select-none">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm pointer-events-auto cursor-pointer"
        onClick={onClose}
      />
      
      {/* Modal Container */}
      <div className="w-full h-full max-w-[1400px] max-h-[850px] flex flex-col bg-[#0d1117] rounded-2xl border border-white/10 shadow-2xl overflow-hidden pointer-events-auto relative z-10">
        
        {/* Top Header */}
        <div className="flex items-center justify-between px-6 h-14 bg-[#161b22] border-b border-white/10 shrink-0 select-none">
          <div className="flex items-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-orange-500 shadow-[0_0_10px_rgba(249,115,22,0.6)]" />
            <span className="text-xs text-gray-200 font-bold tracking-wide">{label}</span>
            <span className="text-[10px] font-mono text-orange-400/80 bg-orange-950/30 border border-orange-500/20 px-2 py-0.5 rounded">
              {shape[0].toLocaleString()} rows × {shape[1]} cols
            </span>
            {dfMeta?.truncated && (
              <span className="text-[10px] text-amber-400 flex items-center gap-1 bg-amber-950/20 px-2 py-0.5 rounded border border-amber-500/20">
                <AlertCircle size={10} /> Visualisation limitée aux 5 000 premières lignes
              </span>
            )}
          </div>
          
          <button
            onClick={onClose}
            aria-label="Fermer"
            className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-white/10 transition-all"
          >
            <X size={18} />
          </button>
        </div>

        {/* Action Controls Bar */}
        <div className="flex items-center justify-between px-6 py-3 bg-[#0d1117] border-b border-white/5 shrink-0 gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-500" />
            <input
              type="text"
              placeholder="Rechercher dans les données..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-[#161b22] text-xs text-gray-200 pl-9 pr-4 py-2 rounded-xl border border-white/10 focus:border-orange-500/50 focus:outline-none placeholder-gray-500 transition-colors"
            />
          </div>

          <div className="flex items-center gap-3">
            {edits.length > 0 && (
              <span className="text-[10px] font-mono text-orange-400 bg-orange-950/30 border border-orange-500/20 px-2 py-1 rounded-xl">
                {edits.length} cellule(s) modifiée(s)
              </span>
            )}
            
            <button
              onClick={handleResetAll}
              disabled={edits.length === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-white/10 bg-[#161b22] text-xs text-gray-400 hover:text-orange-400 disabled:text-gray-600 hover:border-orange-500/20 disabled:hover:border-white/10 hover:bg-orange-950/10 disabled:hover:bg-[#161b22] disabled:opacity-40 transition-all font-semibold"
            >
              <RotateCcw size={12} /> Réinitialiser
            </button>
          </div>
        </div>

        {/* Data Grid Table Area */}
        <div className="flex-1 overflow-auto bg-[#0d1117] min-h-0">
          <table className="w-full border-collapse text-left select-text">
            <thead className="sticky top-0 bg-[#161b22] border-b border-white/10 z-20">
              <tr>
                <th className="px-4 py-2.5 text-[10px] font-bold text-gray-500 font-mono w-16 text-center select-none">
                  INDEX
                </th>
                {columns.map(col => (
                  <th key={col} className="px-4 py-2.5 border-l border-white/5 select-none">
                    <div className="flex flex-col">
                      <span className="text-[11px] font-bold text-gray-300 truncate max-w-[200px]" title={col}>
                        {col}
                      </span>
                      <span className={`text-[9px] font-mono font-medium ${dtypeColor(dtypes[col])}`}>
                        {dtypes[col] || 'unknown'}
                      </span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            
            <tbody className="divide-y divide-white/5">
              {paginatedRows.length > 0 ? (
                paginatedRows.map((row, rIdx) => {
                  const actualIndex = row.__row_index__;
                  return (
                    <tr key={actualIndex} className="hover:bg-white/[0.02] transition-colors">
                      {/* Index Column */}
                      <td className="px-4 py-2 text-center text-[10px] font-mono text-gray-500 bg-[#161b22]/30 select-none">
                        {actualIndex}
                      </td>
                      
                      {/* Cell Data Columns */}
                      {columns.map(col => {
                        const isEditing = editingCell?.rowIndex === actualIndex && editingCell?.colName === col;
                        const isEdited = edits.some(e => e.index === actualIndex && e.col === col);
                        const cellVal = row[col];
                        
                        return (
                          <td 
                            key={col} 
                            className={`px-4 py-2 text-xs font-mono border-l border-white/5 relative min-w-[120px] max-w-[300px] truncate ${
                              isEdited ? 'bg-orange-500/5 text-orange-300 font-semibold' : 'text-gray-300'
                            }`}
                            onDoubleClick={() => {
                              setEditingCell({ rowIndex: actualIndex, colName: col });
                              setTempValue(cellVal === null || cellVal === undefined ? '' : String(cellVal));
                            }}
                          >
                            {/* Orange side indicator if edited */}
                            {isEdited && (
                              <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-orange-500" />
                            )}
                            
                            {isEditing ? (
                              <input
                                ref={inputRef}
                                type="text"
                                value={tempValue}
                                onChange={e => setTempValue(e.target.value)}
                                onBlur={() => handleSaveCell(actualIndex, col, tempValue)}
                                onKeyDown={e => {
                                  if (e.key === 'Enter') handleSaveCell(actualIndex, col, tempValue);
                                  else if (e.key === 'Escape') setEditingCell(null);
                                }}
                                className="w-full bg-[#161b22] text-xs text-orange-300 font-mono py-0.5 px-1 rounded border border-orange-500/50 focus:outline-none"
                              />
                            ) : (
                              <div className="flex items-center justify-between group/cell">
                                <span className="truncate">
                                  {cellVal === null || cellVal === undefined ? (
                                    <span className="text-gray-600 italic select-none">NaN</span>
                                  ) : (
                                    String(cellVal)
                                  )}
                                </span>
                                <Edit2 size={10} className="text-gray-600 opacity-0 group-hover/cell:opacity-100 transition-opacity ml-1.5 shrink-0 select-none cursor-pointer" />
                              </div>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={columns.length + 1} className="text-center py-12 text-xs text-gray-500 select-none">
                    Aucun résultat correspondant à votre recherche
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Footer Pagination Controls */}
        <div className="flex items-center justify-between px-6 h-12 bg-[#161b22] border-t border-white/10 shrink-0 select-none">
          <span className="text-[10px] text-gray-500">
            Lignes {Math.min(filteredRows.length, (currentPage - 1) * itemsPerPage + 1)} à {Math.min(filteredRows.length, currentPage * itemsPerPage)} sur {filteredRows.length}
          </span>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="p-1 rounded bg-white/5 border border-white/10 text-gray-400 hover:text-white disabled:text-gray-600 disabled:opacity-40 disabled:hover:text-gray-600 transition-colors"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-xs text-gray-400 px-2 font-medium">
              Page {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="p-1 rounded bg-white/5 border border-white/10 text-gray-400 hover:text-white disabled:text-gray-600 disabled:opacity-40 disabled:hover:text-gray-600 transition-colors"
            >
              <ChevronRight size={16} />
            </button>
          </div>

          <span className="text-[10px] text-gray-500">
            Double-cliquer pour modifier · Enter pour valider
          </span>
        </div>

      </div>
    </div>
  );

  return ReactDOM.createPortal(modal, document.body);
}
