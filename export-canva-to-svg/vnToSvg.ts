/**
 * vnToSvg.ts — Convertit une scène VNStudio (.vn) en SVG vectoriel propre.
 *
 * On NE capture PAS le DOM ReactFlow (cela ramène previews + thème sombre).
 * On redessine un schéma abstrait à partir de la scène + le registre de nœuds :
 *   - positions reprises de node.position (layout fidèle)
 *   - hauteur recalculée d'après le nombre de ports (boîtes nettes, sans clutter)
 *   - type de port encodé par la FORME → palette mono-teinte conservée
 *   - béziers identiques à ReactFlow (getBezierPath porté à l'identique)
 *
 * Aucune dépendance. Sortie = string SVG, prête à écrire sur disque (Tauri) ou
 * à injecter dans un <img src="data:image/svg+xml,...">.
 *
 * ⚠ Garder PALETTE / constantes géométriques synchronisées avec vn_to_svg.py
 *   (même spec visuelle pour le livre et pour l'app).
 */

// ---- Types ------------------------------------------------------------------
export type PortColor =
  | "image" | "mask" | "scalar" | "string"
  | "dict" | "list" | "any" | "flow" | "audio";

export interface PortDef { id: string; color: PortColor; }
export interface NodeDef { label: string; inputs: PortDef[]; outputs: PortDef[]; }

export interface VnNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  width?: number;
}
export interface VnEdge {
  id?: string;
  source: string; sourceHandle: string;
  target: string; targetHandle: string;
}
export interface VnScene { nodes: VnNode[]; edges: VnEdge[]; }

/** Accès au registre : type de nœud → définition (label + ports). */
export type GetNodeDef = (type: string) => NodeDef | undefined;

export interface RenderOptions {
  title?: string;
  pad?: number;
  showPortLabels?: boolean;
  onlyIds?: Set<string>;   // n'exporter qu'une sélection
}

// ---- Palette (un seul ton : famille rose/rouge) -----------------------------
export const PALETTE = {
  ink: "#7a1330",
  header: "#f3d3da",
  body: "#fdf3f5",
  port: "#b51d44",
  hollow: "#ffffff",
  edge: "#c8607a",
  muted: "#9a5566",
  bg: "#ffffff", // "none" pour transparent
};

const HEADER_H = 30;
const ROW_H = 26;
const PAD = 10;
const PORT_R = 5.5;
const FONT = "ui-sans-serif, -apple-system, 'Segoe UI', Roboto, sans-serif";

type Shape =
  | "disc" | "ring" | "disc_ring" | "square"
  | "square_ring" | "diamond" | "diamond_ring" | "triangle";

const TYPE_SHAPE: Record<PortColor, Shape> = {
  image: "disc", mask: "ring", scalar: "square", string: "diamond",
  dict: "square_ring", list: "diamond_ring", any: "disc_ring",
  flow: "triangle", audio: "disc",
};
const FLOW_TYPES = new Set<PortColor>(["flow"]);

// ---- Helpers ----------------------------------------------------------------
function esc(s: string): string {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]!));
}

/** 'image__main' → ['image', 'main'] (format VNStudio {color}__{port_id}). */
function parseHandle(h: string): [PortColor | null, string] {
  const i = h.indexOf("__");
  if (i >= 0) return [h.slice(0, i) as PortColor, h.slice(i + 2)];
  return [null, h];
}

/** calculateControlOffset de ReactFlow. */
function rfOffset(distance: number, curvature = 0.25): number {
  return distance >= 0 ? 0.5 * distance : curvature * 25 * Math.sqrt(-distance);
}

/** getBezierPath de ReactFlow (source=Right, target=Left). */
function bezier(x1: number, y1: number, x2: number, y2: number): string {
  const cx1 = x1 + rfOffset(x2 - x1);
  const cx2 = x2 - rfOffset(x2 - x1);
  return `M${x1.toFixed(1)},${y1.toFixed(1)} C${cx1.toFixed(1)},${y1.toFixed(1)} ` +
         `${cx2.toFixed(1)},${y2.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}`;
}

function nodeGeom(node: VnNode, def: NodeDef): [number, number] {
  const rows = Math.max(def.inputs.length, def.outputs.length, 1);
  const w = node.width ?? 158;
  const h = HEADER_H + PAD + rows * ROW_H + PAD;
  return [w, h];
}

function portXY(node: VnNode, def: NodeDef, side: "in" | "out", portId: string): [number, number] {
  const ports = side === "in" ? def.inputs : def.outputs;
  let idx = ports.findIndex((p) => p.id === portId);
  if (idx < 0) idx = 0;
  const [w] = nodeGeom(node, def);
  const cx = side === "in" ? node.position.x : node.position.x + w;
  const cy = node.position.y + HEADER_H + PAD + idx * ROW_H + ROW_H / 2;
  return [cx, cy];
}

function portShape(cx: number, cy: number, kind: Shape): string {
  const r = PORT_R, p = PALETTE.port, ring = PALETTE.hollow;
  const f = (n: number) => n.toFixed(1);
  switch (kind) {
    case "disc":
      return `<circle cx="${f(cx)}" cy="${f(cy)}" r="${r}" fill="${p}"/>`;
    case "ring":
      return `<circle cx="${f(cx)}" cy="${f(cy)}" r="${r}" fill="${ring}" stroke="${p}" stroke-width="2"/>`;
    case "disc_ring":
      return `<circle cx="${f(cx)}" cy="${f(cy)}" r="${r + 1}" fill="${ring}" stroke="${p}" stroke-width="1.5"/>` +
             `<circle cx="${f(cx)}" cy="${f(cy)}" r="2" fill="${p}"/>`;
    case "square":
      return `<rect x="${f(cx - r)}" y="${f(cy - r)}" width="${2 * r}" height="${2 * r}" rx="1" fill="${p}"/>`;
    case "square_ring":
      return `<rect x="${f(cx - r)}" y="${f(cy - r)}" width="${2 * r}" height="${2 * r}" rx="1" fill="${ring}" stroke="${p}" stroke-width="2"/>`;
    case "diamond":
      return `<path d="M${f(cx)},${f(cy - r - 1)} L${f(cx + r + 1)},${f(cy)} L${f(cx)},${f(cy + r + 1)} L${f(cx - r - 1)},${f(cy)} Z" fill="${p}"/>`;
    case "diamond_ring":
      return `<path d="M${f(cx)},${f(cy - r - 1)} L${f(cx + r + 1)},${f(cy)} L${f(cx)},${f(cy + r + 1)} L${f(cx - r - 1)},${f(cy)} Z" fill="${ring}" stroke="${p}" stroke-width="2"/>`;
    case "triangle":
      return `<path d="M${f(cx - r)},${f(cy - r)} L${f(cx + r + 1)},${f(cy)} L${f(cx - r)},${f(cy + r)} Z" fill="${p}"/>`;
  }
}

// ---- Rendu principal --------------------------------------------------------
export function renderSceneToSvg(
  scene: VnScene,
  getNodeDef: GetNodeDef,
  opts: RenderOptions = {},
): string {
  const { title, pad = 30, showPortLabels = true, onlyIds } = opts;

  const nodes = scene.nodes.filter((n) => !onlyIds || onlyIds.has(n.id));
  const ids = new Set(nodes.map((n) => n.id));
  const edges = scene.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const defOf = (n: VnNode): NodeDef =>
    getNodeDef(n.type) ?? { label: n.type, inputs: [], outputs: [] };

  if (nodes.length === 0) return `<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>`;

  const geom = new Map(nodes.map((n) => [n.id, nodeGeom(n, defOf(n))]));
  const minx = Math.min(...nodes.map((n) => n.position.x)) - pad;
  const miny = Math.min(...nodes.map((n) => n.position.y)) - pad - (title ? 26 : 0);
  const maxx = Math.max(...nodes.map((n) => n.position.x + geom.get(n.id)![0])) + pad;
  const maxy = Math.max(...nodes.map((n) => n.position.y + geom.get(n.id)![1])) + pad;
  const W = maxx - minx, H = maxy - miny;

  const out: string[] = [];
  out.push(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${minx.toFixed(0)} ${miny.toFixed(0)} ${W.toFixed(0)} ${H.toFixed(0)}" ` +
    `width="${W.toFixed(0)}" height="${H.toFixed(0)}" font-family="${FONT}">`,
  );
  if (PALETTE.bg !== "none") {
    out.push(`<rect x="${minx.toFixed(0)}" y="${miny.toFixed(0)}" width="${W.toFixed(0)}" height="${H.toFixed(0)}" fill="${PALETTE.bg}"/>`);
  }
  if (title) {
    out.push(`<text x="${(minx + pad).toFixed(0)}" y="${(miny + 24).toFixed(0)}" font-size="14" font-weight="600" fill="${PALETTE.ink}">${esc(title)}</text>`);
  }

  // arêtes (sous les nœuds)
  for (const e of edges) {
    const [sc, srcPid] = parseHandle(e.sourceHandle);
    const [, dstPid] = parseHandle(e.targetHandle);
    const sn = byId.get(e.source)!, dn = byId.get(e.target)!;
    const [x1, y1] = portXY(sn, defOf(sn), "out", srcPid);
    const [x2, y2] = portXY(dn, defOf(dn), "in", dstPid);
    const dash = sc && FLOW_TYPES.has(sc) ? ` stroke-dasharray="5 4"` : "";
    out.push(`<path d="${bezier(x1, y1, x2, y2)}" fill="none" stroke="${PALETTE.edge}" stroke-width="2" stroke-linecap="round"${dash}/>`);
  }

  // nœuds
  for (const n of nodes) {
    const def = defOf(n);
    const x = n.position.x, y = n.position.y;
    const [w, h] = geom.get(n.id)!;
    out.push(`<rect x="${x.toFixed(0)}" y="${y.toFixed(0)}" width="${w.toFixed(0)}" height="${h.toFixed(0)}" rx="10" fill="${PALETTE.body}" stroke="${PALETTE.ink}" stroke-width="1.5"/>`);
    out.push(
      `<path d="M${x.toFixed(0)},${(y + HEADER_H).toFixed(0)} L${x.toFixed(0)},${(y + 10).toFixed(0)} ` +
      `Q${x.toFixed(0)},${y.toFixed(0)} ${(x + 10).toFixed(0)},${y.toFixed(0)} L${(x + w - 10).toFixed(0)},${y.toFixed(0)} ` +
      `Q${(x + w).toFixed(0)},${y.toFixed(0)} ${(x + w).toFixed(0)},${(y + 10).toFixed(0)} L${(x + w).toFixed(0)},${(y + HEADER_H).toFixed(0)} Z" ` +
      `fill="${PALETTE.header}" stroke="${PALETTE.ink}" stroke-width="1.5"/>`,
    );
    out.push(`<text x="${(x + w / 2).toFixed(0)}" y="${(y + HEADER_H / 2 + 5).toFixed(0)}" font-size="12.5" font-weight="600" text-anchor="middle" fill="${PALETTE.ink}">${esc(def.label)}</text>`);

    for (const [side, ports] of [["in", def.inputs], ["out", def.outputs]] as const) {
      ports.forEach((port) => {
        const [cx, cy] = portXY(n, def, side, port.id);
        out.push(portShape(cx, cy, TYPE_SHAPE[port.color] ?? "disc"));
        if (showPortLabels) {
          out.push(
            side === "in"
              ? `<text x="${(cx + 12).toFixed(0)}" y="${(cy + 4).toFixed(0)}" font-size="11" fill="${PALETTE.muted}">${esc(port.id)}</text>`
              : `<text x="${(cx - 12).toFixed(0)}" y="${(cy + 4).toFixed(0)}" font-size="11" text-anchor="end" fill="${PALETTE.muted}">${esc(port.id)}</text>`,
          );
        }
      });
    }
  }

  out.push("</svg>");
  return out.join("\n");
}
