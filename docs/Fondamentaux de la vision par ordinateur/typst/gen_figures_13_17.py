"""
gen_figures_13_17.py — Génère les SVG manquants ch13-17 via vn_to_svg.py.
Chaque figure = une scène VNStudio (nodes + edges) définie inline.
Nodes inexistants acceptés : ils seront créés plus tard dans VNStudio.
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

BASE = {
    "image_loader":     {"label": "Image Loader",       "inputs": [],                                  "outputs": [{"id":"image","color":"image"}]},
    "output_display":   {"label": "Output Display",     "inputs": [{"id":"image","color":"image"}],    "outputs": []},
    "scalar_display":   {"label": "Scalar Display",     "inputs": [{"id":"value","color":"scalar"}],   "outputs": []},
    "blur":             {"label": "Blur",                "inputs": [{"id":"image","color":"image"}],    "outputs": [{"id":"image","color":"image"}]},
    "histogram":        {"label": "Histogram",           "inputs": [{"id":"image","color":"image"}],    "outputs": [{"id":"image","color":"image"}]},
    "orb_detector":     {"label": "ORB Detector",        "inputs": [{"id":"image","color":"image"}],    "outputs": [{"id":"keypoints","color":"any"}, {"id":"descriptors","color":"any"}]},
    "bf_matcher":       {"label": "BFMatcher",           "inputs": [{"id":"desc1","color":"any"}, {"id":"desc2","color":"any"}], "outputs": [{"id":"matches","color":"any"}]},
    "match_drawer":     {"label": "Match Drawer",        "inputs": [{"id":"img1","color":"image"}, {"id":"img2","color":"image"}, {"id":"matches","color":"any"}], "outputs": [{"id":"image","color":"image"}]},
    # ch13
    "glcm_extractor":   {"label": "GLCM Extractor",     "inputs": [{"id":"image","color":"image"}],    "outputs": [{"id":"matrix","color":"any"}, {"id":"contrast","color":"scalar"}, {"id":"homogeneity","color":"scalar"}]},
    "lbp_texture":      {"label": "LBP Texture",         "inputs": [{"id":"image","color":"image"}],    "outputs": [{"id":"lbp_map","color":"image"}, {"id":"histogram","color":"any"}]},
    "gabor_bank":       {"label": "Gabor Bank",          "inputs": [{"id":"image","color":"image"}],    "outputs": [{"id":"energy","color":"image"}, {"id":"response","color":"image"}]},
    "texture_energy":   {"label": "Texture Energy",      "inputs": [{"id":"response","color":"image"}], "outputs": [{"id":"energy","color":"image"}]},
    # ch14
    "shift_image":      {"label": "Shift Image",         "inputs": [{"id":"image","color":"image"}],    "outputs": [{"id":"image","color":"image"}]},
    "mse_psnr":         {"label": "MSE / PSNR",          "inputs": [{"id":"ref","color":"image"}, {"id":"distorted","color":"image"}], "outputs": [{"id":"mse","color":"scalar"}, {"id":"psnr","color":"scalar"}]},
    "brightness":       {"label": "Brightness",          "inputs": [{"id":"image","color":"image"}],    "outputs": [{"id":"image","color":"image"}]},
    "ssim_metric":      {"label": "SSIM",                "inputs": [{"id":"ref","color":"image"}, {"id":"distorted","color":"image"}], "outputs": [{"id":"score","color":"scalar"}, {"id":"map","color":"image"}]},
    "laplacian_var":    {"label": "Sharpness (Laplacian Var.)", "inputs": [{"id":"image","color":"image"}], "outputs": [{"id":"score","color":"scalar"}]},
    # ch15
    "classifier":       {"label": "Classifier",          "inputs": [{"id":"image","color":"image"}],    "outputs": [{"id":"logits","color":"any"}]},
    "ground_truth":     {"label": "Ground Truth",        "inputs": [],                                  "outputs": [{"id":"label","color":"any"}]},
    "cross_entropy":    {"label": "Cross-Entropy Loss",  "inputs": [{"id":"logits","color":"any"}, {"id":"label","color":"any"}], "outputs": [{"id":"loss","color":"scalar"}]},
    "object_detector":  {"label": "Object Detector",     "inputs": [{"id":"image","color":"image"}],    "outputs": [{"id":"boxes","color":"any"}]},
    "gt_box":           {"label": "Ground Truth Box",    "inputs": [],                                  "outputs": [{"id":"boxes","color":"any"}]},
    "iou_loss":         {"label": "IoU Loss",            "inputs": [{"id":"pred","color":"any"}, {"id":"gt","color":"any"}],   "outputs": [{"id":"loss","color":"scalar"}]},
    "giou_loss":        {"label": "GIoU Loss",           "inputs": [{"id":"pred","color":"any"}, {"id":"gt","color":"any"}],   "outputs": [{"id":"loss","color":"scalar"}]},
    # ch16
    "sample_gen":       {"label": "Sample Generator",   "inputs": [],                                  "outputs": [{"id":"values","color":"any"}]},
    "robust_mean":      {"label": "Mean (OLS)",          "inputs": [{"id":"values","color":"any"}],     "outputs": [{"id":"estimate","color":"scalar"}]},
    "robust_median":    {"label": "Median",              "inputs": [{"id":"values","color":"any"}],     "outputs": [{"id":"estimate","color":"scalar"}]},
    "mestimator_huber": {"label": "M-Estimator (Huber)", "inputs": [{"id":"values","color":"any"}],     "outputs": [{"id":"estimate","color":"scalar"}, {"id":"influence","color":"any"}]},
    "mestimator_tukey": {"label": "M-Estimator (Tukey)", "inputs": [{"id":"values","color":"any"}],     "outputs": [{"id":"estimate","color":"scalar"}, {"id":"influence","color":"any"}]},
    "ransac_filter":    {"label": "RANSAC Filter",       "inputs": [{"id":"matches","color":"any"}],    "outputs": [{"id":"inliers","color":"any"}, {"id":"mask","color":"mask"}]},
    "homography":       {"label": "Homography",          "inputs": [{"id":"inliers","color":"any"}],    "outputs": [{"id":"H","color":"any"}, {"id":"warped","color":"image"}]},
    # ch17
    "sift_detector":    {"label": "SIFT Detector",       "inputs": [{"id":"image","color":"image"}],    "outputs": [{"id":"keypoints","color":"any"}, {"id":"descriptors","color":"any"}]},
    "log_pyramid":      {"label": "LoG Pyramid",         "inputs": [{"id":"image","color":"image"}],    "outputs": [{"id":"pyramid","color":"any"}]},
    "extrema_detector": {"label": "Scale Extrema",       "inputs": [{"id":"pyramid","color":"any"}],    "outputs": [{"id":"keypoints","color":"any"}]},
    "keypoint_drawer":  {"label": "Keypoint Drawer",     "inputs": [{"id":"image","color":"image"}, {"id":"keypoints","color":"any"}], "outputs": [{"id":"image","color":"image"}]},
    "hog_visualizer":   {"label": "HOG Visualizer",      "inputs": [{"id":"image","color":"image"}],    "outputs": [{"id":"glyph_map","color":"image"}, {"id":"descriptor","color":"any"}]},
    "patch_extractor":  {"label": "Patch Extractor",     "inputs": [{"id":"image","color":"image"}, {"id":"keypoints","color":"any"}], "outputs": [{"id":"patches","color":"any"}]},
    "ssd_matcher":      {"label": "SSD Matcher",         "inputs": [{"id":"patches1","color":"any"}, {"id":"patches2","color":"any"}], "outputs": [{"id":"matches","color":"any"}]},
}

# ── FIGURE DEFINITIONS ────────────────────────────────────────────────────────

FIGURES = {}

# ── ch13 obs1 : GLCM ─────────────────────────────────────────────────────────
FIGURES["fig_ch13_obs1_glcm"] = (
    "Observation 13.1 — GLCM : texture lisse vs contrastée",
    {k: BASE[k] for k in ["image_loader","glcm_extractor","scalar_display","output_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("glcm","glcm_extractor",210, 0, 190),
         n("sc1","scalar_display",  460, 0),
         n("sc2","scalar_display",  460, 66),
         n("out","output_display",  460,132)],
        [e("img","image__image","glcm","image__image"),
         e("glcm","scalar__contrast","sc1","scalar__value"),
         e("glcm","scalar__homogeneity","sc2","scalar__value"),
         e("glcm","any__matrix","out","image__image")]
    )
)

# ── ch13 obs2 : LBP ──────────────────────────────────────────────────────────
FIGURES["fig_ch13_obs2_lbp"] = (
    "Observation 13.2 — LBP : le micro-motif en 8 questions binaires",
    {k: BASE[k] for k in ["image_loader","lbp_texture","histogram","output_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("lbp","lbp_texture",  210, 0, 160),
         n("hist","histogram",   420, 0),
         n("out","output_display",420, 66)],
        [e("img","image__image","lbp","image__image"),
         e("lbp","image__lbp_map","out","image__image"),
         e("lbp","any__histogram","hist","image__image")]
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
         n("out","output_display",430, 66)],
        [e("img","image__image","gb","image__image"),
         e("gb","image__response","te","image__response"),
         e("te","image__energy","out","image__image"),
         e("gb","image__energy","out","image__image")]
    )
)

# ── ch14 obs1 : MSE shift ────────────────────────────────────────────────────
FIGURES["fig_ch14_obs1_mse_shift"] = (
    "Observation 14.1 — MSE : décalage d'1 px invisible à l'œil, PSNR catastrophique",
    {k: BASE[k] for k in ["image_loader","shift_image","mse_psnr","scalar_display"]},
    scene(
        [n("img","image_loader",  0,  0),
         n("shift","shift_image",210, 66),
         n("mse","mse_psnr",     420, 0, 170),
         n("sc1","scalar_display",  640, 0),
         n("sc2","scalar_display",  640, 66)],
        [e("img","image__image","mse","image__ref"),
         e("img","image__image","shift","image__image"),
         e("shift","image__image","mse","image__distorted"),
         e("mse","scalar__mse","sc1","scalar__value"),
         e("mse","scalar__psnr","sc2","scalar__value")]
    )
)

# ── ch14 obs2 : SSIM ─────────────────────────────────────────────────────────
FIGURES["fig_ch14_obs2_ssim"] = (
    "Observation 14.2 — SSIM : luminance décalée, structure intacte",
    {k: BASE[k] for k in ["image_loader","brightness","mse_psnr","ssim_metric","scalar_display"]},
    scene(
        [n("img","image_loader",     0,  0),
         n("bright","brightness",   210, 66),
         n("mse","mse_psnr",        420,  0, 170),
         n("ssim","ssim_metric",    420, 92, 160),
         n("sc1","scalar_display",  640,  0),
         n("sc2","scalar_display",  640, 92)],
        [e("img","image__image","mse","image__ref"),
         e("img","image__image","ssim","image__ref"),
         e("img","image__image","bright","image__image"),
         e("bright","image__image","mse","image__distorted"),
         e("bright","image__image","ssim","image__distorted"),
         e("mse","scalar__psnr","sc1","scalar__value"),
         e("ssim","scalar__score","sc2","scalar__value")]
    )
)

# ── ch14 obs3 : sharpness ────────────────────────────────────────────────────
FIGURES["fig_ch14_obs3_sharpness"] = (
    "Observation 14.3 — Netteté : variance du Laplacien, net vs flouté",
    {k: BASE[k] for k in ["image_loader","blur","laplacian_var","scalar_display"]},
    scene(
        [n("img","image_loader",    0,  0),
         n("blr","blur",          210, 66),
         n("sv1","laplacian_var", 420,  0, 190),
         n("sv2","laplacian_var", 420, 66, 190),
         n("sc1","scalar_display",  660,  0),
         n("sc2","scalar_display",  660, 66)],
        [e("img","image__image","sv1","image__image"),
         e("img","image__image","blr","image__image"),
         e("blr","image__image","sv2","image__image"),
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
        [e("img","image__image","cls","image__image"),
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
        [e("img","image__image","det","image__image"),
         e("det","any__boxes","iou","any__pred"),
         e("det","any__boxes","giu","any__pred"),
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
    {k: BASE[k] for k in ["image_loader","orb_detector","bf_matcher","ransac_filter","homography","output_display"]},
    scene(
        [n("im1","image_loader",   0,   0),
         n("im2","image_loader",   0,  66),
         n("o1","orb_detector",   210,  0, 165),
         n("o2","orb_detector",   210, 66, 165),
         n("bf","bf_matcher",     430, 33, 165),
         n("ra","ransac_filter",  650, 33, 165),
         n("hm","homography",     870, 33),
         n("out","output_display",1040, 33)],
        [e("im1","image__image","o1","image__image"),
         e("im2","image__image","o2","image__image"),
         e("o1","any__descriptors","bf","any__desc1"),
         e("o2","any__descriptors","bf","any__desc2"),
         e("bf","any__matches","ra","any__matches"),
         e("ra","any__inliers","hm","any__inliers"),
         e("hm","image__warped","out","image__image")]
    )
)

# ── ch17 obs1 : SSD vs descriptor ────────────────────────────────────────────
FIGURES["fig_ch17_01_ssd_vs_descripteur"] = (
    "Observation 17.1 — SSD brut vs descripteur invariant : qui survit à la transformation ?",
    {k: BASE[k] for k in ["image_loader","orb_detector","bf_matcher","patch_extractor","ssd_matcher","match_drawer","output_display"]},
    scene(
        [n("im1","image_loader",   0,   0),
         n("im2","image_loader",   0,  66),
         # voie ORB
         n("o1","orb_detector",   210,  0, 165),
         n("o2","orb_detector",   210, 66, 165),
         n("bf","bf_matcher",     430, 33, 165),
         n("md1","match_drawer",  650, 0, 165),
         n("out1","output_display",870,  0),
         # voie SSD
         n("p1","patch_extractor",210, 156, 180),
         n("p2","patch_extractor",210, 222, 180),
         n("ssd","ssd_matcher",   440, 189, 165),
         n("md2","match_drawer",  655, 156, 165),
         n("out2","output_display",875, 156)],
        [e("im1","image__image","o1","image__image"),
         e("im2","image__image","o2","image__image"),
         e("o1","any__descriptors","bf","any__desc1"),
         e("o2","any__descriptors","bf","any__desc2"),
         e("bf","any__matches","md1","any__matches"),
         e("im1","image__image","md1","image__img1"),
         e("im2","image__image","md1","image__img2"),
         e("md1","image__image","out1","image__image"),
         e("im1","image__image","p1","image__image"),
         e("im2","image__image","p2","image__image"),
         e("o1","any__keypoints","p1","any__keypoints"),
         e("o2","any__keypoints","p2","any__keypoints"),
         e("p1","any__patches","ssd","any__patches1"),
         e("p2","any__patches","ssd","any__patches2"),
         e("ssd","any__matches","md2","any__matches"),
         e("im1","image__image","md2","image__img1"),
         e("im2","image__image","md2","image__img2"),
         e("md2","image__image","out2","image__image")]
    )
)

# ── ch17 obs2 : espace d'échelle ─────────────────────────────────────────────
FIGURES["fig_ch17_02_echelle_caracteristique"] = (
    "Observation 17.2 — Espace d'échelle : le blob trouve son σ optimal dans le LoG",
    {k: BASE[k] for k in ["image_loader","log_pyramid","extrema_detector","keypoint_drawer","output_display"]},
    scene(
        [n("img","image_loader",    0,  0),
         n("log","log_pyramid",   210,  0, 160),
         n("ext","extrema_detector",420, 0, 170),
         n("kd","keypoint_drawer", 640, 0, 170),
         n("out","output_display",  860,  0)],
        [e("img","image__image","log","image__image"),
         e("log","any__pyramid","ext","any__pyramid"),
         e("ext","any__keypoints","kd","any__keypoints"),
         e("img","image__image","kd","image__image"),
         e("kd","image__image","out","image__image")]
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
        [e("img","image__image","hog","image__image"),
         e("hog","image__glyph_map","out","image__image")]
    )
)

# ── ch17 obs4 : SIFT orientation ─────────────────────────────────────────────
FIGURES["fig_ch17_04_sift_orientation"] = (
    "Observation 17.4 — SIFT : l'orientation dominante tourne la carte locale du descripteur",
    {k: BASE[k] for k in ["image_loader","sift_detector","keypoint_drawer","output_display"]},
    scene(
        [n("img","image_loader",     0,  0),
         n("sift","sift_detector",  210,  0, 165),
         n("kd","keypoint_drawer",  430,  0, 170),
         n("out","output_display",  650,  0)],
        [e("img","image__image","sift","image__image"),
         e("sift","any__keypoints","kd","any__keypoints"),
         e("img","image__image","kd","image__image"),
         e("kd","image__image","out","image__image")]
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
