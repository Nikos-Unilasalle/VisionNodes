#!/usr/bin/env python3
"""check_node_labels.py — un nœud, un nom.

Trois sources nomment les nœuds, et rien ne les tenait d'accord :

  1. le décorateur `@vision_node(label=…)` dans `engine/plugins/*.py` — la source
     de vérité du moteur, celle que lit la documentation ;
  2. `src/data/categories.ts` — ce que la palette affiche réellement, car
     `App.tsx` ignore le schéma du plugin dès que le `type` y est déjà listé, et
     `scripts/generate_nodes_json.py` écrase le label Python par `ts_label` ;
  3. les pages étudiantes et les scripts de figures, qui citent un nom en dur.

La dérive a atteint 74 nœuds avant d'être mesurée, dont 17 cités par le livre ou
les missions — l'étudiant lisait un nom que la palette n'affichait pas. Ce script
échoue quand les trois sources se contredisent. Il est l'équivalent, côté outil,
du détecteur D7 du livre : sans lui, D7 valide des noms que personne ne voit.

Usage :
    python3 scripts/check_node_labels.py            # tout
    python3 scripts/check_node_labels.py --palette   # seulement décorateur ↔ palette
    python3 scripts/check_node_labels.py --docs      # seulement les noms cités
Sortie : 0 si tout concorde, 1 sinon.
"""
import argparse
import ast
import pathlib
import re
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Nœuds dont le libellé de palette diverge volontairement du décorateur, faute
# d'être cités où que ce soit : les aligner serait un renommage gratuit. Toute
# NOUVELLE divergence doit être décidée, pas héritée — d'où cette liste explicite,
# qui n'a le droit que de rétrécir.
DIVERGENCES_TOLEREES = {
    # préfixe « Math: » du décorateur, que la palette laisse tomber — la catégorie le dit déjà
    'math_abs',
    'math_add',
    'math_clamp',
    'math_cos',
    'math_distance',
    'math_div',
    'math_max',
    'math_min',
    'math_mod',
    'math_mul',
    'math_pow',
    'math_round',
    'math_sin',
    'math_sub',
    # idem pour « String: »
    'string_case',
    'string_concat',
    'string_input',
    'string_length',
    'string_replace',
    'string_split',
    # nœuds de domaine (géo, pétro, racines, IMU) que ni le livre ni les missions ne citent
    'geo_color_segmenter',
    'geo_dn_normalize',
    'geo_grain_segment',
    'geo_grain_stats',
    'geo_index',
    'geo_land_cover',
    'geo_mineral_key',
    'geo_opaque_detect',
    'geo_petro_tableau',
    'geo_sediment_loader',
    'geo_turbidity_stats',
    'imu_phase_dashboard',
    'petro_grain_separator',
    'petro_neighbor_analysis',
    'petro_point_counter',
    'root_aerenchyma_detect',
    'root_calibrate',
    'root_cortex_areas',
    'root_layers',
    'root_protoxylem_detect',
    # divergences héritées sur des nœuds qu'aucune page ne cite
    'analysis_object_mp',
    'cv_shadow_highlight',
    'depth_anything_v2',
    'feat_ndwi',
    'feat_seeds_from_boundaries',
    'feat_water_refine',
    'filter_bg_subtraction',
    'filter_directional_morphology',
    'filter_glitch',
    'filter_high_pass',
    'filter_linear_direction',
    'filter_linearity',
    'geom_approx_poly',
    'geom_warp_affine',
    'logic_presence',
    'mask_to_svg',
    'ocr_east_detect',
    'plugin_brightness_contrast',
    'plugin_evm_color',
    'plugin_evm_motion',
    'plugin_filter_ema',
    'plugin_filter_holt',
    'plugin_filter_loess',
    'plugin_invert',
    'plugin_pixelate',
    'sam_depth_guided',
    'sam_grain_stats',
    'sci_kmeans_list',
    'sci_matrix_dist',
    'sci_normalizer',
    'serial_reader',
    'tracker_visualize',
    'upscale_realesrgan',
    'util_dict_merge',
    'util_filter_label',
    'util_image_masking',
}

# Doublons de libellé antérieurs à ce contrôle. `data_coord_splitter` est pire
# qu'un doublon de nom : le même type_id est déclaré dans deux fichiers, donc une
# des deux implémentations est écrasée au chargement. À trancher, hors de ce lot.
DOUBLONS_TOLERES = {
    'Coord Splitter',
    'Fill Holes',
    'Note',
    'Spectral Index',
}

# Libellés légitimes qu'aucun décorateur ne porte : nœuds purement front-end
# (math, chaînes, logique Python) et étiquettes de canvas.
HORS_REGISTRE = {"Frame", "Note", "Reroute", "Group"}

# Registre des noms retirés : ancien nom -> nom actuel.
#
# Chaque renommage de nœud s'inscrit ici, et le contrôle des pages se fait contre
# cette liste et rien d'autre. C'est ce qui le rend sans faux positif : « Cell
# Mask » ou « Rescue Unseeded Regions » sont des paramètres, « Préparer » un
# intertitre, et aucun des deux n'a jamais nommé un nœud. Une liste de noms morts
# est décidable ; « ce qui ressemble à un nom de nœud » ne l'est pas.
#
# Vider une entrée n'est pas un nettoyage : c'est perdre la capacité de trouver la
# page qui cite encore l'ancien nom. La liste ne se purge qu'en supprimant aussi
# le nœud.
ANCIENS_NOMS = {
    # 18/09/2026 — alignement palette ↔ décorateur sur les nœuds cités par le
    # livre et les missions. Le livre citait le décorateur, la palette affichait
    # autre chose ; les pages étudiantes devaient donner les deux noms.
    "Advanced Threshold":        "Threshold (Advanced)",
    "Advanced Morphology":       "Morphology (Advanced)",
    "Blend Modes":               "Blend",
    "Connected Comp. (CV2)":     "Connected Components (Markers)",
    "Grain Size Histogram":      "Grain Histogram",
    "Filter: Low Pass":          "Low Pass",
    "Apply Colormap":            "Colormap (Simple)",
    "Colormap / LUT":            "Colormap",
    "FastSAM Grain Segmentation": "AI Segmenter (FastSAM)",
    "SAM Segmenter":             "AI Segmenter (SAM)",
    "Group IN":                  "Group Input",
    "Group OUT":                 "Group Output",
    "Data Compare":              "Compare",
    "Sobel Edge":                "Sobel Edge Detector",
    "Offset":                    "Offset Shift",
    "Rotate":                    "Rotate Image",
    "Gradient":                  "Image Gradient",
    "CLAHE":                     "CLAHE (Contrast)",
    "FFT":                       "FFT Analysis",
}

# « Offset », « Rotate », « Gradient », « CLAHE » et « FFT » sont aussi des mots
# de la langue : la prose les emploie légitimement. Le contrôle ne les signale
# donc que balisés comme des nœuds — entre accents graves ou en gras suivi de
# « node » / « nœud » — ce que fait déjà noms_cites() pour les .md.
AMBIGUS = {"Offset", "Rotate", "Gradient", "CLAHE", "FFT", "Compare", "Blend"}


def labels_decorateurs():
    """type_id -> (label, fichier). Lu à l'AST : c'est ce que le moteur enregistre."""
    out = {}
    doublons = defaultdict(list)
    for p in sorted((ROOT / "engine" / "plugins").rglob("*.py")):
        try:
            tree = ast.parse(p.read_text(errors="replace"))
        except SyntaxError as e:
            print(f"  ✗ {p.name} illisible : {e}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for deco in node.decorator_list:
                if not (isinstance(deco, ast.Call)
                        and getattr(deco.func, "id", "") == "vision_node"):
                    continue
                kw = {k.arg: k.value for k in deco.keywords}
                t, l = kw.get("type_id"), kw.get("label")
                if isinstance(t, ast.Constant) and isinstance(l, ast.Constant):
                    out[t.value] = (l.value, p.name)
                    doublons[l.value].append(t.value)
    return out, {l: ts for l, ts in doublons.items() if len(ts) > 1}


def labels_palette():
    """type_id -> label, tel que `categories.ts` le déclare."""
    src = (ROOT / "src" / "data" / "categories.ts").read_text()
    return {m.group(1): m.group(2)
            for m in re.finditer(r"type:\s*'([^']+)'\s*,\s*label:\s*'([^']+)'", src)}


def noms_cites():
    """(nom cité, fichier, ligne) pour les pages étudiantes et les générateurs.

    Ne retient que les noms *balisés* comme des nœuds — entre accents graves ou en
    gras —, jamais la prose : « le gradient » n'est pas une citation de nœud.
    """
    cites = []
    sources = [
        (ROOT / "docs" / "Missions", ("*.md", "*.py", "*.vn")),
        (ROOT / "docs" / "TP", ("*.md", "*.vn")),
        (ROOT / "public" / "templates", ("*.vn",)),
        (ROOT / "gallery", ("*.vn",)),
        (ROOT / "src" / "data", ("examples.ts",)),
    ]
    for base, motifs in sources:
        if not base.exists():
            continue
        for motif in motifs:
            for p in sorted(base.rglob(motif)):
                for k, line in enumerate(p.read_text(errors="replace").split("\n"), 1):
                    if p.suffix in (".py", ".vn", ".ts"):
                        # label d'instance d'un graphe, ou label écrit en dur dans
                        # un générateur de figures : les deux doivent suivre le
                        # registre (interdit n° 1 de docs/Missions/BIBLE.md).
                        trouves = re.findall(r'"label"\s*:\s*"([^"]+)"', line)
                        trouves += re.findall(r"label:\s*'([^']+)'", line)
                    else:
                        trouves = (re.findall(r"`([A-Z][^`\n]{2,40})`", line)
                                   + re.findall(r"\*\*([A-Z][^*\n]{2,40})\*\*", line))
                    for nom in trouves:
                        cites.append((nom.strip(), p.relative_to(ROOT), k))
    return cites


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--palette", action="store_true")
    ap.add_argument("--docs", action="store_true")
    args = ap.parse_args()
    tout = not (args.palette or args.docs)

    dec, doublons = labels_decorateurs()
    connus = {l for l, _ in dec.values()} | HORS_REGISTRE
    echecs = 0

    if tout:
        print(f"registre : {len(dec)} nœuds")
        doublons = {l: ts for l, ts in doublons.items() if l not in DOUBLONS_TOLERES}
        if doublons:
            echecs += len(doublons)
            print(f"\n✗ {len(doublons)} libellé(s) de décorateur en doublon — "
                  f"deux nœuds portent le même nom, aucune page ne peut les distinguer")
            for l, ts in sorted(doublons.items()):
                print(f"    {l!r} → {', '.join(ts)}")

    if tout or args.palette:
        pal = labels_palette()
        mis = {t: (pal[t], dec[t][0]) for t in pal
               if t in dec and pal[t] != dec[t][0] and t not in DIVERGENCES_TOLEREES}
        if mis:
            echecs += len(mis)
            print(f"\n✗ {len(mis)} nœud(s) dont la palette contredit le décorateur.")
            print("    La palette gagne à l'écran : l'étudiant ne verra jamais le nom de droite.")
            for t, (p, d) in sorted(mis.items()):
                print(f"    {t:34s} palette {p!r:32s} ≠ plugin {d!r}")
        elif tout:
            print("✓ palette et décorateurs concordent")

    if tout or args.docs:
        # Seuls les noms retirés sont cherchés : voir ANCIENS_NOMS. Un nom encore
        # porté par un nœud est juste, un nom qui n'en a jamais porté est de la
        # prose — restent les noms morts, et eux seuls sont une erreur.
        perimes = defaultdict(list)
        vivants = {l for l, _ in dec.values()} | set(labels_palette().values())
        for nom, f, k in noms_cites():
            if nom in ANCIENS_NOMS and nom not in vivants:
                perimes[nom].append(f"{f}:{k}")
        if perimes:
            echecs += len(perimes)
            print(f"\n✗ {sum(len(v) for v in perimes.values())} citation(s) d'un nom "
                  f"de nœud retiré, dans {len(perimes)} nom(s)")
            for n, locs in sorted(perimes.items(), key=lambda x: -len(x[1])):
                print(f"    {n!r} → {ANCIENS_NOMS[n]!r} : {len(locs)} citation(s)")
                for loc in locs:
                    print(f"        {loc}")
        elif tout:
            print("✓ aucune page ne cite un nom de nœud retiré")

    if echecs:
        print(f"\n{echecs} incohérence(s). Un nœud, un nom : aligner "
              f"`categories.ts` sur le décorateur, ou l'inverse — mais trancher.")
        return 1
    print("\n✓ un nœud, un nom.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
