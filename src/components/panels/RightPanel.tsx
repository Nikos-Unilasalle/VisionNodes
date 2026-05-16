import React from 'react';
import { Settings, Cpu, Layout } from 'lucide-react';
import { NodeInspectorPanel, AnalysisDataPanel } from '../NodeInspectorPanel';
import type { ExposedParam } from '../NodeInspectorPanel';

interface RightPanelProps {
  selectedNode: any;
  selectedNodeLiveData: any;
  rightPanelWidth: number;
  exposedGroupParams: ExposedParam[];
  activePaletteIndex: number;
  pickColorNodeId: string | null;
  isInsideGroup: boolean;
  isResizing: React.MutableRefObject<boolean>;
  onUpdateParams: (id: string, params: any) => void;
  onPickColorToggle: (id: string | null) => void;
  onRequestCapture: (id: string) => void;
  onToggleExposed: (nodeId: string, paramId: string) => void;
  onUpdateGroupChildParams?: (childNodeId: string, params: any) => void;
  onRenameExposedParam?: (childNodeId: string, paramId: string, newLabel: string) => void;
}

const RightPanel: React.FC<RightPanelProps> = ({
  selectedNode,
  selectedNodeLiveData,
  rightPanelWidth,
  exposedGroupParams,
  activePaletteIndex,
  pickColorNodeId,
  isInsideGroup,
  isResizing,
  onUpdateParams,
  onPickColorToggle,
  onRequestCapture,
  onToggleExposed,
  onUpdateGroupChildParams,
  onRenameExposedParam,
}) => {
  const selectedNodeId = selectedNode?.id;
  const show = !!selectedNodeId;

  return (
    <div
      className="absolute right-0 top-0 bg-[#3d4452] border-l border-[#4f5b6b] flex flex-col transition-all duration-300 h-full overflow-hidden z-30"
      style={{ width: show ? rightPanelWidth : 0, opacity: show ? 1 : 0 }}
    >
      <div 
        className="absolute left-0 top-0 bottom-0 w-1.5 -ml-[3px] cursor-col-resize hover:bg-accent/50 z-20 transition-colors duration-150"
        onMouseDown={() => isResizing.current = true}
      />

      <div className="h-full flex flex-col">
        <div className="h-10 border-b border-[#4f5b6b] flex items-center px-4 bg-[#3d4452] shrink-0">
          <Settings size={14} className="text-gray-500 mr-2" />
          <span className="text-[10px] font-black tracking-widest text-gray-400 uppercase">Unit Inspector</span>
        </div>
        
        <div className="flex-1 flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto p-10 scrollbar-hide">
            {selectedNode ? (
              <div className="space-y-12 animate-in slide-in-from-right-10 duration-500">
                <div className="flex items-center gap-5">
                   <div className="w-16 h-16 bg-accent/5 rounded-3xl border border-accent/20 flex items-center justify-center text-accent shadow-inner">
                      <Cpu size={32} />
                   </div>
                   <div>
                      <h2 className="text-[14px] font-black text-white uppercase tracking-wider">{selectedNode.data.label}</h2>
                      {selectedNode.data.description && (
                        <p className="text-[10px] text-gray-400 italic mt-1 leading-relaxed opacity-80">{selectedNode.data.description}</p>
                      )}
                      <span className="text-[9px] text-gray-600 font-mono italic opacity-40 leading-none">{selectedNode.id}</span>
                   </div>
                </div>

                <NodeInspectorPanel
                  node={selectedNode}
                  liveData={selectedNodeLiveData}
                  activePaletteIndex={activePaletteIndex}
                  pickColorNodeId={pickColorNodeId}
                  onUpdateParams={onUpdateParams}
                  onPickColorToggle={onPickColorToggle}
                  onRequestCapture={onRequestCapture}
                  isInsideGroup={isInsideGroup}
                  onToggleExposed={onToggleExposed}
                  exposedGroupParams={exposedGroupParams}
                  onUpdateGroupChildParams={onUpdateGroupChildParams}
                  onRenameExposedParam={onRenameExposedParam}
                />
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center opacity-5 py-20 grayscale pointer-events-none">
                <Layout size={120} />
              </div>
            )}
          </div>
          
          {selectedNode && (
            <AnalysisDataPanel liveData={selectedNodeLiveData} />
          )}
        </div>
      </div>
    </div>
  );
};

export default RightPanel;
