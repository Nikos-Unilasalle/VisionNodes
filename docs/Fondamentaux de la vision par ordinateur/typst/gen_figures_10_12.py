"""
gen_figures_10_12.py — Génère les SVG ch10-12 via vn_to_svg.py.
Labels alignés sur les vrais noms de nodes VNStudio (juin 2026).
Remplace les anciens SVG générés par un outil externe.
"""
import sys, pathlib

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT.parent.parent / "export-canva-to-svg"))
import vn_to_svg as v

OUT = ROOT / "figures"

def n(id_, type_, x, y, w=158):
    return {"id": id_, "type": type_, "position": {"x": x, "y": y}, "width": w}

def e(src, sh, tgt, th):
    return {"source": src, "sourceHandle": sh, "target": tgt, "targetHandle": th}

def scene(nodes, edges=None):
    return {"nodes": nodes, "edges": edges or []}

BASE = {
    "image_loader":   {"label": "Image File",
                       "inputs": [],
                       "outputs": [{"id": "main", "color": "image"}]},
    "output_display": {"label": "Display",
                       "inputs": [{"id": "main", "color": "image"}],
                       "outputs": []},
    "colormap":       {"label": "Colormap / LUT",
                       "inputs": [{"id": "image", "color": "any"}],
                       "outputs": [{"id": "main", "color": "image"}]},
    "split_half":     {"label": "Split Half",
                       "inputs": [{"id": "image", "color": "image"}, {"id": "mask", "color": "mask"}],
                       "outputs": [{"id": "first_image", "color": "image"}, {"id": "second_image", "color": "image"}]},
    # ch10 — transformées
    "fft_analysis":   {"label": "FFT Analysis",
                       "inputs": [{"id": "image", "color": "image"}],
                       "outputs": [{"id": "main", "color": "image"},
                                   {"id": "magnitude", "color": "image"},
                                   {"id": "complex_data", "color": "data"}]},
    "inverse_fft":    {"label": "Inverse FFT",
                       "inputs": [{"id": "complex_data", "color": "data"}],
                       "outputs": [{"id": "main", "color": "image"}]},
    "threshold":      {"label": "Threshold",
                       "inputs": [{"id": "image", "color": "image"}],
                       "outputs": [{"id": "main", "color": "image"}, {"id": "mask", "color": "mask"}]},
    "dist_transform": {"label": "Distance Transform",
                       "inputs": [{"id": "mask", "color": "any"}],
                       "outputs": [{"id": "main", "color": "image"}, {"id": "dist_map", "color": "any"}]},
    "canny":          {"label": "Canny Edge",
                       "inputs": [{"id": "image", "color": "image"}],
                       "outputs": [{"id": "main", "color": "image"}]},
    "hough_lines":    {"label": "Hough Lines",
                       "inputs": [{"id": "image", "color": "any"}],
                       "outputs": [{"id": "lines_list", "color": "list"}]},
    "draw_overlay":   {"label": "Draw Overlay",
                       "inputs": [{"id": "image", "color": "image"}, {"id": "draw", "color": "dict"}],
                       "outputs": [{"id": "main", "color": "image"}]},
    "python_node":    {"label": "Python Node",
                       "inputs": [{"id": "image", "color": "image"}],
                       "outputs": [{"id": "main", "color": "image"}]},
    # ch11 — morphologie
    "morphology":     {"label": "Morphology",
                       "inputs": [{"id": "mask", "color": "mask"}],
                       "outputs": [{"id": "mask", "color": "mask"}]},
    "morphology_adv": {"label": "Morphology (Advanced)",
                       "inputs": [{"id": "mask", "color": "any"}],
                       "outputs": [{"id": "main", "color": "image"}, {"id": "mask", "color": "mask"}]},
    "skeleton":       {"label": "Skeleton",
                       "inputs": [{"id": "mask", "color": "mask"}],
                       "outputs": [{"id": "main", "color": "image"}]},
    # ch12 — segmentation
    "adaptive_thr":   {"label": "Adaptive Threshold",
                       "inputs": [{"id": "image", "color": "image"}],
                       "outputs": [{"id": "main", "color": "mask"}]},
    "kmeans_seg":     {"label": "K-Means Segmentation",
                       "inputs": [{"id": "image", "color": "image"}],
                       "outputs": [{"id": "main", "color": "image"}]},
    "meanshift_seg":  {"label": "Mean Shift Segmentation",
                       "inputs": [{"id": "image", "color": "image"}],
                       "outputs": [{"id": "main", "color": "image"}]},
}

FIGURES = {}

# ── ch10 obs1 : FFT filter ────────────────────────────────────────────────────
FIGURES["fig_ch10_obs1_fft_filter"] = (
    "Observation 10.1 — FFT : filtrer dans le spectre = convoluer dans l'espace",
    {k: BASE[k] for k in ["image_loader","fft_analysis","inverse_fft","output_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("fft","fft_analysis", 210,  0, 165),
         n("ifft","inverse_fft", 430,  0, 165),
         n("out1","output_display",640,  0),
         n("out2","output_display",640, 66)],
        [e("img","image__main","fft","image__image"),
         e("fft","image__magnitude","out1","image__main"),
         e("fft","data__complex_data","ifft","data__complex_data"),
         e("ifft","image__main","out2","image__main")]
    )
)

# ── ch10 obs2 : distance transform ───────────────────────────────────────────
FIGURES["fig_ch10_obs2_distance_transform"] = (
    "Observation 10.2 — Transform. de distance : iso-contours = éloignement du bord",
    {k: BASE[k] for k in ["image_loader","threshold","dist_transform","colormap","output_display"]},
    scene(
        [n("img","image_loader",     0,  0),
         n("thr","threshold",       210,  0),
         n("dt","dist_transform",   400,  0, 185),
         n("cm","colormap",         640,  0),
         n("out","output_display",  800,  0)],
        [e("img","image__main","thr","image__image"),
         e("thr","mask__mask","dt","any__mask"),
         e("dt","image__main","cm","any__image"),
         e("cm","image__main","out","image__main")]
    )
)

# ── ch10 obs3 : Hough ─────────────────────────────────────────────────────────
FIGURES["fig_ch10_obs3_hough"] = (
    "Observation 10.3 — Hough : un pic dans l'accumulateur = une droite dans l'image",
    {k: BASE[k] for k in ["image_loader","canny","hough_lines","python_node","output_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("can","canny",        210,  0),
         n("hl","hough_lines",   380,  0, 165),
         n("dn","python_node",   590,  0, 165),
         n("out","output_display",800,  0)],
        [e("img","image__main","can","image__image"),
         e("can","image__main","hl","any__image"),
         e("img","image__main","dn","image__image"),
         e("hl","list__lines_list","dn","image__image"),
         e("dn","image__main","out","image__main")]
    )
)

# ── ch11 obs1 : érosion ───────────────────────────────────────────────────────
FIGURES["fig_ch11_obs1_erosion"] = (
    "Observation 11.1 — Érosion : l'objet rétrécit, le bruit disparaît",
    {k: BASE[k] for k in ["image_loader","threshold","morphology","output_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("thr","threshold",    210,  0),
         n("mor","morphology",   400,  0, 165),
         n("out1","output_display",600,  0),
         n("out2","output_display",600, 66)],
        [e("img","image__main","thr","image__image"),
         e("thr","mask__mask","mor","mask__mask"),
         e("thr","image__main","out1","image__main"),
         e("mor","mask__mask","out2","image__main")]
    )
)

# ── ch11 obs2 : gradient morphologique ───────────────────────────────────────
FIGURES["fig_ch11_obs2_morph_gradient"] = (
    "Observation 11.2 — Gradient morpho. : dil − éro = le contour seul",
    {k: BASE[k] for k in ["image_loader","threshold","morphology_adv","colormap","output_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("thr","threshold",    210,  0),
         n("mg","morphology_adv",400,  0, 185),
         n("cm","colormap",      640,  0),
         n("out","output_display",800,  0)],
        [e("img","image__main","thr","image__image"),
         e("thr","mask__mask","mg","any__mask"),
         e("mg","image__main","cm","any__image"),
         e("cm","image__main","out","image__main")]
    )
)

# ── ch11 obs3 : squelette ─────────────────────────────────────────────────────
FIGURES["fig_ch11_obs3_skeleton"] = (
    "Observation 11.3 — Squelette : l'axe médian réduit l'objet à 1 px d'épaisseur",
    {k: BASE[k] for k in ["image_loader","threshold","skeleton","output_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("thr","threshold",    210,  0),
         n("sk","skeleton",      400,  0, 165),
         n("out","output_display",600,  0)],
        [e("img","image__main","thr","image__image"),
         e("thr","mask__mask","sk","mask__mask"),
         e("sk","image__main","out","image__main")]
    )
)

# ── ch12 obs1 : Otsu global vs adaptatif ─────────────────────────────────────
FIGURES["fig_ch12_obs1_otsu"] = (
    "Observation 12.1 — Otsu global vs seuillage adaptatif local",
    {k: BASE[k] for k in ["image_loader","threshold","adaptive_thr","split_half","output_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("gt","threshold",     210,  0),
         n("at","adaptive_thr",  210, 66, 185),
         n("sh","split_half",    430, 33, 165),
         n("out","output_display",630, 33)],
        [e("img","image__main","gt","image__image"),
         e("img","image__main","at","image__image"),
         e("gt","image__main","sh","image__image"),
         e("at","mask__main","sh","mask__mask"),
         e("sh","image__first_image","out","image__main")]
    )
)

# ── ch12 obs2 : K-means ───────────────────────────────────────────────────────
FIGURES["fig_ch12_obs2_kmeans"] = (
    "Observation 12.2 — K-Means : 3 centroides, 3 classes de couleur",
    {k: BASE[k] for k in ["image_loader","kmeans_seg","output_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("km","kmeans_seg",    210,  0, 185),
         n("out","output_display",440,  0)],
        [e("img","image__main","km","image__image"),
         e("km","image__main","out","image__main")]
    )
)

# ── ch12 obs3 : Mean-shift vs K-means ────────────────────────────────────────
FIGURES["fig_ch12_obs3_meanshift"] = (
    "Observation 12.3 — Mean-shift : k auto vs K-Means k fixe",
    {k: BASE[k] for k in ["image_loader","kmeans_seg","meanshift_seg","split_half","output_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("km","kmeans_seg",    210,  0, 185),
         n("ms","meanshift_seg", 210, 66, 200),
         n("sh","split_half",    450, 33, 165),
         n("out","output_display",650, 33)],
        [e("img","image__main","km","image__image"),
         e("img","image__main","ms","image__image"),
         e("km","image__main","sh","image__image"),
         e("ms","image__main","sh","mask__mask"),
         e("sh","image__first_image","out","image__main")]
    )
)

# ── génération ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ok = err = 0
    for slug, (title, defs, sc) in FIGURES.items():
        try:
            svg = v.render(sc, defs, title=title)
            path = OUT / f"{slug}.svg"
            path.write_text(svg, encoding="utf-8")
            print(f"  OK  {slug}.svg")
            ok += 1
        except Exception as ex:
            print(f"  ERR {slug}: {ex}")
            err += 1
    print(f"\n{ok} générés, {err} erreurs")
