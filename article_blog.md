# VisionNodes Studio : la vision par ordinateur sans les prises de tête

**Apex-Unilasalle — Avril 2026**

---

## Le problème que tout chercheur connaît

Vous avez une idée. Une bonne idée. Vous voulez tester si l'algorithme de Watershed peut segmenter les billes de votre expérience, ou si l'amplification vidéo d'Euler (*Eulerian Video Magnification*) est capable de capturer le pouls d'un sujet sans contact. Vous ouvrez votre éditeur, vous écrivez cent lignes de Python, vous lancez le script. Erreur de dimension. Vous corrigez. Le résultat s'affiche une seconde puis la fenêtre se ferme. Vous ajoutez un `waitKey`. Vous relancez. Le seuil que vous avez choisi ne convient pas. Vous modifiez la constante, vous sauvegardez, vous relancez. Encore et encore.

Ce cycle — éditer, sauvegarder, relancer, regarder, recommencer — est le quotidien de milliers de chercheurs, de doctorants et d'ingénieurs en traitement d'image. Ce n'est pas une question de compétence : OpenCV est puissant, Python est expressif. C'est simplement que le modèle de développement en script est mal adapté à l'exploration visuelle et paramétrique. On passe plus de temps à déboguer la plomberie (dimensions de tableaux, conversions BGR/RGB, gestion de la caméra, affichage) qu'à penser à l'algorithme lui-même.

C'est pour répondre à ce problème que le laboratoire **APEX d'UniLaSalle** a développé **VisionNodes Studio**.

---

## Qu'est-ce que VisionNodes Studio ?

VisionNodes Studio est un environnement de programmation visuelle dédié à la vision par ordinateur et au traitement d'image scientifique. L'idée centrale est simple : au lieu d'écrire un script linéaire, vous construisez un **graphe de nœuds** (*node graph*). Chaque nœud représente une opération — lire une image, appliquer un filtre, détecter des objets, exporter un CSV — et vous les connectez entre eux par des câbles colorés. Le résultat se calcule et s'affiche **en temps réel**, à chaque modification d'un paramètre.

L'interface est une application de bureau construite avec **Tauri + React + TypeScript** côté frontend, et un moteur Python tournant en processus séparé côté backend. Les deux communiquent via WebSocket : à chaque fois que vous déplacez un curseur ou ajoutez un nœud, le moteur Python recalcule le graphe et renvoie les images résultantes à l'interface. Aucune latence perceptible pour la plupart des opérations, et une expérience qui ressemble davantage à Blender ou TouchDesigner qu'à un terminal.

Les nœuds sont des **plugins Python** déposés dans un dossier `engine/plugins/`. Le système les détecte et les charge au démarrage. Il suffit d'écrire une classe Python décorée avec `@vision_node` et de la glisser dans le dossier — le moteur n'a pas besoin d'être modifié.

---

## L'interface en un coup d'œil

L'interface se compose de trois zones principales.

**Le canevas central** est l'espace de travail où vous disposez vos nœuds. Chaque nœud affiche ses entrées à gauche et ses sorties à droite, sous forme de ports colorés : bleu pour les images, violet pour les listes, jaune pour les scalaires, blanc pour les types génériques, gris pour les masques, orange pour les flux de données. La couleur permet de repérer d'un coup d'œil les connexions incompatibles.

**Le panneau de paramètres** apparaît lorsque vous sélectionnez un nœud : sliders, menus déroulants, champs de texte, sélecteurs de fichier — chaque paramètre est modifiable à chaud. Déplacer un slider recalcule instantanément tout le sous-graphe en aval.

**La barre latérale** contient le catalogue de nœuds organisé par catégorie, ainsi qu'un menu d'exemples préconfigurés.

---

## Le catalogue de nœuds

À ce jour, VisionNodes Studio embarque plus de **55 nœuds** répartis en plusieurs familles.

### Sources
**Input Image** charge un fichier statique, **Input Webcam** capture en direct depuis une caméra V4L2, **Input Movie** lit une vidéo frame par frame avec contrôle play/pause.

### Filtres et transformations
**Gaussian Blur**, **Sobel Edge**, **Brightness & Contrast**, **Invert Color**, **Pixelate**, **Rotate Image**, **Offset Shift**, **Glitch FX** (décalage de canaux), et trois générateurs de bruit : **Gaussian**, **Salt & Pepper** et **Speckle**.

### Morphologie et segmentation
C'est l'un des points forts pour les scientifiques. Les nœuds **Morphology Advanced** (ouverture, fermeture, gradient, top-hat, black-hat), **Threshold Advanced** (binaire, Otsu, Otsu inversé, seuil relatif), **Distance Transform**, **Connected Components**, **Marker Filter** et **Watershed** permettent de construire des pipelines de segmentation complets sans écrire de code.

### Canaux et masques
**Channel Split** / **Channel Merge** pour décomposer et recomposer les canaux, **Image to Mask** / **Mask to Image** pour passer d'un espace à l'autre, **Blend Images**, **Advanced Blend**, **Blend Modes** pour les fusions.

### Détection et tracking
**YOLO Object Detection** (YOLOv11, plusieurs tailles de modèle), **MediaPipe Object Detector**, **Pose Tracker** (squelette humain temps réel), **Hand Tracker** (landmarks de la main), **SORT Tracker** (Kalman + algorithme hongrois) et **DeepSORT Tracker** (avec embeddings CNN pour la réidentification). Un nœud **Tracker Visualize** superpose les trajectoires et les identifiants sur la vidéo.

### Eulerian Video Magnification (EVM)
Deux nœuds issus de Wu et al. (2012) : **EVM Color** amplifie les variations chromatiques subtiles pour la détection de pouls, **EVM Motion** amplifie les micro-mouvements. Les deux embarquent le filtrage temporel passe-bande dans leur implémentation.

### OCR
**OCR EAST Detect** localise les zones de texte avec le modèle EAST, **OCR Tesseract** les transcrit. Les deux se chaînent naturellement.

### Traitement du signal
**Moving Average**, **Exponential Smoothing (EMA)**, **Kalman Filter**, **Particle Filter**, **Low-pass Filter**, **Median Filter**, **Savitzky-Golay** et **LOESS/LOWESS** — des filtres temporels pour nettoyer des séries mesurées frame par frame, utiles par exemple pour lisser un signal cardiaque extrait par EVM avant affichage.

### Logique et programmation
Le nœud **Python Node** expose un éditeur de code intégré. Les variables `a`, `b`, `c` reçoivent les entrées ; `out_main`, `out_scalar`, `out_any` exposent les sorties. L'objet `state` persiste entre les frames, ce qui permet d'accumuler des données au fil du temps. Complémentaires : **Math Op**, **Logic Op**, **String Op**, **Dict Get**, **Label Filter**, **On Each** (appliquer un sous-graphe à chaque élément d'une liste).

### Géométrie
**Geometry Op**, **Geometry Advanced**, **Warp Affine**, **Coord Center**.

### Visualisation et sorties
**Output Display** affiche une image en temps réel dans le canevas, **Data Inspector** inspecte n'importe quelle valeur, **Analysis Monitor** (graphique barre/valeur numérique), **Sci Plotter** (courbe temporelle défilante), **Sci Marker Analysis** (mesures et centroïdes sur régions segmentées), **CSV Export**, **Snapshot**.

### Dessin et annotation
**Draw Line**, **Draw Point**, **Draw Rect**, **Draw Text**, **Draw Overlay**.

---

## Les exemples comme cas d'école

VisionNodes Studio est livré avec **16 exemples préconfigurés**, chargeable en un clic depuis le menu.

**OCR Scanner (Tesseract)** : détecte les zones de texte dans une image avec EAST, sélectionne la première région détectée et la transcrit avec Tesseract. Un bon point d'entrée pour comprendre comment chaîner des nœuds hétérogènes.

**Movement Analysis (MOG2)** : soustraction de fond en temps réel sur le flux webcam, extraction des contours. Cinq nœuds.

**Harris Corner Detection** : détection des coins d'une image en trois nœuds.

**Body Pose Tracking** : estimation du squelette humain en temps réel avec MediaPipe. Trois nœuds, zéro configuration.

**YOLO Object Detection** : chargement d'une image, détection multi-classe avec YOLOv11, superposition des boîtes englobantes, comptage des objets par catégorie.

**SORT Multi-Object Tracking** : YOLO + SORT sur le flux webcam. Chaque objet reçoit un identifiant persistant tracé par filtrage de Kalman.

**DeepSORT Multi-Object Tracking** : variante avec réidentification visuelle par embeddings CNN. Les identifiants restent stables même après occultation partielle.

**Stone Wall Segmenter** : pipeline complet de segmentation par Watershed sur un mur de pierres. Seuillage Otsu inversé → ouverture morphologique → fermeture → transform distance → marqueurs → filtrage des fragments → Watershed → analyse des régions. Chaque pierre est segmentée, mesurée, dénombrée.

**Billes — Segmentation Watershed** : même logique appliquée à des billes rondes. Flou gaussien pour lisser les reflets, Otsu, opérations morphologiques, peaks de la carte de distance, Watershed. Le nœud *Sci Marker Analysis* affiche l'identifiant et le centroïde de chaque bille. Le pipeline est directement reproductible en lab.

**Interactive Magic Painter** : le Hand Tracker extrait le landmark du bout de l'index ; un nœud Draw Point dessine ce point sur une couche d'overlay accumulée frame par frame. Vous dessinez à la main dans les airs.

**Ghost Motion Trail** : la soustraction de fond MOG2 génère un masque de mouvement que l'on mélange avec l'image originale à faible opacité, produisant une traîne des objets en mouvement.

**Feature Matching (ORB)** : deux images alimentent deux détecteurs ORB. Un nœud *Feature Matcher* (Brute-Force) trouve les correspondances entre keypoints et les visualise.

**Warp Affine : Animated Transform** : un nœud Python calcule une matrice affine animée (rotation + zoom oscillant), le nœud Warp Affine l'applique, un nœud Compose affiche l'original et le résultat côte à côte. Montre comment injecter de la logique temporelle via le nœud Python.

**Python : Image Stats** : exemple minimaliste. Un seul nœud Python inverse l'image (`255 - a`) et calcule la luminosité moyenne (`np.mean(a)`).

**Sprint Race Tracker** : une vidéo de sprint, YOLO, filtre de label (*person* uniquement), SORT, visualisation des trajectoires. Un nœud Python accumule les IDs uniques — comptage cumulatif de coureurs en temps réel.

**EVM Pulse Detector (Wu et al. 2012)** : une vidéo de visage passe dans le nœud EVM Color (alpha 200, bande 0.83–1.0 Hz). Le signal Cr extrait du visage s'affiche en temps réel dans le Sci Plotter : les oscillations correspondent aux battements cardiaques. Paramètres conformes au papier original.

---

## Ce qu'il reste à intégrer

Plusieurs axes sont en cours. Côté sources : lecture de flux RTSP et entrées de profondeur (capteurs RGB-D). Côté vision : nœuds d'**homographie**, de **stéréo-vision** et de **calibration de caméra**. Côté deep learning : intégration d'**ONNX Runtime** pour charger n'importe quel modèle `.onnx` sans dépendance supplémentaire. Et un système d'**export de graphe vers script Python** pour transformer un prototype visuel en code prêt à intégrer dans un pipeline de production.

---

## Et après ?

VisionNodes Studio est conçu pour être étendu. Un fichier Python, un décorateur `@vision_node`, et votre nœud apparaît dans le catalogue au prochain démarrage — rien à compiler, aucune API propriétaire à apprendre.

Ce n'est pas une idée neuve : Blender fait ça pour la 3D depuis des années, TouchDesigner pour la vidéo interactive. VisionNodes Studio applique la même logique au traitement d'image scientifique, avec un catalogue orienté recherche plutôt qu'art génératif.

Si vous travaillez sur la microscopie cellulaire et avez besoin d'un nœud de déconvolution, ou que vous faites de la mécanique des fluides et voulez visualiser des champs de vitesse en temps réel — écrivez votre nœud, dropez-le dans `plugins/`, partagez-le. OpenCV a 25 ans. Les algorithmes sont là depuis longtemps. Ce qui prenait du temps, c'était de recâbler la même plomberie à chaque nouvelle question.

---

*VisionNodes Studio est développé au sein du laboratoire APEX, UniLaSalle. Le code source est disponible sur GitHub.*
