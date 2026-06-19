#import "@preview/bookly:4.0.0": *

// --- Helpers locaux ---
#let subtitle(t) = block(above: 0.2em, below: 1.2em, sticky: true)[#text(style: "italic", fill: rgb("#64748b"))[#t]]

#let figtodo(id, desc) = block(above: 2em, below: 2em, width: 100%)[
  #block(width: 100%, inset: (x: 16pt, y: 14pt), radius: 6pt,
    fill: rgb("#fdf3f5"), stroke: 1pt + rgb("#d0a0aa"))[
    #text(size: 0.78em, weight: "bold", fill: rgb("#c1002a"), font: "Roboto")[▪ IMAGE D'EXERCICE]
    #v(0.4em)
    #text(size: 0.9em, fill: rgb("#334155"), font: "Roboto")[#raw(id)]
  ]
]

#let figfull(path) = block(above: 1em, below: 1.4em, width: 100%)[#image(path, width: 100%)]
#let canvas(body) = tip-box(title: "Dans VNStudio")[
  #show heading: it => block(above: 0.5em, below: 0em)[
    #text(font: "Roboto", weight: "regular", size: 0.95em)[#it.body]
  ]
  #set heading(numbering: none)
  #body
]

// Heading invisible visuellement, mais présent dans la TDM
#[
  #show heading.where(level: 1): _ => []
  = Introduction
]

#v(2em)
#block(breakable: false)[
  #text(size: 2.2em, weight: "bold", fill: rgb("#1e293b"), font: "Roboto")[Comprendre ce qu'on calcule]
  #v(0.4em)
  #line(length: 100%, stroke: 1.5pt + rgb("#c1002a"))
]
#v(1.5em)

Une image, pour une machine, n'est rien d'autre qu'une grille de nombres : à chaque point, une intensité, ou un triplet de couleurs. Là où votre œil reconnaît sans effort un visage, une route, une cellule au microscope, l'ordinateur ne dispose que de ce tableau. La vision par ordinateur est l'art de transformer ce tableau en décision — _ceci est un caractère « O »_, _ce contour passe ici_, _cet objet s'est déplacé de trois pixels vers la droite_ — et de le faire de façon assez fiable et assez rapide pour qu'on puisse s'y fier.

La discipline est exigeante, et il serait malhonnête de le cacher. Elle emprunte à la géométrie — où se projette un point du monde sur le capteur ? —, au traitement du signal — comment lisser sans effacer ? —, à la statistique — que faire des valeurs aberrantes ? —, à l'optique et à l'algèbre linéaire. Chacune de ces branches apporte ses formules, et ces formules ont une forme précise, presque jamais arbitraire.

Mais voici ce qui doit vous rassurer, et qui tient lieu de promesse pour tout l'ouvrage : il n'y a pas, dans ce livre, une seule formule que vous ne puissiez vous représenter mentalement. Aucune n'est un sortilège. Derrière chaque symbole se cache une image géométrique, un mouvement, une intuition que l'on peut dessiner sur un coin de table. Le travail demandé n'est pas de subir les mathématiques, mais de les _voir_.

=== Les mathématiques à leur juste place


Les mathématiques sont ici indispensables — non comme un péage à acquitter, mais comme la langue dans laquelle les opérations se disent. Elles ne servent pas à impressionner ; elles servent à régler. Car chaque formule de ce livre se traduit, très concrètement, en _paramètres_ : le σ d'un flou gaussien, la valeur de coupure d'une binarisation, la taille d'un noyau, la tolérance d'un RANSAC. Comprendre la formule, c'est comprendre ce que fait chaque réglage, dans quel sens le pousser, et à partir de quand il cesse de bien se comporter. Celui qui tourne les boutons au hasard finit par obtenir quelque chose ; celui qui sait ce que mesure le bouton obtient ce qu'il veut.

Pour autant, ce livre n'est pas un traité de mathématiques, et n'en a pas l'ambition. Établir qu'un théorème est vrai, dans toute sa généralité et avec toute la rigueur requise, est le métier du mathématicien : nous lui laissons ce travail. Quand l'inégalité isopérimétrique affirme que le cercle enferme le plus d'aire à périmètre donné, on s'en sert sans la redémontrer. Ce que l'on fait en revanche, systématiquement, c'est montrer _d'où vient la forme_ d'une formule — pourquoi ce facteur 4π, pourquoi un carré au dénominateur, pourquoi une racine. Cette dérivation-là n'a rien d'un exercice de pure rigueur : elle est ce qui transforme une recette en objet compréhensible. On la mène jusqu'à son terme — close d'un ∎ — puis on passe à l'usage. La rigueur complète appartient aux livres de mathématiques ; la compréhension opératoire, celle qui permet de _maîtriser_ un outil dans une situation particulière, est notre seul objectif.

=== Maîtriser, c'est connaître l'angle mort


Appliquer une formule est facile : un appel de bibliothèque y suffit. La maîtriser est autre chose. Chaque opération de la vision par ordinateur voit quelque chose et, du même geste, en ignore une autre — c'est ce qu'on appellera tout au long du livre son _angle mort_. La circularité confond une ellipse lisse et un disque déchiqueté ; un flou qui supprime le bruit émousse aussi les contours ; un seuil qui sépare proprement deux objets en colle deux autres. Manier un outil, ce n'est pas en connaître la formule par cœur : c'est savoir dans quelles situations il vous trahira. C'est pourquoi chaque chapitre insiste autant sur les pièges concrets — l'ordre (ligne, colonne) qui s'inverse, le périmètre discret surestimé de 27 %, l'espace de couleur où une distance perd son sens — que sur les formules elles-mêmes.

La mise en application est donc constante, jamais reléguée à la fin. À chaque formule répondent un exemple chiffré que vous pouvez vérifier de tête et un piège tiré de la pratique réelle. La théorie et son usage avancent ensemble, ligne à ligne.

=== VNStudio : un atelier conforme à cet esprit


Pour que cette pratique reste immédiate, le livre s'appuie sur *VNStudio* (\<https://nikos-unilasalle.github.io/VisionNodes/>), un studio de vision par ordinateur orienté nœuds. Le principe : plutôt que d'écrire du code, on construit un _graphe_ en reliant des boîtes — une source d'image, un flou, un seuillage, un affichage —, chacune effectuant une opération et transmettant son résultat à la suivante. L'image se recalcule en direct à mesure qu'on déplace les réglages.

Cet outil épouse l'esprit du livre pour des raisons précises, et non par commodité. D'abord, *les paramètres d'un nœud sont exactement les quantités des formules* : le curseur qui règle un flou, c'est le σ du noyau gaussien ; le seuil d'un nœud de binarisation, c'est la valeur de coupure de la formule. Pousser le curseur et voir l'image changer sous vos yeux, c'est faire l'expérience directe de ce que la formule signifie — l'intuition s'installe en quelques secondes, là où une page de calcul resterait muette. Ensuite, *le graphe rend visible la structure d'un traitement* : une chaîne de vision n'est qu'une suite d'opérations enchaînées, et c'est précisément ce que dessinent les nœuds et leurs liaisons. Enfin, les connexions y sont strictement typées — une _image_ ne se branche pas là où l'on attend un _masque_ ou un _scalaire_ —, ce qui force, sans douleur, à savoir ce qui circule réellement d'une étape à l'autre. Tout tourne en local, sans boîte noire distante : ce que vous voyez à l'écran est ce que la machine calcule.

=== Un tremplin, non une destination


Qu'on ne s'y trompe pas : *ce livre n'est pas un manuel de VNStudio*. C'est un manuel de vision par ordinateur. VNStudio y tient le rôle d'un établi — un lieu où l'on construit, où l'on essaie, où l'on prend l'outil en main — et non celui d'une fin en soi. Tout ce que vous y apprendrez se transpose, car les concepts ne lui appartiennent pas : un flou gaussien, une transformée de Fourier, un estimateur robuste sont les mêmes partout. Un nœud du graphe correspond à un appel de fonction ; une liaison entre deux nœuds, au passage d'un résultat à l'opération suivante. Le graphe que vous tracez à la souris _est_ déjà, trait pour trait, le programme que vous écririez en Python.

C'est pourquoi le code n'est pas dispersé au fil des pages : ici, la programmation est d'abord *visuelle*, faite dans VNStudio en reliant des nœuds. Mais à chaque opération, le livre tend un *pont explicite entre le nœud et le code*. Chaque fois qu'un nœud expose un réglage, on le nomme en regard de son équivalent exact dans la bibliothèque : le curseur d'un flou, c'est le paramètre `sigmaX` de `cv2.GaussianBlur` ; le champ _Max Features_, c'est `nfeatures` de `cv2.ORB_create`. Le graphe qu'on trace à la souris et la fonction qu'on écrirait en Python désignent la même opération sous deux notations. Et les programmes complets — NumPy, OpenCV, scikit-image, scipy, et PyTorch là où il le faut — sont rassemblés en *annexe*, prêts à être lus, exécutés et réemployés. Vous apprenez d'abord sur VNStudio, où l'effet de chaque choix est visible et immédiat ; puis vous *volez de vos propres ailes* : vous reprenez le traitement en Python depuis l'annexe, vous le portez sur une autre plateforme, vous l'intégrez à votre projet. L'outil est un point de départ commode ; le but, lui, est l'autonomie.

=== Le fil de tout l'ouvrage


Un dernier mot, qui tient tout le reste. À mesure que les dix-sept chapitres avancent — des descripteurs de forme aux distances, des filtres aux contours, de la couleur à la géométrie de la caméra, du flot optique aux bases de transformation, de la morphologie à la segmentation, de la texture à la qualité d'image, des fonctions de coût à l'estimation robuste, jusqu'à l'appariement de points entre deux vues —, une même idée revient sous des déguisements différents : *tout choix de représentation encode une hypothèse sur ce qui compte*. Choisir une distance, c'est déclarer ce qui se ressemble ; choisir un filtre, c'est déclarer ce qu'on tient pour du signal et ce qu'on tient pour du bruit ; choisir un descripteur, c'est décider de ce qu'on accepte d'oublier. Et chaque fois, la leçon est la même : _le bon cadre rend le problème presque résolu_. La difficulté d'un problème de vision tient rarement à la formule finale ; elle tient au choix du point de vue depuis lequel on le regarde.

Un graphe de nœuds rend ce principe tangible : chaque boîte est un choix, posé là, visible, ajustable, dont on observe aussitôt les conséquences. C'est sans doute la meilleure manière d'apprendre cette discipline — non pas en mémorisant des formules, mais en voyant, encore et encore, ce que chacune décide de regarder, et ce qu'elle laisse dans l'ombre.
