import { useCallback } from 'react';
import { save, open } from '@tauri-apps/plugin-dialog';
import { writeTextFile, readTextFile, rename, readDir } from '@tauri-apps/plugin-fs';

export function useFileOperations({
  canvasNodes,
  canvasEdges,
  activeFilePath,
  setActiveFilePath,
  pushNotification,
  setNodes,
  setEdges,
  setGroupStack,
  groupStackRef,
  updateGraph,
  setPreviewSize,
  setPreviewPos,
  setActivePaletteIndex,
  setVisualizedNodeId,
  setPreviewNode,
  workDir,
  refreshWorkDir,
  previewSize,
  previewPos,
  activePaletteIndex,
  visualizedNodeId,
  confirmUnsaved,
}: any) {

  const buildProjectContent = useCallback(() => {
    const ui = { previewSize, previewPos, activePaletteIndex, visualizedNodeId };
    return JSON.stringify({ nodes: canvasNodes, edges: canvasEdges, ui }, null, 2);
  }, [canvasNodes, canvasEdges, previewSize, previewPos, activePaletteIndex, visualizedNodeId]);

  const saveProject = useCallback(async () => {
    try {
      let path = activeFilePath;
      if (!path) {
        path = await save({
          defaultPath: 'project.vn',
          filters: [{ name: 'VisionNodes Project', extensions: ['vn'] }]
        });
      }
      if (path) {
        await writeTextFile(path, buildProjectContent());
        setActiveFilePath(path);
        pushNotification(`Saved → ${path.split(/[\\/]/).pop()}`, 'info');
        if (workDir && path.startsWith(workDir)) refreshWorkDir(workDir);
      }
    } catch (err) {
      console.error('Failed to save project:', err);
      pushNotification('Save failed — see console', 'error');
    }
  }, [activeFilePath, buildProjectContent, setActiveFilePath, pushNotification, workDir, refreshWorkDir]);

  const saveProjectAs = useCallback(async () => {
    try {
      const path = await save({
        defaultPath: activeFilePath ? activeFilePath.split(/[\\/]/).pop()! : 'project.vn',
        filters: [{ name: 'VisionNodes Project', extensions: ['vn'] }]
      });
      if (path) {
        await writeTextFile(path, buildProjectContent());
        setActiveFilePath(path);
        pushNotification(`Saved As → ${path.split(/[\\/]/).pop()}`, 'info');
        if (workDir && path.startsWith(workDir)) refreshWorkDir(workDir);
      }
    } catch (err) {
      console.error('Failed to save project as:', err);
      pushNotification('Save As failed — see console', 'error');
    }
  }, [activeFilePath, buildProjectContent, setActiveFilePath, pushNotification, workDir, refreshWorkDir]);

  const saveProjectIncremental = useCallback(async () => {
    try {
      let basePath: string | null = activeFilePath;
      if (!basePath) {
        basePath = await save({
          defaultPath: 'project.vn',
          filters: [{ name: 'VisionNodes Project', extensions: ['vn'] }]
        });
        if (!basePath) return;
        await writeTextFile(basePath, buildProjectContent());
        setActiveFilePath(basePath);
        return;
      }

      const lastSlash = Math.max(basePath.lastIndexOf('/'), basePath.lastIndexOf('\\'));
      const dir = basePath.slice(0, lastSlash + 1);
      const filename = basePath.slice(lastSlash + 1).replace(/\.vn$/i, '');

      const numMatch = filename.match(/^(.*?) (\d+)$/);
      if (numMatch) {
        const stem = numMatch[1];
        const nextN = parseInt(numMatch[2], 10) + 1;
        const nextPath = `${dir}${stem} ${String(nextN).padStart(2, '0')}.vn`;
        await writeTextFile(nextPath, buildProjectContent());
        setActiveFilePath(nextPath);
        pushNotification(`Saved → ${nextPath.split(/[\\/]/).pop()}`, 'info');
        if (workDir && nextPath.startsWith(workDir)) refreshWorkDir(workDir);
      } else {
        const path01 = `${dir}${filename} 01.vn`;
        const path02 = `${dir}${filename} 02.vn`;
        await rename(basePath, path01);
        await writeTextFile(path02, buildProjectContent());
        setActiveFilePath(path02);
        pushNotification(`Renamed → ${path01.split(/[\\/]/).pop()} · Saved → ${path02.split(/[\\/]/).pop()}`, 'info');
        if (workDir && path02.startsWith(workDir)) refreshWorkDir(workDir);
      }
    } catch (err) {
      console.error('Failed incremental save:', err);
      pushNotification('Incremental save failed — see console', 'error');
    }
  }, [activeFilePath, buildProjectContent, setActiveFilePath, pushNotification, workDir, refreshWorkDir]);

  const loadProjectFromPath = useCallback(async (filePath: string) => {
    try {
      const content = await readTextFile(filePath);
      const { nodes: rawNodes, edges: newEdges, ui } = JSON.parse(content);
      const newNodes = rawNodes.map((n: any) =>
        n.type === 'canvas_reroute' ? { ...n, style: { ...n.style, width: 8, height: (typeof n.style?.height === 'number' && n.style.height >= 24) ? n.style.height : 48 } } : n
      );
      setGroupStack([]); groupStackRef.current = [];
      setNodes(newNodes); setEdges(newEdges); setActiveFilePath(filePath);
      if (ui) {
        if (ui.previewSize) setPreviewSize(ui.previewSize);
        if (ui.previewPos) setPreviewPos(ui.previewPos);
        if (ui.activePaletteIndex !== undefined) setActivePaletteIndex(ui.activePaletteIndex);
        if (ui.visualizedNodeId !== undefined) { setVisualizedNodeId(ui.visualizedNodeId); setPreviewNode(ui.visualizedNodeId); }
      }
      updateGraph(newNodes, newEdges);
      pushNotification(`Opened → ${filePath.split(/[\\/]/).pop()}`, 'info');
    } catch (err) {
      console.error('Failed to load project:', err);
      pushNotification('Open failed — see console', 'error');
    }
  }, [setNodes, setEdges, setActiveFilePath, setPreviewSize, setPreviewPos, setActivePaletteIndex, setVisualizedNodeId, setPreviewNode, updateGraph, pushNotification, setGroupStack, groupStackRef]);

  const loadProject = useCallback(async () => {
    await confirmUnsaved();
    try {
      const path = await open({
        filters: [{ name: 'VisionNodes Project', extensions: ['vn'] }],
        multiple: false
      });
      if (path && typeof path === 'string') await loadProjectFromPath(path);
    } catch (err) {
      console.error('Failed to open dialog:', err);
    }
  }, [confirmUnsaved, loadProjectFromPath]);

  const applyTemplateData = useCallback((data: any) => {
    const nodes = data.nodes || [];
    const edges = data.edges || [];
    setGroupStack([]); groupStackRef.current = [];
    setNodes(nodes); setEdges(edges);
    if (data.ui) {
      if (data.ui.previewSize) setPreviewSize(data.ui.previewSize);
      if (data.ui.previewPos) setPreviewPos(data.ui.previewPos);
      if (data.ui.activePaletteIndex !== undefined) setActivePaletteIndex(data.ui.activePaletteIndex);
      if (data.ui.visualizedNodeId !== undefined) { setVisualizedNodeId(data.ui.visualizedNodeId); setPreviewNode(data.ui.visualizedNodeId); }
    }
    updateGraph(nodes, edges);
  }, [setNodes, setEdges, setPreviewSize, setPreviewPos, setActivePaletteIndex, setVisualizedNodeId, setPreviewNode, updateGraph, setGroupStack, groupStackRef]);

  const loadTemplate = useCallback(async (file: string) => {
    try {
      const data = await fetch(`/templates/${file}`).then(r => r.json());
      applyTemplateData(data);
    } catch(e) {
      console.error('Failed to load template:', file, e);
    }
  }, [applyTemplateData]);

  return {
    saveProject,
    saveProjectAs,
    saveProjectIncremental,
    loadProject,
    loadProjectFromPath,
    applyTemplateData,
    loadTemplate,
    buildProjectContent,
  };
}
