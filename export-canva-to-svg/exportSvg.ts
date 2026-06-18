/**
 * exportSvg.ts — Export "schéma propre" depuis l'app VNStudio (Tauri v2).
 *
 * Branche renderSceneToSvg sur l'état ReactFlow vivant, ouvre une boîte de
 * sauvegarde et écrit le fichier. SVG = sortie primaire (vectorielle). PNG =
 * rasterisation optionnelle via canvas (pratique pour partage rapide).
 *
 * Dépendances Tauri v2 :
 *   npm i @tauri-apps/plugin-dialog @tauri-apps/plugin-fs
 * (et déclarer les permissions dialog:allow-save / fs:allow-write dans capabilities)
 */
import { save } from "@tauri-apps/plugin-dialog";
import { writeTextFile, writeFile } from "@tauri-apps/plugin-fs";
import {
  renderSceneToSvg, type GetNodeDef, type VnScene, type VnNode, type VnEdge,
} from "./vnToSvg";

// --- Adaptateur : nœuds/arêtes ReactFlow → scène .vn -------------------------
// Les nœuds RF exposent déjà id/type/position ; les arêtes id/source/target/handles.
interface RFNode { id: string; type?: string; position: { x: number; y: number }; width?: number | null; }
interface RFEdge { id?: string; source: string; target: string; sourceHandle?: string | null; targetHandle?: string | null; }

export function sceneFromReactFlow(nodes: RFNode[], edges: RFEdge[]): VnScene {
  const vnNodes: VnNode[] = nodes.map((n) => ({
    id: n.id,
    type: n.type ?? "unknown",
    position: { x: n.position.x, y: n.position.y },
    width: n.width ?? undefined,
  }));
  const vnEdges: VnEdge[] = edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle ?? "",
    targetHandle: e.targetHandle ?? "",
  }));
  return { nodes: vnNodes, edges: vnEdges };
}

// --- Rasterisation SVG → PNG (canvas, côté webview) --------------------------
async function svgToPngBytes(svg: string, scale = 2): Promise<Uint8Array> {
  const url = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  const img = new Image();
  await new Promise<void>((res, rej) => {
    img.onload = () => res();
    img.onerror = () => rej(new Error("SVG illisible pour rasterisation"));
    img.src = url;
  });
  const canvas = document.createElement("canvas");
  canvas.width = img.width * scale;
  canvas.height = img.height * scale;
  const ctx = canvas.getContext("2d")!;
  ctx.scale(scale, scale);
  ctx.drawImage(img, 0, 0);
  const blob: Blob = await new Promise((res) => canvas.toBlob((b) => res(b!), "image/png"));
  return new Uint8Array(await blob.arrayBuffer());
}

// --- Export public -----------------------------------------------------------
export interface ExportArgs {
  nodes: RFNode[];
  edges: RFEdge[];
  getNodeDef: GetNodeDef;
  title?: string;
  selectionIds?: Set<string>;     // n'exporter que la sélection
  format?: "svg" | "png";
  defaultName?: string;           // ex. nom de la scène courante
}

export async function exportScene(args: ExportArgs): Promise<string | null> {
  const { nodes, edges, getNodeDef, title, selectionIds, format = "svg", defaultName = "scene" } = args;

  const scene = sceneFromReactFlow(nodes, edges);
  const svg = renderSceneToSvg(scene, getNodeDef, { title, onlyIds: selectionIds });

  const ext = format;
  const path = await save({
    defaultPath: `${defaultName}.${ext}`,
    filters: [{ name: format.toUpperCase(), extensions: [ext] }],
  });
  if (!path) return null; // annulé

  if (format === "svg") {
    await writeTextFile(path, svg);
  } else {
    const png = await svgToPngBytes(svg, 2);
    await writeFile(path, png);
  }
  return path;
}
