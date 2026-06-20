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


#chapter(title: [Métriques de segmentation], toc: false)[

#block(above: 0pt, below: 2em, width: 100%)[#image("/illustrations/chap4.jpeg", width: 100%)]

#pagebreak()
#block(above: 0em, below: 1em)[
  #grid(columns: (auto, 1fr), column-gutter: 0.6em, align: horizon,
    box(width: 3pt, height: 1.2em, fill: rgb("#c1002a"), radius: 1.5pt),
    text(weight: "bold", font: "Roboto", fill: rgb("#1e293b"))[Table des matières])
]
#suboutline(target: heading.where(outlined: true, level: 2))
#pagebreak()

#subtitle[Comparer un découpage à la vérité terrain, c'est le noter. Mais chaque note ne regarde qu'un aspect du travail — surface, frontière, comptage — et reste muette sur les autres.]

Lorsqu'un algorithme délimite une tumeur sur une IRM, découpe une voiture dans une scène de rue ou identifie une colonie bactérienne au microscope, comment savoir s'il a bien travaillé ? La réponse semble simple : comparer ce qu'il a trouvé à la *vérité terrain* — le découpage correct, tracé à la main par un expert, qui sert de référence. Mais cette comparaison soulève aussitôt trois questions distinctes, souvent confondues : _l'objet est-il à la bonne place ?_ (localisation), _l'ai-je trouvé ?_ (rappel), _ce que j'ai trouvé est-il exact ?_ (précision). Ce chapitre construit les métriques qui y répondent, de l'IoU élémentaire à la Panoptic Quality, en montrant comment chacune privilégie un aspect de la qualité au détriment d'un autre.

Le fil du chapitre tient en une phrase : *aucune métrique unique ne capture tout.* Ce n'est pas un défaut de chaque outil mais une propriété de fond. Reporter l'IoU seul, ou l'AP seul, c'est cacher un mode d'échec. Chaque section révèle l'angle mort propre à la métrique qu'elle présente : un évaluateur rigoureux connaît ce que son instrument ne peut pas voir, comme le chapitre 1 montrait que tout descripteur de forme encode ce qu'il choisit d'ignorer.

Quelques mots de vocabulaire. Un *masque binaire* est une image où chaque pixel vaut 1 s'il appartient à un objet, 0 sinon — la forme de données de base pour la segmentation, déjà rencontrée au chapitre 1. On compare le masque prédit au masque de vérité, pixel par pixel, et on classe chaque pixel : *VP* (vrai positif, prédit objet et c'est juste), *FP* (faux positif, prédit objet à tort), *FN* (faux négatif, objet manqué). Les vrais négatifs — le fond correctement laissé de côté — sont en général ignorés en segmentation : ils représentent des millions de pixels et fausseraient tout score.

---

// ============================================================

== IoU : la fraction de surface commune

#subtitle[Deux taches de peinture, et la part du mur qu'elles couvrent ensemble]

#figfull("/illustrations/chap4.1.png")

=== L'intention
On veut un seul nombre qui dise à quel point la région prédite et la vérité terrain se recouvrent — qui sanctionne à la fois les pixels oubliés et les pixels en trop.

=== La forme recherchée
Pour comprendre l'IoU géométriquement, imaginez que vous tenez deux feuilles de papier calque transparent au-dessus d'un dessin :
+ *Le premier calque (A)* représente la zone que votre algorithme a découpée (la prédiction).
+ *Le deuxième calque (B)* représente la zone réelle, découpée par un expert (la vérité terrain).
+ *L'intersection (`A ∩ B`)* est la surface où les deux calques se superposent exactement : c'est la zone où l'algorithme a vu juste.
+ *L'union (`A ∪ B`)* est l'ensemble de la surface couverte par l'un, l'autre ou les deux calques à la fois. C'est l'emprise totale de votre dessin.

L'IoU est le rapport de ces deux surfaces : la surface superposée divisée par la surface totale occupée. Si vos deux feuilles de calque coïncident parfaitement, toute la surface est commune, le rapport vaut 1. Si vous décalez les feuilles, la surface commune diminue tandis que l'emprise totale grandit, et le rapport chute vers 0. C'est le score _Jaccard_.

#info-box(title: "La formule")[
```
IoU(A, B) = |A ∩ B| / |A ∪ B|
```
]

A est la région prédite, B la vérité ; les barres |…| comptent les pixels ; ∩ est l'intersection, ∪ l'union. Le résultat va de 0 à 1. En traduisant l'union par les pixels mal classés, on obtient une écriture révélatrice :

#info-box(title: "La formule")[
```
A ∩ B = VP                        (les pixels justes)
A ∪ B = VP + FP + FN              (justes + en trop + manqués)
⟹ IoU = VP / (VP + FP + FN)
```
]

Cette décomposition montre la double pénalité de l'IoU : il sanctionne d'un même mouvement les pixels oubliés (FN, sous-segmentation) et les pixels en trop (FP, sur-segmentation). C'est sa force — un seul nombre résume les deux erreurs — et son angle mort : il ne dit pas _lequel_ des deux domine. Un IoU de 0,6 peut venir d'un masque trop petit ou trop grand ; les deux obtiennent la même note alors que les corrections à apporter sont opposées. Comme la circularité du chapitre 1, qui confondait allongement et rugosité, une seule valeur masque deux causes distinctes. ∎

=== Le seuil 0,5
En détection, on déclare une prédiction « correcte » (un VP) si son IoU avec la vérité dépasse un seuil. Le seuil historique de 0,5 est un compromis : assez permissif pour tolérer une localisation imparfaite, assez strict pour rejeter les recouvrements fortuits. Les benchmarks modernes moyennent sur plusieurs seuils (de 0,50 à 0,95) pour ne pas dépendre de ce choix.

#question-box(title: "Exemple")[
Deux carrés de côté 10 px, décalés de 3 px à l'horizontale (recouvrement 7 × 10 px) :

```
intersection = 7 × 10 = 70 px²
union = 2 × 100 − 70 = 130 px²
IoU = 70 / 130 ≈ 0,538
```

Un décalage de 3 px sur 10 (30 % de la taille) ne donne qu'un IoU de 0,54 : l'IoU chute vite dès que l'alignement n'est pas parfait, ce qui le rend sévère pour les petits objets.
]

#info-box(title: "Limite — l'IoU n'est pas comparable entre tailles")[
Pour un objet de quelques pixels, une erreur de 1 px de frontière fait beaucoup varier l'IoU ; pour un grand objet, la même erreur est négligeable. L'IoU d'un petit et d'un grand objet ne se comparent donc pas directement — d'où l'usage de reporter des scores séparés par catégorie de taille. Citer un IoU isolé sans préciser la taille des objets évalués prête à confusion.
]

#info-box(title: "Paramètres opérationnels (VNStudio / Python)")[
Dans le nœud `Mask Metrics` (ou lors du codage d'une boucle d'évaluation en Python), le comportement des métriques de détection s'appuie sur deux réglages opérationnels :

- *Seuil de confiance (`confidence threshold`)* :
- Dans VNStudio, ce paramètre correspond au curseur *Confidence Threshold* ; en Python, c'est le seuil appliqué aux scores de probabilité sortis par le modèle.
- Avant de comparer la prédiction à la vérité terrain, le réseau profond fournit un score de confiance (entre 0 et 1) pour chaque zone. Fixer ce seuil trop bas (ex: 0.1) génère de nombreux Faux Positifs (fausses alertes). Le régler trop haut (ex: 0.9) produit des Faux Négatifs (les objets peu visibles sont manqués). Une valeur standard est fixée entre 0.3 et 0.5.
- *Seuil de chevauchement IoU (`IoU threshold`)* :
- Dans VNStudio, ce paramètre correspond au champ *IoU Threshold* ; en Python (scikit-learn), il s'utilise pour filtrer les prédictions via la fonction `jaccard_score`.
- Détermine à partir de quel niveau de chevauchement une boîte prédite est déclarée comme ayant correctement identifié l'objet réel. En détection d'objets standard (comme le benchmark COCO), on fixe ce seuil à `0.5` (détection correcte) ou `0.75` (détection précise). Calculer la moyenne des précisions sur une plage de seuils (de 0.5 à 0.95) donne la métrique robuste appelée *mAP* (mean Average Precision).
]

#canvas[
Dans votre canvas :
`Image File` (prédiction) ──┐
                   ├──> `Mask Metrics` ──> `Display`.
`Image File` (vérité) ──┘

Le nœud `IoU` effectue l'intersection et l'union logiques des deux masques binaires. L'inspecteur affiche instantanément l'IoU (Jaccard) et le coefficient de Dice (F1). Le nœud colore également l'image de sortie (vert pour les Vrais Positifs, rouge pour les Faux Positifs, bleu pour les Faux Négatifs), ce qui révèle aussitôt si l'erreur penche vers la sur- ou la sous-segmentation, sans biais lié à la taille de l'arrière-plan.

*Exercice de dépannage :* L'exercice consiste à charger deux masques de prédiction pour un très petit objet de 10x10 pixels, l'un décalé de 5 pixels par rapport à la vérité terrain. Brancher ces masques au nœud `Mask Metrics` et noter le score (qui s'effondre à 0.33). Charger ensuite deux masques pour un grand objet de 100x100 pixels, décalé de la même distance de 5 pixels. Brancher ces derniers et constater dans l'inspecteur que le score remonte à 0.90. Le lecteur expérimente ainsi de manière directe le biais de sévérité de l'IoU contre les petits objets pour une même imprécision spatiale.

---
]

// ============================================================

== Coefficient de Dice : le même recouvrement, en plus indulgent

#subtitle[Compter l'intersection deux fois]

=== L'intention
On veut la même information de recouvrement que l'IoU, mais avec une note plus généreuse en début d'apprentissage — utile quand on s'en sert comme objectif à optimiser pour entraîner un modèle.

#info-box(title: "La forme recherchée et la formule")[
```
Dice(A, B) = 2|A ∩ B| / (|A| + |B|)
```
]

Pour comprendre le coefficient de Dice, reprenons nos deux feuilles de papier calque (A et B) :
+ *Pourquoi diviser par la somme des surfaces (`|A| + |B|`) ?* Au lieu de mesurer l'emprise globale (l'union), on compare la zone superposée à la somme des surfaces individuelles des deux calques. C'est comme si on pesait séparément chaque morceau de papier découpé.
+ *Le rôle du facteur 2* : Comme la zone de superposition `|A ∩ B|` est présente à la fois dans le calque A et dans le calque B, elle est comptée deux fois dans la somme du dénominateur (`|A| + |B|`). Pour que le score maximal reste égal à 1 (lorsque les calques sont identiques), on doit donc multiplier l'intersection par 2 au numérateur.

Notons I l'intersection et U l'union. Comme |A| + |B| = U + I, un peu d'algèbre donne le lien exact entre les deux mesures :

#info-box(title: "La forme recherchée et la formule")[
```
Dice = 2·IoU / (1 + IoU)   et   IoU = Dice / (2 − Dice)
```
]

Ces formules montrent que Dice et IoU *montent et descendent ensemble* : si un modèle bat un autre selon l'IoU, il le bat aussi selon Dice. Le classement est identique — le choix entre les deux est conventionnel (la médecine utilise Dice, la vision classique l'IoU), pas substantiel. Pour tout recouvrement partiel, Dice ≥ IoU ; à IoU = 0,5, par exemple, Dice ≈ 0,667. Cette indulgence explique sa popularité comme objectif d'entraînement.

En réexprimant par les VP, FP, FN :

#info-box(title: "La forme recherchée et la formule")[
```
Dice = 2·VP / (2·VP + FP + FN)
```
]

C'est exactement le *F1-score* (vu en 4.3) appliqué pixel par pixel au lieu d'objet par objet. Dice en imagerie et F1 en apprentissage sont la même quantité dans deux vocabulaires. ∎

#question-box(title: "Exemple")[
Les deux carrés du §4.1 (intersection 70 px², chaque carré 100 px²) :

```
Dice = 2 × 70 / (100 + 100) = 0,700
```

À comparer à IoU = 0,538. Vérification par la formule de conversion : 2 × 0,538 / (1 + 0,538) ≈ 0,700. ✓
]

#info-box(title: "Limite — instable sur les très petits objets")[
Dice ignore les vrais négatifs, ce qui est un avantage quand l'objet est minuscule dans une grande image (une lésion à 0,1 % des pixels d'une IRM ne doit pas être noyée dans l'immense fond correctement classé). Mais cette propriété le rend instable pour les très petits objets : un segment de 5 pixels dont 2 sont manqués donne Dice = 6/8 = 0,75, alors qu'une seule cellule de différence est en jeu. Un comptage brut (VP, FN) complète utilement le score pour les objets de taille critique.
]

#canvas[
Canvas : `Image File` (prédiction) + `Image File` (vérité terrain) → `Mask Metrics` → `Display`. L'inspecteur affiche Dice et IoU côte à côte avec la vérification de conversion, ce qui montre concrètement que les deux mesures se suivent.

---
]

// ============================================================

== Précision, rappel et F1 : la tension du douanier

#subtitle[Tout fouiller ou ne rien déranger : on ne peut pas les deux]

=== L'intention
On veut séparer deux questions que l'IoU mélange : « parmi mes détections, combien sont justes ? » et « parmi les objets réels, combien ai-je trouvés ? ». La première traque les faux positifs, la seconde les faux négatifs.

=== La forme recherchée
```
Précision = VP / (VP + FP)     « parmi mes détections, combien sont justes ? »
Rappel    = VP / (VP + FN)     « parmi les objets réels, combien ai-je trouvés ? »
```

Les deux s'opposent structurellement, et cette tension est le cœur de l'évaluation. L'image juste est celle d'un douanier. Très soupçonneux, il ouvre chaque bagage : il ne laisse rien passer (rappel = 1) mais multiplie les fouilles inutiles (précision basse). Laxiste, il ne dérange personne (précision élevée sur ses rares arrêts) mais laisse filer les contrebandiers (rappel très bas). Aucune politique ne maximise les deux à la fois : baisser le seuil de décision augmente le rappel et baisse la précision, le remonter fait l'inverse.

Annoncer « 95 % de précision » sans le rappel est un classique trompeur : un détecteur qui ne signale qu'un seul objet, le plus évident, atteint 100 % de précision pour un rappel dérisoire. Les deux chiffres sont inséparables.

Pour résumer les deux en un seul nombre d'équilibre :

#info-box(title: "La formule du F1")[
```
F1 = 2·(P × R) / (P + R)
```
]

C'est une *moyenne harmonique* — une moyenne particulière, tirée vers le bas par la plus petite des deux valeurs (à la différence de la moyenne ordinaire, qui les traite à égalité). Avec une précision de 1,0 et un rappel de 0,01 :

#info-box(title: "La formule du F1")[
```
moyenne ordinaire   = (1,0 + 0,01) / 2 = 0,505   (trompeuse : suggère « moyen »)
moyenne harmonique  = 2 × 1,0 × 0,01 / 1,01 ≈ 0,020   (juste : le système est mauvais)
```
]

La moyenne ordinaire masquerait le déséquilibre ; l'harmonique refuse de récompenser un système qui sacrifie une dimension. Le F1 réduit néanmoins deux chiffres à un, en perdant l'information sur _laquelle_ des deux est sacrifiée — son propre angle mort.

Quand une dimension importe plus que l'autre, on penche le compromis avec un réglage : favoriser le rappel pour un dépistage médical (mieux vaut une fausse alerte qu'un cancer manqué), favoriser la précision pour un filtre anti-spam (mieux vaut laisser passer un spam que bloquer un vrai message). ∎

#question-box(title: "Exemple")[
Un détecteur de cellules malades trouve 80 régions suspectes : 60 vraies, 20 du tissu sain pris pour malade, et 40 cellules malades passées inaperçues.

```
VP = 60,  FP = 20,  FN = 40
Précision = 60 / 80  = 0,750
Rappel    = 60 / 100 = 0,600
F1 = 2 × 0,750 × 0,600 / 1,350 ≈ 0,667
```

Le F1 = 0,667 reflète que ni précision ni rappel ne sont excellents — sans dire s'il faut améliorer la détection (trop de FP) ou la couverture (trop de FN).
]

#canvas[
Canvas : `Image File` (prédiction) + `Image File` (vérité terrain) → `Mask Metrics` → `Display`. Le nœud affiche précision, rappel et F1 avec le détail VP / FP / FN, et expose un réglage pour pencher le compromis vers le rappel ou la précision selon l'enjeu.

---
]

// ============================================================

== Average Precision (AP) : la note à tous les seuils

#subtitle[Juger le détecteur à tous ses réglages d'un coup, pas à un seul]

#figfull("/figures/fig_ch4_obs1_pr_curve.pdf")

#figfull("/figures/fig_ch4_obs2_ap_area.pdf")

=== L'intention
Le F1 ne vaut que pour un seuil de décision fixé. On voudrait une note qui résume la performance du détecteur *à tous les seuils possibles* à la fois, pour ne pas dépendre d'un choix arbitraire.

=== La forme recherchée
Un détecteur attribue à chaque détection un *score de confiance*. On les trie du plus sûr au moins sûr et on descend la liste. À chaque détection ajoutée, on recalcule le couple (précision, rappel) obtenu jusque-là. Il en sort une *courbe précision-rappel* : à mesure qu'on accepte des détections de moins en moins sûres, on en trouve davantage (le rappel monte) mais on se trompe plus souvent (la précision a tendance à baisser). La note résume cette courbe par l'aire en dessous : un détecteur parfait garde une précision de 1 pour tout rappel (aire = 1), un détecteur au hasard reste très bas.

#info-box(title: "La formule")[
```
AP = aire sous la courbe précision-rappel
```
]

(AP pour _Average Precision_, la précision moyenne ; sa moyenne sur toutes les catégories d'objets s'appelle mAP.) La courbe brute étant en dents de scie, on la « repasse » d'abord : à chaque niveau de rappel, on retient la meilleure précision atteignable au-delà, ce qui lisse les irrégularités dues à l'ordre exact des détections. ∎

#question-box(title: "Exemple")[
Cinq détections triées par confiance décroissante, sur 3 objets réels :

```
rang  statut  VP cumulé  précision  rappel
1     VP      1          1,000      0,333
2     VP      2          1,000      0,667
3     FP      2          0,667      0,667
4     VP      3          0,750      1,000
5     FP      3          0,600      1,000
```

Après lissage, les précisions retenues aux rappels {0,33 ; 0,67 ; 1,00} sont {1,00 ; 1,00 ; 0,75}. AP ≈ (1,00 + 1,00 + 0,75) / 3 ≈ 0,917.
]

#info-box(title: "Différence d'implémentation — les conventions divergent")[
Un « mAP de 0,4 » selon une convention stricte (moyenne sur des seuils d'IoU de 0,50 à 0,95) peut valoir « 0,7 » selon une convention permissive (seuil unique à 0,5) pour le même modèle. La convention stricte exige une localisation fine, où un pixel de décalage sur une petite cible suffit à faire basculer une détection de juste à fausse. Comparer des AP de conventions différentes n'a pas de sens.
]

#info-box(title: "Limite — l'AP ne reflète pas le seuil de déploiement")[
L'AP intègre sur tous les seuils de confiance — sa vertu (pas de seuil arbitraire) et son angle mort : elle ne dit rien de la performance au seuil qu'on utilisera vraiment en production. Un modèle peut avoir un excellent AP et être médiocre au seuil de déploiement. Le F1 au seuil effectivement choisi complète donc l'AP pour l'opérationnel.
]

#canvas[
Canvas : `Image File` → `Mask Metrics` → `Display`. Le nœud trace la courbe précision-rappel et sa version lissée, et affiche l'aire (l'AP). Faire varier le seuil d'IoU montre directement l'écart entre conventions stricte et permissive.

---
]

// ============================================================

== Panoptic Quality (PQ) : reconnaître × délimiter

#subtitle[Une seule note pour deux questions indépendantes]

#figfull("/illustrations/chap4.5.png")

=== L'intention
La segmentation panoptique unifie deux tâches : segmenter les objets dénombrables (voitures, piétons, noyaux — chacun une instance distincte) et les régions amorphes (route, ciel, fond — non dénombrables). On cherche une note qui réponde d'un coup à deux questions : « ai-je trouvé les bons objets ? » et « les ai-je bien délimités ? ».

=== La forme recherchée
On apparie d'abord chaque prédiction à la vérité qui lui correspond : un couple est un vrai positif si leur IoU dépasse 0,5. La note combine alors deux choses : la qualité de délimitation des objets trouvés, et la capacité à trouver les bons objets.

#info-box(title: "La formule")[
```
PQ = [ Σ IoU des couples appariés ] / [ |VP| + ½|FP| + ½|FN| ]
```
]

Elle se factorise en deux termes interprétables, dont le produit donne la PQ :

#info-box(title: "La formule")[
```
PQ = SQ × RQ
SQ (Segmentation Quality) = IoU moyen des couples bien appariés
RQ (Recognition Quality)  = F1-score au niveau des objets (pas des pixels)
```
]

La *SQ* mesure la qualité de délimitation des objets _trouvés_ ; la *RQ* mesure la capacité à trouver les bons objets. La factorisation sépare proprement les deux questions. Un modèle médical peut exceller en RQ (il repère toutes les lésions) mais faiblir en SQ (ses contours sont flous) : la PQ seule masque ce diagnostic, la décomposition le révèle. L'appariement à IoU > 0,5 a une propriété commode : il est forcément *unique* (deux prédictions séparées ne peuvent dépasser 0,5 avec la même vérité), ce qui évite toute ambiguïté. ∎

#question-box(title: "Exemple")[
Scène de télédétection, 3 bâtiments à segmenter. Le modèle en prédit 4 : 2 bien appariés (IoU = 0,80 et 0,90), 1 prédiction sans correspondant (FP), 1 bâtiment réel non trouvé (FN).

```
VP = 2,  FP = 2,  FN = 1
SQ = (0,80 + 0,90) / 2 = 0,850
RQ = 2 / (2 + ½×2 + ½×1) = 2 / 3,5 ≈ 0,571
PQ = SQ × RQ = 0,850 × 0,571 ≈ 0,486
```

Lecture immédiate : la segmentation est correcte (SQ = 0,85) mais la reconnaissance insuffisante (RQ = 0,57, trop de FP et FN). Le diagnostic pointe le module de détection, pas les masques — ce que la PQ seule, à 0,49, ne dirait pas.
]

#canvas[
Canvas : `Image File` (prédiction) + `Image File` (vérité) → `Mask Metrics` → `Display`. Le nœud affiche PQ, SQ et RQ séparément — l'essentiel, car c'est la décomposition, pas la PQ globale, qui dit où porter l'effort.

---
]

// ============================================================

== Boundary F1 (BF) : la qualité du tracé de bord

#subtitle[Deux calques posés l'un sur l'autre : les bords se suivent-ils ?]

#figfull("/illustrations/chap4.6.png")

=== L'intention
Deux segmentations peuvent obtenir le même IoU avec des frontières de qualités très différentes : un IoU de 0,90 peut venir d'un large objet aux bords approximatifs ou d'un objet un peu plus petit aux bords parfaits. Là où la frontière compte — découpe chirurgicale, métrologie industrielle, cartographie de parcelles —, il faut une métrique de *contour*.

=== La forme recherchée
L'IoU mesure si deux silhouettes se superposent en surface ; on veut plutôt vérifier si les deux tracés de bord se suivent de près, pixel après pixel, comme deux calques posés l'un sur l'autre. On calcule donc précision et rappel sur les seuls pixels de frontière, avec une *tolérance* de quelques pixels : un pixel de bord prédit est compté correct s'il existe un pixel de bord vérité tout près.

#info-box(title: "La formule")[
```
P_c = pixels de bord prédits proches d'un bord vérité  / total bord prédit
R_c = pixels de bord vérité proches d'un bord prédit   / total bord vérité
BF  = 2 · P_c · R_c / (P_c + R_c)
```
]

C'est un F1 (la moyenne harmonique de 4.3) appliqué aux pixels de frontière. Le BF et la distance de Hausdorff (§3.6) mesurent tous deux l'erreur de frontière, différemment : la Hausdorff rapporte le _pire_ écart ponctuel (sensible à un point aberrant), le BF une _proportion_ de frontière correcte dans la tolérance (robuste, borné entre 0 et 1). Les deux se complètent — BF pour la qualité globale du contour, HD95 pour garantir l'absence d'excursion grave. ∎

#question-box(title: "Exemple")[
Lésion dermique. Frontière vérité 200 px, frontière prédite 210 px, tolérance 2 px. 190 pixels prédits trouvent un voisin vérité proche, 185 pixels vérité trouvent un voisin prédit proche :

```
P_c = 190 / 210 ≈ 0,905
R_c = 185 / 200 = 0,925
BF  = 2 × 0,905 × 0,925 / 1,830 ≈ 0,915
```

Un BF = 0,915 indique que 90 % du tracé prédit suit fidèlement le contour réel, bien que la frontière prédite soit un peu plus longue.
]

#info-box(title: "Réglage — la tolérance dépend de la résolution")[
Le BF dépend du couple (tolérance, résolution de l'image). Doubler la résolution sans adapter la tolérance rend le score plus sévère : la même erreur physique de 0,5 mm couvre désormais deux fois plus de pixels. Exprimer la tolérance en unités physiques (mm, µm) quand c'est possible, la garder constante entre modèles comparés, et reporter la résolution, garde les comparaisons valides.
]

#canvas[
Canvas : `Image File` (prédiction) + `Image File` (vérité terrain) → `Boundary F1` → `Display`. Le nœud extrait les deux contours, mesure leur recouvrement dans la tolérance choisie, et affiche le BF avec ses composantes précision et rappel de bord.

---
]

// ============================================================

== Tableau récapitulatif — quelle métrique pour quoi ?

#table(
  columns: 4,
  table.header(
    [*Outil*], [*Ce qu'il mesure*], [*Angle mort*], [*Usage typique*]
  ),
  [IoU / Jaccard], [recouvrement de surface, pénalise FP et FN], [ne distingue pas sur- et sous-segmentation ; sévère sur petits objets], [évaluation de segmentation, seuil VP/FP],
  [Dice / F1-pixel], [recouvrement (plus indulgent que IoU)], [suit l'IoU ; instable sur très petits objets], [imagerie médicale, objectif d'entraînement],
  [Précision], [taux de faux positifs], [ignore les faux négatifs], [filtrage, tri, spam],
  [Rappel], [taux de faux négatifs], [ignore les faux positifs], [dépistage, surveillance],
  [F1 / F_β], [équilibre précision-rappel], [cache à quel seuil de décision il est atteint], [évaluation globale ; réglable selon enjeu],
  [AP / mAP], [qualité intégrée sur tous les seuils], [ne reflète pas le seuil de déploiement ; conventions divergentes], [benchmarks de détection multi-classes],
  [Panoptic Quality PQ], [reconnaissance (RQ) × segmentation (SQ)], [un seul chiffre masque le déséquilibre des deux], [segmentation panoptique],
  [Boundary F1], [exactitude des contours, bornée \[0,1\]], [dépend de la tolérance et de la résolution ; ignore la surface], [découpe précise, métrologie, cartographie],
)

---

// ============================================================

== une note unique cache toujours quelque chose

Le mode d'échec le plus répandu dans les publications de vision par ordinateur n'est pas un mauvais modèle, c'est une *évaluation incomplète*. Le chapitre l'a montré section après section : l'IoU cache si l'erreur est en sur- ou sous-segmentation ; le Dice ne distingue pas un fort rappel d'une forte précision ; l'AP ne reflète pas le seuil de déploiement ; la PQ masque le déséquilibre détection / délimitation tant qu'on ne la décompose pas ; le BF est muet sur la surface.

Ce n'est pas un déficit corrigeable par une meilleure formule. Une métrique de surface (IoU, Dice) déclare que seule la masse de pixels partagés importe ; une métrique de frontière (BF, Hausdorff) déclare l'inverse. Aucune n'est universellement vraie : elles sont adaptées à des usages, comme un descripteur du chapitre 1 garde une chose et en jette une autre, et comme une distance du chapitre 3 déclare ce qu'elle tient pour proche.

La conduite pratique en découle : une comparaison honnête combine au moins une métrique de surface (IoU ou Dice) et une métrique de frontière (BF ou HD95), en précisant les seuils, la tolérance, la convention employée et la répartition par taille d'objet. Le chapitre 5 quittera l'évaluation pour la transformation des images, où le choix d'un filtre encodera, lui aussi, une hypothèse sur le signal.

---

// EXERCICES — CHAPITRE 4
// ============================================================

#pagebreak()
== Exercices pratiques

=== Exercice 1 · Noter un masque de poumon contre l'avis de l'expert

#figtodo("ex_ch4_radio_poumon", [Radiographie thoracique en niveaux de gris avec deux contours superposés : en ve])

*Ce que vous voyez.* Un masque automatique et un masque expert sur le même organe. La mission : leur attribuer une note de recouvrement et comprendre ce que cette note récompense ou pardonne.

*Pipeline VNStudio*
`Image File` → `Threshold (Advanced)` (masque auto) → `Mask Metrics` → `Display`

Chargez le masque expert comme seconde entrée. Le nœud affiche le score de recouvrement (IoU et Dice) et colorie la zone de désaccord.



*Questions*

+ Lisez les deux scores affichés. Lequel est le plus élevé pour ce même masque ? Repérez sur l'image la bande colorée de désaccord, sur le centre ou sur les bords ?

+ Rétrécissez le masque automatique (érodez-le de quelques pixels). Les deux scores baissent ; lequel chute le plus vite ? Pour noter un petit organe, lequel est le plus « indulgent » ?

+ Trouvez la zone où les deux masques divergent le plus. Plus cette zone est large, plus le score baisse : pourquoi le désaccord pèse-t-il deux fois (compté à la fois comme manque et comme excès) ?

+ *Défi.* Réglez le seuillage pour que le masque automatique tienne entièrement à l'intérieur du contour expert (aucun débordement). Le score atteint-il 100 % ? Sinon, qu'est-ce qui l'en empêche, et que faut-il pour le maximiser ?


=== Exercice 2 · Régler un détecteur d'empreintes entre prudence et excès de zèle

#figtodo("ex_ch4_empreintes", [Scène de relevé d'empreintes : surface granuleuse avec plusieurs empreintes, cer])

*Ce que vous voyez.* Un détecteur qui trouve presque toutes les empreintes mais en invente quelques-unes sur le fond texturé. La mission : trouver le bon seuil de confiance selon l'enjeu.

*Pipeline VNStudio*
`Image File` → `Mask Metrics` → `Display`

Le nœud affiche, pour le seuil de confiance choisi, le nombre de bonnes détections, de fausses alarmes et d'empreintes ratées, ainsi que la précision et le rappel.



*Questions*

+ Réglez le seuil très bas (0,1). Le détecteur attrape-t-il toutes les empreintes ? Combien de fausses alarmes invente-t-il en échange ?

+ Montez le seuil jusqu'à 0,9. Les fausses alarmes disparaissent-elles ? Combien de vraies empreintes perdez-vous au passage ? Décrivez le compromis que vous voyez basculer.

+ Trouvez le seuil qui efface toutes les fausses alarmes. À ce réglage, combien d'empreintes manquent encore ? Et le seuil qui n'en rate aucune : combien de fausses alarmes laisse-t-il ?

+ *Défi.* Dans une enquête, rater une empreinte coûte plus cher qu'une fausse alarme à vérifier. Quel seuil privilégier ? Justifiez votre choix avec les chiffres relevés, puis trouvez celui de l'enquête inverse (où chaque vérification est coûteuse).


=== Exercice 3 · Départager deux découpages de parcelles agricoles

#figtodo("ex_ch4_parcelles", [Image satellitaire de parcelles agricoles délimitées de deux façons : version A ])

*Ce que vous voyez.* Deux découpages qui reconnaissent les mêmes parcelles, mais tracent leurs bords avec un soin différent. La mission : trouver la note qui sait voir cette différence de qualité de bord.

*Pipeline VNStudio*
`Image File` → `Boundary F1` → `Display`

Le nœud compare deux segmentations à une référence et affiche, au choix, le recouvrement global (IoU) ou la note de bord (qualité du tracé des frontières).



*Questions*

+ Notez A et B avec le recouvrement global. La note distingue-t-elle clairement les deux versions, ou les juge-t-elle presque équivalentes ?

+ Passez à la note de bord. Cette fois, l'écart entre A et B se creuse-t-il ? Laquelle des deux versions est récompensée pour ses contours fins ?

+ Élargissez la tolérance de la note de bord (le rayon où un bord prédit compte comme « bien placé »). À partir de quelle tolérance les deux versions redeviennent-elles équivalentes ? Pour une cartographie fine, faut-il une tolérance serrée ou large ?

+ *Défi.* Épaississez volontairement les bords de la version A. Sa note de recouvrement bouge-t-elle ? Sa note de bord se dégrade-t-elle ? Expliquez pourquoi un cadastre de précision doit être évalué sur les bords, pas seulement sur le recouvrement des surfaces.



#v(2em)
#align(center)[
  #image("/QR Code.png", width: 60pt)
  #v(4pt)
  #text(size: 0.8em, style: "italic", fill: rgb("#64748b"))[Télécharger les images de référence]
]

]
