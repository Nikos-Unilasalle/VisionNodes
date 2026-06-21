# Patch de contenu — Chapitre 12 : ajout de la section Watershed
## Section manquante (ligne de partage des eaux)

> **Mode d'emploi.** Patch de **contenu** (distinct du patch pédagogique d'observations) : il ajoute une section complète au chapitre 12, au format des sections existantes (définition → dérivation → angle mort → exemple chiffré → piège → code).
>
> **Placement recommandé : nouvelle section 12.4**, juste après le seuillage adaptatif et **avant** la famille par regroupement (K-means, mean-shift). Le watershed est la méthode classique de segmentation par régions la plus canonique ; le mean-shift, lui, gagnerait à reculer d'un cran. Renumérotation à répercuter : K-means 12.3 → 12.5, mean-shift 12.4 → 12.6, snakes → 12.7, graph cut → 12.8 (ou conserver vos numéros et n'insérer que celui-ci en 12.4 bis si vous préférez ne pas toucher aux renvois existants).
>
> **Renvoi entrant à ajouter** dans le chapitre 10 (Transformées), à la formule de la transformée de distance : « la transformée de distance alimente le watershse par marqueurs — voir §12.4 ».

---

## Section 12.4 — Watershed (ligne de partage des eaux)

Les méthodes vues jusqu'ici partitionnent l'image par une hypothèse sur les *valeurs* : un seuil sépare deux modes d'intensité, K-means regroupe des couleurs proches. Le watershed change de registre. Il lit l'image comme un **relief** et laisse l'eau monter depuis des sources : chaque bassin qui se remplit devient une région, et les crêtes où deux bassins se rejoignent deviennent les frontières. Ce qui décide de la segmentation n'est plus une valeur de coupe, c'est le choix des sources — les *marqueurs*. Là est le fil de la section : sur un relief donné, la segmentation est entièrement déterminée par l'endroit d'où l'on fait partir l'eau.

### Définition

On voit une image scalaire `f(x,y)` comme une surface topographique : l'altitude est `f`. Par immersion, on perce un trou sous chaque minimum régional et on plonge lentement la surface dans l'eau. L'eau monte, les bassins s'étendent. Quand les eaux de deux bassins voisins menacent de se mélanger, on érige une digue d'épaisseur nulle. L'ensemble des digues forme la **ligne de partage des eaux** :

```
Bassins(f)   = composantes connexes remplies depuis chaque minimum régional de f
Watershed(f) = lignes de crête séparant deux bassins distincts
```

En pratique on n'applique presque jamais le watershed à `f = I` (l'image brute a trop de minima — voir l'angle mort). Les deux reliefs utiles sont :

```
Relief « contours »  : f = ‖∇I‖   (les bords sont des crêtes hautes ; les régions, des cuvettes)
Relief « distance »  : f = −DT(M)  (M = masque binaire ; DT = transformée de distance, §10)
```

Le second est le cas canonique pour **séparer des objets convexes qui se touchent** : chaque objet creuse une cuvette unique (son intérieur, où `DT` est maximale), et le pincement entre deux objets est une crête.

### Dérivation — pourquoi `−DT` sépare deux blobs collés

Soit `M` un masque binaire formé de deux disques de rayon `r` dont les centres sont distants de `2r − δ` (ils se chevauchent légèrement, `δ > 0` petit). La transformée de distance `DT(p) = min_{q∉M} d(p,q)` vaut localement la distance au bord le plus proche.

Au centre de chaque disque, `DT` atteint un maximum isolé valant ≈ `r` : c'est l'unique minimum régional de `−DT` à l'intérieur de ce disque. Sur le segment qui joint les deux centres, `DT` décroît de `r` vers les centres jusqu'à une valeur de **selle** au point de pincement, puis remonte. En inondant `−DT` depuis les deux minima, les deux fronts d'eau se rencontrent exactement à cette selle : la digue tombe sur le pincement. La frontière produite est donc la médiatrice locale du col, c'est-à-dire l'endroit géométriquement le plus étroit du « 8 ». ∎

L'argument tient tant que chaque objet n'a qu'un seul maximum de `DT` — soit, en pratique, tant que les objets sont **convexes** (ou peu concaves). Un objet en croissant a deux maxima de `DT` et sera scindé à tort : voir l'angle mort.

### Ce que ça mesure / l'angle mort

Le watershd ne mesure pas une intensité : il mesure une **topologie de bassins**. Sa fragilité tient en un mot — la **sur-segmentation**. Chaque minimum régional, même creusé par un seul pixel de bruit, ouvre un bassin. Sur un relief de gradient `‖∇I‖` non lissé, on obtient couramment des centaines de bassins pour une image qui n'a que trois objets. C'est pourquoi le watershed *brut* est presque inutilisable et le watershed *par marqueurs* est la norme : on impose la liste des minima (un marqueur par objet voulu, un pour le fond) et l'on inonde seulement depuis ceux-là.

Trois cas où il échoue, à garder en tête :
- **Objets concaves.** Un `DT` à plusieurs maxima scinde un objet unique. Remède : `h-maxima` (fusionner les maxima séparés par moins de `h`) ou marqueurs manuels.
- **Objets de tailles très inégales.** Le petit objet a un `DT` faible ; un lissage trop fort efface son maximum et il disparaît dans le voisin.
- **Contact franc sans pincement.** Deux carrés accolés bord à bord n'ont pas de col dans le `DT` : aucune crête à trouver, le watershed les laisse fusionnés.

### Exemple numérique (calculable à la main)

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

**Deux régions.** Pour comparaison, un simple étiquetage en composantes connexes du masque donne **une seule** région : les deux blobs se touchent, rien ne les distingue sans la topographie de `DT`. C'est exactement le service que rend le watershed — compter et séparer des objets qui se chevauchent — partout où il y a des cellules accolées, des grains soudés, des pièces en contact.

### Piège d'implémentation

- **Le signe du relief.** `skimage.segmentation.watershed(image, markers, mask)` inonde depuis les **minima** de `image`. Pour séparer des objets par leur intérieur, on passe `−DT`, *pas* `DT` : oublier le moins inonde depuis les bords et colle tout. Sur un relief de contours on passe `‖∇I‖` directement (les bords *sont* déjà les crêtes).
- **Marqueurs.** `peak_local_max` renvoie des **coordonnées**, pas un masque étiqueté ; il faut les transformer en marqueurs entiers via `ndi.label`. Sans `min_distance` adapté ni `labels=mask`, on récupère des maxima multiples par objet (sur-segmentation) ou des maxima hors masque.
- **OpenCV diffère.** `cv2.watershed(img, markers)` attend une image **3 canaux** et un tableau `markers` en **int32** ; il **écrit en place**, marque les lignes de partage à **−1**, et la région inconnue à **0**. On lui fournit des marqueurs « sûrs » (objets certains, fond certain) et il étiquette la bande d'incertitude. Convention de connectivité (4 vs 8) à vérifier : elle change le tracé exact des digues.
- **Lisser avant.** Sur un relief de gradient, un `Gaussian(σ≈1–2)` ou une reconstruction morphologique en amont supprime les minima parasites ; c'est souvent ce qui sépare un résultat exploitable d'une bouillie sur-segmentée.

### Schéma de nœuds

```
[Masque] ──> [Transformée de distance] ──> [Maxima locaux → Marqueurs]
         ──> [Watershed(−DT, marqueurs, masque)] ──> [Objets séparés]
```

Variante « relief de contours » (régions non pleines) :

```
[Image] ──> [Sobel : relief des bords] ──> [Marqueurs sûrs (fond / objets)]
        ──> [Watershed] ──> [Régions]
```

*Schémas à produire ; scripts de référence en Annexe 1, §A1‑12.4.*

---

## Ligne à ajouter au tableau récapitulatif du chapitre 12

| Outil | Ce qu'il mesure | Angle mort | Hypothèse de région | Usage |
|---|---|---|---|---|
| Watershed (par marqueurs) | Topologie de bassins d'un relief | Sur-segmentation ; objets concaves scindés ; contacts francs non séparés | Une région = un bassin issu d'une source imposée | Séparer des objets convexes accolés (cellules, grains, pièces) |

## Raccord à l'encadré final du chapitre

> Le watershed déplace la question. Otsu demandait *où couper les valeurs* ; le watershed demande *d'où faire partir l'eau*. Le relief — gradient ou distance — fixe la forme du paysage, mais ce sont les marqueurs qui décident combien d'objets existent et lesquels. Mal placés, ils sur-segmentent ou fusionnent ; bien placés, ils transforment un problème de comptage en un simple remplissage. On retrouvera au chapitre 16 la même dépendance d'un résultat « automatique » à quelques germes bien choisis, quand RANSAC fera émerger un modèle d'une poignée de points tirés au sort.
