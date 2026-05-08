import React from 'react';
import {
  FilePlus, FolderOpen, Save, SaveAll, Undo2, Redo2,
  AlignHorizontalDistributeCenter, AlignVerticalDistributeCenter, Grid3x3,
  Image, Film, Camera, Type, Layout, GitCommit, FileCode,
  Palette, FolderSearch, BookOpen, RefreshCw
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import * as N from '../Nodes';
import logo from '../../assets/logo.svg';
import type { Canvas } from '../../data/canvases';

interface HeaderProps {
  isConnected: boolean;
  activeCanvasId: string;
  canvases: Canvas[];
  activeFilePath: string | null;
  canUndo: boolean;
  canRedo: boolean;
  snapEnabled: boolean;
  activePaletteIndex: number;
  isPaletteSelectOpen: boolean;
  isProjectsOpen: boolean;
  isTemplatesOpen: boolean;
  workDir: string | null;
  workDirFiles: string[];
  templates: { name: string; description: string; file: string }[];
  setActiveCanvasId: (id: string) => void;
  handleUndo: () => void;
  handleRedo: () => void;
  alignNodes: (direction: 'horizontal' | 'vertical') => void;
  snapToggle: () => void;
  addNode: (type: string, label: string) => void;
  saveProject: () => void;
  saveProjectAs: () => void;
  saveProjectIncremental: () => void;
  loadProject: () => void;
  newProject: () => void;
  setIsPaletteSelectOpen: (v: boolean) => void;
  setActivePaletteIndex: (i: number) => void;
  setIsProjectsOpen: (v: boolean) => void;
  setIsTemplatesOpen: (v: boolean) => void;
  setWorkDirAndSave: () => void;
  refreshWorkDir: (dir: string) => void;
  confirmUnsaved: () => Promise<boolean>;
  loadProjectFromPath: (path: string) => void;
  loadTemplate: (file: string) => void;
  setShowAbout: (v: boolean) => void;
}

const Header: React.FC<HeaderProps> = ({
  isConnected, activeCanvasId, canvases, activeFilePath,
  canUndo: canU, canRedo: canR, snapEnabled, activePaletteIndex,
  isPaletteSelectOpen, isProjectsOpen, isTemplatesOpen,
  workDir, workDirFiles, templates,
  setActiveCanvasId, handleUndo, handleRedo, alignNodes, snapToggle,
  addNode, saveProject, saveProjectAs, saveProjectIncremental,
  loadProject, newProject,
  setIsPaletteSelectOpen, setActivePaletteIndex,
  setIsProjectsOpen, setIsTemplatesOpen,
  setWorkDirAndSave, refreshWorkDir,
  confirmUnsaved, loadProjectFromPath, loadTemplate,
  setShowAbout,
}) => {
  return (
    <header className="h-10 bg-[#3d4452] border-b border-[#4f5b6b] flex items-center justify-between px-4 z-50">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="h-8 flex items-center justify-center transition-transform hover:scale-110">
            <img src={logo} className="h-6 w-6" alt="VN Logo" />
          </div>
          <h1
            className="text-[11px] font-black tracking-[0.3em] text-white uppercase ml-1 cursor-pointer hover:text-accent/80 transition-colors"
            onClick={() => setShowAbout(true)}
          >VNStudio</h1>
        </div>
        <div className={`px-2 py-0.5 rounded text-[8px] font-bold ${isConnected ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'} border border-current opacity-60`}>
          {isConnected ? 'RUNTIME_CONNECTED' : 'WAITING_FOR_WS'}
        </div>
        <div className="h-4 w-[1px] bg-[#222] mx-1" />
        
        <div className="flex items-center bg-[#3d4452] rounded-lg border border-[#4f5b6b] p-0.5">
          <button onClick={newProject} className="p-1.5 hover:bg-white/10 rounded-md text-gray-400 transition-all" title="New">
            <FilePlus size={14} />
          </button>
          <div className="w-[1px] h-3 bg-[#333] mx-0.5" />
          <button onClick={loadProject} className="p-1.5 hover:bg-white/10 rounded-md text-gray-400 transition-all" title="Open">
            <FolderOpen size={14} />
          </button>
          <div className="w-[1px] h-3 bg-[#333] mx-0.5" />
          <button onClick={saveProject} className="p-1.5 bg-accent/10 hover:bg-accent/20 rounded-md text-accent transition-all" title={activeFilePath ? `Save → ${activeFilePath.split(/[\\/]/).pop()}` : 'Save As…'}>
            <Save size={14} />
          </button>
          <div className="w-[1px] h-3 bg-[#333] mx-0.5" />
          <button onClick={saveProjectAs} title="Save As…" className="p-1.5 hover:bg-white/10 rounded-md text-gray-400 transition-all">
            <SaveAll size={14} />
          </button>
          {activeFilePath && (<>
            <div className="w-[1px] h-3 bg-[#333] mx-0.5" />
            <button onClick={saveProjectIncremental} title="Save incremental version (+01, +02…)" className="p-1.5 hover:bg-accent/20 rounded-md text-accent transition-all">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14"/><path d="M12 5v14"/>
              </svg>
            </button>
          </>)}
        </div>

        <div className="h-4 w-[1px] bg-[#222] mx-1" />

        <div className="flex items-center bg-[#3d4452] rounded-lg border border-[#4f5b6b] p-0.5">
          <button onClick={handleUndo} disabled={!canU} title="Undo (⌘Z)" className="p-1.5 hover:bg-white/10 rounded-md text-gray-400 transition-all disabled:opacity-25 disabled:cursor-not-allowed">
            <Undo2 size={14} />
          </button>
          <div className="w-[1px] h-3 bg-[#333] mx-0.5" />
          <button onClick={handleRedo} disabled={!canR} title="Redo (⌘⇧Z)" className="p-1.5 hover:bg-white/10 rounded-md text-gray-400 transition-all disabled:opacity-25 disabled:cursor-not-allowed">
            <Redo2 size={14} />
          </button>
        </div>

        <div className="h-4 w-[1px] bg-[#222] mx-1" />

        <div className="flex items-center gap-1 bg-[#3d4452] rounded-lg border border-[#4f5b6b] p-0.5">
          <button onClick={() => alignNodes('horizontal')} title="Align Horizontally" className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors">
            <AlignHorizontalDistributeCenter size={14} />
          </button>
          <button onClick={() => alignNodes('vertical')} title="Align Vertically" className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors">
            <AlignVerticalDistributeCenter size={14} />
          </button>
          <div className="w-[1px] h-3 bg-[#333] mx-1" />
          <button onClick={snapToggle} title="Snap to Grid" className={`p-1 rounded transition-colors ${snapEnabled ? 'text-accent bg-accent/20' : 'text-gray-500 hover:text-white hover:bg-white/10'}`}>
            <Grid3x3 size={14} />
          </button>
        </div>

        <div className="h-4 w-[1px] bg-[#222] mx-1" />

        <div className="flex items-center gap-1 bg-[#3d4452] rounded-lg border border-[#4f5b6b] p-0.5">
          <button onClick={() => addNode('input_image', 'Image File')} title="Add Image Node" className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors">
            <Image size={14} />
          </button>
          <button onClick={() => addNode('input_movie', 'Movie File')} title="Add Movie Node" className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors">
            <Film size={14} />
          </button>
          <button onClick={() => addNode('input_webcam', 'Webcam')} title="Add Webcam Node" className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors">
            <Camera size={14} />
          </button>
        </div>

        <div className="h-4 w-[1px] bg-[#222] mx-1" />

        <div className="flex items-center gap-1 bg-[#3d4452] rounded-lg border border-[#4f5b6b] p-0.5">
          <button onClick={() => addNode('canvas_note', 'Note')} title="Add Note Node" className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors">
            <Type size={14} />
          </button>
          <button onClick={() => addNode('canvas_frame', 'Frame')} title="Add Frame Node" className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors">
            <Layout size={14} />
          </button>
          <button onClick={() => addNode('canvas_reroute', 'Reroute')} title="Add Reroute Node" className="p-1 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors">
            <GitCommit size={14} />
          </button>
        </div>

        <div className="h-4 w-[1px] bg-[#222] mx-1" />

        <div className="flex items-center bg-[#3d4452] rounded-lg border border-[#4f5b6b] p-0.5">
          <button onClick={() => addNode('export_py', 'Export .py')} title="Export as Python script" className="p-1.5 hover:bg-white/10 rounded-md text-gray-400 transition-all">
            <FileCode size={14} className="text-yellow-400" />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="flex items-center gap-0.5 bg-[#3d4452] rounded-lg border border-[#4f5b6b] p-0.5">
          {canvases.map((c, i) => (
            <button
              key={c.id}
              onClick={() => setActiveCanvasId(c.id)}
              className={`px-3 py-1 rounded-md text-[10px] font-bold transition-all ${
                activeCanvasId === c.id
                  ? 'bg-accent/20 text-accent'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
              }`}
            >
              {i + 1}
            </button>
          ))}
        </div>

        <div className="w-[1px] h-4 bg-white/10 mx-1" />

         <div className="relative">
          <button
              onClick={() => setIsPaletteSelectOpen(!isPaletteSelectOpen)}
              className="p-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-gray-400 transition-all border border-white/5"
              title="Palette"
            >
              <Palette size={14} />
            </button>
            <AnimatePresence>
              {isPaletteSelectOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setIsPaletteSelectOpen(false)} />
                  <motion.div 
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    className="absolute right-0 mt-2 w-48 bg-[#3d4452] border border-[#4f5b6b] rounded-xl shadow-2xl z-50 p-2 overflow-hidden"
                  >
                    {N.PALETTES.map((pal, i) => (
                      <button 
                        key={i}
                        onClick={() => { setActivePaletteIndex(i); setIsPaletteSelectOpen(false); }}
                        className={`w-full text-left p-2 rounded-lg group transition-all flex flex-col gap-1.5 ${i === activePaletteIndex ? 'bg-accent/20 border border-accent/30' : 'hover:bg-white/5 border border-transparent'}`}
                      >
                        <div className="text-[9px] font-bold text-gray-200 group-hover:text-accent uppercase tracking-tighter">{pal.name}</div>
                        <div className="flex h-3 w-full rounded overflow-hidden">
                           {pal.colors.map((c, ci) => (
                             <div key={ci} className="flex-1" style={{ backgroundColor: c.bg }} />
                           ))}
                        </div>
                      </button>
                    ))}
                  </motion.div>
                </>
              )}
            </AnimatePresence>
         </div>
         
         <div className="relative">
            <button
              onClick={() => setIsProjectsOpen(!isProjectsOpen)}
              className="p-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-gray-400 transition-all border border-white/5"
              title="My Projects"
            >
              <FolderSearch size={14} />
            </button>
            <AnimatePresence>
              {isProjectsOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setIsProjectsOpen(false)} />
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    className="absolute right-0 mt-2 w-72 bg-[#3d4452] border border-[#4f5b6b] rounded-xl shadow-2xl z-50 p-2 overflow-y-auto max-h-[70vh]"
                  >
                    <button
                      onClick={async () => { await setWorkDirAndSave(); }}
                      className="w-full flex items-center gap-2 p-3 hover:bg-accent/10 rounded-lg group transition-all text-left"
                    >
                      <FolderSearch size={13} className="text-accent shrink-0" />
                      <div>
                        <div className="text-[10px] font-bold text-gray-200 group-hover:text-accent uppercase tracking-tighter">Set Work Directory</div>
                        {workDir && <div className="text-[8px] text-gray-600 mt-0.5 truncate max-w-[220px]">{workDir}</div>}
                      </div>
                    </button>

                    {workDir && (
                      <>
                        <div className="flex items-center justify-between px-3 py-1.5">
                          <div className="w-full h-[1px] bg-[#2a2a2a]" />
                          <button onClick={() => refreshWorkDir(workDir)} className="ml-2 text-gray-600 hover:text-accent transition-colors shrink-0">
                            <RefreshCw size={10} />
                          </button>
                        </div>
                        {workDirFiles.length === 0 ? (
                          <div className="text-[9px] text-gray-600 px-3 py-2 italic">No .vn files in this directory</div>
                        ) : (
                          workDirFiles.map(file => (
                            <button
                              key={file}
                              onClick={async () => {
                                await confirmUnsaved();
                                await loadProjectFromPath(`${workDir}/${file}`);
                                setIsProjectsOpen(false);
                              }}
                              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-accent/10 rounded-lg group transition-all text-left"
                            >
                              <Save size={11} className="text-gray-600 group-hover:text-accent shrink-0" />
                              <span className="text-[10px] font-bold text-gray-300 group-hover:text-accent truncate">
                                {file.replace(/\.vn$/i, '')}
                              </span>
                              {activeFilePath === `${workDir}/${file}` && (
                                <span className="ml-auto text-[8px] text-accent font-black uppercase tracking-wider">active</span>
                              )}
                            </button>
                          ))
                        )}
                      </>
                    )}
                  </motion.div>
                </>
              )}
            </AnimatePresence>
         </div>

         <div className="relative">
            <button
              onClick={() => setIsTemplatesOpen(!isTemplatesOpen)}
              className="p-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-gray-400 transition-all border border-white/5"
              title="Templates"
            >
              <BookOpen size={14} />
            </button>
            <AnimatePresence>
              {isTemplatesOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setIsTemplatesOpen(false)} />
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    className="absolute right-0 mt-2 w-64 bg-[#3d4452] border border-[#4f5b6b] rounded-xl shadow-2xl z-50 p-2 overflow-y-auto max-h-[70vh]"
                  >
                    {templates.map((t, i) => (
                      <button
                        key={i}
                        onClick={() => loadTemplate(t.file)}
                        className="w-full text-left p-3 hover:bg-accent/10 rounded-lg group transition-all"
                      >
                        <div className="text-[10px] font-bold text-gray-200 group-hover:text-accent uppercase tracking-tighter">{t.name}</div>
                        <div className="text-[8px] text-gray-500 mt-1 leading-tight">{t.description}</div>
                      </button>
                    ))}
                  </motion.div>
                </>
              )}
            </AnimatePresence>
         </div>
      </div>
    </header>
  );
};

export default Header;
