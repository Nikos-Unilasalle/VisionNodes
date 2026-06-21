#import "@preview/bookly:4.0.0": *

// --- Helpers locaux ---
#let subtitle(t) = block(above: 0.2em, below: 1.2em, sticky: true)[#text(style: "italic", fill: rgb("#64748b"))[#t]]

#chapter(title: [Cahier de code], toc: false)[

#subtitle[Tout le code Python du livre, prêt à exécuter.]

Ce livre a fait le choix de ne montrer aucun code dans ses chapitres : on y lit des intentions, des silhouettes de formules et des canvas VNStudio, jamais des lignes de Python. Le code existe pourtant, et il est ici à votre disposition.

L'intégralité des traitements décrits dans l'ouvrage est fournie sous forme de *notebooks Jupyter*, à raison d'*un notebook par chapitre*. Chaque notebook reprend, dans l'ordre du chapitre, les calculs et les illustrations correspondants : la première cellule prépare les données d'entrée (une forme synthétique ou une image de référence selon le sujet), puis chaque sous-chapitre se lit comme une suite de cellules à exécuter pas à pas. Vous pouvez les parcourir, les modifier, les détourner sur vos propres images.

Les dix-sept notebooks sont accessibles en ligne. Scannez le QR code ci-dessous pour ouvrir le cahier de code complet.

#v(1fr)

#align(center)[
  #image("/Annexe B/QRcode_Annexe_B.svg", width: 18%)
]

]
