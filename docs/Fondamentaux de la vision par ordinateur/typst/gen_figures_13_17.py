"""
gen_figures_13_17.py — Génère les SVG manquants ch13-17 via vn_to_svg.py.
Chaque figure = une scène VNStudio (nodes + edges) définie inline.
Labels alignés sur les vrais noms de nodes VNStudio (mai 2026).
"""
import sys, os, pathlib

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT.parent.parent / "export-canva-to-svg"))
import vn_to_svg as v

OUT = ROOT / "figures"

# ── helpers de placement ──────────────────────────────────────────────────────

def n(id_, type_, x, y, w=158):
    return {"id": id_, "type": type_, "position": {"x": x, "y": y}, "width": w}

def e(src, sh, tgt, th):
    return {"source": src, "sourceHandle": sh, "target": tgt, "targetHandle": th}

def scene(nodes, edges=None):
    return {"nodes": nodes, "edges": edges or []}

# ── node_defs partagés ────────────────────────────────────────────────────────
# Ports: format {color}__{port_id} dans les edges.
# Labels = vrais noms VNStudio. Nodes sans équivalent réel → "Python Node".

BASE = {
    # ── entrées / sorties réelles ─────────────────────────────────────────────
    "image_loader":     {"label": "Image File",        "inputs": [],                                   "outputs": [{"id":"main","color":"image"}]},
    "output_display":   {"label": "Display",           "inputs": [{"id":"main","color":"image"}],      "outputs": []},
    "scalar_display":   {"label": "Display",           "inputs": [{"id":"value","color":"scalar"}],    "outputs": []},
    # ── filtres / traitements réels ───────────────────────────────────────────
    "blur":             {"label": "Blur",              "inputs": [{"id":"image","color":"image"}],     "outputs": [{"id":"main","color":"image"}]},
    "histogram":        {"label": "Histogram",         "inputs": [{"id":"image","color":"any"}],       "outputs": [{"id":"main","color":"image"}]},
    "brightness":       {"label": "Bright & Contrast", "inputs": [{"id":"image","color":"image"}],     "outputs": [{"id":"main","color":"image"}]},
    # ── détecteurs de points d'intérêt réels ─────────────────────────────────
    "orb_detector":     {"label": "ORB Detector",
                         "inputs":  [{"id":"image","color":"image"}],
                         "outputs": [{"id":"keypoints","color":"list"}, {"id":"descriptors","color":"any"}]},
    "sift_detector":    {"label": "SIFT Detector",
                         "inputs":  [{"id":"image","color":"image"}],
                         "outputs": [{"id":"keypoints","color":"list"}, {"id":"descriptors","color":"any"}]},
    "feat_matcher":     {"label": "Feature Matcher",
                         "inputs":  [{"id":"des1","color":"any"}, {"id":"des2","color":"any"},
                                     {"id":"kp1","color":"list"},  {"id":"kp2","color":"list"},
                                     {"id":"img1","color":"image"}, {"id":"img2","color":"image"}],
                         "outputs": [{"id":"main","color":"image"}, {"id":"matches_count","color":"scalar"}]},
    "ransac_hom":       {"label": "RANSAC Homography",
                         "inputs":  [{"id":"kp1","color":"list"},  {"id":"kp2","color":"list"},
                                     {"id":"des1","color":"any"},  {"id":"des2","color":"any"},
                                     {"id":"img1","color":"image"}, {"id":"img2","color":"image"}],
                         "outputs": [{"id":"warped","color":"image"}]},
    # ── ch13 texture ─────────────────────────────────────────────────────────
    "glcm_extractor":   {"label": "GLCM",
                         "inputs":  [{"id":"image","color":"image"}],
                         "outputs": [{"id":"main","color":"image"},
                                     {"id":"contrast","color":"scalar"},
                                     {"id":"homogeneity","color":"scalar"}]},
    "lbp_texture":      {"label": "Local Binary Pattern",
                         "inputs":  [{"id":"image","color":"image"}],
                         "outputs": [{"id":"main","color":"image"}, {"id":"hist_image","color":"image"}]},
    "gabor_bank":       {"label": "Gabor Bank",
                         "inputs":  [{"id":"image","color":"image"}],
                         "outputs": [{"id":"energy","color":"image"}, {"id":"response","color":"image"}]},
    "texture_energy":   {"label": "Python Node",
                         "inputs":  [{"id":"response","color":"image"}],
                         "outputs": [{"id":"energy","color":"image"}]},
    # ── ch14 qualité image ───────────────────────────────────────────────────
    "shift_image":      {"label": "Offset Shift",
                         "inputs":  [{"id":"image","color":"image"}],
                         "outputs": [{"id":"main","color":"image"}]},
    "ssim_psnr":        {"label": "SSIM / PSNR",
                         "inputs":  [{"id":"image","color":"image"}, {"id":"reference","color":"image"}],
                         "outputs": [{"id":"main","color":"image"},
                                     {"id":"ssim","color":"scalar"}, {"id":"psnr","color":"scalar"}]},
    "laplacian_var":    {"label": "Focus Metric",
                         "inputs":  [{"id":"image","color":"any"}],
                         "outputs": [{"id":"main","color":"image"}, {"id":"score","color":"scalar"}]},
    # ── ch15 apprentissage profond ────────────────────────────────────────────
    "classifier":       {"label": "Python Node",
                         "inputs":  [{"id":"image","color":"image"}],
                         "outputs": [{"id":"logits","color":"any"}]},
    "ground_truth":     {"label": "Python Node",   "inputs": [],                                  "outputs": [{"id":"label","color":"any"}]},
    "cross_entropy":    {"label": "Python Node",
                         "inputs":  [{"id":"logits","color":"any"}, {"id":"label","color":"any"}],
                         "outputs": [{"id":"loss","color":"scalar"}]},
    "object_detector":  {"label": "YOLO Detector",
                         "inputs":  [{"id":"image","color":"image"}],
                         "outputs": [{"id":"main","color":"image"}, {"id":"objects_list","color":"list"}]},
    "gt_box":           {"label": "Python Node",   "inputs": [],                                  "outputs": [{"id":"boxes","color":"any"}]},
    "iou_loss":         {"label": "Python Node",
                         "inputs":  [{"id":"pred","color":"any"}, {"id":"gt","color":"any"}],
                         "outputs": [{"id":"loss","color":"scalar"}]},
    "giou_loss":        {"label": "Python Node",
                         "inputs":  [{"id":"pred","color":"any"}, {"id":"gt","color":"any"}],
                         "outputs": [{"id":"loss","color":"scalar"}]},
    # ── ch16 estimation robuste ───────────────────────────────────────────────
    "sample_gen":       {"label": "Python Node",   "inputs": [],                                  "outputs": [{"id":"values","color":"any"}]},
    "robust_mean":      {"label": "Python Node",
                         "inputs":  [{"id":"values","color":"any"}],
                         "outputs": [{"id":"estimate","color":"scalar"}]},
    "robust_median":    {"label": "Python Node",
                         "inputs":  [{"id":"values","color":"any"}],
                         "outputs": [{"id":"estimate","color":"scalar"}]},
    "mestimator_huber": {"label": "Python Node",
                         "inputs":  [{"id":"values","color":"any"}],
                         "outputs": [{"id":"estimate","color":"scalar"}, {"id":"influence","color":"any"}]},
    "mestimator_tukey": {"label": "Python Node",
                         "inputs":  [{"id":"values","color":"any"}],
                         "outputs": [{"id":"estimate","color":"scalar"}, {"id":"influence","color":"any"}]},
    # ── ch17 descripteurs locaux ──────────────────────────────────────────────
    "log_pyramid":      {"label": "Python Node",
                         "inputs":  [{"id":"image","color":"image"}],
                         "outputs": [{"id":"pyramid","color":"any"}]},
    "extrema_detector": {"label": "Python Node",
                         "inputs":  [{"id":"pyramid","color":"any"}],
                         "outputs": [{"id":"keypoints","color":"any"}]},
    "keypoint_drawer":  {"label": "Python Node",
                         "inputs":  [{"id":"image","color":"image"}, {"id":"keypoints","color":"any"}],
                         "outputs": [{"id":"main","color":"image"}]},
    "hog_visualizer":   {"label": "Python Node",
                         "inputs":  [{"id":"image","color":"image"}],
                         "outputs": [{"id":"glyph_map","color":"image"}, {"id":"descriptor","color":"any"}]},
    "patch_extractor":  {"label": "Python Node",
                         "inputs":  [{"id":"image","color":"image"}, {"id":"keypoints","color":"any"}],
                         "outputs": [{"id":"patches","color":"any"}]},
    "ssd_matcher":      {"label": "Python Node",
                         "inputs":  [{"id":"patches1","color":"any"}, {"id":"patches2","color":"any"}],
                         "outputs": [{"id":"main","color":"image"}]},
}

# ── FIGURE DEFINITIONS ────────────────────────────────────────────────────────

FIGURES = {}

# ── ch13 obs1 : GLCM ─────────────────────────────────────────────────────────
FIGURES["fig_ch13_obs1_glcm"] = (
    "Observation 13.1 — GLCM : texture lisse vs contrastée",
    {k: BASE[k] for k in ["image_loader","glcm_extractor","scalar_display","output_display"]},
    scene(
        [n("img","image_loader",    0,  0),
         n("glcm","glcm_extractor",210,  0, 190),
         n("sc1","scalar_display",  460,  0),
         n("sc2","scalar_display",  460, 66),
         n("out","output_display",  460,132)],
        [e("img","image__main","glcm","image__image"),
         e("glcm","scalar__contrast","sc1","scalar__value"),
         e("glcm","scalar__homogeneity","sc2","scalar__value"),
         e("glcm","image__main","out","image__main")]
    )
)

# ── ch13 obs2 : LBP ──────────────────────────────────────────────────────────
FIGURES["fig_ch13_obs2_lbp"] = (
    "Observation 13.2 — LBP : le micro-motif en 8 questions binaires",
    {k: BASE[k] for k in ["image_loader","lbp_texture","histogram","output_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("lbp","lbp_texture",  210, 0, 180),
         n("hist","histogram",   440, 0),
         n("out","output_display",440, 66)],
        [e("img","image__main","lbp","image__image"),
         e("lbp","image__main","out","image__main"),
         e("lbp","image__hist_image","hist","image__image")]
    )
)

# ── ch13 obs3 : Gabor ────────────────────────────────────────────────────────
FIGURES["fig_ch13_obs3_gabor"] = (
    "Observation 13.3 — Banc de Gabor : résonance fréquentielle et angulaire",
    {k: BASE[k] for k in ["image_loader","gabor_bank","texture_energy","output_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("gb","gabor_bank",    210, 0, 170),
         n("te","texture_energy",430, 0),
         n("out1","output_display",430, 66),
         n("out2","output_display",430,132)],
        [e("img","image__main","gb","image__image"),
         e("gb","image__response","te","image__response"),
         e("te","image__energy","out1","image__main"),
         e("gb","image__energy","out2","image__main")]
    )
)

# ── ch14 obs1 : PSNR shift ───────────────────────────────────────────────────
FIGURES["fig_ch14_obs1_mse_shift"] = (
    "Observation 14.1 — PSNR : décalage d'1 px invisible à l'œil, score catastrophique",
    {k: BASE[k] for k in ["image_loader","shift_image","ssim_psnr","scalar_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("shift","shift_image",210, 66),
         n("qm","ssim_psnr",     420,  0, 165),
         n("sc1","scalar_display",  640, 0),
         n("sc2","scalar_display",  640, 66)],
        [e("img","image__main","qm","image__reference"),
         e("img","image__main","shift","image__image"),
         e("shift","image__main","qm","image__image"),
         e("qm","scalar__psnr","sc1","scalar__value"),
         e("qm","scalar__ssim","sc2","scalar__value")]
    )
)

# ── ch14 obs2 : SSIM ─────────────────────────────────────────────────────────
FIGURES["fig_ch14_obs2_ssim"] = (
    "Observation 14.2 — SSIM : luminance décalée, structure intacte",
    {k: BASE[k] for k in ["image_loader","brightness","ssim_psnr","scalar_display"]},
    scene(
        [n("img","image_loader",     0,  0),
         n("bright","brightness",   210, 66),
         n("qm","ssim_psnr",        420, 33, 165),
         n("sc1","scalar_display",  640,  0),
         n("sc2","scalar_display",  640, 66)],
        [e("img","image__main","qm","image__reference"),
         e("img","image__main","bright","image__image"),
         e("bright","image__main","qm","image__image"),
         e("qm","scalar__psnr","sc1","scalar__value"),
         e("qm","scalar__ssim","sc2","scalar__value")]
    )
)

# ── ch14 obs3 : sharpness ────────────────────────────────────────────────────
FIGURES["fig_ch14_obs3_sharpness"] = (
    "Observation 14.3 — Netteté : Focus Metric, net vs flouté",
    {k: BASE[k] for k in ["image_loader","blur","laplacian_var","scalar_display"]},
    scene(
        [n("img","image_loader",    0,  0),
         n("blr","blur",          210, 66),
         n("sv1","laplacian_var", 420,  0, 175),
         n("sv2","laplacian_var", 420, 66, 175),
         n("sc1","scalar_display",  650,  0),
         n("sc2","scalar_display",  650, 66)],
        [e("img","image__main","sv1","image__image"),
         e("img","image__main","blr","image__image"),
         e("blr","image__main","sv2","image__image"),
         e("sv1","scalar__score","sc1","scalar__value"),
         e("sv2","scalar__score","sc2","scalar__value")]
    )
)

# ── ch15 obs1 : cross-entropy ────────────────────────────────────────────────
FIGURES["fig_ch15_obs1_crossentropy"] = (
    "Observation 15.1 — Entropie croisée : le coût explose quand la confiance s'effondre",
    {k: BASE[k] for k in ["image_loader","classifier","ground_truth","cross_entropy","scalar_display"]},
    scene(
        [n("img","image_loader",   0,  0),
         n("gt","ground_truth",    0, 66),
         n("cls","classifier",    210,  0),
         n("ce","cross_entropy",  420,  0, 175),
         n("sc","scalar_display",   645,  0)],
        [e("img","image__main","cls","image__image"),
         e("cls","any__logits","ce","any__logits"),
         e("gt","any__label","ce","any__label"),
         e("ce","scalar__loss","sc","scalar__value")]
    )
)

# ── ch15 obs2 : GIoU ─────────────────────────────────────────────────────────
FIGURES["fig_ch15_obs2_giou"] = (
    "Observation 15.2 — IoU plat à 0, GIoU qui guide vers la cible",
    {k: BASE[k] for k in ["image_loader","object_detector","gt_box","iou_loss","giou_loss","scalar_display"]},
    scene(
        [n("img","image_loader",    0,  0),
         n("gt","gt_box",           0, 66),
         n("det","object_detector",210,  0),
         n("iou","iou_loss",       420,  0, 155),
         n("giu","giou_loss",      420, 66, 155),
         n("sc1","scalar_display",   625,  0),
         n("sc2","scalar_display",   625, 66)],
        [e("img","image__main","det","image__image"),
         e("det","list__objects_list","iou","any__pred"),
         e("det","list__objects_list","giu","any__pred"),
         e("gt","any__boxes","iou","any__gt"),
         e("gt","any__boxes","giu","any__gt"),
         e("iou","scalar__loss","sc1","scalar__value"),
         e("giu","scalar__loss","sc2","scalar__value")]
    )
)

# ── ch16 obs1 : median ───────────────────────────────────────────────────────
FIGURES["fig_ch16_obs1_median"] = (
    "Observation 16.1 — Médiane : la valeur centrale qui résiste à l'aberrant",
    {k: BASE[k] for k in ["sample_gen","robust_mean","robust_median","scalar_display"]},
    scene(
        [n("sg","sample_gen",      0,  0),
         n("mn","robust_mean",   210,  0),
         n("md","robust_median", 210, 66),
         n("sc1","scalar_display",  420,  0),
         n("sc2","scalar_display",  420, 66)],
        [e("sg","any__values","mn","any__values"),
         e("sg","any__values","md","any__values"),
         e("mn","scalar__estimate","sc1","scalar__value"),
         e("md","scalar__estimate","sc2","scalar__value")]
    )
)

# ── ch16 obs2 : M-estimators ─────────────────────────────────────────────────
FIGURES["fig_ch16_obs2_mestimators"] = (
    "Observation 16.2 — Fonctions d'influence ψ : MCO, Huber, Tukey",
    {k: BASE[k] for k in ["sample_gen","robust_mean","mestimator_huber","mestimator_tukey","scalar_display"]},
    scene(
        [n("sg","sample_gen",         0,  0),
         n("ols","robust_mean",      210,  0),
         n("hub","mestimator_huber", 210, 66, 185),
         n("tuk","mestimator_tukey", 210,148, 185),
         n("sc1","scalar_display",     445,  0),
         n("sc2","scalar_display",     445, 66),
         n("sc3","scalar_display",     445,148)],
        [e("sg","any__values","ols","any__values"),
         e("sg","any__values","hub","any__values"),
         e("sg","any__values","tuk","any__values"),
         e("ols","scalar__estimate","sc1","scalar__value"),
         e("hub","scalar__estimate","sc2","scalar__value"),
         e("tuk","scalar__estimate","sc3","scalar__value")]
    )
)

# ── ch16 obs3 : RANSAC ───────────────────────────────────────────────────────
FIGURES["fig_ch16_obs3_ransac"] = (
    "Observation 16.3 — RANSAC : consensus contre le mensonge des outliers",
    {k: BASE[k] for k in ["image_loader","orb_detector","ransac_hom","output_display"]},
    scene(
        [n("im1","image_loader",   0,   0),
         n("im2","image_loader",   0,  66),
         n("o1","orb_detector",   210,   0, 165),
         n("o2","orb_detector",   210,  66, 165),
         n("ra","ransac_hom",     430,  10, 185),
         n("out","output_display", 665,  33)],
        [e("im1","image__main","o1","image__image"),
         e("im2","image__main","o2","image__image"),
         e("o1","list__keypoints","ra","list__kp1"),
         e("o2","list__keypoints","ra","list__kp2"),
         e("o1","any__descriptors","ra","any__des1"),
         e("o2","any__descriptors","ra","any__des2"),
         e("im1","image__main","ra","image__img1"),
         e("im2","image__main","ra","image__img2"),
         e("ra","image__warped","out","image__main")]
    )
)

# ── ch17 obs1 : SSD vs descriptor ────────────────────────────────────────────
FIGURES["fig_ch17_01_ssd_vs_descripteur"] = (
    "Observation 17.1 — SSD brut vs descripteur invariant : qui survit à la transformation ?",
    {k: BASE[k] for k in ["image_loader","orb_detector","feat_matcher","patch_extractor","ssd_matcher","output_display"]},
    scene(
        [n("im1","image_loader",   0,   0),
         n("im2","image_loader",   0,  66),
         # voie descripteur (ORB + Feature Matcher)
         n("o1","orb_detector",   210,  0, 165),
         n("o2","orb_detector",   210, 66, 165),
         n("fm","feat_matcher",   430,  10, 180),
         n("out1","output_display", 660,  33),
         # voie SSD (patches bruts)
         n("p1","patch_extractor",210, 170, 180),
         n("p2","patch_extractor",210, 246, 180),
         n("ssd","ssd_matcher",   430, 208, 165),
         n("out2","output_display", 650, 208)],
        [e("im1","image__main","o1","image__image"),
         e("im2","image__main","o2","image__image"),
         e("o1","any__descriptors","fm","any__des1"),
         e("o2","any__descriptors","fm","any__des2"),
         e("o1","list__keypoints","fm","list__kp1"),
         e("o2","list__keypoints","fm","list__kp2"),
         e("im1","image__main","fm","image__img1"),
         e("im2","image__main","fm","image__img2"),
         e("fm","image__main","out1","image__main"),
         e("im1","image__main","p1","image__image"),
         e("im2","image__main","p2","image__image"),
         e("o1","list__keypoints","p1","any__keypoints"),
         e("o2","list__keypoints","p2","any__keypoints"),
         e("p1","any__patches","ssd","any__patches1"),
         e("p2","any__patches","ssd","any__patches2"),
         e("ssd","image__main","out2","image__main")]
    )
)

# ── ch17 obs2 : espace d'échelle ─────────────────────────────────────────────
FIGURES["fig_ch17_02_echelle_caracteristique"] = (
    "Observation 17.2 — Espace d'échelle : le blob trouve son σ optimal dans le LoG",
    {k: BASE[k] for k in ["image_loader","log_pyramid","extrema_detector","keypoint_drawer","output_display"]},
    scene(
        [n("img","image_loader",    0,  0),
         n("log","log_pyramid",   210,  0, 160),
         n("ext","extrema_detector",420, 0, 175),
         n("kd","keypoint_drawer", 640, 0, 165),
         n("out","output_display",  860,  0)],
        [e("img","image__main","log","image__image"),
         e("log","any__pyramid","ext","any__pyramid"),
         e("ext","any__keypoints","kd","any__keypoints"),
         e("img","image__main","kd","image__image"),
         e("kd","image__main","out","image__main")]
    )
)

# ── ch17 obs3 : HOG glyphs ───────────────────────────────────────────────────
FIGURES["fig_ch17_03_hog_glyphes"] = (
    "Observation 17.3 — HOG : glyphes d'orientation, invariant à la lumière",
    {k: BASE[k] for k in ["image_loader","hog_visualizer","output_display"]},
    scene(
        [n("img","image_loader",   0,  0),
         n("hog","hog_visualizer",210,  0, 175),
         n("out","output_display", 435,  0)],
        [e("img","image__main","hog","image__image"),
         e("hog","image__glyph_map","out","image__main")]
    )
)

# ── ch17 obs4 : SIFT orientation ─────────────────────────────────────────────
FIGURES["fig_ch17_04_sift_orientation"] = (
    "Observation 17.4 — SIFT : l'orientation dominante tourne la carte locale du descripteur",
    {k: BASE[k] for k in ["image_loader","sift_detector","keypoint_drawer","output_display"]},
    scene(
        [n("img","image_loader",     0,  0),
         n("sift","sift_detector",  210,  0, 165),
         n("kd","keypoint_drawer",  430,  0, 165),
         n("out","output_display",  650,  0)],
        [e("img","image__main","sift","image__image"),
         e("sift","list__keypoints","kd","any__keypoints"),
         e("img","image__main","kd","image__image"),
         e("kd","image__main","out","image__main")]
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
