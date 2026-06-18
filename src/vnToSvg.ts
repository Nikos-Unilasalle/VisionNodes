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
  label?: string;    // overrides schema label (e.g. frame title)
  noteText?: string; // raw markdown body for canvas_note
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
  onlyIds?: Set<string>;
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
  bg: "#ffffff",
};

const HEADER_H = 30;
const ROW_H = 26;
const PAD = 10;
const PORT_R = 5.5;
const NOTE_PAD = 12;
const NOTE_LINE_H = 15;
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

// ---- Markdown inline → SVG tspan fragments ----------------------------------
function parseInlineMd(raw: string): string {
  let out = "";
  let i = 0;
  while (i < raw.length) {
    // **bold**
    if (raw[i] === "*" && raw[i + 1] === "*") {
      const end = raw.indexOf("**", i + 2);
      if (end > i + 1) {
        out += `<tspan font-weight="700">${esc(raw.slice(i + 2, end))}</tspan>`;
        i = end + 2;
        continue;
      }
    }
    // *italic*
    if (raw[i] === "*") {
      const end = raw.indexOf("*", i + 1);
      if (end > i) {
        out += `<tspan font-style="italic">${esc(raw.slice(i + 1, end))}</tspan>`;
        i = end + 1;
        continue;
      }
    }
    // `code`
    if (raw[i] === "`") {
      const end = raw.indexOf("`", i + 1);
      if (end > i) {
        out += `<tspan font-family="monospace" font-size="10">${esc(raw.slice(i + 1, end))}</tspan>`;
        i = end + 1;
        continue;
      }
    }
    out += esc(raw[i]);
    i++;
  }
  return out;
}

/** Calcule la hauteur d'un bloc note d'après son texte markdown. */
function noteHeight(text: string): number {
  let h = NOTE_PAD;
  for (const line of text.split("\n")) {
    if (!line.trim()) { h += 8; continue; }
    if (line.startsWith("# "))   { h += 22; continue; }
    if (line.startsWith("## "))  { h += 19; continue; }
    if (line.startsWith("### ")) { h += 17; continue; }
    h += NOTE_LINE_H;
  }
  return h + NOTE_PAD;
}

/** Renders each markdown line as SVG text elements, returns array of SVG strings. */
function renderNoteLines(x: number, startY: number, text: string): string[] {
  const out: string[] = [];
  const px = x + NOTE_PAD;
  let y = startY + NOTE_PAD;

  for (const line of text.split("\n")) {
    if (!line.trim()) { y += 8; continue; }

    if (line.startsWith("# ")) {
      out.push(`<text x="${px.toFixed(0)}" y="${y.toFixed(0)}" font-size="15" font-weight="800" fill="${PALETTE.ink}">${parseInlineMd(line.slice(2))}</text>`);
      y += 22;
    } else if (line.startsWith("## ")) {
      out.push(`<text x="${px.toFixed(0)}" y="${y.toFixed(0)}" font-size="13" font-weight="700" fill="${PALETTE.ink}">${parseInlineMd(line.slice(3))}</text>`);
      y += 19;
    } else if (line.startsWith("### ")) {
      out.push(`<text x="${px.toFixed(0)}" y="${y.toFixed(0)}" font-size="11.5" font-weight="700" fill="${PALETTE.ink}">${parseInlineMd(line.slice(4))}</text>`);
      y += 17;
    } else if (line.startsWith("> ")) {
      out.push(`<text x="${(px + 8).toFixed(0)}" y="${y.toFixed(0)}" font-size="11" font-style="italic" fill="${PALETTE.muted}">${parseInlineMd(line.slice(2))}</text>`);
      y += NOTE_LINE_H;
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      out.push(`<text x="${px.toFixed(0)}" y="${y.toFixed(0)}" font-size="11" fill="${PALETTE.ink}"><tspan fill="${PALETTE.port}">• </tspan>${parseInlineMd(line.slice(2))}</text>`);
      y += NOTE_LINE_H;
    } else {
      out.push(`<text x="${px.toFixed(0)}" y="${y.toFixed(0)}" font-size="11" fill="${PALETTE.ink}">${parseInlineMd(line)}</text>`);
      y += NOTE_LINE_H;
    }
  }
  return out;
}

// ---- Géométrie --------------------------------------------------------------
function nodeGeom(node: VnNode, def: NodeDef): [number, number] {
  const w = node.width ?? 158;
  if (node.type === "canvas_frame") return [w, HEADER_H];
  if (node.type === "canvas_note")  return [w, Math.max(noteHeight(node.noteText ?? ""), NOTE_LINE_H + 2 * NOTE_PAD)];
  const rows = Math.max(def.inputs.length, def.outputs.length, 1);
  return [w, HEADER_H + PAD + rows * ROW_H + PAD];
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

  const defOf = (n: VnNode): NodeDef => {
    const base = getNodeDef(n.type) ?? { label: n.type, inputs: [], outputs: [] };
    return n.label ? { ...base, label: n.label } : base;
  };

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
    const f = (v: number) => v.toFixed(0);

    if (n.type === "canvas_frame") {
      // Chapeau uniquement : bande pleine arrondie en haut
      out.push(
        `<path d="M${f(x)},${f(y + h)} L${f(x)},${f(y + 10)} ` +
        `Q${f(x)},${f(y)} ${f(x + 10)},${f(y)} L${f(x + w - 10)},${f(y)} ` +
        `Q${f(x + w)},${f(y)} ${f(x + w)},${f(y + 10)} L${f(x + w)},${f(y + h)} Z" ` +
        `fill="${PALETTE.header}" stroke="${PALETTE.ink}" stroke-width="1.5"/>`,
      );
      const frameTitle = n.label ?? "";
      if (frameTitle) {
        out.push(`<text x="${f(x + 12)}" y="${f(y + h / 2 + 5)}" font-size="11" font-weight="700" letter-spacing="1" fill="${PALETTE.ink}">${esc(frameTitle.toUpperCase())}</text>`);
      }

    } else if (n.type === "canvas_note") {
      // Corps uniquement : boîte sans chapeau, texte markdown à l'intérieur
      out.push(`<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" rx="10" fill="${PALETTE.body}" stroke="${PALETTE.ink}" stroke-width="1.5"/>`);
      out.push(...renderNoteLines(x, y, n.noteText ?? ""));

    } else {
      // Nœud standard : corps + chapeau + ports
      out.push(`<rect x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" rx="10" fill="${PALETTE.body}" stroke="${PALETTE.ink}" stroke-width="1.5"/>`);
      out.push(
        `<path d="M${f(x)},${f(y + HEADER_H)} L${f(x)},${f(y + 10)} ` +
        `Q${f(x)},${f(y)} ${f(x + 10)},${f(y)} L${f(x + w - 10)},${f(y)} ` +
        `Q${f(x + w)},${f(y)} ${f(x + w)},${f(y + 10)} L${f(x + w)},${f(y + HEADER_H)} Z" ` +
        `fill="${PALETTE.header}" stroke="${PALETTE.ink}" stroke-width="1.5"/>`,
      );
      out.push(`<text x="${f(x + w / 2)}" y="${f(y + HEADER_H / 2 + 5)}" font-size="12.5" font-weight="600" text-anchor="middle" fill="${PALETTE.ink}">${esc(def.label)}</text>`);

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
  }

  out.push("</svg>");
  return out.join("\n");
}
