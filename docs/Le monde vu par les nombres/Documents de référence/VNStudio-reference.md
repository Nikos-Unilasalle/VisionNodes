# VNStudio — Note de référence pour assistant LLM
 
## Qu'est-ce que VNStudio ?
 
**VNStudio** (VisionNodes Studio) est un studio de vision par ordinateur **orienté nœuds** (node-based), similaire à Blender compositor ou KNIME, mais spécialisé pour le traitement d'images et les pipelines CV en temps réel. L'utilisateur construit visuellement un graphe de traitement en connectant des nœuds — sans écrire de code pour les cas courants.
 
**Stack technique :**
- Frontend : Tauri v2 + React 18 + ReactFlow + TypeScript + Tailwind CSS
- Backend : moteur Python (`engine/engine.py`) qui tourne en sidecar local
- Communication : WebSocket sur le port 8765, frames base64 à ~30 fps
- Fichiers de scène : format `.vn` (JSON)
---
 
## Interface utilisateur
 
### Canvases (scènes)
 
4 canvases indépendants (c1–c4), chacun avec ses nœuds/arêtes/fichier. L'utilisateur switche entre scènes sans arrêter le moteur.
 
### Nœuds
 
Chaque nœud est une boîte avec :
- **Ports d'entrée** (gauche) — couleur-codés par type
- **Ports de sortie** (droite) — idem
- **Preview intégrée** — affiche le résultat en live dans le corps du nœud (pour les nœuds image)
- **Paramètres inline** — quelques contrôles directement dans le nœud
### Inspecteur (panneau droit)
 
Quand un nœud est sélectionné, le panneau droit affiche tous ses paramètres détaillés : sliders, enums, toggles, éditeur de code Python, etc.
 
### Raccourcis clavier
 
| Raccourci | Action |
|---|---|
| Cmd+Z / Cmd+Shift+Z | Undo / Redo |
| Cmd+C / Cmd+V | Copier / Coller nœuds |
| Cmd+A | Tout sélectionner |
| Cmd+S | Sauvegarder |
| Cmd+O | Ouvrir |
| Cmd+M | Menu ajout de nœud |
| Cmd+F | Fit view |
 
---
 
## Système de ports (couleurs)
 
**Règle stricte** : un port ne peut se connecter qu'à un port de même couleur (sauf `any` qui accepte tout).
 
| Couleur | Type | Usage |
|---|---|---|
| Bleu | `image` | Frame BGR NumPy (H×W×3 uint8) |
| Gris | `mask` | Masque binaire ou alpha (H×W uint8) |
| Jaune | `scalar` | Flottant ou entier unique |
| Bleu clair | `string` | Texte |
| Vert | `dict` | Dictionnaire Python |
| Violet | `list` | Liste Python |
| Blanc | `any` | Tout type |
| Rouge | `flow` | Signal de contrôle (trigger) |
| Indigo | `audio` | Buffer audio |
 
---
 
## Catégories de nœuds (≈312 nœuds au total)
 
### `input` — Sources
Nœuds de départ du graphe. Exemples :
- `webcam_source` — flux webcam live
- `image_loader` — image statique depuis disque
- `video_source` — fichier vidéo
- `scalar_input` — valeur numérique manuelle
- `string_input` — texte manuel
### `image` — Traitement image de base
- `plugin_brightness_contrast` — luminosité/contraste
- `plugin_blur` / `plugin_gaussian_blur` — flou
- `plugin_sobel` / `plugin_laplacian` — dérivées
- `plugin_rotate` / `plugin_pixelate` / `plugin_invert`
- `filter_noise_gaussian` / `filter_noise_salt_pepper`
- `filter_high_pass` / `filter_low_pass`
- `filter_glitch` — effet glitch
### `color` — Espace colorimétrique
- `cv_colorspace` — conversion BGR↔HSV↔Lab↔YCrCb…
- `plugin_split_channels` / `plugin_merge_channels`
- `cv_levels` — courbes de niveaux
- `cv_shadow_highlight`
- `raster_colorizer` — colormap sur grayscale
### `mask` — Masques
- `plugin_threshold` — seuillage basique
- `filter_float_threshold` — seuillage flottant
- `plugin_image_to_mask` / `plugin_mask_to_image`
- `plugin_invert_mask`
- `fill_holes` — remplissage morphologique
### `geometry` — Transformations géométriques
- `plugin_crop_rect` / `sci_roi_stats`
- `plugin_resize` / `plugin_flip`
- `plugin_warp_perspective`
- `util_split_half` — divise une image en deux moitiés
### `draw` — Annotations visuelles
- `draw_rect` / `draw_line` / `draw_arrow` / `draw_ellipse`
- `draw_text` — texte sur image
- `draw_point` — point/cercle
- `draw_overlay` — superposition image sur image
- `draw_tint_mask` — colorier une région masquée
### `analysis` — Mesure et analyse
- `sci_histogram` — histogramme des valeurs
- `sci_region_props` — propriétés de régions (aire, centroïde…)
- `sci_connected_components` — composantes connexes
- `sci_focus_metric` — mesure de netteté
- `sci_line_profile` — profil de ligne
- `sci_roi_stats` — stats sur ROI
### `measure` — Mesures physiques
- `sci_visual_measure` — mesure de distance en pixels
- `sci_scale_bar` — barre d'échelle
- `sci_calibration` / `sci_interactive_calibration`
- `util_monte_carlo_propagation` — propagation d'incertitude
### `segmentation` — Segmentation
- `fast_sam_segmenter` / `sam_segmenter` — SAM (Segment Anything)
- `sam_depth_guided` — segmentation guidée par profondeur
- `sci_general_segmenter` — segmentation générique
- `sci_kmeans_list` — K-Means
- `sci_index_painter` — peinture par index
### `Machine Learning` — Modèles ML
- `depth_anything_v2` — estimation de profondeur
- `dinov2_classifier` — classification DINOv2
- `cv_clip` — embeddings CLIP (similarité texte/image)
- `classif_loader` — chargeur de classificateur
- `seg_loader` — chargeur de segmenteur
- `upscale_realesrgan` — super-résolution Real-ESRGAN
### `tracking` — Suivi d'objets
- `tracker_sort` / `tracker_deepsort` — SORT / DeepSORT
- `tracker_visualize` — affichage des tracks
- `filter_bg_subtraction` — soustraction de fond (MOG2/KNN)
- `forensic_footprint` — accumulation de traces
### `body` — Analyse corporelle
- `analysis_pose_mp` — estimation de pose (MediaPipe)
- `analysis_head_pose` — orientation de tête
- `analysis_gaze` — direction du regard
- `analysis_object_mp` — détection d'objets MediaPipe
- `transform_eye_crop` — recadrage sur les yeux
### `keypoints` — Points caractéristiques
- `cv_features` — détection ORB/SIFT/AKAZE
- `cv_ransac` — RANSAC pour homographie
### `math` — Opérations mathématiques
- Opérations arithmétiques entre scalaires et images
- `plugin_gradient` — gradient d'une image
- `sci_fft` / `sci_ifft` — transformée de Fourier
- `sci_normalizer` — normalisation [0,1]
- `sci_spectral_gain`
### `signal` — Signaux temporels
- `signal_clock` — horloge / timestamp
- `signal_gate` — porte conditionnelle
- `signal_generator` — générateur sinusoïdal/carré
- `plugin_filter_median` / `plugin_filter_lowpass` / `plugin_filter_ma` — filtres temporels
### `visualize` — Visualisation de données
- `sci_colormap` — colormaps matplotlib
- `sci_cluster_heatmap` — heatmap de clustering
- `viz_grid_compare` — grille de comparaison
- `sci_plotter` — plotter de courbes (ports dynamiques)
### `logic` — Contrôle de flux
- `logic_if` / `logic_switch` — branchement conditionnel
- `logic_python` — nœud Python libre (code exécuté frame par frame)
- `logic_collect` — collecte de valeurs
### `utility` — Utilitaires
- `util_csv_export` — export CSV
- `util_image_masking` — application de masque
- `variable_store` — stockage d'une variable entre frames
- `util_on_each` — itération sur liste
### `output` — Sorties
- `output_display` — affichage image (ports dynamiques, accepte plusieurs images)
- `sci_export_particles` — export de données
- `df_export` — export DataFrame
### `canvas` — Annotations de scène
- `gen_canvas` — canvas de notes/annotations (non-traitement)
- `canvas_frame` / `canvas_note` — blocs visuels dans la scène
### `DataFrame` — Tableaux de données
Suite complète de nœuds pandas-like :
`df_editor`, `df_export`, `df_fillna`, `df_groupby`, `df_merge`, `df_new_col`, `df_rename`, `df_sample`, `df_select`, `df_sort`
 
### `geography` / `geology` (62 nœuds)
Domaine spécialisé (télédétection, GIS, géologie) — moins pertinent pour un livre CV généraliste.
 
---
 
## Comment construire un pipeline typique
 
### Exemple minimal : seuillage en temps réel
 
```
[webcam_source] → [cv_colorspace (BGR→Gray)] → [plugin_threshold] → [output_display]
```
 
### Exemple moyen : détection de contours
 
```
[webcam_source]
    → [plugin_blur]
    → [plugin_sobel]
    → [plugin_threshold]
    → [draw_overlay] ← [webcam_source]
    → [output_display]
```
 
### Exemple avancé : pipeline ML
 
```
[image_loader] → [depth_anything_v2] → [sci_colormap] → [output_display]
              ↘ [fast_sam_segmenter] → [draw_overlay]  ↗
```
 
---
 
## Nœud `logic_python` — Code Python libre
 
Nœud spécial : l'utilisateur écrit du code Python exécuté à chaque frame. Ports `input_1..N` / `output_1..N` configurables. Sandbox sécurisé (exec). Idéal pour expliquer des algos sans créer un vrai plugin.
 
```python
# Exemple dans logic_python
import cv2
img = inputs.get('input_1')
result = cv2.Canny(img, 100, 200)
outputs['output_1'] = result
```
 
---
 
## Créer un nouveau nœud (pour exercices avancés)
 
Créer un fichier `.py` dans `engine/plugins/` :
 
```python
import cv2
import numpy as np
from registry import vision_node, NodeProcessor
 
@vision_node(
    type_id='mon_algo',
    label='Mon Algorithme',
    category='image',
    icon='Zap',
    inputs=[{'id': 'image', 'color': 'image'}],
    outputs=[{'id': 'main', 'color': 'image'}],
    params=[
        {'id': 'ksize', 'label': 'Kernel', 'type': 'int', 'min': 1, 'max': 31, 'default': 5}
    ]
)
class MonAlgo(NodeProcessor):
    def process(self, inputs, params):
        img = inputs.get('image')
        if img is None:
            return {'main': None}
        k = int(params.get('ksize', 5))
        # ... logique ici
        return {'main': result}
```
 
**Règles importantes :**
- `type_id` doit être unique dans tout le projet
- Ne jamais importer un autre plugin depuis un plugin (architecture isolée)
- Ne jamais modifier `engine.py` ou `registry.py`
- Le nœud apparaît immédiatement au redémarrage du moteur
---
 
## Format de fichier `.vn`
 
JSON avec structure :
```json
{
  "nodes": [
    {
      "id": "node-1",
      "type": "webcam_source",
      "position": { "x": 100, "y": 200 },
      "data": { "params": {}, "ports": [] }
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "node-1",
      "sourceHandle": "image__main",
      "target": "node-2",
      "targetHandle": "image__image"
    }
  ]
}
```
 
Les `handle` IDs suivent le format `{color}__{port_id}`.
 
---
 
## Patterns pédagogiques recommandés pour le livre
 
### Structure d'un chapitre pratique
 
1. **Concept théorique** → expliqué textuellement
2. **Pipeline de référence** → screenshot ou description du graphe `.vn`
3. **Exercice guidé** → "construire ce pipeline étape par étape"
4. **Exercice libre** → "modifier un paramètre et observer l'effet"
5. **Extension** → "créer un nœud custom qui implémente X"
---
 
## Contraintes et limitations à connaître
 
- **Pas de GPU obligatoire** — les nœuds ML (SAM, DepthAnything…) fonctionnent en CPU mais lentement ; indiquer aux lecteurs que la preview peut ralentir
- **Toujours en local** — aucune donnée ne quitte la machine
- **30 fps théorique** — les nœuds lourds (ML) font chuter le framerate ; normal
- **Connexions strictement typées** — connecter un port `image` à un port `scalar` est impossible visuellement
- **`logic_python` = bac à sable** — idéal pour les exercices d'implémentation manuelle d'algos
- **Labels des nœuds toujours en anglais** dans le code source (même si l'UI peut être localisée)
---
 
## Commandes de développement
 
```bash
npm run studio        # Lance l'app (Tauri + moteur Python)
pytest engine/tests/  # Tests Python
npm test              # Tests TypeScript (Vitest)
```
 
---
