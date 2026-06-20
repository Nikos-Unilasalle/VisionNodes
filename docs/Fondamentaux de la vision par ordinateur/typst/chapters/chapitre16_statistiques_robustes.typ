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


#chapter(title: [Statistiques robustes], toc: false)[

#block(above: 0pt, below: 2em, width: 100%)[#image("/illustrations/chap16.jpeg", width: 100%)]

#pagebreak()
#block(above: 0em, below: 1em)[
  #grid(columns: (auto, 1fr), column-gutter: 0.6em, align: horizon,
    box(width: 3pt, height: 1.2em, fill: rgb("#c1002a"), radius: 1.5pt),
    text(weight: "bold", font: "Roboto", fill: rgb("#1e293b"))[Table des matières])
]
#suboutline(target: heading.where(outlined: true, level: 2))
#pagebreak()

#subtitle[Une seule donnée folle peut détruire une mesure juste pour mille autres. Être robuste, c'est décider à l'avance combien de poids une observation a le droit de prendre — et refuser de croire l'aberration.]

La vision par ordinateur produit des données truffées d'aberrations : appariements faux entre deux images, pixels saturés ou morts, occlusions partielles, annotations imprécises, reflets qui font briller un point là où il n'y a rien. Or les outils classiques — la moyenne, les moindres carrés — accordent à chaque observation une influence *non bornée* : une seule valeur aberrante peut emporter l'estimation arbitrairement loin. Un faux appariement dans une homographie, un pixel brûlé dans une mesure de dispersion, un point 3D mal reconstruit dans un bundle adjustment — une donnée corrompue peut détruire un résultat juste pour les quatre-vingt-dix-neuf autres.

Les statistiques robustes refondent l'estimation autour d'une question de *confiance* : combien de poids accorder à une observation selon qu'elle est plausible ou suspecte ? Le fil du chapitre tient en une phrase : *être robuste, c'est borner l'influence d'une donnée.* L'outil pour lire cette influence est la *fonction d'influence* ψ, qui quantifie combien un résidu de taille e pèse sur le résultat final. Les estimateurs s'ordonnent alors sur un spectre : influence *non bornée* (moyenne), *bornée constante* (médiane), *écrêtée* (Huber), *redescendante vers zéro* (Tukey), puis *binaire* — gardée ou jetée (RANSAC). À chaque section, la même question : jusqu'où une seule donnée a-t-elle le droit de déplacer le résultat ?

Les statistiques robustes traversent tout le livre et en révèlent la face « méfiance ». La moyenne minimise la distance L2, la médiane la L1 (chapitre 3) : le choix L1/L2 est déjà le choix non-robuste / robuste. Le filtre médian (chapitre 5) est un estimateur robuste appliqué localement — d'où son effacement du bruit poivre-et-sel. RANSAC estime homographie et matrice fondamentale au milieu d'appariements faux (chapitre 8). Et le lien avec le chapitre 15 est exact, pas analogique : la fonction d'influence ψ *est* la dérivée du coût ρ, c'est-à-dire le gradient. Là où le chapitre 15 demandait _où le gradient sature ou explose_, ce chapitre demande _où l'influence d'une donnée est bornée_ — la même dérivée, lue dans l'autre sens.

=== Un peu de vocabulaire avant de commencer

- *Estimateur* : Une formule statistique calculant une grandeur recherchée (comme la moyenne ou la variance) à partir d'un échantillon de pixels.
- *Donnée aberrante (outlier)* : Une valeur extrême qui ne suit pas le modèle général (bruit impulsionnel, mauvaise mesure).
- *Point de rupture (breakdown point)* : La proportion maximale de données aberrantes qu'un estimateur peut tolérer avant de produire une valeur aberrante.

---

// ============================================================

== Médiane et point de rupture : la robustesse comme influence bornée

#subtitle[Un capteur fou tire sur la moyenne de tout son poids ; sur la médiane, d'un seul cran]

#figfull("/figures/fig_ch16_obs1_median.svg")

#figfull("/figures/fig_ch16_obs1_median.svg")

=== L'intention
On veut résumer un échantillon par un point central qui ne se laisse pas emporter par une valeur folle. La moyenne échoue à cette tâche ; on cherche un estimateur dont une donnée aberrante ne puisse pas détourner le résultat.

=== La forme recherchée
La différence se lit dans le poids accordé à un écart. La moyenne minimise la somme des écarts *au carré* (L2) : un grand écart domine tout, et son influence croît sans limite avec sa distance. La médiane minimise la somme des écarts *absolus* (L1) : près de l'optimum, chaque point ne pèse que par son *signe* — au-dessus ou en dessous. Sa dérivée s'annule quand il y a autant de points d'un côté que de l'autre, ce qui est précisément la valeur centrale. Un outlier à 1000 unités de la médiane tire donc autant qu'un point à 1 unité : par son côté, jamais par son amplitude.

#info-box(title: "La formule")[
```
moyenne :  μ̂ = argmin_m Σᵢ (xᵢ − m)²     (minimise L2)
médiane :  m̂ = argmin_m Σᵢ |xᵢ − m|      (minimise L1)
```
]

Deux notions chiffrent la robustesse. Le *point de rupture* est la fraction de données qu'on peut corrompre avant que l'estimation parte à l'infini : 1/n → 0 % pour la moyenne (un seul point suffit), 50 % pour la médiane (il faut corrompre plus de la moitié de l'échantillon). La *fonction d'influence* ψ mesure l'effet d'ajouter une observation en x — l'image du levier : combien la balance bascule quand on pose un poids en x. Pour la moyenne, ψ(x) = x − μ, non bornée ; pour la médiane, ψ(x) ∝ sign(x − m), bornée. Borner ψ, c'est être robuste. ∎

#question-box(title: "Exemple")[
Cinq mesures d'un capteur de distance (cm), dont la dernière déraille sur un reflet :

```
propre :    x = [2, 3, 5, 7, 8]          moyenne = 5,0     médiane = 5
corrompu :  x = [2, 3, 5, 7, 800]        moyenne = 163,4   médiane = 5
            (1 outlier sur 5 = 20 % < seuil 50 %)
```

Un seul point aberrant déplace la moyenne de 5 à 163 — elle est détruite. La médiane ne bouge pas : tant que les outliers restent minoritaires, ils ne peuvent franchir le centre. L'influence de la médiane est bornée — le capteur fou ne tire qu'avec le poids de son signe, jamais proportionnellement à ses 800 cm d'écart.
]

=== Son angle mort — l'efficacité sur données propres
En ne lisant que le signe, la médiane jette de l'information utile quand les données sont propres : la moyenne est alors plus _efficace_ (de plus faible variance). Et sa fonction d'influence en escalier (`sign`) est discontinue en zéro — un défaut numérique que Huber corrige au §16.3 en arrondissant ce coude.

#info-box(title: "Subtilité — nombre pair et égalité de valeurs")[
La médiane d'un nombre *pair* d'éléments est, par convention, la moyenne des deux centraux : elle redevient localement sensible à ces deux valeurs. Sur des données entières (intensités 8 bits), elle peut renvoyer une demi-valeur. Et elle n'est ni la moyenne tronquée, ni le mode — à ne pas confondre quand un outil parle de « valeur centrale ».
]

#canvas[
Canvas : `Scalar List` → `Robust Location` → `Inspector`. Le nœud affiche moyenne et médiane côte à côte, plus l'influence de la dernière valeur sur chacune. Pousser un échantillon vers une valeur folle montre la moyenne dériver pendant que la médiane reste plantée.

---
]

// ============================================================

== MAD : l'échelle robuste qui définit l'aberration

#subtitle[Avant de dire qu'une mesure est « loin », il faut un mètre que l'aberration ne tord pas]

#figfull("/nvlle illu/A_humorous,_highly_stylized_line-art_202606191414.jpeg")

=== L'intention
Pour borner une influence « à ±k », encore faut-il savoir ce que k signifie en unités de bruit. L'écart-type classique serait le mètre-étalon naturel, mais il est lui-même détruit par un seul outlier (il contient une somme de carrés). On veut une mesure de dispersion que l'aberration ne puisse pas gonfler.

=== La forme recherchée
On applique l'idée de la médiane à la dispersion elle-même : la *MAD* (_median absolute deviation_) est la médiane des écarts absolus à la médiane — une double médiane, donc aussi robuste qu'elle (point de rupture 50 %). Brute, elle sous-estime l'écart-type d'une loi normale ; on la recalibre par un facteur fixe pour qu'elle l'estime fidèlement. Ce facteur, 1,4826, vient de la statistique de la loi normale (l'inverse du quartile à 75 %) ; il n'a pas à être retenu, seulement appliqué.

#info-box(title: "La formule")[
```
MAD = médiane(|xᵢ − médiane(x)|)
σ̂  = 1,4826 · MAD
```
]

L'influence de la MAD est bornée : une aberration ne peut pas gonfler l'échelle estimée au-delà d'un plafond. C'est ce qui la rend indispensable pour paramétrer Huber (§16.3) et le seuil d'inlier de RANSAC (§16.5) : sans mètre-étalon robuste, « borner l'influence à ±k » n'a pas de sens, car k doit s'exprimer en unités de bruit, pas en pixels bruts. ∎

#question-box(title: "Exemple")[
Les deux échantillons du §16.1 :

```
propre :    x = [2, 3, 5, 7, 8],   médiane = 5
            écarts |x−5| triés [0, 2, 2, 3, 3]  → MAD = 2,  σ̂ = 2,97
            (écart-type classique : 2,55)

corrompu :  x = [2, 3, 5, 7, 800], médiane = 5
            écarts |x−5| triés [0, 2, 2, 3, 795] → MAD = 2,  σ̂ = 2,97
            (écart-type classique : 356)
```

L'échelle robuste ne bouge pas (2,97 → 2,97) là où l'écart-type classique explose de 2,55 à 356. On peut alors *détecter* l'outlier par un score z modifié `z = 0,6745·(x − médiane)/MAD`, signalé au-delà de 3,5 :

```
pour x = 800 :  z = 0,6745 · (800 − 5) / 2 = 268   ≫ 3,5   → aberration flagrante
```
]

#warning-box(title: "Piège — MAD nulle")[
Dès que plus de la moitié des valeurs coïncident — cas fréquent en vision : capteur saturé (majorité de pixels à 255), zone uniforme, données quantifiées —, la MAD vaut 0 et la division par elle produit des valeurs infinies, un résultat faux et silencieux. La parade ajoute un petit terme de garde, ou bascule sur une autre échelle robuste (écart interquartile). Autre écart : certaines bibliothèques renvoient la MAD brute, d'autres la version calibrée par 1,4826 — comparer des seuils issus des deux conventions introduit un facteur ~1,48 d'erreur.
]

#canvas[
Canvas : `Scalar List` → `MAD Scale` → `Inspector`. Le nœud sort la médiane, la MAD, l'échelle calibrée σ̂ et les scores z modifiés, avec un drapeau d'aberration par valeur. L'aberration à 800 ressort à |z| = 268, bien au-delà du seuil 3,5.

---
]

// ============================================================

== M-estimateurs : de Huber à Tukey, doser l'influence

#subtitle[Jusqu'à quelle distance un résidu a-t-il le droit de tirer sur l'estimation]

#figfull("/figures/fig_ch16_obs2_mestimators.svg")

#figfull("/figures/fig_ch16_obs2_mestimators.svg")

=== L'intention
La médiane est robuste mais grossière (elle ne lit que des signes) ; les moindres carrés sont précis mais fragiles (influence non bornée). On veut un réglage continu entre les deux : précis près de la cible, robuste au loin, et avec un curseur pour décider _à partir d'où_ on se méfie.

=== La forme recherchée
Un M-estimateur remplace le coût au carré des moindres carrés par une fonction ρ dont la dérivée ψ — la fonction d'influence — plafonne ou redescend. L'image du bras de fer : jusqu'à quelle distance un adversaire a-t-il le droit de tirer ?

- *Huber* : ψ vaut e tant que le résidu est petit (régime moindres carrés, précis), puis se *fige à ±k*. Un résidu énorme ne tire plus que d'une force constante : influence *bornée mais non nulle*, l'outlier est atténué, pas rejeté. C'est exactement le smooth L1 du chapitre 15.
- *Tukey* (biweight) : ψ monte, culmine, puis *redescend à zéro* au-delà de son seuil. Un outlier franc reçoit une influence _strictement nulle_ — il disparaît de l'équation.

La différence cruciale est entre ψ *monotone* (Huber, qui plafonne) et ψ *redescendante* (Tukey, qui rejette).

#info-box(title: "La formule")[
```
estimation :  θ̂ = argmin_θ  Σᵢ ρ(eᵢ / σ̂)        eᵢ = résidu, σ̂ = MAD (§16.2)
influence  :  ψ = ρ′

Huber :  ψ(e) = e            si |e| ≤ k        Tukey :  ψ(e) = e(1−(e/k)²)²  si |e| ≤ k
                k·sign(e)    sinon                            0               sinon
```
]

Le spectre complet de l'influence se lit alors d'un coup :

#info-box(title: "La formule")[
```
MCO        → ψ(e) = e          non bornée, un outlier emporte tout
médiane/L1 → ψ = sign(e)       bornée constante, compte les côtés
Huber      → ψ écrêtée à ±k     bornée et monotone, atténue sans rejeter
Tukey      → ψ redescend à 0    influence annulée au-delà du seuil, rejette franchement
```
]

Les seuils `k = 1,345·σ̂` (Huber) et `c = 4,685·σ̂` (Tukey) donnent tous deux *95 % d'efficacité* sous bruit gaussien : on ne perd que 5 % de précision sur données propres, tout en gagnant la robustesse. ∎

#question-box(title: "Exemple")[
Quatre résidus d'un ajustement de profil en imagerie industrielle, dont un aberrant (éclat de métal), seuil k = 2 :

```
résidu e   ψ_MCO (=e)   ψ_Huber (écrêté ±2)   ψ_Tukey (k=2)
  0,5         0,5             0,5                0,439
 −0,8        −0,8            −0,8               −0,564
  0,3         0,3             0,3                0,287
  6,0 (★)     6,0             2,0                0,000
```

L'outlier (★) pèse 6,0 en moindres carrés — il dicte l'ajustement. Huber rabote son influence à 2,0, du même ordre que les résidus sains. Tukey l'annule : 6,0 dépasse le seuil, donc ψ = 0, l'éclat disparaît de l'équation. C'est le mécanisme d'un ajustement de matrice fondamentale ou d'un bundle adjustment robustes (chapitre 8) : un faux appariement ne fausse plus la géométrie estimée.
]

#info-box(title: "Réglage — le seuil en unités de bruit, et l'initialisation de Tukey")[
Le seuil k s'exprime en unités de σ̂ (recalculé par la MAD à chaque problème), jamais en pixels fixes : k = 2 px est lâche sur une image bruitée, strict sur une image propre. Le coût de Tukey étant non convexe (il a des minima locaux), on ne l'initialise jamais par les moindres carrés (déjà tirés par l'outlier) : on part de la médiane ou d'un ajustement L1.
]

#canvas[
Canvas : `Residuals` → `M-Estimator` → `Inspector`. Le nœud expose le choix du noyau (Huber, Tukey), le seuil en unités de σ̂, et trace la fonction d'influence ψ : on voit la branche de Huber se figer à ±k, celle de Tukey redescendre vers zéro.

---
]

// ============================================================

== IRLS : comment on résout un M-estimateur en pratique

#subtitle[Une négociation où l'on baisse le micro de qui parle trop fort, tour après tour]

=== L'intention
Un M-estimateur n'a pas de solution explicite : sa fonction d'influence est non linéaire. On veut une méthode de résolution qui réutilise l'outil le plus simple qu'on ait — les moindres carrés — en boucle.

=== La forme recherchée
L'astuce : transformer l'influence en un *poids*. On écrit ψ(e) = w(e)·e, ce qui ramène l'équation à des moindres carrés *pondérés* par les wᵢ. Comme les poids dépendent des résidus, donc de la solution, on itère : ajustement pondéré → nouveaux résidus → nouveaux poids → … L'image d'une négociation : au premier tour tout le monde parle à égalité ; après chaque round, celui dont la voix paraît trop extrême voit son micro baissé ; on répète jusqu'à ce que les voix restantes s'accordent. C'est l'IRLS (_iteratively reweighted least squares_).

#info-box(title: "La formule")[
```
poids :  wᵢ = ψ(eᵢ) / eᵢ
itérer : θ ← argmin_θ Σᵢ wᵢ · eᵢ(θ)²

Huber :  w(e) = 1       si |e| ≤ k       Tukey :  w(e) = (1−(e/k)²)²  si |e| ≤ k
                k/|e|   sinon                            0              sinon
```
]

Huber dégrade le poids des grands résidus comme 1/|e| (jamais à zéro) ; Tukey le met à zéro au-delà du seuil. Un ajustement robuste n'est donc qu'un moindres carrés où les outliers sont progressivement éteints par leur propre influence bornée. ∎

#question-box(title: "Exemple")[
Estimer une profondeur en reconstruction 3D à partir de y = \[10,0 ; 10,2 ; 9,8 ; 25,0\], dont *25,0* est aberrant (mauvaise triangulation sur un fond spéculaire) :

```
moindres carrés (moyenne) : θ = 13,75                ← tiré vers le haut par 25,0
init médiane              : θ₀ = 10,1
résidus                   : e = [−0,1 ; 0,1 ; −0,3 ; 14,9]
échelle (MAD)             : σ̂ = 0,297
poids Tukey (c = 4,685)   : w ≈ [0,99 ; 0,99 ; 0,91 ; 0,00]   ← 25,0 reçoit le poids 0
ajustement pondéré        : θ₁ ≈ 10,01
```

Les moindres carrés donnent 13,75 (faux) ; une seule passe d'IRLS, en annulant le poids de l'outlier, ramène l'estimation à 10,01 — la vraie profondeur. Les itérations suivantes ne bougent plus : l'aberration est définitivement éteinte.
]

#info-box(title: "Subtilité — division par zéro et ré-estimation de l'échelle")[
La division par e dans w = ψ(e)/e explose pour les résidus quasi nuls : on protège par un terme de garde, ou on utilise directement les formes fermées de w (qui valent 1 près de zéro). On ré-estime σ̂ *avant* les poids à chaque tour, sinon une échelle mal initialisée fausse tout. Et on borne le nombre d'itérations : avec Tukey, un point au bord du seuil qui entre et sort à chaque passe peut empêcher la stabilisation.
]

#canvas[
Canvas : `Data Points` → `IRLS Fit` → `Inspector`. Le nœud part d'une initialisation par la médiane, itère la repondération (noyau et seuil au choix) et affiche l'estimation robuste face à celle des moindres carrés, plus la carte des poids finaux — l'outlier ressort avec un poids nul.

---
]

// ============================================================

== RANSAC : la robustesse par consensus

#subtitle[Tirer un petit jury au sort, lui demander une version des faits, compter qui la confirme]

#figfull("/figures/fig_ch16_obs3_ransac.svg")

#figfull("/figures/fig_ch16_obs3_ransac.svg")

=== L'intention
Quand les outliers sont nombreux — la moitié des appariements entre deux images peuvent être faux —, même les M-estimateurs cèdent. On veut une méthode qui tolère une *majorité* de données corrompues, en les excluant carrément plutôt qu'en les atténuant.

=== La forme recherchée
Pour comprendre cette approche, on imagine une assemblée de 100 témoins réunis dans une pièce pour reconstituer un événement (par exemple, déterminer la position exacte d'une ligne d'horizon). La difficulté est majeure : 60 % de ces témoins sont des menteurs pathologiques (les données aberrantes ou _outliers_) qui racontent n'importe quoi au hasard, tandis que les 40 % restants sont des citoyens honnêtes (les données valides ou _inliers_) qui disent la vérité à un petit bruit de mesure près.

Si on tente de faire la moyenne de tous les témoignages (comme dans la méthode des moindres carrés), les mensonges farfelus vont complètement fausser le résultat. Même les M-estimateurs risquent de faillir, car la majorité silencieuse est ici composée de menteurs.

L'algorithme RANSAC (pour _Random Sample Consensus_) résout le problème par un vote démocratique basé sur le consensus, en procédant ainsi :

+ *Le tirage d'un micro-jury* : Au lieu d'écouter tout le monde, on tire au hasard un groupe minimal de témoins, juste assez pour pouvoir formuler une hypothèse unique. Par exemple, pour tracer une ligne, deux témoins suffisent (car deux points définissent une droite).
+ *La version des faits* : On trace la ligne d'horizon uniquement basée sur les déclarations de ce micro-jury.
+ *Le vote de consensus* : On présente cette ligne d'horizon à tous les autres témoins de la pièce. Chacun vote : « Cette ligne passe-t-elle près de mon observation ? » (à une tolérance t près). Si c'est le cas, le témoin rejoint le consensus et est compté comme _inlier_. Sinon, sa voix est ignorée.
+ *La répétition* : On répète cette opération N fois avec de nouveaux jurys tirés au hasard. Si un jury contient ne serait-ce qu'un seul menteur, sa ligne sera absurde et ne récoltera presque aucun vote. En revanche, le jour où le hasard réunit un jury composé exclusivement de témoins honnêtes, leur ligne passera naturellement près de tous les autres témoins honnêtes de la pièce, récoltant un consensus massif (40 % des voix).
+ *Le verdict final* : On conserve la ligne qui a réuni le plus grand nombre de votes. On écarte définitivement tous les menteurs qui ont voté contre, et on recalcule la ligne finale par la méthode classique sur le groupe entier des citoyens honnêtes ainsi identifiés.

RANSAC pousse ainsi l'influence robuste à son extrémité binaire : un témoin est soit pleinement intégré au calcul (inlier), soit totalement effacé (outlier). Cela permet d'obtenir un point de rupture bien supérieur à 50 % (on peut trouver la vérité même avec 90 % de menteurs, à condition de faire assez de tirages N).

On raisonne sur les probabilités. Si w est la proportion d'inliers et n la taille de l'échantillon minimal, la probabilité qu'un tirage soit entièrement pur est wⁿ, donc qu'il soit contaminé 1 − wⁿ, donc que les N tirages soient _tous_ contaminés (1 − wⁿ)ᴺ. On veut que cette dernière soit assez faible (au plus 1 − p) :

#info-box(title: "La formule")[
```
N = log(1 − p) / log(1 − wⁿ)
```
]

p est la probabilité souhaitée de toucher au moins un tirage pur, n la taille de l'échantillon minimal (2 pour une droite, 4 pour une homographie, 8 pour la matrice fondamentale — chapitre 8). Point capital : N dépend exponentiellement de n et de w, mais *pas de la taille du jeu de données*. L'influence de RANSAC est binaire — un point est inlier (poids 1, il fonde le modèle) ou outlier (poids 0, ignoré). Son point de rupture peut *dépasser 50 %* (il tolère une majorité d'outliers, à condition d'allonger N), là où aucun M-estimateur ne va. ∎

#question-box(title: "Exemple")[
Combien de tirages pour p = 0,99 dans trois scénarios courants ?

```
homographie (n=4),  w=0,5 :  N = log(0,01)/log(1−0,5⁴)  ≈ 72
homographie (n=4),  w=0,3 :  N = log(0,01)/log(1−0,3⁴)  ≈ 567
mat. fondamentale (n=8), w=0,5 : N = log(0,01)/log(1−0,5⁸) ≈ 1177
```

Trois leçons. Doubler n (4 → 8) multiplie N par ~16 (72 → 1177) : d'où la règle d'or « toujours le plus petit échantillon minimal ». Faire chuter w (0,5 → 0,3) multiplie N par ~8 (72 → 567) : la moindre dégradation du taux d'inliers coûte cher. C'est le calcul qu'on pose pour budgéter un recalage d'images ou un _structure-from-motion_ (chapitre 8).
]

#info-box(title: "Réglage — le seuil d'inlier et l'échantillon minimal")[
Le seuil d'inlier t est le paramètre le plus délicat : trop serré, le bon modèle est rejeté ; trop lâche, des outliers passent pour inliers et corrompent le consensus. On le cale en unités de bruit via la MAD (§16.2). On utilise toujours le *minimum* de points par tirage (en mettre plus gonfle N exponentiellement), on rejette les configurations dégénérées (4 points colinéaires pour une homographie) avant d'ajuster, et comme w est rarement connu d'avance, on l'estime en cours de route (RANSAC adaptatif).
]

#info-box(title: "Paramètres opérationnels (VNStudio / Python)")[
Dans le nœud `Find Homography (RANSAC)` (ou via `cv2.findHomography` avec la méthode `cv2.RANSAC` en Python), le comportement de l'estimateur robuste dépend des paramètres suivants :

- *Seuil de tolérance (`ransacReprojThreshold`)* :
- Dans VNStudio, ce paramètre correspond au curseur *Reprojection Threshold* ; en Python (OpenCV), il se nomme `ransacReprojThreshold` dans la fonction `cv2.findHomography`.
- Ce paramètre (exprimé en pixels, généralement réglé entre 1.0 et 5.0) définit la distance maximale autorisée pour qu'un point apparié soit considéré comme valide (inlier). Si un point projeté s'écarte de sa cible de moins de ce seuil, il est accepté. S'il s'écarte davantage, il est classé comme aberration (outlier) et totalement exclu du calcul de l'homographie finale. Fixer ce seuil trop bas exclut de bons points en raison du bruit de numérisation ; le fixer trop haut réintroduit de fausses correspondances qui faussent la géométrie.
- *Nombre maximal d'itérations (`maxIters`)* :
- Dans VNStudio, ce paramètre correspond au champ *Max Iterations* ; en Python (OpenCV), il correspond à l'argument `maxIters` dans `cv2.findHomography`.
- Définit le nombre d'échantillons aléatoires tirés par l'algorithme. RANSAC calcule la probabilité de trouver un groupe de points sains en fonction du taux d'aberrations estimé. Plus le nombre d'itérations est grand, plus on est certain de trouver la solution idéale, mais plus le calcul prend du temps. Une valeur standard est de `2000` itérations.
- *Confiance minimale (`confidence`)* :
- Dans VNStudio, ce paramètre correspond au curseur *Confidence* ; en Python (OpenCV), il correspond à l'argument `confidence` dans `cv2.findHomography`.
- La probabilité attendue (ex. : `0.99` ou 99 %) de tomber sur au moins un sous-ensemble composé exclusivement de points valides lors des tirages aléatoires. OpenCV utilise cette valeur pour arrêter les itérations plus tôt si la solution trouvée est déjà statistiquement très solide.
]

#canvas[
Dans votre canvas :
`Image A` + `Image B` ──> `Feature Matching` ──> `Find Homography (RANSAC)` ──> `Inspector`.

Le nœud `Find Homography (RANSAC)` filtre en continu les correspondances aberrantes. L'inspecteur affiche le nombre d'appariements, le nombre d'inliers, le taux estimé de points valides (inliers) retenus, et permet d'ajuster le curseur du seuil de tolérance pour voir en temps réel comment l'algorithme rejette ou accepte les points selon leur cohérence géométrique.

*Exercice de dépannage :* L'exercice consiste à apparier deux images présentant un bruit de numérisation normal. Dans le nœud *Find Homography (RANSAC)*, régler le paramètre *Reprojection Threshold* sur une valeur extrêmement basse (ex. : 0.1 pixel). Le lecteur observe dans l'inspecteur que le nombre d'inliers retenus s'effondre à 0, provoquant l'échec de l'alignement. Cet échec contrôlé démontre que le bruit de mesure naturel des pixels sains dépasse cette tolérance excessivement stricte, les faisant classer à tort comme des données aberrantes.

---
]

// ============================================================

== Au-delà du RANSAC « vanilla » : situer chaque variante

#subtitle[RANSAC compte les mains levées ; ses variantes mesurent l'enthousiasme]

=== L'intention
Le RANSAC d'origine compte les inliers : tous se valent (poids 1), un point juste à la limite du seuil et un point parfait contribuent autant. C'est une perte d'information, et deux modèles à égalité d'inliers sont indépartageables. On veut affiner ce comptage binaire sans renoncer à la robustesse.

=== La forme recherchée
L'image : RANSAC compte les mains levées, ses variantes mesurent l'enthousiasme. *MSAC* remplace le comptage par un coût tronqué — un inlier presque parfait coûte moins qu'un inlier de justesse — ce qui départage deux modèles de même nombre d'inliers pour un surcoût négligeable. *MLESAC* maximise la vraisemblance d'un mélange inliers/outliers. *LMedS* supprime le seuil en minimisant la *médiane* des carrés des résidus (point de rupture 50 %, aucun paramètre), mais échoue dès que les inliers passent sous 50 % et reste peu efficace. ∎

#info-box(title: "La formule")[
```
LMedS  :  θ̂ = argmin_θ  médiane_i (eᵢ²)         (pas de seuil ; point de rupture 50 %)
MSAC   :  score = Σᵢ min(eᵢ², t²)               (coût tronqué au lieu d'un comptage 0/1)
MLESAC :  score = vraisemblance d'un mélange inliers/outliers
```
]

#question-box(title: "Exemple")[
Deux modèles candidats, même nombre d'inliers (3 sur 4, t = 2), départagés par MSAC :

```
résidus  modèle A : [0,2 ; 0,5 ; 1,9 ; 8,0]   modèle B : [0,1 ; 0,2 ; 0,3 ; 8,0]
RANSAC (comptage) : A et B → 3 inliers           ÉGALITÉ
MSAC Σmin(e²,t²)  : A → 0,04+0,25+3,61+4 = 7,90  B → 0,01+0,04+0,09+4 = 4,14
                    → B gagne (résidus inliers plus serrés)
```

Là où RANSAC bute sur une égalité, MSAC préfère sans surcoût le modèle dont les inliers sont mieux concentrés. Son influence n'est plus strictement binaire : eᵢ² pour les inliers (croissante, plafonnée à t²), t² pour les outliers (constante) — un pont entre l'influence binaire de RANSAC et l'influence écrêtée de Huber.
]

=== État de l'art
*PROSAC* trie les tirages par qualité d'appariement (scores ORB/SIFT) et touche un échantillon pur bien plus vite ; *MAGSAC++* marginalise sur le seuil et supprime ainsi le choix fragile de t — c'est aujourd'hui un défaut solide dans les pipelines d'appariement. Plus loin, l'estimation robuste _apprise_ (réseaux qui pondèrent les correspondances, estimateurs de pose de bout en bout) remplace le tirage uniforme par un a priori entraîné — le pendant, pour la robustesse, de « descripteurs appris vs Hu » (chapitre 1). Rien de tout cela ne périme le RANSAC classique, simple et universel : chaque variante occupe un créneau (vitesse, absence de seuil, robustesse extrême).

#info-box(title: "Différence d'implémentation — seuils non interchangeables")[
LMedS plafonne à 50 % de point de rupture, en deçà de ce que RANSAC + N suffisant atteint. Les seuils des variantes ne sont pas interchangeables : MSAC réutilise t comme borne de troncature, MAGSAC s'en passe — comparer deux méthodes « à même t » n'a pas toujours de sens. Et l'on ré-ajuste toujours le modèle final sur l'ensemble des inliers (moindres carrés, voire IRLS du §16.4) : le modèle issu du seul échantillon minimal est robuste mais peu précis.
]

#canvas[
Canvas : `Image A` + `Image B` → `Feature Matching` → `Robust Fit` → `Inspector`. Le nœud expose le choix de la méthode (RANSAC, MSAC, MAGSAC++) et compare leurs inliers retenus sur la même paire — l'écart se voit sur les scènes à fort taux d'outliers.

---
]

// ============================================================

== Tableau récapitulatif — qui a le droit de déplacer l'estimation ?

#table(
  columns: 5,
  table.header(
    [*Estimateur*], [*Fonction d'influence ψ*], [*Sort d'un outlier extrême*], [*Point de rupture*], [*Usage typique*]
  ),
  [Moyenne / MCO], [`ψ(e) = e`, non bornée], [le laisse tout dominer], [0 %], [bruit gaussien pur, données propres],
  [Médiane / L1], [`ψ = sign(e)`, bornée constante], [ignoré en amplitude], [50 %], [localisation robuste, filtre médian (ch. 5)],
  [MAD], [échelle robuste, ψ bornée], [insensible], [50 %], [normaliser, définir le seuil d'outlier],
  [Huber], [écrêtée à ±k, monotone], [influence plafonnée (jamais nulle)], [élevé\*], [régression douce, bundle adjustment (ch. 15)],
  [Tukey biweight], [redescend à 0 au-delà de c], [rejeté (poids nul)], [élevé, init sensible\*], [rejet d'aberrations franches],
  [RANSAC / variantes], [binaire (inlier 1 / outlier 0)], [exclu du modèle], [> 50 % possible], [homographie, matrice F, recalage (ch. 8)],
)

\* Pour les M-estimateurs, le point de rupture dépend de l'estimation conjointe de l'échelle (MAD) et, pour Tukey, de l'initialisation. La hiérarchie qui compte est celle de l'influence : non bornée → bornée constante → écrêtée → redescendante → binaire.

---

// ============================================================

== être robuste, c'est décider à l'avance ce qu'on refuse de croire

Le fil du chapitre tient en une fonction, ψ, et une question : jusqu'où une seule donnée a-t-elle le droit de déplacer le résultat ? Tous les estimateurs ne sont que des réponses différentes, lisibles sur la forme de ψ.

```
moyenne / MCO   → ψ(e) = e            non bornée : un point emporte tout
médiane / L1    → ψ = sign(e)         bornée constante : seul le côté compte
MAD             → mètre-étalon robuste : « loin » se mesure en unités de bruit
Huber           → ψ écrêtée à ±k      on plafonne l'influence sans la nier
Tukey           → ψ redescend à 0     au-delà du seuil, l'outlier n'existe plus
RANSAC          → ψ binaire           inlier ou rien : on partitionne, on jette
```

Le lien avec le chapitre 15 boucle une équivalence exacte : ψ est la dérivée du coût, c'est-à-dire le gradient. Le chapitre 15 sculptait des paysages de gradients pour qu'une descente atteigne une métrique ; ici, on sculpte la même dérivée pour qu'une observation suspecte ne puisse pas détourner l'estimation. Borner le gradient (stabilité d'entraînement) et borner l'influence (robustesse statistique) sont une seule décision regardée sous deux angles.

C'est la dernière pièce du méta-fil de l'ouvrage. Un descripteur, un filtre, une distance, une base, un coût encodaient déjà chacun une hypothèse sur ce qui compte ; l'estimation robuste y ajoute une hypothèse sur ce dont il faut se *méfier* — fixée à l'avance, en bornant le poids qu'une observation pourra prendre. À chaque fois, le même geste : le bon cadre rend le problème presque résolu. La conclusion du livre reprendra ce fil pour le nouer.

---

// EXERCICES — CHAPITRE 16
// ============================================================

#pagebreak()
== Exercices pratiques

=== Exercice 1 · Compter une température fiable malgré les capteurs chauds

#figtodo("ex_ch16_thermique", [Image thermique d'un atelier en fausses couleurs : fond bleu-vert uniforme autou])

*Ce que vous voyez.* Une scène où quelques pixels extrêmes (les moteurs chauds) risquent de fausser l'estimation de la température ambiante. La mission : estimer la température du fond sans se laisser tromper par les points chauds.

*Pipeline VNStudio*
`Image File` → `Region Properties` → `Display`

Le nœud affiche dans l'inspecteur la moyenne, la médiane et l'écart absolu médian (MAD) de la zone sélectionnée.



*Questions*

+ Relevez la moyenne et la médiane de l'image entière. Laquelle annonce une température proche du fond réel (20 °C) ? De combien de degrés la moyenne s'éloigne-t-elle à cause des moteurs ?

+ Avec l'outil de sélection, masquez les trois moteurs chauds, puis relisez les deux valeurs. Laquelle a bougé, laquelle est restée stable ? Qu'est-ce que cela vous apprend sur la valeur à privilégier pour un capteur de surveillance ?

+ Comparez l'écart-type classique et le MAD affichés. Le premier est gonflé par les moteurs, le second non. Lequel utiliseriez-vous pour fixer un seuil d'alerte « température anormale » qui ne se déclenche pas en permanence ?

+ *Défi.* Ajoutez de plus en plus de points chauds (peignez des zones rouges dans l'image source). À partir de quelle proportion de pixels chauds la médiane se met-elle enfin à grimper ? Vérifiez qu'elle tient bon presque jusqu'à ce que la moitié de l'image soit chaude.


=== Exercice 2 · Retrouver la ligne d'horizon dans une scène encombrée

#figtodo("ex_ch16_horizon", [Photographie d'un bord de mer : l'horizon sépare nettement ciel et mer, mais la ])

*Ce que vous voyez.* Une ligne dominante (l'horizon) noyée parmi des éléments qui ne la respectent pas. La mission : faire trouver l'horizon automatiquement malgré ces intrus.

*Pipeline VNStudio*
`Image File` → `Canny Edge` → `Python Node` → `Display` → `Display`

Le nœud RANSAC trace la droite consensus et affiche le nombre de points qui la soutiennent (inliers).



*Questions*

+ Lancez le pipeline. La droite tracée suit-elle bien l'horizon, ou se laisse-t-elle attirer par le ponton et le voilier ? Notez le nombre d'inliers affiché.

+ Remplacez RANSAC par un simple ajustement de droite sur tous les points de contour (option « moindres carrés » du nœud). La droite penche-t-elle maintenant vers les intrus ? Comparez les deux tracés superposés.

+ Augmentez le seuil de tolérance de RANSAC (la distance en pixels pour qu'un point compte comme inlier). À partir de quelle valeur le ponton commence-t-il à être avalé dans le consensus et à fausser l'horizon ?

+ *Défi.* Couvrez la moitié de l'image de fausses lignes (ajoutez des objets inclinés). RANSAC retrouve-t-il toujours l'horizon ? Augmentez le nombre d'itérations du nœud et observez à partir de combien de tirages le résultat redevient stable d'un lancement à l'autre.


=== Exercice 3 · Calibrer un capteur de distance avec des mesures parasites

#figtodo("ex_ch16_calibration_capteur", [Nuage de points d'une calibration de télémètre : distance mesurée en fonction de])

*Ce que vous voyez.* Des mesures fiables pour la plupart, avec quatre relevés aberrants dus à des réflexions. La mission : trouver la vraie droite de calibration sans que ces quatre points la tordent.

*Pipeline VNStudio*
`CSV Reader` (mesures) → `Python Node` → `Scatter Plot` → `Display`

Le nœud propose trois modes d'ajustement : ordinaire (L2), Huber (résistant), médian (très résistant). Il affiche la pente trouvée et superpose la droite au nuage.



*Questions*

+ Ajustez en mode ordinaire. La droite passe-t-elle au milieu des bons points, ou est-elle tirée vers le haut par les quatre parasites ? Notez la pente.

+ Basculez en mode Huber, puis médian. La droite revient-elle se poser sur la tendance correcte ? Comparez les trois pentes : laquelle colle le mieux à la grappe des bonnes mesures ?

+ Réglez le curseur de tolérance du mode Huber du plus serré au plus large. Trouvez la plage où la droite ignore les quatre parasites tout en suivant fidèlement les bons points. Que se passe-t-il si vous serrez trop ?

+ *Défi.* Ajoutez quelques parasites supplémentaires dans le CSV. Jusqu'à combien de mesures erronées le mode médian tient-il avant de basculer ? Comparez avec le mode ordinaire, qui décroche dès le premier parasite. Pour un capteur embarqué, quel mode choisiriez-vous ?



#v(2em)
#align(center)[
  #image("/QR Code.png", width: 60pt)
  #v(4pt)
  #text(size: 0.8em, style: "italic", fill: rgb("#64748b"))[Télécharger les images de référence]
]

]
