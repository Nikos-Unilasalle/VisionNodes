#import "@preview/bookly:4.0.0": *

// --- Helpers locaux ---
#let subtitle(t) = block(above: 0.2em, below: 1.2em, sticky: true)[#text(style: "italic", fill: rgb("#64748b"))[#t]]

#let figtodo(id, desc) = figure(
  block(width: 100%, inset: 14pt, radius: 6pt,
    fill: luma(246), stroke: (dash: "dashed", thickness: 0.8pt, paint: luma(170)))[
    #align(center)[#text(fill: luma(110), style: "italic", size: 0.9em)[
      Figure à créer — #raw(id)\
      #desc
    ]]
  ]
)

#let figfull(path) = block(above: 1em, below: 1.4em, width: 100%)[#image(path, width: 100%)]
#let canvas(body) = tip-box(title: "Dans VNStudio")[#body]


#chapter(title: [Où couper ? seuillage et segmentation classique], toc: false)[

#figtodo("chap12", [Illustration de couverture du chapitre 12])

#pagebreak()
#block(above: 0em, below: 1em)[
  #grid(columns: (auto, 1fr), column-gutter: 0.6em, align: horizon,
    box(width: 3pt, height: 1.2em, fill: rgb("#c1002a"), radius: 1.5pt),
    text(weight: "bold", font: "Roboto", fill: rgb("#1e293b"))[Table des matières])
]
#suboutline(target: heading.where(outlined: true, level: 2))
#pagebreak()

#subtitle[Segmenter, c'est trancher pour chaque pixel : à quelle région appartiens-tu ? L'image seule ne le dit pas. Chaque méthode ajoute une hypothèse, et place la décision là où cette hypothèse devient facile à trancher.]

Segmenter, c'est partitionner l'image : décider, pour chaque pixel, à quelle région il appartient. Avant l'apprentissage profond, les méthodes classiques couvrent tout un spectre — trancher pixel par pixel sur l'intensité (seuillage), regrouper les pixels qui se ressemblent (_clustering_, c'est-à-dire « mise en groupes »), ou faire émerger les régions d'une recherche du meilleur découpage possible (contours actifs, coupe de graphe). Le chapitre les construit dans cet ordre, et montre que la difficulté n'est jamais le calcul mais le *choix de ce qu'on suppose* d'une bonne segmentation.

L'image seule ne dit pas où couper. Le bruit la rend ambiguë, les objets se fondent dans des fonds similaires, l'éclairage crée des dégradés qui masquent les vraies frontières. Le fil du chapitre : *toute segmentation arbitre entre fidélité aux données et a priori de régularité.* La fidélité aux données, c'est suivre exactement ce que disent les pixels. La régularité, c'est l'idée qu'une vraie région est cohérente — d'un seul tenant, aux bords lisses, sans trous isolés. Chaque méthode ajoute une hypothèse de ce genre et place la décision dans l'espace où elle devient facile à trancher. La progression va du *purement local* (le seuillage, où chaque pixel décide seul, et où le bruit passe tout entier) au *globalement cohérent* (la coupe de graphe, où chaque pixel se décide en accord avec ses voisins, ce qui résiste au bruit).

La segmentation classique est un carrefour du livre. Le couple « coller aux données / rester lisse » de Horn-Schunck pour le mouvement (§9.4) reparaît ici à l'identique dans l'énergie de la coupe de graphe (§12.7). Le _clustering_ (§12.4–12.5) repose sur une distance choisie entre pixels (chapitre 3), souvent calculée en espace Lab plutôt qu'en RGB (chapitre 7) parce que Lab épouse mieux la perception. Les masques de seuillage se nettoient ensuite par morphologie (chapitre 11) ou alimentent la transformée de distance pour le watershed (§12.3), et toute segmentation s'évalue par IoU et Dice (chapitre 4).

=== Un peu de vocabulaire avant de commencer

- *Seuillage* : La séparation des pixels en deux classes (généralement objet et fond) selon que leur intensité dépasse ou non une valeur pivot appelée *seuil (T)*.
- *Composante connexe* : Un groupe de pixels de même nature en contact physique direct (qui forment d'un seul tenant un « îlot » dans l'image).
- *Image d'étiquettes (label image)* : Une image où chaque îlot d'objet reçoit un numéro entier unique pour pouvoir les distinguer et les compter individuellement.

---

// ============================================================

== Seuillage d'Otsu : couper au creux de l'histogramme

#subtitle[Un arbitre qui scinde une file en deux groupes aussi homogènes que possible]

#figfull("/figures/fig_ch12_obs1_otsu.svg")

=== L'intention
Quand une image contient un objet clair sur fond sombre, on veut trouver tout seul le niveau de gris qui sépare les deux — le *seuil* : en dessous, c'est le fond ; au-dessus, l'objet. Et on veut le trouver sans le régler à la main.

=== La forme recherchée
Commençons par l'*histogramme*, l'outil de base de ce chapitre. C'est le portrait-robot statistique de l'image : pour chaque niveau de gris possible (de 0, noir, à 255, blanc), il compte combien de pixels portent ce niveau. Un objet clair posé sur un fond sombre donne un histogramme en *double bosse* — une bosse de pixels sombres (le fond), une vallée, puis une bosse de pixels clairs (l'objet). Le bon seuil est au fond de la vallée : c'est là que se séparent les deux populations.

L'image utile est celle d'un arbitre qui coupe une file d'attente en deux groupes. Pour chaque seuil possible, il met d'un côté les pixels sombres, de l'autre les clairs, et il regarde si chaque groupe est bien « serré » autour de sa propre couleur moyenne. Le seuil idéal est celui qui rend les deux groupes le plus homogènes possible à l'intérieur, et le plus différents possible entre eux.

Pour mesurer cette homogénéité, on utilise la *variance*, qui dit à quel point des valeurs s'éloignent de leur moyenne : faible quand tout est tassé autour de la moyenne, élevée quand les valeurs sont dispersées. Otsu maximise la *variance inter-classes* — l'écart entre la moyenne du groupe sombre et celle du groupe clair, pondéré par leurs tailles :

#info-box(title: "La formule")[
```
σ²_inter(t) = ω₀(t) · ω₁(t) · [μ₀(t) − μ₁(t)]²
T* = argmax_t  σ²_inter(t)
```
]

Ici ω₀ et ω₁ sont les proportions de pixels dans chaque groupe (au seuil t), μ₀ et μ₁ leurs niveaux moyens, et `argmax_t` veut simplement dire « le t qui rend cette quantité maximale ». Pourquoi maximiser l'écart entre les deux moyennes revient-il à rendre chaque groupe homogène ? Parce que la dispersion totale de l'image est une constante, fixée une fois pour toutes, et qu'elle se partage en deux morceaux : la dispersion _entre_ les groupes et la dispersion _dans_ les groupes. Si la première augmente, la seconde diminue d'autant. Pousser les deux moyennes à s'écarter le plus possible, c'est donc, mécaniquement, rendre chaque groupe le plus serré possible. Et comme cette quantité ne demande que des moyennes, on la calcule pour les 256 seuils possibles en un seul passage sur l'histogramme.

Otsu place ainsi la décision dans l'espace de l'*histogramme* plutôt que dans l'image. C'est un résumé qui jette la position des pixels, comme les moments du chapitre 2 ne gardaient que la répartition de la masse. L'a priori est « il y a deux classes d'intensité bien séparées » ; quand cet a priori est faux — histogramme à une seule bosse, ou une classe minuscule (un petit défaut perdu sur une grande surface lisse, qui n'apparaît presque pas dans l'histogramme) — Otsu place le seuil n'importe où. ∎

#question-box(title: "Exemple chiffré")[
Histogramme jouet sur les niveaux 0 à 4, 16 pixels, effectifs `[5, 3, 0, 3, 5]` :

```
seuil t = 1  (groupe sombre = {0,1}, groupe clair = {2,3,4}) :
  ω₀ = 0.5   μ₀ = (0·5 + 1·3)/8 = 0.375
  ω₁ = 0.5   μ₁ = (3·3 + 4·5)/8 = 3.625
  σ²_inter = 0.5 · 0.5 · (0.375 − 3.625)² ≈ 2.64   ← maximum

seuil t = 0 (ou t = 3) : σ²_inter ≈ 1.82
```

Le maximum tombe dans la *vallée* de l'histogramme (le niveau 2, vide), exactement là où l'œil placerait le seuil. Otsu n'a fait que mettre en chiffres « coupe au creux ».
]

#warning-box(title: "Piège — un seul canal, et gare à l'éclairage inégal")[
Le seuil d'Otsu se calcule sur une image en *niveaux de gris* (un seul canal, donc un seul histogramme) : il faut convertir une image couleur avant. Et sur une image à éclairage inégal, un seuil unique pour toute l'image est le mauvais outil — c'est l'objet du §12.2. Un léger flou (chapitre 5) avant le calcul lisse le bruit qui creuse de fausses petites vallées dans l'histogramme.
]

#canvas[
Canvas : `Image Source` → `Grayscale` → `Otsu Threshold` → `Output Display`. Le nœud de seuillage affiche dans l'inspecteur le seuil trouvé et superpose l'histogramme avec le trait de coupe, ce qui permet de voir d'un coup d'œil si l'histogramme est vraiment bimodal.

_Domaines :_ binarisation de documents (OCR), tri de grains sur fond contrasté, masquage de cellules colorées en microscopie.

---
]

// ============================================================

== Seuillage adaptatif : suivre le fond plutôt que le trancher

#subtitle[Un niveau à bulle qui épouse la pente du terrain]

=== L'intention
Quand l'éclairage varie lentement — une page photographiée sous une lampe oblique, une plaque éclairée par le côté —, aucun seuil unique ne convient : trop bas dans l'ombre on perd l'objet, trop haut dans la lumière on prend le fond pour l'objet. On veut un seuil qui change d'un endroit à l'autre.

=== La forme recherchée
Plutôt que de chercher une seule horizontale pour tout le terrain, on prend un niveau à bulle qui épouse la pente locale. Concrètement, en chaque pixel, on estime la luminosité du fond à cet endroit — simplement la moyenne des pixels alentour — et on compare le pixel à ce fond local. L'a priori est explicite : *le fond varie doucement à l'échelle du voisinage* (le même principe que le top-hat morphologique du chapitre 11, qui estimait aussi le fond pour le soustraire). Une petite marge de sécurité évite de prendre le grain du fond pour de l'objet.

#info-box(title: "La formule")[
```
T(x, y) = moyenne_locale(x, y) − C
```
]

Le pixel est de l'objet si son niveau passe sous ce seuil local (cas d'un texte sombre sur fond clair). La constante C est la marge de sécurité. Le raisonnement : si le fond suit une nappe lentement variable et que l'objet est toujours un peu plus sombre que cette nappe, alors « pixel nettement sous la moyenne locale » désigne exactement les pixels d'objet. On gagne la robustesse à l'éclairage inégal, on perd la vision d'ensemble : un objet *plus grand que le voisinage* devient invisible, car son intérieur ressemble localement à un fond uniforme. L'angle mort est donc la taille du voisinage. ∎

#question-box(title: "Exemple chiffré")[
Une ligne de pixels, fond en dégradé `[200, 200, 100, 100]`, texte toujours 50 niveaux sous le fond local (donc 150 en zone claire, 50 en zone sombre) :

```
seuil global (Otsu ≈ 125) :
  texte clair 150 > 125 → classé FOND  (raté)
  fond sombre 100 < 125 → classé TEXTE (raté)

seuil adaptatif T = moyenne_locale − 20 :
  zone claire : T ≈ 180 → texte 150 < 180 → TEXTE ✓,  fond 200 → FOND ✓
  zone sombre : T ≈ 80  → texte 50 < 80   → TEXTE ✓,  fond 100 → FOND ✓
```

Le seuil local *suit* le fond et tranche juste partout, là où le seuil unique se trompait des deux côtés.
]

#info-box(title: "Réglage — la taille du voisinage")[
La taille du voisinage est le réglage critique. Trop petit, l'intérieur des traits épais se vide (le seuil regarde si peu de pixels qu'il confond le cœur d'un trait avec le fond) ; trop grand, on retombe sur un seuil quasi global et l'éclairage inégal ressurgit. Pondérer les voisins par une cloche gaussienne (plus de poids au centre) lisse les transitions et évite les marches visibles d'un bloc à l'autre.
]

#info-box(title: "Paramètres opérationnels (VNStudio / Python)")[
Dans le nœud `Adaptive Threshold` (ou via `cv2.adaptiveThreshold` en Python), la qualité de la binarisation locale dépend des trois paramètres suivants :

- *Taille du voisinage (`blockSize`)* :
- Dans VNStudio, ce paramètre correspond au champ *Block Size* ; en Python (OpenCV), il se nomme `blockSize` dans la fonction `cv2.adaptiveThreshold`.
- Configure la taille de la fenêtre carrée locale (ex. : 11×11, 21×21) utilisée pour calculer la moyenne ou la moyenne gaussienne du fond. Ce paramètre doit être impair. La règle d'or est de choisir un `blockSize` supérieur à la largeur maximale des traits ou des objets à segmenter (ex. : l'épaisseur d'une lettre). Si le voisinage est plus petit que la largeur du trait, le centre du trait sera confondu avec le fond et se videra, ne laissant apparaître que les contours extérieurs du texte.
- *Constante de soustraction (C)* :
- Dans VNStudio, ce paramètre correspond au curseur *Constant (C)* ; en Python (OpenCV), il se nomme `C` dans la fonction `cv2.adaptiveThreshold`.
- Un décalage numérique soustrait de la moyenne calculée (ex. : C = 5 ou 10). Elle fait office de seuil de sécurité : pour qu'un pixel soit classé comme objet, il ne doit pas seulement être plus sombre que la moyenne locale, il doit l'être d'au moins `C` niveaux. Augmenter `C` réduit le bruit dans les zones homogènes (fausses alertes), mais une valeur trop élevée peut couper les traits fins ou effacer les objets peu contrastés.
- *Méthode d'adaptation (`adaptiveMethod`)* :
- Dans VNStudio, ce paramètre correspond au menu déroulant *Adaptive Method* ; en Python (OpenCV), il correspond à l'argument `adaptiveMethod` de `cv2.adaptiveThreshold`.
- `cv2.ADAPTIVE_THRESH_MEAN_C` : Calcule une moyenne arithmétique simple de la fenêtre.
- `cv2.ADAPTIVE_THRESH_GAUSSIAN_C` : Calcule une moyenne pondérée par une cloche gaussienne, donnant plus d'importance aux pixels proches du centre. Ce choix produit des contours plus lisses et réduit les artefacts géométriques près des transitions brusques.
]

#canvas[
Dans votre canvas :
`Image Source` ──> `Grayscale` ──> `Adaptive Threshold` ──> `Output Display`.

En faisant glisser le curseur `Block Size` de manière à ce qu'il dépasse la taille des motifs d'intérêt, et en ajustant le curseur `C` pour éliminer le bruit du fond, vous obtiendrez un masque binaire parfaitement net de vos objets, quel que soit l'éclairage de la scène.

*Exercice de dépannage (échec contrôlé) :* L'exercice consiste à charger une image de texte sous un éclairage oblique très asymétrique. Tenter d'abord d'isoler les lettres avec un nœud *Threshold* en mode automatique d'Otsu. Le lecteur constate que le masque sépare simplement l'image en deux zones (ombre et lumière) sans extraire le texte. Remplacer par un nœud *Adaptive Threshold* en réglant le *Block Size* sur une valeur trop petite de 3 pixels. Le lecteur observe que le texte s'évide, ne laissant que de fins contours illisibles. Monter enfin le *Block Size* à 21 pixels (dépassant la largeur des lettres) pour voir le texte se dessiner proprement, prouvant la supériorité de l'adaptation locale et la nécessité d'un calibrage d'échelle de référence.

_Domaines :_ OCR sur pages photographiées sous éclairage oblique, lecture de plaques sous éclairage inégal, défauts sur surfaces non uniformément éclairées.

---
]

// ============================================================

== Watershed (ligne de partage des eaux) : segmenter par le relief

#subtitle[L'eau qui monte depuis les sources au fond des vallées et forme des lacs séparés par des digues]

Les méthodes vues jusqu'ici partitionnent l'image par une hypothèse sur les _valeurs_ : un seuil sépare deux modes d'intensité, K-means regroupe des couleurs proches. Le watershed change de registre. Il lit l'image comme un *relief* et laisse l'eau monter depuis des sources : chaque bassin qui se remplit devient une région, et les crêtes où deux bassins se rejoignent deviennent les frontières. Ce qui décide de la segmentation n'est plus une valeur de coupe, c'est le choix des sources — les _marqueurs_. Là est le fil de la section : sur un relief donné, la segmentation est entièrement déterminée par l'endroit d'où l'on fait partir l'eau.

=== L'intention
Séparer des objets en contact ou délimiter des régions sur un relief de contours, en s'appuyant sur des points de départ (les marqueurs) plutôt que sur un seuil d'intensité global. C'est l'outil privilégié pour scinder des disques ou des cellules accolés.

=== La forme recherchée
L'image mentale est celle d'un paysage topographique que l'on inonde. Les zones sombres de l'image (ou les intérieurs d'objets sur une transformée de distance) forment des cuvettes, tandis que les contours forment des crêtes. En plaçant une source d'eau (un marqueur) au fond de chaque cuvette et en laissant monter l'eau, les bassins s'étendent. Dès que deux bassins se rencontrent, on érige une ligne de crête (digue) pour former la frontière.

Pour séparer deux disques de rayon `r` qui se chevauchent légèrement, la transformée de distance `DT` du masque possède un maximum au centre de chaque disque. Le point de chevauchement forme un col (une selle) où la distance est minimale. En inondant le relief inversé `-DT` depuis les centres, les deux fronts d'eau se rencontrent exactement au col, plaçant la ligne de séparation à l'endroit géométriquement le plus étroit.

On note `f(x,y)` le relief topographique. L'ensemble des digues construites lors de l'inondation forme la ligne de partage des eaux :

#info-box(title: "La formule")[
```
Bassins(f)   = composantes connexes remplies depuis chaque minimum régional de f
Watershed(f) = lignes de crête séparant deux bassins distincts
```
]

Pour séparer deux objets convexes qui se touchent, le relief inversé de distance s'écrit : ∎

#info-box(title: "La formule")[
```
f = −DT(M)
```
]

=== Ce qu'il mesure, et son angle mort
Le watershed mesure une *topologie de bassins*. Son angle mort principal est la *sur-segmentation* : le bruit crée de faux minima locaux, ouvrant chacun un bassin. C'est pourquoi on utilise le watershed _par marqueurs_ (inonder uniquement depuis des sources imposées). De plus, il scinde à tort les objets fortement concaves (qui génèrent plusieurs maxima de `DT`) et ne peut séparer des objets accolés sans pincement physique (comme deux carrés parfaits bord à bord).

#question-box(title: "Exemple chiffré")[
Masque binaire 7×13 : deux blobs reliés par un pont d'un pixel de large (ligne 3, colonne 6 pincée).

```
0 0 0 0 0 0 0 0 0 0 0 0 0
0 1 1 1 1 1 0 1 1 1 1 1 0
0 1 1 1 1 1 1 1 1 1 1 1 0
0 1 1 1 1 1 1 1 1 1 1 1 0
0 1 1 1 1 1 1 1 1 1 1 1 0
0 1 1 1 1 1 0 1 1 1 1 1 0
0 0 0 0 0 0 0 0 0 0 0 0 0
```

Transformée de distance euclidienne (arrondie), ligne centrale (ligne 3) :

```
DT[3] = 0  1  2  3  2.83  2.24  2.00  2.24  2.83  3  2  1  0
                  ↑                ↑                ↑
               max=3        selle=2.00          max=3
              (col 3)        (col 6)            (col 9)
```

Deux maxima isolés à `DT = 3` (centres en (3,3) et (3,9)), séparés par une selle à `DT = 2` au pincement (3,6). On pose un marqueur sur chaque maximum, on inonde `−DT` : les deux bassins se rejoignent en colonne 6, où tombe la digue. Étiquetage obtenu :

```
. . . . . . . . . . . . .
. 1 1 1 1 1 . 2 2 2 2 2 .
. 1 1 1 1 1 1 2 2 2 2 2 .
. 1 1 1 1 1 1 2 2 2 2 2 .
. 1 1 1 1 1 1 2 2 2 2 2 .
. 1 1 1 1 1 . 2 2 2 2 2 .
. . . . . . . . . . . . .
```

*Deux régions.* Pour comparaison, un étiquetage en composantes connexes du masque donne *une seule* région : les deux blobs se touchent, rien ne les distingue sans la topographie de `DT`. C'est le service principal du watershed : séparer des objets en contact.
]

#info-box(title: "Subtilité d'implémentation")[
- *Le signe du relief.* `skimage.segmentation.watershed(image, markers, mask)` inonde depuis les *minima* de `image`. Pour séparer des objets par leur intérieur, on passe `−DT`, _pas_ `DT` : oublier le moins inonde depuis les bords et colle tout. Sur un relief de contours on passe `‖∇I‖` directement (les bords _sont_ déjà les crêtes).
- *Marqueurs.* `peak_local_max` renvoie des *coordonnées*, pas un masque étiqueté ; il faut les transformer en marqueurs entiers via `ndi.label`. Sans `min_distance` adapté ni `labels=mask`, on récupère des maxima multiples par objet (sur-segmentation) ou des maxima hors masque.
- *OpenCV diffère.* `cv2.watershed(img, markers)` attend une image *3 canaux* et un tableau `markers` en *int32* ; il *écrit en place*, marque les lignes de partage à *−1*, et la région inconnue à *0*. On lui fournit des marqueurs « sûrs » (objets certains, fond certain) et il étiquette la bande d'incertitude. Convention de connectivité (4 vs 8) à vérifier : elle change le tracé exact des digues.
- *Lisser avant.* Sur un relief de gradient, un `Gaussian(σ≈1–2)` ou une reconstruction morphologique en amont supprime les minima parasites ; c'est souvent ce qui sépare un résultat exploitable d'une bouillie sur-segmentée.
]

#canvas[
Canvas : `Image Source` -> `Threshold` -> `Distance Transform` -> `Python Node (watershed)` -> `Output Display`
]

=== Schéma de nœuds
```
[Masque] ──> [Transformée de distance] ──> [Maxima locaux → Marqueurs]
         ──> [Watershed(−DT, marqueurs, masque)] ──> [Objets séparés]
```

Variante « relief de contours » (régions non pleines) :

```
[Image] ──> [Sobel : relief des bords] ──> [Marqueurs sûrs (fond / objets)]
        ──> [Watershed] ──> [Régions]
```

_Schémas à produire ; scripts de référence en Annexe 1, §A1‑12.4._

---

// ============================================================

== K-means : regrouper ce qui se ressemble

#subtitle[K aimants dans l'espace des couleurs, chacun attirant les points proches]

#figfull("/figures/fig_ch12_obs2_kmeans.svg")

=== L'intention
Jusqu'ici, chaque pixel décidait seul sur son intensité. On veut maintenant regrouper les pixels qui se ressemblent, dans un espace plus riche que le simple niveau de gris — par exemple leur couleur, ou leur couleur _et_ leur position.

=== La forme recherchée
L'idée clé est l'*espace de caractéristiques*. Au lieu de penser un pixel comme un point dans l'image, on le pense comme un point dans un espace où chaque axe est une de ses propriétés. Un pixel couleur devient un point dans un cube à trois axes (rouge, vert, bleu) : deux pixels de teinte voisine sont proches dans ce cube, deux pixels de teintes opposées sont éloignés. Les pixels d'une image y forment des *nuages* — des amas naturels correspondant aux couleurs dominantes.

K-means cherche ces amas. On lui dit combien de groupes on veut (le nombre K), il place K points-repères dans le nuage, et chaque pixel rejoint le repère le plus proche — comme K aimants qui se partagent une nuée de billes. Choisir les caractéristiques et leur échelle, c'est déclarer ce qui rapproche deux pixels (l'esprit du chapitre 3) : ajouter la position (x, y) aux côtés de la couleur favorise des régions compactes ; ne garder que la couleur laisse des zones éloignées mais de même teinte dans le même groupe.

#info-box(title: "La formule")[
```
argmin_S   Σ_k  Σ_{x ∈ S_k}  ‖x − μ_k‖²
```
]

Cette ligne se lit en mots : on cherche le découpage S (les groupes S₁…S_K) qui rend *la plus petite possible* la somme, sur tous les pixels, du carré de leur distance à leur repère μ_k. La notation `‖x − μ_k‖²` est juste la distance (au carré) entre un pixel et son repère — la distance euclidienne « à vol d'oiseau » du chapitre 3. Minimiser cette somme, c'est demander des amas les plus serrés possible.

Trouver le découpage parfait est en théorie hors de portée pour un grand nombre de pixels. Mais une astuce simple s'en approche très bien, en alternant deux étapes qui, chacune, ne peuvent que resserrer les amas :

#info-box(title: "La formule")[
```
1. Affectation : chaque pixel rejoint le repère le plus proche
2. Mise à jour : chaque repère se replace au centre (la moyenne) de ses pixels
```
]

Pourquoi le centre ? Parce que la moyenne est précisément le point qui minimise la somme des distances au carré (rappel du chapitre 3 : la moyenne est le « point d'équilibre »). On répète ces deux gestes jusqu'à ce que plus rien ne bouge. Le résultat est un *minimum local* : un bon découpage, mais pas forcément le meilleur dans l'absolu — selon les repères de départ, on peut tomber sur un creux ou sur un autre. L'a priori de K-means est que les groupes sont des amas *ronds, de tailles comparables* ; sur des amas allongés, imbriqués, ou de densités très différentes, il se trompe. Et K doit être fixé d'avance. ∎

#question-box(title: "Exemple chiffré")[
Points sur une ligne {1, 2, 9, 10, 11}, K = 2, repères de départ 1 et 10 :

```
Affectation : {1, 2} → repère 1     {9, 10, 11} → repère 10
Mise à jour : repère 1 → 1.5         repère 10 → 10
Ré-affectation : rien ne change → terminé
```

Deux amas : {1, 2} (centre 1,5) et {9, 10, 11} (centre 10). Sur des données réelles, un mauvais choix de repères de départ piège l'algorithme dans un découpage médiocre — d'où l'astuce *k-means++*, qui éparpille les repères de départ pour éviter ce piège.
]

#info-box(title: "Réglage — normaliser les axes, travailler en Lab")[
Si l'on mélange couleur (de 0 à 255) et position (de 0 à 2000 pixels) sans précaution, la position, aux grands nombres, écrase complètement la couleur : il faut mettre les axes à la même échelle. Travailler en espace *Lab* (où les distances correspondent à peu près aux différences perçues par l'œil, chapitre 7) plutôt qu'en RGB donne des amas plus proches de ce qu'un humain regrouperait. Lancer le calcul plusieurs fois et garder le meilleur résultat protège contre les mauvais départs.
]

#canvas[
Canvas : `Image Source` → `Color Convert (BGR→Lab)` → `K-Means` → `Output Display`. Le nœud `K-Means` expose le nombre de classes K et le nombre d'essais ; l'inspecteur affiche le nombre de pixels par classe et recolore l'image avec la couleur moyenne de chaque groupe.

_Domaines :_ segmentation couleur en télédétection (couvert végétal, zones urbaines), réduction du nombre de couleurs, classification de tissus en histologie.

---
]

// ============================================================

== Mean-shift : remonter vers les sommets de densité

#subtitle[Des billes qui remontent chacune vers la bosse la plus proche]

#figfull("/figures/fig_ch12_obs3_meanshift.svg")

=== L'intention
K-means oblige à dire d'avance combien de groupes on cherche. On voudrait laisser ce nombre *se révéler tout seul* : trouver les zones denses de l'espace de caractéristiques sans préjuger de leur nombre.

=== La forme recherchée
Imaginons l'espace des couleurs non plus comme un nuage de points, mais comme un *paysage de collines* : là où beaucoup de pixels se ressemblent, la densité de points est forte, et le paysage forme une bosse. Chaque sommet de colline est une couleur dominante. Mean-shift lâche une bille à l'endroit de chaque pixel et la laisse *remonter la pente* jusqu'au sommet le plus proche. Toutes les billes qui finissent sur le même sommet appartiennent au même groupe. Le nombre de groupes est simplement le nombre de sommets atteints — il n'a jamais été fixé d'avance.

Comment une bille « sent-elle » la pente ? À chaque pas, on regarde les pixels proches (dans une fenêtre de largeur h) et on calcule leur centre ; ce centre est légèrement décalé vers la zone la plus peuplée du voisinage. Déplacer la bille vers ce centre, c'est faire un pas vers le haut de la colline. C'est exactement une *montée vers le plus dense*, cousine de la montée de pente du chapitre 6, mais appliquée à la densité de points plutôt qu'à l'intensité.

#info-box(title: "La formule")[
```
m(x) = [ Σᵢ xᵢ · K(‖x − xᵢ‖² / h²) ] / [ Σᵢ K(‖x − xᵢ‖² / h²) ]  −  x
```
]

Sous cette apparence touffue, c'est une moyenne pondérée : chaque voisin xᵢ tire la bille vers lui d'autant plus fort qu'il est proche (le poids K diminue avec la distance, h fixant la portée). La fraction est le centre pondéré du voisinage ; on en retranche la position actuelle x pour obtenir le *pas* à faire. On le répète jusqu'à ce que la bille ne bouge plus : elle est arrivée au sommet.

L'avantage : mean-shift épouse des amas de *forme quelconque* (aucune hypothèse de rondeur, contrairement à K-means) et trouve le nombre de groupes tout seul. L'angle mort se déplace sur *h*, la largeur de la fenêtre : trop petit, chaque petite bosse devient un groupe (sur-découpage) ; trop grand, toutes les collines fusionnent en une (sous-découpage). Et le calcul est lourd, car chaque bille doit consulter beaucoup de voisins à chaque pas. ∎

#question-box(title: "Exemple chiffré")[
Points groupés autour de 2 et de 10, fenêtre h = 3, bille lâchée en x = 4 :

```
Voisins dans [1, 7] : surtout {1, 2, 3}  →  centre ≈ 2  →  la bille glisse vers 2
Pas suivant depuis ~2 : plus de mouvement → sommet = 2
```

Une bille lâchée en x = 8 remonte vers le sommet 10. Deux groupes émergent *sans qu'on ait dit « K = 2 »* : c'est la densité qui décide, pas l'opérateur.
]

#info-box(title: "Réglage — la largeur de fenêtre h")[
h est le seul vrai réglage, et il n'a pas de valeur universelle : on le choisit selon l'échelle des structures attendues (des objets séparés par ~30 niveaux de gris appellent un h d'une quinzaine). La version image de mean-shift lisse aussi l'image en préservant les bords — un cousin proche du filtre bilatéral du chapitre 5, qui moyennait lui aussi seulement entre pixels proches en couleur.
]

#canvas[
Canvas : `Image Source` → `Mean Shift` → `Output Display`. Le nœud expose les deux rayons (spatial et couleur) ; l'inspecteur indique le nombre de régions distinctes obtenues après convergence, ce qui rend visible l'effet de h sur le sur- ou sous-découpage.

_Domaines :_ simplification d'images satellite, détection de régions d'intérêt sans nombre de classes connu, lissage de textures en conservant les contours.

---
]

// ============================================================

== Contours actifs (snakes) : une courbe élastique attirée par les bords

#subtitle[Un anneau de caoutchouc qui se contracte jusqu'à épouser le contour]

=== L'intention
Au lieu d'étiqueter chaque pixel indépendamment, on veut poser une courbe dans l'image et la laisser se déformer jusqu'à ce qu'elle vienne se coller sur le bord d'un objet — pour obtenir directement une frontière lisse et fermée.

=== La forme recherchée
L'image est celle d'un anneau de caoutchouc posé autour d'un objet : il se contracte, reste souple, et se laisse aimanter par les bords. Trois forces se disputent en permanence la forme de la courbe (appelée _snake_, « serpent ») :

- l'*élasticité* rapproche les points voisins de la courbe, comme un élastique tendu qui veut se raccourcir ;
- la *rigidité* refuse les pliures trop brusques, comme une tige qui résiste à être cassée net ;
- l'*attache aux données* tire la courbe vers les zones de fort gradient, c'est-à-dire les contours détectés (chapitre 6) — là où l'image change brutalement.

Les deux premières forces incarnent l'a priori de régularité : *une frontière d'objet réel est lisse, sans dents de scie ni cassures*. La troisième est la fidélité aux données. La forme finale est l'équilibre entre les deux.

#info-box(title: "La formule")[
```
E = ∫ [ α‖v'(s)‖²  +  β‖v''(s)‖²  +  E_image(v(s)) ] ds
       └─ élasticité ─┘  └─ rigidité ─┘  └── attache aux données ──┘
```
]

Ce qu'il faut lire : on attribue à chaque forme possible de la courbe une *énergie* (le grand ∫ additionne la contribution de tout le long de la courbe), et on cherche la forme d'énergie la plus basse. `v'` mesure à quelle vitesse la courbe s'allonge (l'élasticité la pénalise), `v''` mesure à quel point elle tourne brusquement (la rigidité la pénalise), et `E_image` est basse là où le gradient est fort (l'attache aux bords y attire la courbe). Les curseurs α et β règlent le poids de la souplesse contre celui de la fidélité aux bords.

Il n'existe pas de formule donnant directement la meilleure courbe. On procède donc *par petits pas* : on découpe la courbe en points, et à chaque itération on déplace légèrement chaque point dans le sens qui fait baisser l'énergie, jusqu'à ce que tout se stabilise. C'est exactement la même mécanique que celle de Horn-Schunck pour le mouvement (§9.4) — chercher le minimum d'une énergie en ajustant pas à pas — appliquée ici à une courbe au lieu d'un champ de vecteurs.

Le snake produit un contour lisse et fermé, idéal pour un objet unique aux bords doux (un organe, une silhouette). Ses angles morts : il faut le *poser près* de l'objet au départ, sinon il s'accroche au mauvais bord ou s'effondre ; il ne *change pas de forme topologique* (une seule courbe ne peut se scinder pour entourer deux objets séparés) ; et il a du mal à pénétrer dans les creux profonds. ∎

#question-box(title: "Exemple chiffré")[
L'élasticité préfère des points *régulièrement espacés*. Pour trois points consécutifs, sa contribution est à peu près la somme des carrés des écarts entre points :

```
Espacement (10, 10) :  α(10² + 10²) = 200 α
Espacement (5, 15)  :  α(5²  + 15²) = 250 α   (plus coûteux)
```

À longueur totale égale, l'espacement régulier coûte moins d'énergie : le snake répartit donc ses points uniformément, pendant que l'attache aux bords les tire vers le contour. La forme finale est le compromis entre ces deux tendances.
]

#warning-box(title: "Piège — l'initialisation décide du résultat")[
Tout se joue sur la courbe de départ : posée trop loin de l'objet, elle aboutit à un résultat faux. Pour des objets multiples ou qui changent de forme (une cellule qui se divise), on préfère une variante dite _level set_, qui autorise la frontière à se scinder et à fusionner toute seule. Lisser légèrement l'image avant le calcul élargit la zone d'attraction des bords et stabilise la convergence.
]

#canvas[
Canvas : `Image Source` → `Grayscale` → `Gaussian Blur` → `Active Contour` → `Output Display`. Le nœud `Active Contour` prend une courbe initiale (un cercle posé sur l'objet) et expose les curseurs d'élasticité et de rigidité ; il superpose la courbe finale sur l'image et l'inspecteur en donne le centre et le nombre de points.

_Domaines :_ segmentation d'organes en imagerie médicale, suivi de silhouette en vidéo, délimitation de cellules isolées.

---
]

// ============================================================

== Coupe de graphe (graph cut) : la décision globale et cohérente

#subtitle[Un réseau de tuyaux qu'on coupe au moindre coût pour séparer objet et fond]

=== L'intention
Les méthodes précédentes décident localement, ou dans un espace sans géométrie. On veut une décision *globale*, où un pixel dont on est sûr aide à trancher le cas de ses voisins hésitants — pour que la segmentation reste cohérente d'un bout à l'autre.

=== La forme recherchée
On voit l'image entière comme un *réseau de tuyaux d'eau*. Chaque pixel est un carrefour de tuyaux. Deux robinets spéciaux représentent les deux étiquettes possibles : « objet » et « fond ». Chaque tuyau a une capacité maximale de débit. Segmenter, c'est *couper* des tuyaux pour isoler complètement le robinet « objet » du robinet « fond », en coupant le moins de capacité possible. Cette coupe la moins chère porte un nom : la *coupe minimale*.

Deux sortes de tuyaux. Ceux qui relient un pixel à un robinet portent le *coût des données* : un pixel qui ressemble fortement à l'objet a un gros tuyau vers le robinet « objet », qu'on hésitera donc à couper. Ceux qui relient deux pixels voisins portent le *coût de lissage* : il est élevé entre deux pixels qui se ressemblent, pour décourager de faire passer une frontière au beau milieu d'une zone uniforme. Trouver la coupe la moins chère trouve donc la frontière qui colle aux données _et_ tombe entre régions vraiment différentes.

#info-box(title: "La formule")[
```
E(L) = Σ_p  D_p(L_p)  +  λ  Σ_{(p,q)}  V(L_p, L_q)
        └── terme de données ──┘         └── terme de lissage ──┘
```
]

L est l'étiquetage complet (chaque pixel reçoit « objet » ou « fond »). Le premier terme additionne, sur tous les pixels p, le coût D_p de l'étiquette qu'on leur donne. Le second additionne, sur toutes les paires de voisins (p, q), un coût V de désaccord, élevé quand deux voisins semblables reçoivent des étiquettes différentes. Le curseur λ dose le poids du lissage. On démontre que cet étiquetage d'énergie minimale correspond exactement à la coupe de tuyaux la moins chère, et qu'on sait la trouver *vite et de façon exacte* dans le cas à deux étiquettes (algorithme de flot maximal). C'est rare et précieux : ailleurs dans le livre, on se contentait d'un minimum local ; ici, on atteint le meilleur découpage absolu.

La structure est identique à Horn-Schunck (§9.4) : le terme de lissage du mouvement devient ici le coût de désaccord entre voisins. Et il joue le même rôle — il *propage* les décisions sûres vers les pixels hésitants, comme la régularité du flot remplissait les zones sans texture. Le curseur λ rend le fil du chapitre littéral :

#info-box(title: "La formule")[
```
λ = 0     → chaque pixel décide seul = SEUILLAGE (§12.1), bruité
λ petit   → données dominantes, frontières fidèles mais découpées
λ grand   → lissage dominant, frontières nettes mais détails perdus
λ → ∞    → une seule région (tout est lissé en bloc)
```
]

C'est exactement le même curseur fidélité/régularité que le α de Horn-Schunck. ∎

#question-box(title: "Exemple chiffré")[
Deux pixels voisins. p ressemble nettement à l'objet (coût 1 pour « objet », 8 pour « fond ») ; q est ambigu (coût 5 pour « objet », 4 pour « fond »). Le désaccord entre voisins coûte 2.

```
(obj, obj) :  1 + 5 + 0 = 6    ← le moins cher
(obj, fond) : 1 + 4 + 2 = 7
(fond, obj) : 8 + 5 + 2 = 15
(fond,fond) : 8 + 4 + 0 = 12
```

Tout seul, q pencherait pour « fond » (4 \< 5). Mais le coût de désaccord et la grande confiance de p *font basculer q vers « objet »* : la cohérence avec le voisin l'emporte sur une préférence individuelle fragile. C'est précisément ce qu'on attend d'une bonne segmentation.
]

#warning-box(title: "Piège — il faut une amorce")[
La version interactive (GrabCut) a besoin d'une *amorce* : un rectangle grossier autour de l'objet, ou quelques traits indiquant « ça c'est l'objet, ça c'est le fond ». Sans cette amorce, l'algorithme n'a rien pour distinguer les deux robinets. Le curseur λ n'a pas d'unité absolue : on le règle relativement à l'échelle des coûts de données (si ceux-ci vont de 0 à 10, un λ entre 0,1 et 5 balaie tout l'éventail du curseur).
]

#canvas[
Canvas : `Image Source` → `GrabCut` → `Output Display`. Le nœud `GrabCut` prend l'amorce (un rectangle tracé sur l'image, ou des traits objet/fond) et le curseur λ ; il sort le masque objet/fond et l'inspecteur compte les pixels de chaque côté.

_Domaines :_ détourage semi-automatique en retouche, segmentation interactive d'organes (un radiologue trace l'amorce), séparation objet/fond en robotique de saisie.

---
]

// ============================================================

== Tableau récapitulatif — méthode, a priori, forces, limites

#table(
  columns: 5,
  table.header(
    [*Méthode*], [*A priori (ce qu'elle suppose)*], [*Forces*], [*Limites*], [*Usage type*]
  ),
  [Otsu], [deux classes d'intensité en double bosse], [automatique, rapide, sans réglage], [échoue si une seule bosse ou classes très déséquilibrées], [binarisation de documents, tri de grains],
  [Adaptatif], [le fond varie lentement dans l'espace], [robuste à l'éclairage inégal], [objets plus grands que le voisinage invisibles], [OCR sur pages photographiées, contrôle qualité],
  [Watershed (par marqueurs)], [une région est un bassin issu d'un marqueur imposé], [sépare les objets convexes accolés, automatique si marqueurs trouvés], [sur-segmentation si bruit, scinde les objets concaves, pas de contact franc sans pincement], [séparation d'objets convexes accolés (cellules, grains, pièces)],
  [K-means], [K amas ronds, de tailles comparables], [multi-classes, souple], [K fixé d'avance, dépend du départ, lent sur grandes images], [segmentation couleur, télédétection],
  [Mean-shift], [des sommets de densité séparés (largeur h)], [nombre de groupes automatique, formes libres], [h critique, calcul lourd], [images satellite, histologie sans K connu],
  [Snakes], [une frontière lisse, un objet unique], [contour précis et régulier], [départ proche requis, forme topologique fixe], [organes médicaux, silhouettes vidéo],
  [Graph cut], [données + voisins cohérents], [meilleur découpage absolu (2 classes), robuste], [amorce requise, λ à régler], [détourage interactif, segmentation guidée],
)

_État de l'art :_ ces méthodes précèdent l'apprentissage profond (U-Net, Mask R-CNN, SAM), qui domine aujourd'hui la segmentation générale. Elles gardent leur créneau — aucune donnée d'entraînement, résultats interprétables, rapides, fiables sur des problèmes bien posés — et survivent _à l'intérieur_ des pipelines profonds : un raffineur de bords cousin de la coupe de graphe nettoie souvent la sortie d'un réseau.

---

// ============================================================

== un seul axe, six fois

Le chapitre raconte une histoire déclinée sept fois : l'image seule ne tranche pas, il faut *ajouter une hypothèse* et choisir *où* placer la décision.

```
Otsu       : suppose « deux classes d'intensité » — décide sur l'histogramme
Adaptatif  : suppose « le fond varie lentement »  — décide localement
Watershed  : suppose « une région = un bassin de relief » — décide par les marqueurs
K-means    : suppose « K amas compacts »          — décide dans l'espace des couleurs
Mean-shift : suppose « des sommets de densité »   — décide dans l'espace des couleurs
Snakes     : suppose « une frontière lisse »      — décide sur une courbe
Graph cut  : suppose « données + voisins cohérents » — décide globalement
```

Le watershed déplace la question. Otsu demandait _où couper les valeurs_ ; le watershed demande _d'où faire partir l'eau_. Le relief — gradient ou distance — fixe la forme du paysage, mais ce sont les marqueurs qui décident combien d'objets existent et lesquels. Mal placés, ils sur-segmentent ou fusionnent ; bien placés, ils transforment un problème de comptage en un simple remplissage. On retrouvera au chapitre 16 la même dépendance d'un résultat « automatique » à quelques germes bien choisis, quand RANSAC fera émerger un modèle d'une poignée de points tirés au sort.

D'un bout à l'autre, le même axe : à gauche le pur attachement aux données (le seuillage, où chaque pixel décide seul et où le bruit passe entier), à droite la régularité dominante (le lissage qui propage et nettoie, au risque d'effacer le détail). La coupe de graphe le rend visible avec son curseur λ — le même curseur que le α de Horn-Schunck pour le mouvement (chapitre 9), la même tension qu'un filtre encode comme a priori sur le signal (chapitre 5), la même question qu'une distance pose en déclarant ce qui rapproche deux pixels (chapitre 3). Comme un descripteur du chapitre 1 garde une chose et en jette une autre, une segmentation déclare ce qu'elle suppose d'une frontière : tout l'art est de choisir, pour l'image qu'on a, ce qu'on accepte de tenir pour vrai. Le chapitre 13 reprendra cette idée pour décrire les textures.

---

]
