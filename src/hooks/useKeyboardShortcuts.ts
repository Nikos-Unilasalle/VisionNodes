import { useEffect, useCallback } from 'react';
import { getCurrentWindow } from '@tauri-apps/api/window';

export function useKeyboardShortcuts({
  copyNodes,
  pasteNodes,
  duplicateNodes,
  handleUndo,
  handleRedo,
  pushSnapshot,
  setViewNodes,
  nodesRef,
  instance,
  groupSelectedNodes,
  exitGroup,
  groupStackRef,
  canBypass,
  setIsAddMenuOpen,
  saveProject,
  loadProject,
  setPendingConnection,
  handleRotate,
  handleVisualize,
}: any) {

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const cmdKey = isMac ? e.metaKey : e.ctrlKey;

      if (cmdKey && e.key === 'c') copyNodes();
      if (cmdKey && e.key === 'v') pasteNodes();
      if (cmdKey && !e.shiftKey && e.key === 'z') { e.preventDefault(); handleUndo(); }
      if (cmdKey && e.shiftKey && e.key === 'z') { e.preventDefault(); handleRedo(); }
      if (cmdKey && e.key.toLowerCase() === 'd') {
        e.preventDefault();
        duplicateNodes();
      }
      if (cmdKey && e.key.toLowerCase() === 'm') { e.preventDefault(); setIsAddMenuOpen(prev => !prev); }
      if (cmdKey && e.key.toLowerCase() === 'a') {
        e.preventDefault();
        setViewNodes((nds: any) => nds.map((n: any) => ({ ...n, selected: true })));
      }
      if (cmdKey && e.key.toLowerCase() === 'g') {
        e.preventDefault();
        groupSelectedNodes();
      }
      if (cmdKey && e.key.toLowerCase() === 'o') { e.preventDefault(); loadProject(); }
      if (cmdKey && e.key.toLowerCase() === 's') { e.preventDefault(); saveProject(); }
      if (cmdKey && e.shiftKey && e.key.toLowerCase() === 'f') {
        e.preventDefault();
        getCurrentWindow().isFullscreen().then(is => getCurrentWindow().setFullscreen(!is));
      }
      if (cmdKey && !e.shiftKey && e.key.toLowerCase() === 'f') {
        e.preventDefault();
        const selectedIds = nodesRef.current.filter((n: any) => n.selected).map((n: any) => ({ id: n.id }));
        if (selectedIds.length > 0) {
          instance?.fitView({ nodes: selectedIds, duration: 350, padding: 0.15 });
        } else {
          instance?.fitView({ duration: 350 });
        }
      }

      if (e.key === 'Tab' && !e.shiftKey) {
        e.preventDefault();
        const selectedNodes = nodesRef.current.filter((n: any) => n.selected);
        if (selectedNodes.length > 0) {
          if (cmdKey) {
            pushSnapshot();
            setViewNodes((nds: any) => nds.map((n: any) => {
              if (!n.selected) return n;
              const isUiNode = ['canvas_frame', 'canvas_note', 'canvas_reroute'].includes(n.type || '');
              if (isUiNode) return n;
              const isLocked = !!(n.data as any)?.lockedOut;
              return { ...n, data: { ...n.data, lockedOut: !isLocked } };
            }));
          } else {
            pushSnapshot();
            setViewNodes((nds: any) => nds.map((n: any) => {
              if (!n.selected) return n;
              if (n.type === 'canvas_frame') {
                const collapsed = !!(n.data?.params?.collapsed);
                if (!collapsed) {
                  return { ...n, style: { ...n.style, height: 34 }, data: { ...n.data, params: { ...n.data.params, collapsed: true, savedHeight: (n.style?.height as number) ?? 400 } } };
                } else {
                  return { ...n, style: { ...n.style, height: (n.data?.params?.savedHeight as number) ?? 400 }, data: { ...n.data, params: { ...n.data.params, collapsed: false } } };
                }
              }
              const isMinified = !!(n.data as any)?.minified;
              return { ...n, data: { ...n.data, minified: !isMinified } };
            }));
          }
        } else if (groupStackRef.current.length > 0) {
          exitGroup();
        } else {
          setIsAddMenuOpen(false);
          setPendingConnection(null);
        }
      }
      if (cmdKey && e.key.toLowerCase() === 'r') {
        e.preventDefault();
        handleRotate();
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        const selectedNode = nodesRef.current.find((n: any) => n.selected);
        if (selectedNode) {
          handleVisualize(selectedNode.id);
        }
      }
      if (e.key === 'b' && cmdKey) {
        e.preventDefault();
        const selectedNode = nodesRef.current.find((n: any) => n.selected);
        if (selectedNode && canBypass(selectedNode.id)) {
          const isBypassed = !!(selectedNode.data as any)?.bypassed;
          pushSnapshot();
          setViewNodes((nds: any) => nds.map((n: any) => n.id === selectedNode.id
            ? { ...n, data: { ...n.data, bypassed: !isBypassed } }
            : n
          ));
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [copyNodes, pasteNodes, duplicateNodes, handleUndo, handleRedo, instance, groupSelectedNodes, exitGroup, pushSnapshot, setViewNodes, canBypass, saveProject, loadProject, setIsAddMenuOpen, setPendingConnection, nodesRef, groupStackRef, handleRotate, handleVisualize]);
}
