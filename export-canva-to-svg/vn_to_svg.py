"""
vn_to_svg.py — Convertit une scene .vn (JSON VNStudio) en SVG vectoriel propre.

Principe : on ne capture PAS l'UI. On relit la scene + les definitions de noeuds
(le registre) et on redessine un schema abstrait, monochrome, sans preview.

- Positions reprises depuis node.position (layout fidele a la scene)
- Hauteur recalculee depuis le nombre de ports (boites propres, sans clutter)
- Type de port encode par la FORME (mono-teinte conservee)
- Beziers identiques a ReactFlow (getBezierPath porte a l'identique)

Entree : scene .vn + node_defs (type -> {label, inputs[], outputs[]}).
Les ports portent un id + un type (couleur VNStudio), mappe sur une forme.
"""
import json, math, html

PALETTE = {
    "ink": "#7a1330", "header": "#f3d3da", "body": "#fdf3f5",
    "port": "#b51d44", "port_fill_hollow": "#ffffff",
    "edge": "#c8607a", "muted": "#9a5566", "bg": "#ffffff",
}
HEADER_H, ROW_H, PAD, PORT_R = 30, 26, 10, 5.5
FONT = "ui-sans-serif, -apple-system, 'Segoe UI', Roboto, sans-serif"

# type de port (couleur VNStudio) -> forme. Mono-teinte : seule la forme varie.
TYPE_SHAPE = {
    "image": "disc", "mask": "ring", "scalar": "square", "string": "diamond",
    "dict": "square_ring", "list": "diamond_ring", "any": "disc_ring",
    "flow": "triangle", "audio": "disc",
}
# arete de type flow (trigger) = pointillee
FLOW_TYPES = {"flow"}


def parse_handle(h):
    """'image__main' -> ('image', 'main'). Format VNStudio {color}__{port_id}."""
    if h and "__" in h:
        c, _, pid = h.partition("__")
        return c, pid
    return None, h


def _rf_offset(distance, curvature=0.25):
    """calculateControlOffset de ReactFlow."""
    if distance >= 0:
        return 0.5 * distance
    return curvature * 25 * math.sqrt(-distance)


def bezier(x1, y1, x2, y2):
    """getBezierPath de ReactFlow, source=Right, target=Left."""
    cx1 = x1 + _rf_offset(x2 - x1)
    cx2 = x2 - _rf_offset(x2 - x1)
    return f"M{x1:.1f},{y1:.1f} C{cx1:.1f},{y1:.1f} {cx2:.1f},{y2:.1f} {x2:.1f},{y2:.1f}"


def _node_geom(node, ndef):
    rows = max(len(ndef["inputs"]), len(ndef["outputs"]), 1)
    w = node.get("width", 158)
    h = HEADER_H + PAD + rows * ROW_H + PAD
    return w, h


def _port_xy(node, ndef, side, port_id):
    ports = ndef["inputs"] if side == "in" else ndef["outputs"]
    idx = next((i for i, p in enumerate(ports) if p["id"] == port_id), 0)
    x = node["position"]["x"]
    w, _ = _node_geom(node, ndef)
    cx = x if side == "in" else x + w
    cy = node["position"]["y"] + HEADER_H + PAD + idx * ROW_H + ROW_H / 2
    return cx, cy


def _shape(cx, cy, kind, pal):
    r = PORT_R
    p, fillc, ring = pal["port"], pal["port"], pal["port_fill_hollow"]
    if kind == "disc":
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{p}"/>'
    if kind == "ring":
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{ring}" stroke="{p}" stroke-width="2"/>'
    if kind == "disc_ring":
        return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r+1}" fill="{ring}" stroke="{p}" stroke-width="1.5"/>'
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2" fill="{p}"/>')
    if kind == "square":
        return f'<rect x="{cx-r:.1f}" y="{cy-r:.1f}" width="{2*r}" height="{2*r}" rx="1" fill="{p}"/>'
    if kind == "square_ring":
        return f'<rect x="{cx-r:.1f}" y="{cy-r:.1f}" width="{2*r}" height="{2*r}" rx="1" fill="{ring}" stroke="{p}" stroke-width="2"/>'
    if kind == "diamond":
        return f'<path d="M{cx:.1f},{cy-r-1:.1f} L{cx+r+1:.1f},{cy:.1f} L{cx:.1f},{cy+r+1:.1f} L{cx-r-1:.1f},{cy:.1f} Z" fill="{p}"/>'
    if kind == "diamond_ring":
        return f'<path d="M{cx:.1f},{cy-r-1:.1f} L{cx+r+1:.1f},{cy:.1f} L{cx:.1f},{cy+r+1:.1f} L{cx-r-1:.1f},{cy:.1f} Z" fill="{ring}" stroke="{p}" stroke-width="2"/>'
    if kind == "triangle":
        return f'<path d="M{cx-r:.1f},{cy-r:.1f} L{cx+r+1:.1f},{cy:.1f} L{cx-r:.1f},{cy+r:.1f} Z" fill="{p}"/>'
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{p}"/>'


def render(scene, node_defs, title=None, pal=PALETTE, pad=30, show_port_labels=True):
    nodes = scene["nodes"]
    edges = scene.get("edges", [])
    by_id = {n["id"]: n for n in nodes}

    geoms = {n["id"]: _node_geom(n, node_defs[n["type"]]) for n in nodes}
    minx = min(n["position"]["x"] for n in nodes) - pad
    miny = min(n["position"]["y"] for n in nodes) - pad - (26 if title else 0)
    maxx = max(n["position"]["x"] + geoms[n["id"]][0] for n in nodes) + pad
    maxy = max(n["position"]["y"] + geoms[n["id"]][1] for n in nodes) + pad
    W, H = maxx - minx, maxy - miny

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{minx:.0f} {miny:.0f} {W:.0f} {H:.0f}" '
         f'width="{W:.0f}" height="{H:.0f}" font-family="{FONT}">']
    if pal["bg"] != "none":
        s.append(f'<rect x="{minx:.0f}" y="{miny:.0f}" width="{W:.0f}" height="{H:.0f}" fill="{pal["bg"]}"/>')
    if title:
        s.append(f'<text x="{minx+pad:.0f}" y="{miny+24:.0f}" font-size="14" font-weight="600" '
                 f'fill="{pal["ink"]}">{html.escape(title)}</text>')

    # aretes
    for e in edges:
        sc, src_pid = parse_handle(e["sourceHandle"])
        tc, dst_pid = parse_handle(e["targetHandle"])
        sn, dn = by_id[e["source"]], by_id[e["target"]]
        x1, y1 = _port_xy(sn, node_defs[sn["type"]], "out", src_pid)
        x2, y2 = _port_xy(dn, node_defs[dn["type"]], "in", dst_pid)
        dash = ' stroke-dasharray="5 4"' if sc in FLOW_TYPES else ''
        s.append(f'<path d="{bezier(x1,y1,x2,y2)}" fill="none" stroke="{pal["edge"]}" '
                 f'stroke-width="2" stroke-linecap="round"{dash}/>')

    # noeuds
    for n in nodes:
        ndef = node_defs[n["type"]]
        x, y = n["position"]["x"], n["position"]["y"]
        w, h = geoms[n["id"]]
        s.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="10" '
                 f'fill="{pal["body"]}" stroke="{pal["ink"]}" stroke-width="1.5"/>')
        s.append(f'<path d="M{x:.0f},{y+HEADER_H:.0f} L{x:.0f},{y+10:.0f} Q{x:.0f},{y:.0f} {x+10:.0f},{y:.0f} '
                 f'L{x+w-10:.0f},{y:.0f} Q{x+w:.0f},{y:.0f} {x+w:.0f},{y+10:.0f} L{x+w:.0f},{y+HEADER_H:.0f} Z" '
                 f'fill="{pal["header"]}" stroke="{pal["ink"]}" stroke-width="1.5"/>')
        s.append(f'<text x="{x+w/2:.0f}" y="{y+HEADER_H/2+5:.0f}" font-size="12.5" font-weight="600" '
                 f'text-anchor="middle" fill="{pal["ink"]}">{html.escape(ndef["label"])}</text>')
        for side, ports in (("in", ndef["inputs"]), ("out", ndef["outputs"])):
            for i, port in enumerate(ports):
                cx, cy = _port_xy(n, ndef, side, port["id"])
                s.append(_shape(cx, cy, TYPE_SHAPE.get(port.get("color"), "disc"), pal))
                if show_port_labels:
                    if side == "in":
                        s.append(f'<text x="{cx+12:.0f}" y="{cy+4:.0f}" font-size="11" fill="{pal["muted"]}">{html.escape(port["id"])}</text>')
                    else:
                        s.append(f'<text x="{cx-12:.0f}" y="{cy+4:.0f}" font-size="11" text-anchor="end" fill="{pal["muted"]}">{html.escape(port["id"])}</text>')
    s.append('</svg>')
    return "\n".join(s)


if __name__ == "__main__":
    import sys
    scene = json.load(open(sys.argv[1]))
    defs = json.load(open(sys.argv[2]))
    title = sys.argv[3] if len(sys.argv) > 3 else None
    out = sys.argv[1].rsplit(".", 1)[0] + ".svg"
    open(out, "w").write(render(scene, defs, title))
    print("ecrit:", out)
