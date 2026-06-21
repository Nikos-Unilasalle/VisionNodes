# Chapitre 9 — Lire le mouvement : flot optique

![Un observateur regarde une barre oblique en mouvement à travers une fente étroite ; il ne peut deviner qu'une seule des deux composantes du déplacement](../figures/fig_ch9_couverture.jpg)
*Une seule équation par pixel, deux inconnues à trouver. Comme regarder un objet bouger par une fente : on ne voit qu'une partie du mouvement, et il faut parier sur le reste.*

---

Entre deux images successives d'une vidéo, les choses bougent. Un piéton traverse un carrefour, un bras de robot pivote, une cellule migre sous le microscope : l'image suivante diffère de la précédente, et cette différence porte l'empreinte du mouvement. Le **flot optique** est le champ de flèches qui tente de lire cette empreinte, pixel par pixel, en associant à chaque point une direction et une vitesse apparentes.

Le fil du chapitre tient en une phrase : **le problème est mal posé — une seule équation pour deux inconnues — et chaque méthode ajoute un a priori différent pour le résoudre.** « Mal posé » veut dire que les données ne suffisent pas à déterminer la réponse de façon unique : on dispose d'une seule équation par pixel, mais un déplacement dans le plan a deux composantes (horizontale et verticale). Ce manque est irréductible par les seules données ; il faut ajouter une hypothèse sur la nature du mouvement. Lucas-Kanade suppose un mouvement localement uniforme ; Horn-Schunck un mouvement qui varie doucement sur toute l'image. Ces hypothèses ne sont pas des artifices — ce sont deux visions du monde physique, avec chacune ses forces et ses zones d'échec.

Le schéma **données insuffisantes + a priori = solution déterminée** n'est pas propre au mouvement : on l'a vu en filtrage (chapitre 5, un filtre est un a priori sur le signal) et en distance (chapitre 3, une distance déclare ce qui compte). Le flot optique en est l'archétype le plus explicite — ici le manque est comptable, un contre deux. Deux liens : la stéréovision (chapitre 8) appariait deux vues décalées dans l'**espace** pour la profondeur ; le flot apparie deux vues décalées dans le **temps** pour le mouvement. Et le tenseur de structure du chapitre 6 reparaît ici au cœur de Lucas-Kanade : les pixels où le flot est fiable sont exactement les coins que Shi-Tomasi repère.

### Un peu de vocabulaire avant de commencer

*   **Flot optique** : Le déplacement apparent des intensités lumineuses dans une séquence d'images, représenté par un champ de vecteurs.
*   **Vecteur de vitesse (u, v)** : Les deux inconnues recherchées pour chaque pixel, où `u` est le déplacement horizontal et `v` le déplacement vertical entre deux instants.
*   **Dérivées spatio-temporelles (Ix, Iy, It)** : Les variations de luminosité de l'image selon l'espace (gradients horizontal `Ix` et vertical `Iy`) et selon le temps (différence entre deux images successives `It`).

---

## 9.1 — La contrainte du flot optique : une équation pour deux inconnues

> *Un point garde sa luminosité quand il se déplace*

### L'intention

On veut relier le déplacement d'un point à ce qu'on peut mesurer dans les images : les intensités et leurs variations. Il faut une équation qui lie l'inconnue (la vitesse) aux observables.

### La forme recherchée

Le point de départ est une hypothèse d'apparence innocente : un point conserve sa luminosité d'une image à la suivante. S'il était sombre, il reste sombre quand il bouge. C'est l'a priori zéro, sur lequel tout se construit (il tient quand l'éclairage est stable, et se brise sur un reflet soudain). De cette idée on tire une équation : si un pixel change de valeur entre deux images, c'est parce que de la matière s'est déplacée, et ce changement temporel est lié au déplacement par les variations spatiales de l'image — le gradient du chapitre 6.

### La formule

```
Iₓ·u + Iᵧ·v + Iₜ = 0          (équation du flot optique)
```

Iₓ et Iᵧ sont les variations spatiales d'intensité (le gradient, horizontal et vertical) ; Iₜ est la variation temporelle, c'est-à-dire la simple différence entre les deux images au même pixel ; u et v sont l'inconnue cherchée — le déplacement horizontal et vertical. Tout est mesurable sauf u et v. Et là est le problème : **une seule équation, deux inconnues**. Les données ne suffisent pas à les déterminer ; il faudra ajouter une hypothèse. ∎

### Exemple

Un bord vertical dans une image de scanner : fort gradient horizontal (Iₓ = 50), aucun gradient vertical (Iᵧ = 0). Entre deux images, la région s'éclaircit (Iₜ = −100) :

```
50·u + 0·v + (−100) = 0  ⟹  u = 2,  v indéterminé
```

Le bord s'est déplacé de 2 pixels horizontalement, mais v reste libre : faire glisser un bord vertical le long de lui-même ne change aucune intensité, donc aucune mesure ne le détecte. Les données ne contraignent qu'une direction.

### Limite — petits déplacements seulement

L'équation suppose des déplacements de l'ordre de 1 à 2 pixels entre deux images. Un objet rapide qui bouge de 10 à 30 pixels viole cette hypothèse, et l'équation s'effondre silencieusement. Les méthodes pyramidales (§9.3) y remédient.

### Dans VNStudio

Canvas : `Webcam` → `Optical Flow (Lucas-Kanade)` → `Display`. Le nœud calcule le déplacement image par image ; le tenseur de structure (§9.2) indique aux endroits à flux fiable les variations Iₓ, Iᵧ qui satisfont la contrainte de luminosité.

---

## 9.2 — Le problème d'ouverture : voir par une fente

> *Une barre oblique derrière un judas : impossible de dire son vrai sens*

### L'intention

Comprendre *pourquoi* les données seules ne suffisent pas, et *où* elles suffisent malgré tout — pour savoir quels pixels portent une information de mouvement fiable.

### La forme recherchée

L'équation du §9.1 ne contraint que la composante du mouvement **perpendiculaire au bord**. La composante le long du bord reste libre. L'image utile est celle d'un observateur regardant un mur à travers un étroit judas : une barre oblique passe derrière, et il ne la voit se déplacer que perpendiculairement à elle-même. Pourtant, la barre pourrait bouger dans n'importe quelle direction oblique et produire exactement la même image dans le judas. Ce n'est pas une illusion subjective mais un manque d'information objectif — le **problème d'ouverture**. La fente, c'est la fenêtre d'observation locale ; le mur entier, c'est l'image complète dont on se prive pour aller vite.

### Où le flot est-il fiable ?

Le mouvement n'est pleinement déterminé qu'aux endroits où le gradient varie dans **plusieurs directions** — les **coins** (rappel du §6.4). Sur un bord droit, le gradient pointe toujours dans la même direction, le flot est ambigu. Dans une région uniforme, le gradient est nul, le flot est totalement indéterminé. On suit ce qui est suivable, et ce qui est suivable est exactement ce que Shi-Tomasi identifie comme un bon coin.

### Subtilité — un vecteur calculé n'est pas un vecteur mesuré

Calculer le flot sur toute l'image donne un résultat « complet », mais dans les régions uniformes ou le long des bords droits, ce résultat n'est pas faux au sens d'un bug : il est **indéterminé**, n'importe quelle valeur conviendrait. Des flèches numériquement présentes dans ces zones ne mesurent rien de réel. Regarder la carte du tenseur de structure (où est-on coin, bord, plat ?) avant d'interpréter un champ de flot évite de prendre du bruit pour du mouvement.

### Dans VNStudio

Canvas : `Image File` → `Structure Tensor` → `Display`. La carte « plat / bord / coin » du chapitre 6 indique directement où le flot sera fiable (les coins) et où il sera ambigu (les bords, les zones plates).

---

## 9.3 — Lucas-Kanade : la solution locale

> *Faire voter 25 pixels d'une fenêtre pour un seul déplacement*

### L'intention

Combler le manque d'information avec l'hypothèse la plus simple : sur un petit voisinage, tous les pixels bougent de la même façon.

### La forme recherchée

Lucas-Kanade suppose le mouvement **uniforme sur une fenêtre** de, disons, 5 × 5 pixels. Les 25 pixels partagent alors la même vitesse (u, v). On passe ainsi d'une seule équation à 25 équations pour 2 inconnues : un système **surdéterminé** (plus d'équations que d'inconnues). On a donc de la marge pour « faire voter » les 25 pixels et atténuer le bruit. L'hypothèse suppose le voisinage rigide — raisonnable pour le coin d'un panneau, grossière pour un tissu biologique qui se déforme.

### La formule

Comme aucune vitesse ne satisfait exactement les 25 équations à la fois (à cause du bruit), on cherche celle qui s'en approche le mieux : la solution dite **aux moindres carrés**, celle qui rend la plus petite possible la somme des erreurs au carré. C'est la même idée que chercher la droite qui passe « au mieux » par un nuage de points. Le calcul fait apparaître, au cœur de la résolution, un petit tableau 2×2 : c'est **exactement le tenseur de structure** du chapitre 6. Ses deux valeurs propres λ₁ et λ₂ (le « degré de variation » dans les deux directions principales, §6.4) disent si la solution est fiable :

```
λ₁ et λ₂ tous deux grands  (coin)   → solution unique et stable
λ₁ grande, λ₂ ≈ 0          (bord)   → ambiguë (problème d'ouverture)
λ₁ et λ₂ ≈ 0               (plat)   → totalement indéterminée
```

Le problème d'ouverture réapparaît donc sous forme chiffrée : le flot n'est fiable que si les deux valeurs propres sont grandes, c'est-à-dire sur un coin. C'est pourquoi Lucas-Kanade s'applique presque toujours aux **points de Shi-Tomasi** plutôt qu'à tous les pixels : on ne suit que là où le suivi a un sens. Le résultat est un flot **épars** — quelques centaines de points — mais chaque flèche est fiable.

Pour les grands déplacements (où l'équation du §9.1 s'effondre), on utilise une **pyramide d'images** : on réduit la résolution par deux à chaque niveau, si bien qu'un déplacement de 20 pixels n'en fait plus que 2 ou 3 au niveau le plus grossier ; on y calcule le flot, puis on l'affine niveau par niveau jusqu'à la pleine résolution. ∎

### Exemple

Fenêtre 5×5 sur le coin d'un marqueur : valeurs propres λ₁ = 1200, λ₂ = 950 — toutes deux grandes, la solution sort sans ambiguïté. Fenêtre sur le bord droit d'un couloir : gradients tous horizontaux, λ₁ = 1100 mais λ₂ ≈ 3. Le rapport 1100/3 ≈ 367 indique une solution numériquement instable, à rejeter — c'est le problème d'ouverture qui frappe.

### Dans VNStudio

Canvas : `Webcam` → `Optical Flow (Lucas-Kanade)` → `Display`. Le nœud détecte automatiquement les coins fiables (Shi-Tomasi) et les suit par pyramide entre les images successives ; le port `Overlay` trace une flèche par point suivi et l'inspecteur donne le déplacement moyen.

---

## 9.4 — Horn-Schunck : la solution globale

> *Une nappe tendue sur le paysage : des pentes, mais ni plis ni déchirures*

### L'intention

Là où Lucas-Kanade renonce aux zones sans coin, on voudrait un champ de mouvement **partout** — y compris dans les régions uniformes — en propageant l'information depuis les zones fiables.

### La forme recherchée

Pour vous représenter la logique globale de Horn-Schunck, imaginez que vous étendez une fine **nappe de caoutchouc élastique** au-dessus de votre image :
1. **La contrainte physique** : Cette nappe est fixée à l'image par de petits ressorts. Partout où un pixel a une texture reconnaissable (un contour, un coin), le ressort est très rigide : il force la nappe de caoutchouc à suivre le mouvement mesuré localement.
2. **La propagation par élasticité** : Dans les zones lisses et uniformes (un mur blanc ou le ciel), il n'y a aucun ressort (aucune donnée locale de mouvement). Mais comme la nappe de caoutchouc est élastique et continue, le mouvement s'y propage tout de suite par traction depuis les bords et les coins environnants. C'est l'image d'une nappe en caoutchouc : tirez sur un côté, et tout le milieu suit le mouvement de façon fluide et continue.
3. **Le coût des déchirures** : La nappe de caoutchouc peut s'étirer (avoir des pentes douces), mais elle refuse de se déchirer (pas de sauts de vitesse brusques).

Cette hypothèse de régularité globale est justifiée dans bien des cas réels : le fond d'une scène de surveillance bouge de façon cohérente, ou les tissus d'un cœur en mouvement lors d'une IRM cardiaque se déplacent continûment.

### La formule

On attribue à chaque champ de mouvement possible une **énergie** faite de deux termes, et on cherche le champ d'énergie minimale :

```
E = (terme de données) + α · (terme de lissage)
```

Le **terme de données** mesure à quel point le champ respecte l'équation du flot (§9.1) — il colle aux observations. Le **terme de lissage** mesure à quel point le champ varie d'un pixel au voisin — il pénalise les à-coups. Le curseur α dose entre les deux : grand α = champ très lisse, petit α = fidèle aux données. C'est exactement le schéma « coller aux données + rester régulier » qu'on retrouvera partout (segmentation, débruitage).

Le cœur de l'affaire est le terme de lissage. Là où les données ne disent rien (zones plates, bords droits — le problème d'ouverture), il **propage** le mouvement depuis les zones fiables (les coins) vers les zones ambiguës, par une sorte de diffusion. Horn-Schunck remplit les trous que Lucas-Kanade laissait vides. Le prix : un champ **dense** (une flèche par pixel) mais **flou aux frontières** (objet et fond voient leurs vitesses se mélanger si α est grand). On atteint le minimum non par une formule directe, mais **par petits pas** : on ajuste le champ itérativement jusqu'à ce qu'il se stabilise — la même mécanique que les snakes du chapitre 12. ∎

### Exemple

Sur une image de vélocimétrie (suivi de particules dans un fluide), un grand α donne un champ lisse où les tourbillons sont visibles mais les bords du vaisseau flous ; un petit α restitue les gradients de vitesse à la paroi mais introduit du bruit au cœur du flux peu contrasté. Le bon réglage dépend de l'échelle du mouvement attendu — un lien direct avec le chapitre 5.

Horn-Schunck (1981) et Lucas-Kanade (1981) fondent le domaine ; le flot dense de haute précision repose aujourd'hui sur l'apprentissage profond (RAFT, PWC-Net). La structure reste identique — coller aux données + rester régulier — mais l'a priori de régularité n'est plus posé à la main : il est **appris** sur des milliers de scènes annotées.

### Paramètres opérationnels (VNStudio / Python)

Dans les nœuds de flot optique (ou via OpenCV en Python), le comportement de la détection dépend des paramètres suivants :

*   **Taille de la fenêtre locale (`winSize`)** :
    *   Dans VNStudio, ce paramètre correspond au champ **Window Size** ; en Python (OpenCV), il correspond à l'argument `winSize` dans `cv2.calcOpticalFlowPyrLK`.
    *   Dans l'algorithme de Lucas-Kanade (`cv2.calcOpticalFlowPyrLK`), ce paramètre (ex. : 15×15 ou 21×21) définit la taille de la région dans laquelle le mouvement est supposé uniforme. Une fenêtre trop petite est très sensible au bruit ; une fenêtre trop grande lisse les mouvements et échoue près des contours des objets en mouvement (effet de débordement).
*   **Nombre de niveaux de pyramide (`maxLevel`)** :
    *   Dans VNStudio, ce paramètre correspond au champ **Pyramid Levels** ; en Python (OpenCV), il correspond à l'argument `maxLevel` dans `cv2.calcOpticalFlowPyrLK`.
    *   Ce paramètre (ex. : 3 ou 4) permet de construire des versions sous-échantillonnées de l'image. Le flot optique est d'abord calculé sur les petites images (pour capter les mouvements rapides de grande amplitude), puis affiné sur les images haute résolution. Si `maxLevel = 0`, le calcul n'utilise pas de pyramide et ne peut détecter que des mouvements de l'ordre de quelques pixels.
*   **Coefficient de lissage (`alpha` dans Horn-Schunck)** :
    *   Dans VNStudio, ce paramètre correspond au curseur **Alpha** ; en Python, il correspond au paramètre `alpha` dans les implémentations de Horn-Schunck.
    *   Règle le poids accordé à la régularité globale du champ de vecteurs par rapport à l'équation de contrainte locale. Une valeur de `alpha` élevée produit un champ de mouvement très lisse et continu, mais floute les frontières de mouvement entre un objet mobile et le fond.

### Dans VNStudio

Dans votre canvas :
`Webcam` ──> `Optical Flow` ──> `Flow Visualizer` ──> `Display`.

Le nœud `Flow Visualizer` traduit les composantes horizontal `u` et vertical `v` du flot optique (Farneback) en un code couleur HSV : la direction du mouvement est codée par la teinte (couleur) et la vitesse par la saturation. Un nœud aval peut router le champ brut (deux composantes par pixel) vers une analyse ultérieure via le port `flow` dédié.

**Exercice de dépannage :** L'exercice consiste à utiliser deux images successives présentant un mouvement rapide d'un objet (déplacement supérieur à 30 pixels). Brancher ces images à un nœud de flot optique éparse (comme **Lucas-Kanade Tracker**). Régler le paramètre **Pyramid Levels** sur `0` avec une **Window Size** de 7x7. Le lecteur observe dans l'inspecteur que le suivi décroche complètement et renvoie des vecteurs de mouvement nuls. Repasser le paramètre **Pyramid Levels** à `3`. Le lecteur constate que le suivi réussit immédiatement à capter le grand déplacement, illustrant ainsi l'apport crucial du schéma pyramidal pour la capture de mouvements à grande échelle.

---

## 9.5 — Flot épars ou dense : choisir selon le besoin

> *Suivre quelques points sûrs, ou cartographier tout le mouvement*

### L'intention

Les deux familles répondent à des questions différentes ; le choix dépend de ce qu'on cherche, pas d'une supériorité abstraite.

### La forme recherchée

```
ÉPARS (Lucas-Kanade sur coins de Shi-Tomasi)
  + rapide, robuste, fiable là où il répond
  + idéal pour le suivi de points (tracking, stabilisation, odométrie)
  − ne dit rien entre les points suivis

DENSE (Horn-Schunck, Farneback, RAFT)
  + une flèche par pixel, champ complet
  + idéal pour segmenter le mouvement, interpoler des images, les effets vidéo
  − plus coûteux ; sensible dans les zones ambiguës si α est mal réglé
```

La question n'est pas « lequel est meilleur ? » mais « ai-je besoin du mouvement partout, ou seulement de suivre des points fiables ? ». Un stabilisateur vidéo a besoin de quelques dizaines de flèches fiables pour estimer le mouvement de la caméra : Lucas-Kanade suffit. Analyser le déplacement d'une foule depuis une caméra aérienne demande un champ dense pour segmenter les flux : il faut une méthode dense.

Ensemble, les deux familles couvrent un large spectre : suivi d'objets et odométrie (robots, drones), stabilisation vidéo, compression vidéo (les vecteurs de mouvement de MPEG sont un flot épars par blocs), analyse de perfusion en IRM cardiaque, ralenti par interpolation d'images, reconnaissance d'actions, suivi de glaciers entre images satellite.

### Dans VNStudio

Canvas : `Webcam` → `Optical Flow (Lucas-Kanade)` → `Display`. La superposition dessine une flèche par point suivi et un point sur sa position de départ ; l'inspecteur résume le nombre de points suivis et leur déplacement moyen.

---

## Tableau récapitulatif — combler l'équation manquante

| Méthode | A priori ajouté | Densité | Condition de fiabilité | Usage type |
|---|---|---|---|---|
| Équation seule | constance de luminosité | — | jamais seule (1 éq., 2 inconnues) | base théorique |
| Lucas-Kanade | mouvement uniforme sur fenêtre | épars (coins) | coin (deux valeurs propres grandes) | suivi de points, odométrie, stabilisation |
| Horn-Schunck | champ globalement lisse | dense (tous pixels) | partout, par propagation | flot dense, segmentation de mouvement, IRM |
| Farneback | approximation locale par polynômes | dense | bonnes textures locales | flot dense rapide, effets vidéo |
| Réseaux (RAFT, PWC-Net) | régularités apprises sur corpus | dense | dépend du corpus d'entraînement | flot dense haute précision, benchmarks |

---

## Encadré final — comprendre une méthode, c'est connaître son pari

Le flot optique est l'exemple le plus transparent d'un **problème mal posé** : une équation par pixel pour deux inconnues par pixel. La formule est impitoyable, un contre deux, et aucun algorithme ne peut extraire deux inconnues d'une seule équation sans ajouter de l'information extérieure aux données. Cette information, c'est l'**a priori** : une hypothèse sur le monde, formulée avant d'avoir vu les images. Lucas-Kanade dit « le mouvement est localement rigide » ; Horn-Schunck « il varie doucement » ; RAFT « il ressemble à ce que j'ai vu dans des millions de scènes annotées ». Trois paris, et la qualité d'une méthode tient autant à la justesse de son pari qu'à celle de ses calculs.

Le schéma — données insuffisantes + a priori = solution déterminée — court dans tout le livre : un filtre (chapitre 5) est un a priori sur les fréquences du signal, une distance (chapitre 3) un a priori sur ce qui se ressemble, et la segmentation par coupe de graphe (chapitre 12) minimisera la même énergie « coller aux données + rester régulier » que Horn-Schunck. Le choix de l'a priori décide de ce que la méthode réussit et de ce qu'elle rate : un lissage global échoue aux frontières d'objets (un bras devant un mur), une rigidité locale échoue sur les déformations (un drapeau qui ondule), un a priori appris sur des scènes intérieures échoue sur des images satellite. Le chapitre 12 reprendra exactement cette énergie, appliquée cette fois à l'appartenance d'un pixel à une région.

---

## Figures à créer

| Identifiant | Section | Contenu | Format |
|---|---|---|---|
| `fig_ch9_couverture` | chapeau | Illustration : observateur regardant une barre oblique en mouvement par une fente étroite | JPG/PNG |
| `fig_ch9_01_ofce` | 9.1 | Bord en mouvement + gradient ; seule la composante perpendiculaire est mesurée | SVG |
| `fig_ch9_obs2_horn_schunck` | 9.4 | Déjà existant (PDF) : champ dense lisse, propagation depuis les coins | — |
| `fig_ch9_02_aperture` | 9.2 | Le judas : même image dans la fente pour plusieurs mouvements réels de la barre | SVG |
| `fig_ch9_03_pyramide` | 9.3 | Pyramide d'images : grand déplacement → petit déplacement au niveau grossier | SVG |
| `fig_ch9_04_epars_dense` | 9.5 | Côte à côte : flot épars (flèches sur coins) vs flot dense (carte couleur) | SVG |
