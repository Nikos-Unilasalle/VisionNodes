import React from 'react';
import {
  Eye, Save, Maximize, Minimize2, Lock, LockOpen, ChevronsRight,
  Layers, Package, LogIn, LogOut, Plus, RotateCcw
} from 'lucide-react';
import * as N from '../Nodes';
import type { Node } from 'reactflow';

interface ContextMenuProps {
  menu: { id: string; x: number; y: number } | null;
  paneMenu: { x: number; y: number } | null;
  nodes: Node[];
  canVisualize: (id: string) => boolean;
  canSaveAsImage: (id: string) => boolean;
  canBypass: (id: string) => boolean;
  visualizedNodeId: string | null;
  activePaletteIndex: number;
  handleVisualize: (id: string) => void;
  handleSaveAsImage: (id: string) => void;
  pushSnapshot: () => void;
  setViewNodes: (updater: any) => void;
  enterGroup: (id: string) => void;
  ungroupNode: (id: string) => void;
  groupSelectedNodes: () => void;
  handleRotate: (id: string) => void;
  setMenu: (m: any) => void;
  setPaneMenu: (m: any) => void;
  setPreviewNode: (id: string | null) => void;
  setVisualizedNodeId: (id: string | null) => void;
}

const ContextMenu: React.FC<ContextMenuProps> = ({
  menu, paneMenu, nodes, canVisualize, canSaveAsImage, canBypass,
  visualizedNodeId, activePaletteIndex, handleVisualize, handleSaveAsImage,
  pushSnapshot, setViewNodes, enterGroup, ungroupNode, groupSelectedNodes,
  handleRotate, setMenu, setPaneMenu, setPreviewNode, setVisualizedNodeId,
}) => {
  return (
    <>
      {paneMenu && (() => {
        const selCount = nodes.filter(n => n.selected).length;
        return selCount > 1 ? (
          <div
            className="absolute z-[200] bg-[#3d4452]/95 backdrop-blur-xl border border-white/10 shadow-2xl rounded-2xl p-1.5 min-w-[180px] animate-in zoom-in-95 duration-150 origin-top-left"
            style={{ top: paneMenu.y, left: paneMenu.x }}
            onClick={() => setPaneMenu(null)}
          >
            <button
              onClick={() => { groupSelectedNodes(); setPaneMenu(null); }}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-accent rounded-xl text-white text-[11px] font-bold transition-all group"
            >
              <Package size={16} className="text-accent group-hover:text-white" />
              <span>Group selection ({selCount} nodes)</span>
            </button>
          </div>
        ) : null;
      })()}

      {menu && (
        <div
          className="absolute z-[200] bg-[#3d4452]/95 backdrop-blur-xl border border-white/10 shadow-2xl rounded-2xl p-1.5 min-w-[180px] animate-in zoom-in-95 duration-150 origin-top-left"
          style={{ top: menu.y, left: menu.x }}
          onClick={() => setMenu(null)}
        >
          {canVisualize(menu.id) && (
            <>
              <button
                onClick={(e) => { e.stopPropagation(); handleVisualize(menu.id); }}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-accent rounded-xl text-white text-[11px] font-bold transition-all group"
              >
                <Eye size={16} className={visualizedNodeId === menu.id ? "text-yellow-400 group-hover:text-white" : "text-accent group-hover:text-white"} />
                <span>{visualizedNodeId === menu.id ? 'Stop Visualizing' : 'Visualize'}</span>
                <span className="ml-auto text-[9px] text-gray-500 font-mono">↵</span>
              </button>
              <div className="h-px bg-white/5 my-1 mx-2" />
            </>
          )}
          {canSaveAsImage(menu.id) && (
            <button
              onClick={() => handleSaveAsImage(menu.id)}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-accent rounded-xl text-white text-[11px] font-bold transition-all group"
            >
              <Save size={16} className="text-accent group-hover:text-white" />
              <span>Save as Image...</span>
            </button>
          )}
          {(() => {
            const menuNode = nodes.find(n => n.id === menu.id);
            if (menuNode?.type === 'canvas_frame') {
              const isCollapsed = !!(menuNode?.data?.params?.collapsed);
              return (
                <>
                  <div className="h-px bg-white/5 my-1 mx-2" />
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      pushSnapshot();
                      setViewNodes((nds: any) => nds.map((n: any) => {
                        if (n.id !== menu.id) return n;
                        const collapsed = !!(n.data?.params?.collapsed);
                        if (!collapsed) {
                          return { ...n, style: { ...n.style, height: 34 }, data: { ...n.data, params: { ...n.data.params, collapsed: true, savedHeight: (n.style?.height as number) ?? 400 } } };
                        } else {
                          return { ...n, style: { ...n.style, height: (n.data?.params?.savedHeight as number) ?? 400 }, data: { ...n.data, params: { ...n.data.params, collapsed: false } } };
                        }
                      }));
                      setMenu(null);
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-white text-[11px] font-bold transition-all group hover:bg-white/10"
                  >
                    {isCollapsed
                      ? <Maximize size={16} className="text-accent group-hover:text-white" />
                      : <Minimize2 size={16} className="text-accent group-hover:text-white" />}
                    <span>{isCollapsed ? 'Déplier' : 'Replier'}</span>
                  </button>
                </>
              );
            }
            const isUiNode = ['canvas_note', 'canvas_reroute'].includes(menuNode?.type || '');
            if (isUiNode) return null;
            const isLocked = !!(menuNode?.data as any)?.lockedOut;
            const isBypassed = !!(menuNode?.data as any)?.bypassed;
            const isMinified = !!(menuNode?.data as any)?.minified;
            return (
              <>
                <div className="h-px bg-white/5 my-1 mx-2" />
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    pushSnapshot();
                    setViewNodes((nds: any) => nds.map((n: any) => n.id === menu.id
                      ? { ...n, data: { ...n.data, lockedOut: !isLocked } }
                      : n
                    ));
                    setMenu(null);
                  }}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-white text-[11px] font-bold transition-all group ${isLocked ? 'bg-red-500/20 hover:bg-red-500/80' : 'hover:bg-red-500/80'}`}
                >
                  {isLocked
                    ? <LockOpen size={16} className="text-red-400 group-hover:text-white" />
                    : <Lock    size={16} className="text-red-400 group-hover:text-white" />}
                  <span>{isLocked ? 'Unlock Output' : 'Lock Out'}</span>
                  <span className="ml-auto text-[9px] text-gray-500 font-mono">⌘⇥</span>
                </button>
                {canBypass(menu.id) && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      pushSnapshot();
                      setViewNodes((nds: any) => nds.map((n: any) => n.id === menu.id
                        ? { ...n, data: { ...n.data, bypassed: !isBypassed } }
                        : n
                      ));
                      setMenu(null);
                    }}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-white text-[11px] font-bold transition-all group ${isBypassed ? 'bg-gray-500/30 hover:bg-gray-500/60' : 'hover:bg-gray-500/60'}`}
                  >
                    <ChevronsRight size={16} className="text-gray-400 group-hover:text-white" />
                    <span>{isBypassed ? 'Remove Bypass' : 'Bypass'}</span>
                    <span className="ml-auto text-[9px] text-gray-500 font-mono">⌘B</span>
                  </button>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    pushSnapshot();
                    setViewNodes((nds: any) => nds.map((n: any) => {
                      if (!n.selected && n.id !== menu.id) return n;
                      if (n.type === 'canvas_frame') return n;
                      const isMinified = !!(n.data as any)?.minified;
                      if (!isMinified) {
                        // Minifying: Save current height and set to 24
                        return { 
                          ...n, 
                          style: { ...n.style, height: 24 }, 
                          data: { ...n.data, minified: true, savedHeight: n.style?.height } 
                        };
                      } else {
                        // Expanding: Restore height
                        return { 
                          ...n, 
                          style: { ...n.style, height: n.data?.savedHeight }, 
                          data: { ...n.data, minified: false } 
                        };
                      }
                    }));
                    setMenu(null);
                  }}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-white text-[11px] font-bold transition-all group ${isMinified ? 'bg-purple-500/30 hover:bg-purple-500/60' : 'hover:bg-purple-500/60'}`}
                >
                  <Layers size={16} className="text-purple-400 group-hover:text-white" />
                  <span>{isMinified ? 'Expand Nodes' : 'Mininode'}</span>
                  <span className="ml-auto text-[9px] text-gray-500 font-mono">⇥</span>
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleRotate(menu.id); }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-white/10 rounded-xl text-white text-[11px] font-bold transition-all group"
                >
                  <RotateCcw size={16} className="text-gray-400 group-hover:text-white" />
                  <span>Rotate</span>
                  <span className="ml-auto text-[9px] text-gray-500 font-mono">⌘R</span>
                </button>
              </>
            );
          })()}

          <div className="h-px bg-white/5 my-1 mx-2" />

          {(() => {
            const isMultiSel = nodes.find(n => n.id === menu.id)?.selected && nodes.filter(n => n.selected).length > 1;
            const colorTargetIds = isMultiSel ? new Set(nodes.filter(n => n.selected).map(n => n.id)) : new Set([menu.id]);
            return (
              <div className="px-3 py-2 flex items-center justify-center gap-1.5 flex-wrap">
                {N.PALETTES[activePaletteIndex].colors.map((c: any, i: number) => (
                  <button
                    key={i}
                    onClick={(e) => {
                      e.stopPropagation();
                      setViewNodes((nds: any) => nds.map((n: any) => colorTargetIds.has(n.id) ? { ...n, data: { ...n.data, params: { ...n.data.params, color_index: i, bg_color: undefined, text_color: undefined } } } : n));
                    }}
                    className="w-4 h-4 rounded-full border border-black/20 shadow-sm hover:scale-125 transition-transform"
                    style={{ backgroundColor: c.bg }}
                  />
                ))}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setViewNodes((nds: any) => nds.map((n: any) => colorTargetIds.has(n.id) ? { ...n, data: { ...n.data, params: { ...n.data.params, color_index: undefined, bg_color: undefined, text_color: undefined } } } : n));
                  }}
                  className="w-4 h-4 rounded-full border border-white/20 hover:bg-white/10 hover:text-white transition-all flex items-center justify-center text-[10px] text-gray-500 bg-transparent shrink-0"
                >
                  ×
                </button>
              </div>
            );
          })()}
          <div className="h-px bg-white/5 my-1 mx-2" />

          {nodes.find(n => n.id === menu.id)?.type === 'group_node' ? (
            <>
              <button
                onClick={() => { enterGroup(menu.id); setMenu(null); }}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-accent rounded-xl text-white text-[11px] font-bold transition-all group"
              >
                <LogIn size={16} className="text-accent group-hover:text-white" />
                <span>Enter Group</span>
              </button>
              <button
                onClick={() => { ungroupNode(menu.id); setMenu(null); }}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-accent rounded-xl text-white text-[11px] font-bold transition-all group"
              >
                <LogOut size={16} className="text-accent group-hover:text-white" />
                <span>Ungroup</span>
              </button>
            </>
          ) : (() => {
            const selCount = nodes.filter(n => n.selected).length;
            const isInSelection = nodes.find(n => n.id === menu.id)?.selected;
            const multiSel = selCount > 1 && isInSelection;
            if (!multiSel) return null;
            return (
              <button
                onClick={() => { groupSelectedNodes(); setMenu(null); }}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-accent rounded-xl text-white text-[11px] font-bold transition-all group"
              >
                <Package size={16} className="text-accent group-hover:text-white" />
                <span>Group selection ({selCount} nodes)</span>
              </button>
            );
          })()}
          <div className="h-px bg-white/5 my-1 mx-2" />

          <button
            onClick={() => {
              pushSnapshot();
              if (menu.id === visualizedNodeId) { setVisualizedNodeId(null); setPreviewNode(null); }
              setViewNodes((nds: any) => nds.filter((n: any) => n.id !== menu.id));
            }}
            className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-red-500 rounded-xl text-white text-[11px] font-bold transition-all group"
          >
            <Plus size={16} className="text-red-500 group-hover:text-white rotate-45" />
            <span>Delete</span>
            <span className="ml-auto text-[9px] text-gray-500 font-mono">⌫</span>
          </button>
        </div>
      )}
    </>
  );
};

export default ContextMenu;
