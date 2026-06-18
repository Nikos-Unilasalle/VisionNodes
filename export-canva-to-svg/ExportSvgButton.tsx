/**
 * ExportSvgButton.tsx — Exemple de wiring dans la toolbar VNStudio.
 *
 * Récupère l'état ReactFlow vivant + le registre de nœuds, puis exporte.
 * Adaptez `useNodeRegistry()` au store réel (celui qui alimente le menu Cmd+M).
 */
import { useReactFlow } from "reactflow";
import { exportScene } from "./exportSvg";
import type { GetNodeDef } from "./vnToSvg";

// ⚠ À remplacer par votre vrai accès au registre (type → {label, inputs, outputs}).
// Le registre existe déjà côté front : c'est lui qui dessine les ports ReactFlow.
declare function useNodeRegistry(): { getNodeDef: GetNodeDef };

export function ExportSvgButton({ sceneName = "scene" }: { sceneName?: string }) {
  const rf = useReactFlow();
  const { getNodeDef } = useNodeRegistry();

  const onExport = async (format: "svg" | "png") => {
    const nodes = rf.getNodes();
    const edges = rf.getEdges();
    // sélection courante uniquement, si non vide :
    const selected = nodes.filter((n) => n.selected).map((n) => n.id);
    const selectionIds = selected.length ? new Set(selected) : undefined;

    const path = await exportScene({
      nodes, edges, getNodeDef,
      title: sceneName,
      selectionIds,
      format,
      defaultName: sceneName,
    });
    if (path) console.info("Schéma exporté →", path);
  };

  return (
    <div className="flex gap-1">
      <button className="px-2 py-1 text-sm" onClick={() => onExport("svg")}>
        Export SVG
      </button>
      <button className="px-2 py-1 text-sm" onClick={() => onExport("png")}>
        PNG
      </button>
    </div>
  );
}

/*
 Raccourci clavier (à ajouter au gestionnaire existant, à côté de Cmd+S/Cmd+M) :

   useEffect(() => {
     const onKey = (e: KeyboardEvent) => {
       if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "e") {
         e.preventDefault();
         onExport("svg");
       }
     };
     window.addEventListener("keydown", onKey);
     return () => window.removeEventListener("keydown", onKey);
   }, []);

 Cmd+Shift+E = « Export schéma » (libre, ne percute pas Cmd+F/Cmd+M/Cmd+S).
*/
