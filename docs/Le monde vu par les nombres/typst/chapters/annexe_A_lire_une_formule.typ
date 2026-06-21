#import "@preview/bookly:4.0.0": *

// --- Helpers locaux ---
#let subtitle(t) = block(above: 0.2em, below: 1.2em, sticky: true)[#text(style: "italic", fill: rgb("#64748b"))[#t]]

#let figA(path, w: 72%) = block(above: 1.8em, below: 1.8em, width: 100%)[
  #align(center)[#image("/figures annexe A/" + path, width: w)]
]

#let figAduo(pathL, pathR) = block(above: 1.8em, below: 1.8em, width: 100%)[
  #grid(columns: (1fr, 1fr), column-gutter: 1em,
    align(center)[#image("/figures annexe A/" + pathL, width: 100%)],
    align(center)[#image("/figures annexe A/" + pathR, width: 100%)]
  )
]

#chapter(title: [Lire une formule], toc: false)[

#pagebreak()
#block(above: 0em, below: 1em)[
  #grid(columns: (auto, 1fr), column-gutter: 0.6em, align: horizon,
    box(width: 3pt, height: 1.2em, fill: rgb("#c1002a"), radius: 1.5pt),
    text(weight: "bold", font: "Roboto", fill: rgb("#1e293b"))[Table des matières])
]
#suboutline(target: heading.where(outlined: true, level: 2))
#pagebreak()

#subtitle[Reconnaître une silhouette, c'est lire une intention — chaque composant encode une décision sur ce qui compte.]

Une formule de ce livre ne se déchiffre pas symbole par symbole, comme on épellerait un mot lettre à lettre. On la lit par *silhouettes* : un œil entraîné reconnaît d'un coup une exponentielle qui escompte, un carré qui pénalise, un cosinus qui mesure un alignement, et il sait aussitôt ce que la formule a décidé de faire. Cette annexe rassemble ces silhouettes. Pour chaque composant courant — le logarithme, la racine, le carré, l'exponentielle, le cosinus, le maximum, la division… — elle donne la courbe de référence, ce que le composant fait à une grandeur, les endroits du livre où il revient, et le piège qui l'accompagne.

Le fil conducteur prolonge celui de tout l'ouvrage : *chaque composant d'une formule encode une intention*. Choisir d'élever au carré, c'est déclarer que les grands écarts comptent démesurément ; prendre une valeur absolue, c'est déclarer que seule l'ampleur compte, pas le sens ; diviser, c'est déclarer que seule la proportion compte. Lire une formule, c'est donc lire une suite de ces déclarations.

== Comment se servir de cette annexe

Les entrées sont rangées non par ordre alphabétique mais *par intention* — comprimer, amplifier, aligner, sélectionner, mettre en proportion —, car c'est ainsi qu'on les choisit en pratique. Chaque entrée présente la courbe du composant directement dans le texte : regardez d'abord la forme, lisez ensuite la description pour ancrer ce que vous voyez, puis vérifiez sur le petit calcul proposé. Aucune entrée n'exige de connaissances mathématiques préalables.

---

== 1. Comprimer — ramener les grands écarts à l'échelle humaine

Ces trois composants prennent une grandeur qui peut être énorme, ou s'étaler sur plusieurs ordres de grandeur, et la rabattent vers une échelle maniable.

=== `log` — le compresseur d'échelles

```
log(1) = 0                                  le point de référence
log(10) = 1, log(100) = 2, log(1000) = 3   (base 10) : ×10 ajoute 1
log(a·b) = log(a) + log(b)                 un produit devient une somme
```

#figA("fig_A01_log.svg")

*La forme.* On lit « logarithme de x ». La courbe monte, mais de plus en plus lentement : passer de 1 à 10 fait gagner autant que passer de 10 à 100, ou de 100 à 1000. Chaque fois qu'on _multiplie_ l'entrée par dix, on _ajoute_ une marche à la sortie. Le logarithme transforme ainsi une échelle multiplicative en une échelle additive — exactement le mode de comptage de nos sens et de nos instruments.

*Ce qu'il fait à une grandeur.* Monter d'une octave en musique double la fréquence ; deux octaves la quadruplent ; trois la multiplient par huit. On _additionne_ les octaves quand les fréquences se _multiplient_. Le logarithme est la fonction qui fait ce pont : il convertit des facteurs en marches régulières. C'est pourquoi le décibel (son), le pH (acidité), l'échelle de Richter (séismes) sont tous logarithmiques — ils rendent comparables des grandeurs qui, brutes, s'étaleraient sur des milliards. Appliqué à une donnée, `log` écrase le haut de l'échelle et étire le bas, ce qui colle à notre perception : on distingue mieux deux sons faibles que deux sons assourdissants.

*Où, dans le livre.* L'entropie d'image et les descripteurs d'Haralick (chapitre 13), le PSNR avec son facteur `10·log₁₀` (chapitre 14), l'entropie croisée des fonctions de coût (chapitre 15), et la log-vraisemblance tapie derrière la distance de Mahalanobis (chapitre 3).

*Vérification chiffrée.* Le PSNR, avec une intensité maximale de 255 et une erreur quadratique moyenne de 25, vaut `10·log₁₀(255²/25) = 10·log₁₀(2601) ≈ 34,15 dB`. Surtout, _diviser l'erreur par deux_ ajoute toujours `10·log₁₀(2) ≈ 3,01 dB` : sur une échelle logarithmique, « +3 dB » se lit directement « deux fois moins d'erreur ».

*Le piège.* `log(0)` vaut moins l'infini : toute entropie ou entropie croisée doit ajouter un petit `ε` aux probabilités nulles, sous peine de produire `−inf`. Et la _base_ change le résultat d'un facteur constant — `log₂` compte en bits, `ln` (logarithme népérien) en nats, l'écart valant `ln 2 ≈ 0,693`. Toujours préciser la base employée.

=== `√` — l'adoucisseur qui rétablit l'unité

```
√0 = 0,  √1 = 1,  √4 = 2,  √9 = 3      monte, mais en se couchant
√(longueur²) = longueur                 défait un carré, rend l'unité d'origine
```

#figA("fig_A02_racine.svg")

*La forme.* On lit « racine carrée de x ». La courbe monte sans fin mais en s'aplatissant : pour _doubler_ la sortie, il faut _quadrupler_ l'entrée. C'est l'allure des rendements décroissants — chaque gain supplémentaire coûte de plus en plus cher.

*Ce qu'elle fait à une grandeur.* Sa fonction la plus utile n'est pas d'adoucir, mais de _rétablir une unité_. Un champ carré de 3 mètres de côté a une aire de 9 mètres carrés ; la racine de l'aire redonne le côté, en mètres. De même, la variance s'exprime dans le _carré_ de l'unité des données (des pixels carrés) — une quantité qu'on ne sait pas se représenter. En prendre la racine donne l'écart-type, dans la _même unité_ que les données : une dispersion qu'on peut enfin comparer aux mesures elles-mêmes.

*Où, dans le livre.* La norme L2 et la distance euclidienne (chapitre 3), la magnitude du gradient `√(Iₓ² + Iᵧ²)` (chapitre 6), et le passage de la variance à l'écart-type partout où l'on mesure une dispersion (chapitre 16).

*Vérification chiffrée.* Un gradient dont les composantes valent `Iₓ = 3` et `Iᵧ = 4` a pour magnitude `√(3² + 4²) = √25 = 5` : le théorème de Pythagore ramène deux variations perpendiculaires à une seule longueur.

*Le piège.* La racine d'un nombre négatif n'existe pas (elle produit `NaN`) : une variance calculée numériquement peut sortir très légèrement négative par arrondi — borner à zéro avant la racine. Par ailleurs, `√(Iₓ² + Iᵧ²)` présente un _coin_ non dérivable à l'origine ; on ajoute alors un petit `ε` sous la racine, `√(Iₓ² + Iᵧ² + ε)`.

=== `σ` — la sigmoïde, l'interrupteur en douceur

```
σ(x) = 1 / (1 + exp(−x))
σ(−∞) → 0,   σ(0) = 0,5,   σ(+∞) → 1       un « S » qui va de 0 à 1
σ(x) + σ(−x) = 1                            symétrique autour de 0
```

#figA("fig_A03_sigmoide.svg")

*La forme.* On lit « sigmoïde de x ». C'est un S allongé : tout en bas (loin à gauche) la sortie vaut presque 0, tout en haut (loin à droite) presque 1, et le passage est doux, centré sur 0 où la sortie vaut exactement la moitié.

*Ce qu'elle fait à une grandeur.* Un variateur de lumière ne saute pas brutalement d'éteint à allumé : il monte progressivement, et passé un certain point pousser encore le curseur ne change presque plus rien. La sigmoïde est ce variateur. Elle prend n'importe quel nombre, si grand ou si négatif soit-il, et le rabat dans l'intervalle 0–1 — un nombre qui se lit comme une _probabilité_ ou comme l'ouverture d'une _porte_. C'est la version _douce_ d'une marche tout-ou-rien (voir le seuil `1[·]`, §4).

*Où, dans le livre.* La sortie d'une décision binaire et les portes des réseaux de neurones (chapitre 15) ; c'est exactement le softmax à deux classes (§5) ; et c'est la version continue du seuil dur `s(x)` du Local Binary Pattern (chapitre 13).

*Vérification chiffrée.* `σ(2) = 1/(1 + e⁻²) ≈ 0,881` et `σ(−2) ≈ 0,119` : un score de +2 se lit « environ 88 % oui », un score de −2 « environ 12 % ». Leur somme vaut 1.

*Le piège.* Loin de 0, la courbe est presque plate : sa pente s'annule (à `σ = 0,99`, la pente ne vaut que `0,0099`). En apprentissage, cette saturation produit le fameux « gradient qui s'évanouit ».

---

== 2. Amplifier et séparer — creuser les différences

À l'opposé du groupe précédent, ces composants accentuent les écarts au lieu de les tasser.

=== Les puissances — `x²`, et au-delà

```
x²           une parabole : plate près de 0, de plus en plus raide ; (−x)² = x² (aveugle au signe)
xⁿ, n grand  sur [0,1] : reste près de 0, puis bondit vers 1 — creuse le contraste
```

#figAduo("fig_A04_Aarre.svg", "fig_A05_puissances.svg")

*La forme.* On lit « x au carré » (gauche), « x puissance n » (droite). Le carré est une cuvette symétrique : au fond, près de zéro, la courbe est presque plate — les petits écarts comptent à peine ; sur les flancs elle s'élève de plus en plus raide — les grands écarts comptent énormément. Le carré est _aveugle au signe_ : `(−3)²` et `3²` valent tous deux 9. Pour les puissances élevées (droite), sur l'intervalle 0–1, `xⁿ` reste collé à zéro puis bondit vers 1 — il creuse le contraste, façon « le gagnant rafle presque tout ».

*Ce qu'il fait à une grandeur.* Étirer un ressort de 2 cm demande quatre fois plus d'énergie que de l'étirer de 1 cm, pas deux fois : l'énergie suit le _carré_ de l'allongement. C'est le geste du carré — transformer un écart en un _coût_ qui punit les grands écarts hors de proportion, tout en ignorant leur direction. Ce choix est la fondation des moindres carrés : la dérivée de `x²` est `2x`, une simple droite, ce qui rend la minimisation linéaire — et la solution optimale est la _moyenne_.

*Où, dans le livre.* La distance L2, la variance et les moments (chapitres 2 et 3), l'erreur quadratique moyenne (chapitre 14), la partie « près de zéro » de Huber et du Smooth-L1 (chapitres 15 et 16), la variance inter-classe d'Otsu (chapitre 12) ; côté puissances élevées, l'exposant `γ` de la focal loss (chapitre 15) et le poids `(i−j)²` du contraste GLCM (chapitre 13).

*Vérification chiffrée.* Sur quatre erreurs `{1, 1, 1, 5}`, l'aberrant (le 5) pèse en valeur absolue `5/8 = 62 %` du total. Au carré, il pèse `25/28 = 89 %`. Le carré reporte presque tout le poids sur l'aberrant.

*Le piège.* Le carré _change l'unité_ (le carré d'une longueur est une aire) : il faut souvent reprendre une racine pour revenir à une grandeur lisible. Et il fait dominer les aberrants — il n'est pas robuste.

=== `exp(−·)` — le poids qui escompte, sans jamais s'annuler

```
exp(−x)                    part de 1, décroît, tend vers 0 sans l'atteindre ni passer négatif
exp(−x²)                   la cloche : sommet plat en 0, puis effondrement
exp(a + b) = exp(a)·exp(b) une somme dans l'exposant devient un produit au-dehors
```

#figAduo("fig_A06_exp.svg", "fig_A07_Aloche.svg")

*La forme.* À gauche, `exp(−x)` : une courbe qui descend de 1 vers 0 sans jamais y toucher, et sans jamais devenir négative. Chaque unité supplémentaire ne retranche pas une part fixe du poids : elle le multiplie par un même facteur (`1/e ≈ 0,37`). C'est l'arithmétique d'une demi-vie. À droite, `exp(−x²)` : la cloche, avec un plateau près de zéro — les petites valeurs sont à peine pénalisées — avant un effondrement brutal.

*Ce qu'elle fait à une grandeur.* Elle prend un coût, une distance, un score — potentiellement grand et sans borne — et le rabat en un poids positif entre 0 et 1. C'est l'outil standard pour transformer « loin = sans importance » en un nombre. Fait capital : l'identité `exp(a+b) = exp(a)·exp(b)` transforme une somme (dans l'exposant) en produit (au-dehors). Ce pont permet de séparer le filtre gaussien en deux passes 1D successives — la séparabilité du gaussien, raison pour laquelle un flou reste rapide même avec un grand noyau.

*Où, dans le livre.* Le noyau gaussien du filtrage (chapitre 5) et la fenêtre de pondération du tenseur de structure (chapitre 6) ; le softmax, la focal loss et l'InfoNCE (chapitre 15) ; la densité gaussienne derrière la distance de Mahalanobis (chapitre 3).

*Vérification chiffrée.* Sur le poids `exp(−x²/2σ²)` : à `x = σ`, poids `0,607` ; à `2σ`, `0,135` ; à `3σ`, `0,011`. Au-delà de quelques σ, le poids est nul pour le calcul — voilà le support quasi borné du flou gaussien.

*Le piège.* `exp` d'un grand argument déborde vers l'infini : tout softmax sérieux soustrait d'abord le maximum, `exp(zᵢ − max z)`, sans changer le résultat (astuce log-sum-exp). À l'autre bout, `exp(−grand)` tombe à zéro exact par underflow — gênant si l'on en reprend le logarithme.

---

== 3. Aligner — mesurer un accord de direction

Ces composants ne mesurent pas une quantité mais un _accord_ : à quel point deux directions pointent dans le même sens.

=== `cos` et `sin` — la boussole

```
cos(0°) = 1 (alignés)   cos(90°) = 0 (perpendiculaires)   cos(180°) = −1 (opposés)
cos et sin : une onde entre −1 et +1, de période 360° (l'angle « fait le tour »)
```

#figA("fig_A08_Aos_sin.svg")

*La forme.* On lit « cosinus », « sinus ». Le cosinus oscille entre −1 et +1 : il vaut 1 quand deux directions coïncident, 0 quand elles sont perpendiculaires, −1 quand elles s'opposent. Le sinus est la même onde décalée d'un quart de tour.

*Ce qu'ils font à une grandeur.* Plantez un bâton et éclairez-le bien à la verticale : l'ombre qu'il projette sur le sol est la plus longue quand il est couché dans la direction du sol, et nulle quand il est dressé tout droit. Le cosinus, c'est cette longueur d'ombre — quelle part d'une direction se couche le long d'une autre. Il mesure donc un _alignement_, ramené entre −1 et +1 quelles que soient les longueurs en jeu. Pris ensemble, sinus et cosinus rendent manipulable une grandeur _cyclique_ — un angle qui « fait le tour » — au moyen de deux nombres ordinaires.

*Où, dans le livre.* La similarité cosinus (chapitre 3), la transformée de Hough `ρ = x·cos θ + y·sin θ` (chapitre 10), les rotations et la projection caméra (chapitre 8), la base de la DCT (chapitre 10), l'orientation du gradient (chapitre 6).

*Vérification chiffrée.* Deux vecteurs `a = (1, 0)` et `b = (1, 1)` ont pour cosinus `(1·1 + 0·1) / (1 · √2) = 1/1,414 ≈ 0,707`, soit un angle de 45°. Pour `b = (−1, 0)`, le cosinus vaut −1 : directions opposées.

*Le piège.* Comme l'angle « fait le tour », `arctan` ne distingue pas `(x, y)` de `(−x, −y)` : il faut `arctan2` (voir entrée suivante). La similarité cosinus _ignore la longueur_ : deux vecteurs de même direction mais de tailles très différentes ont une similarité de 1.

=== Le produit scalaire `a·b` — l'accord brut

```
a·b = a₁b₁ + a₂b₂ + …      somme des produits terme à terme
a·b > 0 même sens,  = 0 perpendiculaires,  < 0 sens opposés
a·b = |a|·|b|·cos(angle)   → cos est le produit scalaire « normalisé »
```

#figA("fig_A09_produit_scalaire.svg")

*La forme.* On lit « a scalaire b ». C'est une somme de produits terme à terme. Positif si les deux vecteurs pointent dans des sens voisins, nul s'ils sont perpendiculaires, négatif s'ils s'opposent.

*Ce qu'il fait à une grandeur.* Pour pousser une charge, seule la part de la force _alignée_ sur le déplacement travaille ; la part perpendiculaire ne sert à rien. Le produit scalaire ne retient que cette part alignée — mais sans la normaliser : il porte à la fois l'accord de direction _et_ les longueurs. Divisez-le par les deux longueurs, et vous retombez sur le cosinus. Fait capital : la réponse de tout filtre linéaire est un produit scalaire entre le noyau et l'imagette qu'il recouvre.

*Où, dans le livre.* La réponse d'un filtre `= noyau · imagette` (chapitre 5), la similarité cosinus une fois normalisé (chapitre 3), toutes les projections.

*Vérification chiffrée.* Le noyau-gradient `(1, 0, −1)` appliqué à l'imagette `(10, 10, 40)` donne `1·10 + 0·10 − 1·40 = −30` : une forte transition (le bord) se lit comme un grand produit scalaire négatif. Un filtre « répond fort » là où l'image ressemble à son motif.

*Le piège.* Le produit scalaire grandit avec la longueur des vecteurs : il compare mal des vecteurs de tailles différentes, d'où la normalisation qui redonne le cosinus.

=== `arctan` et `arctan2` — de la direction vers l'angle

```
arctan(0) = 0°,   arctan(1) = 45°,   arctan(x) → 90° quand x → +∞
arctan ne voit que le rapport y/x  →  plage −90°…+90°  (perd le quadrant)
arctan2(y, x) lit les deux signes séparément  →  plage −180°…+180°  (angle complet)
```

*La forme.* On lit « arc-tangente ». Là où cosinus et sinus partent d'un angle pour donner une direction, l'arc-tangente fait le chemin _inverse_ : elle part d'une direction et rend l'angle. `arctan` prend une pente — un rapport « montée sur avancée » — et renvoie l'inclinaison correspondante : pente nulle → 0°, pente de 1 → 45°, pente infinie (vertical) → 90°.

*Ce qu'elles font à une grandeur.* Une girouette transforme la direction du vent en un cap lisible sur le cadran. Mais annoncer la pente d'une route — « elle monte d'un mètre pour un mètre parcouru » — ne dit pas si vous la montez ou la descendez. C'est l'angle mort de `arctan`, qui confond `(x, y)` et `(−x, −y)`. `arctan2(y, x)` écoute en plus _quel signe_ portent séparément `x` et `y` — donc dans quel quadrant — et rend l'angle complet de −180° à +180°.

*Où, dans le livre.* L'orientation du gradient `θ = arctan2(Iᵧ, Iₓ)` (chapitre 6), l'orientation de l'ellipse d'inertie `θ = ½·arctan2(2μ₁₁, μ₂₀ − μ₀₂)` (chapitre 2), la direction du flot optique (chapitre 9), la phase d'une réponse de Fourier ou de Gabor (chapitre 10).

*Vérification chiffrée.* Un gradient `(Iₓ, Iᵧ) = (1, 1)` pointe à `arctan2(1, 1) = 45°`. Le gradient opposé `(−1, −1)` a le même rapport `y/x = 1`, donc `arctan(1) = 45°` à nouveau — faux. `arctan2(−1, −1) = −135°` rétablit le bon quadrant.

*Le piège.* L'ordre des arguments est `arctan2(y, x)` — l'ordonnée d'abord : l'inverser fait pivoter tous les angles de 90°. La convention d'axe image (l'axe `y` pointe vers le _bas_) inverse le signe de l'angle par rapport au repère mathématique usuel. Enfin, les angles « font le tour » : un écart entre angles se prend modulo 360°.

---

== 4. Sélectionner et trancher — choisir sans compromis

Ici, plus de moyenne pondérée : on choisit, on replie, on décide.

=== `max` / `min` — le sélecteur

```
max(5, 2, 8) = 8        min(5, 2, 8) = 2
on retient une valeur, on jette les autres — aucune moyenne
```

#figA("fig_A10_max_min.svg")

*La forme.* On lit « maximum », « minimum ». Ce n'est pas une courbe lisse mais un _choix_ : la sortie est l'une des entrées — la plus grande, ou la plus petite — et toutes les autres sont purement ignorées.

*Ce qu'ils font à une grandeur.* L'eau qui s'écoule trouve le point le plus bas ; le podium ne photographie que le vainqueur. Min et max _sélectionnent_ au lieu de mélanger. Ils remplacent la grammaire « pondérer puis sommer » des filtres par une grammaire fondée sur l'_ordre_ — celle de la morphologie (chapitre 11). Une seule valeur extrême décide de tout : tranchants, mais fragiles.

*Où, dans le livre.* La morphologie — l'érosion est un min, la dilatation un max (chapitre 11) ; le max-pooling ; la distance de Hausdorff, un max de plus-proches-distances (chapitre 3) ; la suppression des non-maxima en détection (chapitre 4). Le softmax en est le cousin _doux_ (§5).

*Vérification chiffrée.* Une érosion 1D du signal `(5, 2, 8)` par une sonde de largeur 3 renvoie le min, `2`. La dilatation renvoie le max, `8`. Et la distance de Hausdorff : un seul point éloigné fixe à lui seul la valeur — d'où sa fragilité aux aberrants.

*Le piège.* `max` et `min` sont discontinus et non dérivables : on ne peut pas les optimiser directement par descente de gradient, d'où les substituts « doux » (softmax, soft-min). Et comme un seul point extrême domine, ils sont fragiles à une valeur aberrante isolée.

=== La valeur absolue `|·|` — la distance sans direction

```
|3| = 3    |−3| = 3       un « V » : on replie le négatif sur le positif
coin pointu en 0
```

#figA("fig_A11_valeur_absolue.svg")

*La forme.* On lit « valeur absolue de x ». C'est un V : la branche négative est repliée sur la positive. Seule l'ampleur subsiste, avec un coin pointu en zéro.

*Ce qu'elle fait à une grandeur.* Un compteur kilométrique compte les kilomètres parcourus, que vous rouliez en avant ou en marche arrière : seule la quantité de route compte, pas le sens. La valeur absolue transforme de même un écart _signé_ en une simple ampleur. Une somme de telles ampleurs — la norme L1 — pénalise les erreurs _proportionnellement_ (et non hors de proportion comme le carré) : elle est donc plus robuste aux aberrants, et favorise des solutions parcimonieuses, proches de la médiane.

*Où, dans le livre.* La distance L1 / Manhattan (chapitre 3), l'erreur absolue moyenne, la partie « loin de zéro » de Huber et du Smooth-L1 (chapitres 15 et 16), la médiane qui minimise `Σ|écart|` (lien avec la MAD, chapitre 16), l'homogénéité GLCM `1/(1+|i−j|)` (chapitre 13).

*Vérification chiffrée.* Sur les erreurs `{1, 1, 1, 5}` : en valeur absolue, l'aberrant pèse `5/8 = 62 %` du total, contre `89 %` au carré. La valeur absolue laisse l'aberrant peser bien moins — c'est la racine de la robustesse de la norme L1.

*Le piège.* Le coin en zéro rend la fonction non dérivable à l'origine ; le Smooth-L1 arrondit précisément ce coin pour récupérer un gradient propre (lien chapitre 15). Et, aveugle au signe, la valeur absolue ne distingue pas une surestimation d'une sous-estimation.

=== L'indicatrice / le seuil `1[·]` — le juge binaire

```
1[x ≥ t] = 1 si x ≥ t, sinon 0      une marche : pas d'entre-deux
```

#figA("fig_A12_seuil.svg")

*La forme.* On lit « un, si la condition est vraie ». C'est une marche : 0 en deçà du seuil, 1 au-delà. La décision la plus tranchée qui soit — aucun entre-deux.

*Ce qu'elle fait à une grandeur.* Le portique d'un manège mesure votre taille face à une barre : ou vous êtes assez grand, ou vous ne l'êtes pas ; un millimètre décide, et dépasser largement la barre ne compte pas plus que la dépasser de justesse. L'indicatrice transforme de même une grandeur continue en un _oui/non_. C'est la brique de base de la binarisation et du comptage — au prix d'oublier, par construction, _de combien_ on dépasse.

*Où, dans le livre.* Le seuillage et la binarisation (chapitre 12, où Otsu choisit _où_ placer la marche), le `s(x) = 1 si x ≥ 0` du LBP (chapitre 13), le comptage des vrais/faux positifs via un seuil d'IoU (chapitre 4) ; un masque n'est rien d'autre que l'indicatrice d'appartenance à une région.

*Vérification chiffrée.* Un seuil `t = 128` appliqué aux pixels `(120, 130, 250)` donne `(0, 1, 1)`. Notez que 130 et 250 deviennent identiques — la marche oublie l'écart au seuil.

*Le piège.* Près d'une frontière bruitée, un pixel qui oscille entre 127 et 129 fait _clignoter_ la sortie ; la sigmoïde est le remplaçant doux et dérivable (§1). Et, l'indicatrice jetant toute l'information d'amplitude, le choix du seuil décide de tout.

---

== 5. Mettre en proportion — rendre les choses comparables

Ces composants ne mesurent pas une grandeur isolée : ils la rapportent à une référence.

=== La division / le rapport — la mise en proportion

```
a / b : « combien de b dans a ? »         on ramène a à une référence b
un rapport de deux grandeurs de même unité est sans dimension (sans unité)
```

#figA("fig_A13_division.svg")

*La forme.* On lit « a divisé par b ». La division compare une grandeur à une référence ; quand les deux ont la même unité, le résultat n'a plus d'unité du tout — il est _sans dimension_.

*Ce qu'elle fait à une grandeur.* Un prix au kilo, une moyenne au bâton, un taux de change : le nombre brut ne dit rien tant qu'on ne l'a pas divisé par une référence pour le rendre comparable. La division retire ainsi une échelle ou une unité, transforme des effectifs en proportions, des coûts en taux. Beaucoup de descripteurs de forme sont des rapports _justement_ pour devenir insensibles à la taille (chapitre 1).

*Où, dans le livre.* La circularité, la solidité, l'étendue (chapitre 1, tous des rapports), l'IoU (chapitre 4), la précision et le rappel (chapitre 4), l'histogramme normalisé en probabilités, le coefficient de corrélation.

*Vérification chiffrée.* La circularité vaut `4π·A / P²`. Pour un disque de rayon `r` : `A = π r²` et `P = 2π r`, donc `4π · π r² / (2π r)² = 1`. Le rayon se simplifie : la mesure ne dépend pas de la taille et vaut 1 pour le disque parfait.

*Le piège.* Une division par zéro, ou par presque-zéro, explose : sur une région minuscule ou vide, circularité et IoU deviennent indéfinies — on ajoute un `ε` ou un garde-fou. Et un rapport _cache les tailles absolues_ : une cellule minuscule et une cellule énorme peuvent partager la même circularité de 1.

=== `softmax` — le partage proportionnel

```
softmax(z)ᵢ = exp(zᵢ) / Σⱼ exp(zⱼ)
des scores quelconques → des nombres positifs qui somment à 1 (des probabilités)
```

#figA("fig_A14_softmax.svg")

*La forme.* On lit « softmax ». Il prend une liste de scores, en exponentie chacun, puis divise par le total. La sortie : des nombres positifs qui somment à 1 — une distribution de probabilités. Le plus grand score reçoit la part du lion, mais aucun ne reçoit zéro.

*Ce qu'il fait à une grandeur.* Partager une cagnotte au prorata de la réputation de chacun : non pas « le gagnant rafle tout » (ce serait le `max`, §4), mais le favori emporte la plus grosse part. Une élection _douce_. Le softmax assemble deux silhouettes déjà vues — l'exponentielle (pour rendre positif et écarter les scores en _rapports_) et la division (pour normaliser à 1).

*Où, dans le livre.* La classification (chapitre 15), l'attention, l'InfoNCE de CLIP et SimCLR (chapitre 15) ; cousin doux du `max` (§4).

*Vérification chiffrée.* Pour les scores `(2, 1, 0)` : les exponentielles valent `(7,39 ; 2,72 ; 1,00)`, de somme `11,11` ; les probabilités sont donc `(0,665 ; 0,245 ; 0,090)`. L'écart _additif_ de 1 entre les deux premiers scores ressort en un _rapport_ de probabilités `7,39 / 2,72 = 2,72 = e`.

*Le piège.* Des scores grands font déborder l'exponentielle ; on soustrait d'abord le maximum, `exp(zᵢ − max z)`, sans changer le résultat (astuce log-sum-exp). La « température » `τ` — diviser les scores par `τ` avant le softmax — durcit ou adoucit le partage : `τ` petit tend vers le `max` dur, `τ` grand vers le partage uniforme.

---

== Tableau récapitulatif

#table(
  columns: (auto, auto, 1fr, 1fr),
  [*Composant*], [*Silhouette*], [*Ce qu'il fait*], [*Où il revient*],
  [`log`], [compresse], [un produit devient une somme ; colle à la perception], [entropie, PSNR, entropie croisée],
  [`√`], [rétablit l'unité], [ramène une « aire » à une « longueur »], [norme L2, écart-type, magnitude gradient],
  [`σ`], [interrupteur doux], [rabat tout réel dans 0–1, lu comme une probabilité], [sorties binaires, softmax 2 classes],
  [`x²`, `xⁿ`], [amplifie les écarts], [punit les grands écarts hors de proportion, aveugle au signe], [L2, MSE, variance, moments, focal loss],
  [`exp(−·)`], [escompte], [additif → multiplicatif ; distance → poids du proche], [gaussien, softmax, RBF, Mahalanobis],
  [`cos`, `sin`], [boussole], [mesure un alignement entre directions, gère le cyclique], [similarité cosinus, Hough, rotations],
  [`a·b`], [accord brut], [part alignée, longueurs comprises ; normalisé → cos], [réponse de filtre, projections],
  [`arctan2`], [direction → angle], [retrouve l'angle, quadrant compris], [orientation du gradient et des formes, flot],
  [`max` / `min`], [sélecteur], [retient un extrême, jette le reste ; dur, fragile], [morphologie, Hausdorff, NMS],
  [`|·|`], [ampleur sans signe], [écart signé → ampleur ; pénalité proportionnelle, robuste], [L1, MAE, Huber, médiane],
  [`1[·]`], [juge binaire], [grandeur continue → oui/non ; oublie l'amplitude], [seuillage, LBP, comptage VP/FP],
  [`a / b`], [mise en proportion], [retire une échelle/unité ; rend comparable], [circularité, IoU, précision/rappel],
  [`softmax`], [partage proportionnel], [scores → probabilités (exp puis division)], [classification, attention, InfoNCE],
)

---

== Lire un symbole, c'est lire une décision

L'introduction promettait qu'aucune formule de ce livre n'est un sortilège, et que derrière chaque symbole se cache une image qu'on peut dessiner sur un coin de table. Cette annexe en a donné le vocabulaire. Ces composants sont l'alphabet ; les chapitres en font des phrases.

Reste une remarque qui referme le fil de tout l'ouvrage. Chacun de ces composants est lui-même un choix sur ce qui compte. Le carré déclare que les grands écarts comptent par-dessus tout ; la valeur absolue, que seule l'ampleur compte, pas le sens ; le cosinus, que seule la direction compte, pas la longueur ; la division, que seule la proportion compte, pas la taille. Le maximum refuse le compromis ; la sigmoïde le réintroduit. Jusque dans le moindre symbole, donc, la loi du livre tient : _choisir, c'est déclarer ce qui compte_. Quand vous lirez le recueil qui suit, ne lisez pas des suites de signes — lisez, à chaque symbole, la décision qu'il encode.

]
