#import "@preview/bookly:4.0.0": *

// --- Helpers locaux ---
#let subtitle(t) = block(above: 0.2em, below: 1.2em, sticky: true)[#text(style: "italic", fill: rgb("#64748b"))[#t]]

#let figtodo(id, desc) = block(above: 2em, below: 2em, width: 100%)[
  #block(width: 100%, inset: (x: 16pt, y: 14pt), radius: 6pt,
    fill: rgb("#fdf3f5"), stroke: 1pt + rgb("#d0a0aa"))[
    #grid(columns: (1fr, auto), column-gutter: 14pt, align: horizon,
      align(left)[
        #text(size: 0.78em, weight: "bold", fill: rgb("#c1002a"), font: "Roboto")[▪ IMAGE]
        #v(0.4em)
        #text(size: 0.9em, fill: rgb("#334155"), font: "Roboto")[#raw(id)]
      ],
      box(width: 42pt, height: 34pt, radius: 3pt, fill: rgb("#fff0f2"), stroke: 1pt + rgb("#c1002a"), clip: true)[
        #align(center)[
          #v(5pt)
          #circle(radius: 4pt, fill: rgb("#c1002a").lighten(35%), stroke: none)
          #v(2pt)
          #polygon(fill: rgb("#c1002a").lighten(55%), stroke: none,
            (0pt, 9pt), (13pt, 0pt), (26pt, 9pt))
          #v(2pt)
        ]
      ]
    )
  ]
]

#let figfull(path) = block(above: 1em, below: 1.4em, width: 100%)[#image(path, width: 100%)]
#let figcap(path, cap) = block(above: 1em, below: 1.4em, width: 100%)[#text(weight: "bold", size: 0.95em, fill: rgb("#7a1330"))[#cap]#v(0.35em)#image(path, width: 100%)]
#let canvas(body) = tip-box(title: "Dans VNStudio")[
  #show heading: it => block(above: 0.5em, below: 0em)[
    #text(font: "Roboto", weight: "regular", size: 0.95em)[#it.body]
  ]
  #set heading(numbering: none)
  #body
]


#chapter(title: [Descripteurs locaux], toc: false)[

#block(above: 0pt, below: 2em, width: 100%)[#image("/illustrations/chap17.jpeg", width: 100%)]

#pagebreak()
#block(above: 0em, below: 1em)[
  #grid(columns: (auto, 1fr), column-gutter: 0.6em, align: horizon,
    box(width: 3pt, height: 1.2em, fill: rgb("#c1002a"), radius: 1.5pt),
    text(weight: "bold", font: "Roboto", fill: rgb("#1e293b"))[Table des matières])
]
#suboutline(target: heading.where(outlined: true, level: 2))
#pagebreak()

#subtitle[Reconnaître un même point du monde sous un autre éclairage, une autre échelle ou un autre angle : le descripteur local jette le variable pour ne garder que le stable.]

Deux photographies d'une même façade, prises de deux endroits, à deux heures. Un même angle de fenêtre y figure deux fois — mais pas avec les mêmes pixels : l'échelle a changé, l'appareil a tourné, le soleil a baissé. Reconnaître que ces deux taches de pixels désignent le même point du monde est le problème central de la mise en correspondance, et il est à la racine du panorama, de la reconstruction 3D, du SLAM et du suivi. Ce chapitre construit la chaîne complète qui le résout : *détecter* des points stables, les *décrire* par un vecteur, *apparier* ces vecteurs entre deux images, puis *filtrer* les erreurs par un modèle géométrique robuste.

Le fil de ce chapitre tient en une phrase : *un descripteur local est l'invariance qu'on s'autorise*. Il jette délibérément ce qui change d'une vue à l'autre — la position, la taille, l'orientation, le gain de lumière — pour ne retenir que ce qui identifie le point. Sa qualité ne se mesure pas à ce qu'il enregistre, mais à ce qu'il sait ignorer sans perdre le pouvoir de distinguer.

Ce chapitre relie et concrétise des outils vus séparément. La détection s'appuie sur les coins de Harris et Shi-Tomasi (§6.5–6.6) et sur la différence de gaussiennes (§5.3). L'appariement se mesure avec les distances du chapitre 3 — euclidienne pour les descripteurs réels, Hamming pour les binaires. Le filtrage final renvoie à RANSAC (§16.5) et à l'homographie (§8.4). Et le fil rejoint celui du chapitre 1 : décrire une forme, ou décrire un point-clé, c'est dans les deux cas décider de ce qui compte.

=== Un peu de vocabulaire avant de commencer

- *Point clé (keypoint)* : Un pixel remarquable de l'image (souvent un coin ou un centre de motif) identifiable de manière stable malgré les changements de pose.
- *Descripteur* : Un vecteur (liste de nombres) résumant l'apparence visuelle du voisinage d'un point clé de façon robuste aux rotations et changements de lumière.
- *Appariement (matching)* : La mise en correspondance des points clés de deux images en trouvant les paires de descripteurs les plus similaires.

---

// ============================================================

== Le problème de l'appariement : pourquoi les pixels bruts ne suffisent pas

#subtitle[Reconnaître une structure sans se laisser abuser par sa couleur exacte]

#figfull("/figures/fig_ch17_01_ssd_vs_descripteur.svg")

=== L'intention
On veut mettre en correspondance des points homologues entre deux vues d'une même scène. Pour chaque point d'une image, on cherche son jumeau dans l'autre, malgré les changements de cadrage, de zoom et d'éclairage.

=== La forme recherchée
Le descripteur doit être insensible aux transformations physiques de l'image.

#info-box(title: "Image mentale : reconnaître un visage, pas mémoriser des pixels.")[
Vous reconnaissez un ami dans la rue sans avoir mémorisé la valeur de chaque pixel de son visage sous l'éclairage d'un jour précis. Ce que vous gardez, c'est ce qui ne change pas : les proportions, l'écart des yeux, la forme du nez — pas la teinte exacte de la peau à midi ou à l'ombre. Un bon descripteur fait le même tri. Il enregistre la structure stable du voisinage d'un point et jette ce que la lumière, la distance et l'angle font varier. C'est ce tri, et non une mémoire photographique, qui permet de retrouver le même point d'une vue à l'autre.
]

On cherche donc à extraire autour de chaque point un vecteur `f(p)` tel que la distance entre les vecteurs de deux points homologues soit minimale.

#info-box(title: "La formule")[
```
match(p) = argmin_q  d( f(p), g(q) )
```
]

Le candidat naïf prend pour descripteur le patch de pixels lui-même et pour distance la somme des carrés des écarts (SSD) :

#info-box(title: "La formule")[
```
SSD(P, Pt) = Σ_i (P_i − Pt_i)²
```
]

Ce choix naïf échoue car il ne possède aucune invariance. Les invariances doivent être construites :
- Translation : acquise en extrayant le descripteur autour de points-clés d'intérêt, et non sur une grille fixe.
- Échelle : résolue par l'échelle caractéristique (§17.2).
- Rotation : résolue par l'orientation dominante (§17.4) ou les tests orientés (§17.5).
- Éclairage : résolue par le passage au gradient et la normalisation (§17.3). ∎

=== Ce qu'elle mesure, et son angle mort
Le descripteur mesure la ressemblance locale. L'angle mort de cette invariance est qu'en jetant de l'information pour devenir insensible aux transformations, on perd en distinctivité. Un descripteur invariant en rotation ne distingue plus un motif de sa version tournée, ce qui peut créer des faux positifs. Les descripteurs classiques ne gèrent pas non plus les forts changements de point de vue perspectifs ou les déformations non rigides.

#question-box(title: "Exemple")[
Soit un patch `P` de valeur moyenne 100 et sa copie `Pt` éclaircie par un gain de 1.3 puis assombrie par un offset de −10 (`Pt = 1.3·P − 10`). L'écart moyen par pixel est de `0.3·100 − 10 = 20`. Le SSD pixel à pixel vaut `20² = 400` par pixel, soit des dizaines de milliers sur un patch 16×16, alors que c'est le même point. Le gradient, lui, élimine l'offset (`∇(I − 10) = ∇I`) et le gain est réduit à un facteur d'échelle que la normalisation efface.
]

#info-box(title: "Subtilité d'implémentation")[
Centrer et réduire les intensités d'un patch corrige le gain et l'offset, mais pas la rotation ni l'échelle. L'invariance géométrique se gagne par la construction du descripteur, pas par un post-traitement des pixels.
]

#canvas[
==== Ce que vous verriez
Sur une image et sa copie transformée (tournée de 30°, zoomée de 20%, éclaircie) :
- Comparer les patchs bruts par SSD donne des appariements incohérents reliant des zones sans rapport.
- Comparer les descripteurs ORB retrouve les vrais homologues, reliant proprement les mêmes angles de fenêtre.

==== Observation 17.A — Pixels bruts contre descripteurs : qui survit ?
- *Pipeline :*
  ```
  Image File ──> Rotate (30°) ──> Resize (x1.2) ──> Brightness/Contrast (+40) \[Vue B\]
  Image File ─┬─> ORB Detector ─┐
  Vue B  ───────┴─> ORB Detector ─┴─> Python Node (appariement + ratio) ──> Display ──> Display
  ```
- *Missions :*
+ Lancez l'appariement ORB. Constatez les lignes d'appariement parallèles reliant les points homologues.
+ Dans le _Python Node_, remplacez ORB par un SSD sur des patchs 16×16 bruts. Observez l'incohérence des lignes.
+ Augmentez l'angle de rotation (10°, 30°, 60°, 90°). Notez à quel angle ORB commence à perdre l'appariement.

---
]

// ============================================================

== Échelle caractéristique : à quel point zoomer ?

#subtitle[Le bon recul de lecture, qui s'ajuste à la taille de la structure]

#figfull("/figures/fig_ch17_02_echelle_caracteristique.svg")

=== L'intention
Pour comparer des points-clés d'images zoomées différemment, on doit extraire le descripteur sur un voisinage proportionnel à la taille de la structure dans l'image. Il faut trouver automatiquement cette taille pour chaque point.

=== La forme recherchée
On cherche la taille en analysant l'image à plusieurs résolutions (espace d'échelle) à l'aide d'une sonde qui résonne avec la structure.

#info-box(title: "Image mentale : le bon recul pour lire un mot.")[
Un mot imprimé a une distance de lecture naturelle. Le nez collé à la page, vous ne voyez que le grain du papier ; à dix mètres, le mot a disparu ; entre les deux, il existe un recul où il se lit le mieux. L'espace d'échelle cherche exactement ce recul pour chaque structure de l'image. Le `σ` caractéristique d'un point-clé, c'est la distance de lecture de la tache à laquelle il appartient — la taille à laquelle cette tache « ressort » le plus du fond. Extraire le descripteur à cette taille-là, et non à une taille fixe, est ce qui le rend insensible au zoom.
]

Le détecteur se comporte comme un diapason qui résonne au maximum lorsque son échelle `σ` coïncide avec l'échelle physique de la structure.

La réponse du Laplacien de Gaussienne (LoG) normalisé en échelle est :

#info-box(title: "La formule")[
```
réponse(x,y,σ) = σ² · ∇²[G_σ * I](x,y)
```
]

La différence de gaussiennes (DoG) l'approxime rapidement par :

#info-box(title: "La formule")[
```
DoG(x,y,σ) = (G_{kσ} − G_σ) * I  ≈  (k−1)σ² · ∇²G_σ * I
```
]

Multiplier par `σ²` compense la baisse d'amplitude naturelle de `∇²G_σ` à grand `σ` et crée un vrai maximum stable au pic de résonance. ∎

=== Ce qu'elle mesure, et son angle mort
Elle mesure la position et l'échelle caractéristique `σ₀` d'une structure isotrope (un blob). Son angle mort principal est les contours rectilignes : la courbure transverse crée une réponse forte le long des arêtes. SIFT résout cela en rejetant les points où le rapport des valeurs propres de la matrice hessienne du DoG dépasse un seuil (typiquement 10), excluant ainsi les contours comme le faisait le critère de Harris (§6.5).

#question-box(title: "Exemple")[
Pour un blob gaussien d'écart-type `s = 6` pixels, balayer `σ` de 2 à 12 montre que la réponse normalisée du LoG atteint son maximum exact à `σ = 6,00`. Le descripteur extrait à cette taille sera identique, que l'image soit zoomée ou non.
]

#info-box(title: "Réglage et sensibilité")[
Le nombre d'octaves et d'échelles par octave détermine la précision de la localisation de l'échelle. Un échantillonnage trop lâche fait passer le maximum entre deux échelles, dégradant l'invariance.
]

#canvas[
==== Ce que vous verriez
Sur une image avec points SIFT affichés sous forme de cercles de rayon proportionnel à `σ` :
- Les petits détails ont de petits cercles, les grandes structures de grands cercles.
- En zoomant l'image de x2, les mêmes cercles apparaissent deux fois plus grands, montrant que l'échelle s'adapte au zoom.

==== Observation 17.B — Le cercle qui suit le zoom
- *Pipeline :*
  ```
  Image File ─┬──> ORB Detector ──> Display ──> Display (Vue A)
                └──> Resize (x2) ──> ORB Detector ──> Display ──> Display (Vue B)
  ```
  _(Comparez les deux vues via le nœud Split Half)._
- *Missions :*
+ Repérez trois points-clés sur des structures de tailles différentes. Vérifiez que le rayon est proportionnel à la structure.
+ Vérifiez que sur la vue B (agrandie), le cercle d'un point homologue est deux fois plus grand.
+ Comprenez pourquoi un détecteur sans espace d'échelle (Harris nu) échoue à apparier ces deux images.

---
]

// ============================================================

== HOG : la rose des vents des orientations

#subtitle[Un plan de bordures résumé par des roses des orientations]

#figfull("/figures/fig_ch17_03_hog_glyphes.svg")

=== L'intention
On souhaite décrire la forme locale pour reconnaître des objets à la pose fixe (comme des piétons ou des composants sur un tapis roulant) de manière robuste à la lumière.

=== La forme recherchée
On découpe la zone en petites cellules et on comptabilise les directions des gradients dans chaque cellule. ∎

#info-box(title: "Image mentale : la rose des vents des bords.")[
Chaque cellule HOG est une petite rose des vents : au lieu d'indiquer d'où vient le vent, elle indique dans quelles directions pointent les bords du voisinage, et avec quelle force. Une zone rayée verticalement donne une rose qui pointe fort vers l'horizontale (les bords sont verticaux, leurs gradients horizontaux) ; une zone lisse donne une rose plate, sans direction dominante. Décrire une image par HOG, c'est la couvrir d'un quadrillage de ces petites roses. Tourner l'image fait tourner toutes les roses d'un bloc — ce qui explique d'un coup pourquoi HOG ne résiste pas à la rotation.
]

#info-box(title: "La formule")[
```
Pour chaque pixel : magnitude ‖∇I‖ , orientation θ = arctan2(Iᵧ, Iₓ) mod 180°
Cellule : histogramme à 9 bins de 20°, vote pondéré par ‖∇I‖
Bloc : regroupement de cellules voisines et normalisation L2
```
]

=== Ce qu'elle mesure, et son angle mort
HOG mesure la distribution locale des orientations de contours. Son angle mort majeur est qu'il n'est *pas invariant en rotation* : tourner l'image décale circulairement les bins des histogrammes. C'est un choix assumé pour la détection à pose connue.

#question-box(title: "Exemple")[
Dans une cellule 8×8 traversée par un dégradé à 45° où en chaque pixel `Iₓ = 10, Iᵧ = 10` : la magnitude vaut `‖∇I‖ = 14,14` et l'angle `θ = 45°`. Les 36 pixels intérieurs accumulent un vote total de `36 × 14,14 = 509,1` qui tombe entièrement dans le bin `[40°, 60°)`.
]

#info-box(title: "Différence d'implémentation")[
Pour éviter les effets de seuil (aliasing), les vrais algorithmes répartissent chaque vote entre les bins adjacents par interpolation trilinéaire. Les gradients non signés (0–180°) sont souvent préférés aux signés (0–360°) pour ignorer le sens du contraste.
]

#canvas[
==== Ce que vous verriez
En visualisant les glyphes HOG (étoiles d'orientations) sur un piéton :
- Modifier la luminosité ou le contraste ne change pas les glyphes (grâce au gradient et à la normalisation de bloc).
- Tourner la silhouette de 20° fait tourner toutes les étoiles, modifiant le vecteur final.

==== 📷 Observation 17.C — HOG : sensible à la rotation, insensible à la lumière
- *Pipeline :*
  ```
  Image File ─┬─> Brightness/Contrast ──> Python Node (HOG, visualize) ──> Display
                └─> Rotate ──────────────> Python Node (HOG, visualize) ──> Display
  ```
  _(Comparez via Grid Compare)._
- *Missions :*
+ Variez la luminosité et le contraste. Constatez la stabilité des glyphes HOG.
+ Faites tourner l'image de 0° à 45°. Relevez à quel angle le descripteur devient méconnaissable.
+ Déterminez si HOG est adapté pour trier des pièces jetées en vrac à angles quelconques.

---
]

// ============================================================

== SIFT : le descripteur de référence

#subtitle[Orienter la carte locale pour la lire toujours dans le même sens]

#figfull("/figures/fig_ch17_04_sift_orientation.svg")

=== L'intention
On souhaite combiner les invariances d'échelle, de rotation et d'éclairage pour obtenir le descripteur le plus robuste et universel possible pour apparier des scènes complexes.

=== La forme recherchée
Pour annuler la rotation, on mesure toutes les orientations par rapport à la direction dominante du point-clé.

#info-box(title: "Image mentale : orienter la carte avant de la lire.")[
Avant de lire une carte en marchant, on la tourne pour que le « haut » corresponde à la direction où l'on va. La carte n'a pas changé, mais on la lit toujours dans le même repère, quel que soit le cap. SIFT fait cela pour chaque point-clé : il détecte d'abord l'orientation dominante du voisinage, puis tourne mentalement le patch pour décrire tous ses gradients dans ce repère. Deux vues du même point, prises avec l'appareil incliné différemment, produisent alors le même descripteur — parce que chacune a été « remise droite » avant d'être lue.
]

#info-box(title: "La formule")[
```
1. orientation dominante : angle du pic principal de l'histogramme 36 bins des gradients
2. descripteur : grille 4×4 de sous-régions, avec histogramme 8 bins de gradients relatifs
   Vecteur final = 4 × 4 × 8 = 128 composantes
3. normalisation : L2, puis seuillage (clip) à 0,2, puis re-normalisation L2
```
]

Le seuillage à 0,2 élimine l'influence excessive des variations d'éclairage non linéaires (comme les saturations). ∎

=== Ce qu'elle mesure, et son angle mort
Il mesure la structure fine des gradients dans le repère propre du point. Son angle mort est qu'il suppose une déformation purement plane et isotrope (similitude). Il tolère mal les grands angles de perspective (cisaillement) et se fait piéger par les motifs répétés (carrelages, fenêtres).

#question-box(title: "Exemple")[
Si un point-clé a une orientation dominante de 40° et qu'un gradient y est mesuré à 85° dans l'image, il est consigné à `85° − 40° = 45°` dans le descripteur. Si l'image tourne de 30°, l'orientation dominante passe à 70° et le gradient à 115°. La valeur consignée reste `115° − 70° = 45°`.
]

#info-box(title: "Différence d'implémentation")[
RootSIFT est une variante améliorant la robustesse : on normalise le vecteur en L1, on prend la racine carrée des composantes, puis on normalise en L2, convertissant la distance euclidienne en distance de Hellinger.
]

#canvas[
==== Ce que vous verriez
Sur deux vues d'une même affiche, l'une tournée de 45° :
- Les flèches d'orientation dessinées sur les points SIFT tournent de 45° avec la scène.
- Les lignes d'appariement restent majoritairement droites et correctes.

==== Observation 17.D — Les flèches qui tournent
- *Pipeline :*
  ```
  Image File (vue droite)  ──> ORB Detector ─┐
  Image File (vue inclinée) ──> ORB Detector ─┴─> Python Node (match + ratio) ──> Display ──> Display
  ```
- *Missions :*
+ Observez les flèches d'orientation pour un même détail physique. Vérifiez que l'écart angulaire correspond à la rotation.
+ Comptez le nombre d'appariements valides à 0°, 45° et 90°. La baisse est-elle abrupte ou progressive ?
+ Comparez avec HOG sous les mêmes rotations.

---
]

// ============================================================

== ORB et BRIEF : la rapidité binaire

#subtitle[La comparaison d'intensités, codée en bits]

=== L'intention
En temps réel ou sur processeur embarqué sans GPU, le calcul des distances de SIFT est trop lourd. On veut un descripteur très rapide à générer et à comparer.

=== La forme recherchée
On remplace les gradients réels par de simples tests binaires comparant des paires de pixels.

On définit à l'avance `n` paires de coordonnées `(a_i, b_i)` dans le patch standardisé. La distance de Hamming compte les différences de bits par un simple `XOR` machine. Pour résister à la rotation, ORB utilise le centroïde d'intensité du patch pour estimer l'orientation et faire tourner la grille de test avant la comparaison.

#info-box(title: "La formule")[
```
bit_i = 1 si I(a_i) < I(b_i) , sinon 0          (n = 256 bits, soit 32 octets)
distance Hamming = popcount( d1 XOR d2 )
```
]

L'angle d'orientation dominante est estimé par les moments d'ordre 1 (§2) : ∎

#info-box(title: "La formule")[
```
θ = arctan2(m01, m10)
```
]

=== Ce qu'elle mesure, et son angle mort
Il mesure un motif de comparaison relative de clarté. Son angle mort est sa sensibilité aux déformations sévères (zoom important, distorsions) et sa distinctivité plus faible que celle de SIFT, ce qui génère plus de faux appariements.

#question-box(title: "Exemple")[
Soient deux descripteurs 8 bits :
```
d1  = 1 0 1 1 0 0 1 0
d2  = 1 1 1 0 0 0 1 1
XOR = 0 1 0 1 0 0 0 1  ⟹  distance de Hamming = 3 (bits à 1)
```
]

#info-box(title: "Différence d'implémentation")[
L'utilisation de la distance de Hamming (`cv2.NORM_HAMMING`) est nécessaire pour comparer ces descripteurs : sans elle, les bits seraient traités comme des réels par défaut, faussant entièrement la mesure.
]

#canvas[
==== Ce que vous verriez
- ORB s'exécute de façon fluide en temps réel (30 fps) sur flux vidéo.
- Pour des transformations modérées, ORB et SIFT donnent des résultats similaires, mais sous déformation ou flou important, SIFT préserve plus de lignes correctes.

==== Observation 17.E — Mesurer le compromis ORB/SIFT
- *Pipeline :*
  ```
  Paire d'images ─┬─> ORB Detector ──> Python Node (match + chrono) ─┐
                  └─> ORB Detector ─> Python Node (match + chrono) ─┴─> Display ──> Grid Compare
  ```
- *Missions :*
+ Relevez le temps d'exécution et le nombre d'appariements pour ORB et SIFT.
+ Introduisez un flou ou dégradez la perspective via Warp Perspective. Lequel des deux conserve le plus de correspondances ?
+ Évaluez si le gain de vitesse d'ORB est indispensable pour un flux live à 30 fps sur votre machine.

---
]

// ============================================================

== Le ratio test de Lowe : rejeter l'ambiguïté

#subtitle[Exiger un coup de cœur, éliminer le doute]

=== L'intention
Les points-clés situés sur des zones répétitives ou du bruit génèrent de faux appariements à faible distance. On veut les rejeter sans utiliser de seuil de distance absolu, qui varie d'une image à l'autre.

=== La forme recherchée
On exige que le candidat trouvé soit nettement meilleur que le deuxième meilleur candidat de toute l'image.

#info-box(title: "Image mentale : la séance d'identification.")[
Un témoin passe devant une rangée de suspects. S'il en désigne un avec beaucoup plus d'assurance que tous les autres, son identification vaut quelque chose. S'il hésite entre deux personnes presque autant l'une que l'autre, son témoignage ne vaut rien — non parce qu'il a tort, mais parce qu'il n'est pas distinctif. Le ratio test applique cette règle à chaque point : il ne demande pas « ce candidat est-il proche ? » mais « est-il nettement plus proche que le suivant ? ». Un point qui a un quasi-jumeau ailleurs dans l'image est écarté, même si son meilleur candidat semble bon.
]

#info-box(title: "La formule")[
```
d1 / d2 < τ        (Lowe : τ ≈ 0,8)
```
]

où `d₁` est la distance au plus proche voisin dans l'espace des descripteurs, et `d₂` la distance au deuxième plus proche. ∎

=== Ce qu'elle fait, et son angle mort
Elle élimine les appariements ambigus. Son angle mort est les structures répétitives légitimes (carrelages, fenêtres de gratte-ciel) : elle rejette les correspondances réelles car elles se ressemblent toutes, affamant le pipeline.

#question-box(title: "Exemple")[
Sur deux points comparés :
- Point distinctif : `d₁ = 0,32, d₂ = 0,51`. Ratio = `0,32 / 0,51 = 0,63 < 0,8` ──> *Accepté*.
- Motif répété : `d₁ = 0,45, d₂ = 0,49`. Ratio = `0,45 / 0,49 = 0,92 ≥ 0,8` ──> *Rejeté*.
Le second est rejeté bien que sa distance `d₁` soit faible, car il y a ambiguïté.
]

#info-box(title: "Subtilité d'implémentation")[
L'algorithme requiert de chercher les 2 plus proches voisins (`knnMatch` avec `k=2`) et non un seul. Pour les descripteurs binaires, l'indexation doit être réglée en LSH.
]

#info-box(title: "Paramètres opérationnels (VNStudio / Python)")[
Dans les nœuds d'extraction et d'appariement de descripteurs (ou via les classes OpenCV comme `cv2.SIFT_create` et `cv2.BFMatcher` en Python), les réglages suivants contrôlent la précision de la mise en correspondance :

- *Nombre de caractéristiques maximum (`nfeatures`)* :
- Dans VNStudio, ce paramètre correspond au champ *Max Features* ; en Python (OpenCV), il se nomme `nfeatures` lors de l'appel à `cv2.SIFT_create` ou `cv2.ORB_create`.
- Définit le nombre maximal de points clés à conserver par image (ex. : `1000` ou `2000`). Les points détectés sont triés par ordre de contraste (les plus stables d'abord). Augmenter cette valeur permet d'apparier des scènes très texturées ou peu contrastées, mais ralentit le calcul de recherche des correspondances.
- *Seuil du ratio test de Lowe (`ratio`)* :
- Dans VNStudio, ce paramètre correspond au curseur *Lowe Ratio* ; en Python, c'est le seuil appliqué manuellement sur la division des distances après un `BFMatcher.knnMatch(k=2)`.
- Ce paramètre (généralement réglé entre `0.7` et `0.8`) est le filtre d'ambiguïté principal. Pour chaque point clé, on cherche le premier et le second plus proche voisin dans l'autre image. Si la distance du premier voisin divisée par la distance du second est inférieure au ratio, l'appariement est validé. Si le ratio est proche de `1.0` (ex: 0.95), on accepte des correspondances même si le point ressemble presque autant à un autre endroit (ce qui arrive sur des textures répétitives comme des briques). Un ratio de `0.7` garantit des appariements uniques et élimine les fausses correspondances.
- *Nombre d'octaves (`nOctaveLayers`)* :
- Dans VNStudio, ce paramètre correspond au champ *Octave Layers* ; en Python (OpenCV), il se nomme `nOctaveLayers` dans la fonction `cv2.SIFT_create`.
- Spécifie le nombre d'échelles analysées par octave de taille d'image. Une valeur de `3` (la valeur par défaut) offre un bon compromis entre robustesse aux zooms importants et rapidité de détection.
]

#canvas[
==== Ce que vous verriez
- À `τ = 0,95`, les appariements forment un nuage de lignes croisées désordonnées.
- À `τ = 0,8`, la quasi-totalité des lignes croisées disparaît, ne laissant que les appariements cohérents.
- Sur un motif de grille, presque aucun point ne survit.

==== Observation 17.F — Le curseur du ratio test
- *Pipeline :*
  ```
  Paire d'images (facile vs répétitive) ──> ORB Detector ──> Python Node (ratio τ réglable) ──> Display ──> Display
  ```
- *Missions :*
+ Sur l'image facile, faites varier `τ` de 0,95 à 0,6. Notez à quelle valeur le bruit visuel s'éteint.
+ Sur la scène répétitive, observez la disparition de presque tous les points.
+ Retenez que devant un désordre de lignes, le premier réflexe est de *serrer le ratio test*.

*Exercice de dépannage :* L'exercice consiste à apparier deux images présentant un motif répétitif (ex. un carrelage ou une grille). Dans le nœud *BFMatcher*, désactiver le ratio test de Lowe en réglant *Lowe Ratio* sur `1.0`. Le lecteur observe à l'écran un réseau chaotique et inexploitable de lignes croisées reliant des points n'ayant aucun rapport géométrique. Activer ensuite le ratio test de Lowe avec un seuil de `0.7`. Le lecteur constate que la quasi-totalité des fausses correspondances s'efface instantanément, démontrant l'efficacité de cette méthode pour éliminer les ambiguïtés structurelles inhérentes aux décors répétitifs.

---
]

// ============================================================

== RANSAC et homographie : imposer la cohérence géométrique

#subtitle[Trouver l'accord général dans un nuage de suspects]

=== L'intention
Malgré le ratio test, des appariements erronés subsistent (outliers). On veut estimer la transformation globale entre les deux images et rejeter les correspondances qui ne la respectent pas.

=== La forme recherchée
On cherche un modèle de transformation géométrique par consensus aléatoire.

#info-box(title: "Image mentale : tracer la droite à travers une foule de farceurs.")[
On vous demande de tracer la droite que « suit » un groupe de personnes, mais la moitié d'entre elles se sont placées au hasard pour vous tromper. Faire la moyenne de tout le monde donne une droite absurde, tirée vers les farceurs. La bonne stratégie : tirer deux personnes au hasard, tracer la droite qui les joint, compter combien d'autres tombent dessus, et recommencer. La droite qui rassemble le plus grand groupe d'accord est la vraie. RANSAC procède ainsi sur les correspondances : il ne moyenne pas les appariements, il cherche le plus grand sous-ensemble qui s'accorde sur une même transformation, et déclare le reste aberrant.
]

Le nombre d'itérations nécessaires pour garantir la réussite avec une confiance `p` est :

#info-box(title: "La formule")[
```
N = log(1 − p) / log(1 − wⁿ)
```
]

où `w` est la proportion de vrais appariements (inliers) et `n` le nombre de points requis pour le modèle (`n = 4` pour une homographie plane, §8.4). ∎

=== Ce qu'elle fait, et son angle mort
Elle estime le modèle géométrique dominant (homographie, matrice fondamentale) et filtre les correspondances aberrantes. Son angle mort est les configurations dégénérées (4 points alignés) et les scènes multi-plans : RANSAC ne capture que le plan dominant et rejette le reste comme du bruit ; il faut alors l'appliquer en séquence.

#question-box(title: "Exemple")[
Avec `w = 0,5` (50% de vrais appariements) et `p = 0,99`, RANSAC demande `N = 72` tirages. Si `w = 0,3` (sans ratio test préalable), il faut `N = 567` tirages. Préfiltrer les appariements par le ratio test de Lowe divise le coût calculatoire de RANSAC par huit.
]

#info-box(title: "Limite d'implémentation")[
Le seuil de tolérance (distance de reprojection) est exprimé en pixels et doit être ajusté selon la résolution. OpenCV renvoie un masque d'inliers utile pour filtrer et afficher les correspondances.
]

#canvas[
==== Ce que vous verriez
- Les appariements inliers s'affichent en *vert* (parallèles et propres), les outliers rejetés en *rouge* (directions aberrantes).
- Appliquer l'homographie estimée aligne parfaitement les deux images dans un panorama. Sans RANSAC, l'image déformée part en vrille.

==== Observation 17.G — Voir le panorama se former
- *Pipeline :*
  ```
  Image A ─┬─> ORB Detector ─┐
  Image B ─┼─> ORB Detector ─┴─> Python Node (match + RANSAC homographie) ─┬─> \[inliers/outliers\] ──> Display ──> Display
           └──────────────────────────────────────────────────────────────────┴─> \[H\] ──> Warp Perspective (A) ──> Display (sur B) ──> Display
  ```
- *Missions :*
+ Affichez les lignes vertes et rouges. Notez le ratio d'inliers trouvés par RANSAC.
+ Observez l'alignement des textures communes dans la superposition finale.
+ Désactivez RANSAC en augmentant le seuil de tolérance à l'infini. Constatez l'effet de cisaillement provoqué par les outliers.

---
]

// ============================================================

== L'état de l'art : la révolution de l'apprentissage profond

#subtitle[Des réseaux entraînés à détecter et à décrire]

=== L'intention
Dans les situations extrêmes de texture lisse (surfaces métalliques, murs uniformes) ou sous des angles de vue très prononcés, les descripteurs géométriques classiques SIFT/ORB échouent à trouver des points stables.

=== La forme recherchée
On entraîne des réseaux de neurones convolutionnels de bout en bout pour extraire des points-clés et leurs vecteurs (comme SuperPoint) et pour les mettre en correspondance de façon globale (comme LightGlue ou LoFTR).

=== Ce qu'elle fait, et son angle mort
Ces méthodes apprises résolvent l'appariement sur des surfaces peu texturées ou sous de fortes distorsions de perspective. Leur angle mort réside dans leur lourdeur : elles nécessitent un GPU et un modèle pré-entraîné, là où SIFT et ORB restent rapides, légers et ne requièrent aucune phase d'apprentissage.

---

// ============================================================

== Tableau récapitulatif

#table(
  columns: 6,
  table.header(
    [*Descripteur*], [*Invariances acquises*], [*Ce qu'il jette*], [*Dimension*], [*Distance*], [*Créneau*]
  ),
  [Patch brut], [aucune (ou gain/offset si normalisé)], [rien], [k² pixels], [SSD / L2], [Inutilisable hors translation pure],
  [HOG], [éclairage (offset + gain)], [rotation, échelle], [~3780], [L2], [Détection à pose connue (piétons)],
  [SIFT], [similitude + éclairage], [rotation, échelle, gain, offset], [128 (float)], [L2 / Hellinger], [Référence générale, SfM, panoramas],
  [ORB / BRIEF], [similitude (rotation par steering)], [idem SIFT, moins discriminant], [256 bits], [Hamming], [Temps réel, embarqué, SLAM léger],
  [Appris (SuperPoint, LoFTR…)], [jusqu'à la perspective, appris], [selon l'entraînement], [variable], [L2 / cosinus], [Point de vue extrême, faible texture],
)

#table(
  columns: 4,
  table.header(
    [*Filtre*], [*Rôle*], [*Paramètre clé*], [*Angle mort*]
  ),
  [Ratio test de Lowe], [Rejeter les appariements ambigus], [`τ ≈ 0,8`], [Rejette les structures répétées légitimes],
  [RANSAC + homographie], [Imposer un modèle géométrique global], [seuil de reprojection (px)], [Un seul modèle dominant ; configurations dégénérées],
)

---

// ============================================================

== l'invariance est un tri

Tout ce chapitre tient dans une décision prise quatre fois : que faut-il ignorer ? On ignore la position en n'extrayant qu'aux points-clés, l'échelle en mesurant l'échelle caractéristique, la rotation en travaillant dans un référentiel tourné, le gain et l'offset par le gradient et la normalisation. Ce que le descripteur jette n'est pas une perte : c'est ce qui changeait d'une vue à l'autre, et qui l'empêchait de reconnaître un même point.

La même logique relie les étapes. Le ratio test élève le taux d'inliers, ce qui effondre le nombre d'itérations de RANSAC : un bon tri en amont rend la robustesse en aval presque gratuite. C'est le fil conducteur de tout l'ouvrage : bien poser la représentation laisse peu de travail au reste. Le chapitre 16 a donné l'estimateur ; ce chapitre lui a fourni des correspondances assez propres pour qu'il converge.

---

// EXERCICES — CHAPITRE 17
// ============================================================

#pagebreak()
== Exercices pratiques

=== Exercice 1 · Décrire une silhouette par ses orientations

#figtodo("ex_ch17_pieton", [Photographie d'un piéton de face sur un trottoir : silhouette bien contrastée su])

*Ce que vous voyez.* Une silhouette humaine dont la « rose des vents » des contours est très caractéristique. La mission : en tirer une signature de forme stable, à la base de la détection de piétons.

*Pipeline VNStudio*
`Image File` → `Python Node` (HOG) → `Display` → `Display`

Le nœud découpe l'image en cellules et dessine dans chacune les orientations de contour dominantes.



*Questions*

+ Sur la visualisation, où les traits d'orientation sont-ils les plus marqués : sur les bords du corps, la peau, ou le fond ? Pointent-ils en travers des contours, comme attendu ?

+ Sur une cellule posée sur une épaule, quelle orientation domine ? Correspond-elle à la ligne de l'épaule que vous voyez ?

+ Faites pivoter le piéton de 10°. La signature change-t-elle beaucoup, ou tient-elle bon ? La détection survit-elle à un sujet légèrement penché ?

+ *Défi.* Comparez la signature d'un piéton et celle d'un cycliste. Sont-elles plus proches entre elles qu'entre deux piétons différents ? Si les deux se confondent, quel trait de silhouette partagent-ils, et que faudrait-il ajouter pour les distinguer ?


=== Exercice 2 · Apparier deux vues d'un livre en rejetant les erreurs

#figtodo("ex_ch17_livre_appariement", [Deux photos du même livre : de face à gauche, légèrement en angle et plus éclair])

*Ce que vous voyez.* Deux vues du même objet avec un léger changement d'angle et de lumière. Certains appariements sont justes, d'autres faux. La mission : ne garder que les bons, étape clé pour la reconnaissance d'objet et les panoramas.

*Pipeline VNStudio*
`Image File` (gauche) + `Image File` (droite) → `ORB Detector` → `Feature Matcher` → `Display`

Le détecteur trouve des points caractéristiques ; le matcher les relie et applique un test pour rejeter les appariements ambigus.



*Questions*

+ Comptez les appariements verts (gardés) et rouges (rejetés). Quelle part le test rejette-t-il ? Serrez le test : combien d'appariements restent, et paraissent-ils plus sûrs à l'œil ?

+ Comparez un coin net du livre et une zone de texture répétitive (la trame du papier). Pour lequel l'appariement est-il franc et sans hésitation ? Pourquoi une zone qui se répète crée-t-elle des appariements ambigus ?

+ Montez le nombre de points détectés. Le nombre de bons appariements grimpe-t-il autant, ou les nouveaux points sont-ils surtout du bruit ? Le rapport bons/total s'améliore-t-il ?

+ *Défi.* Éclaircissez fortement l'image de droite. Les appariements tiennent-ils malgré ce changement de lumière ? Comparez avec un descripteur SIFT _(à créer)_. Lequel résiste le mieux, et lequel choisiriez-vous pour des photos prises à des heures différentes ?


=== Exercice 3 · Imposer une cohérence géométrique pour redresser une affiche

#figtodo("ex_ch17_affiche_ransac", [Deux vues d'une affiche : de face et à 30° de côté. Avant nettoyage, quelques ap])

*Ce que vous voyez.* Des appariements bruts encore truffés d'erreurs. La mission : ne garder que ceux qui racontent tous le même mouvement, puis s'en servir pour remettre l'affiche de face.

*Pipeline VNStudio*
`Image File` (gauche) + `Image File` (droite) → `ORB Detector` → `Feature Matcher` → `RANSAC Homography` → `Display` → `Display`

RANSAC cherche la transformation que soutient le plus grand nombre d'appariements et écarte les autres comme intrus.



*Questions*

+ Notez le nombre d'appariements avant RANSAC, puis le nombre d'inliers gardés après. Quelle proportion d'intrus le test simple avait-il laissé passer ?

+ Sur l'image, les inliers gardés relient-ils des points qui se correspondent vraiment ? Les lignes sont-elles maintenant toutes cohérentes, ou en reste-t-il une de travers ?

+ Resserrez la tolérance de RANSAC, puis élargissez-la. Combien d'inliers dans chaque cas ? Décrivez le compromis : trop serré on perd de bons points, trop large on laisse entrer des intrus.

+ *Défi.* Servez-vous de la transformation trouvée pour redresser la vue oblique de l'affiche. Le résultat est-il bien rectangulaire ? Si les coins restent un peu déformés, d'où vient le défaut : objectif non corrigé, surface non plane, ou trop peu d'inliers ?



#v(2em)
#align(center)[
  #image("/QR Code.png", width: 60pt)
  #v(4pt)
  #text(size: 0.8em, style: "italic", fill: rgb("#64748b"))[Télécharger les images de référence]
]

]
