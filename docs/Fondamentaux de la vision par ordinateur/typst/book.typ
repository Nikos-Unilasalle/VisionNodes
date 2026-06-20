#import "@preview/bookly:4.0.0": *
#import "@preview/itemize:0.2.0" as el
#import "@preview/hydra:0.6.2": hydra

// Option 1 Theme: The Modern Academic
#let option1-theme-func(colors: default-colors, it) = {
  // Level 1 heading (Chapter)
  show heading.where(level: 1): it => context {
    pagebreak(weak: true)
    reset-counters
    
    let type-chapter = if states.isappendix.get() {
      states.localization.get().appendix
    } else {
      states.localization.get().chapter
    }
    
    v(3em)
    grid(
      columns: (1fr, auto),
      align: bottom + left,
      [
        #set par(justify: false)
        #text(size: 1.1em, fill: colors.primary, weight: "bold", font: "Roboto")[#upper(type-chapter)]
        #v(0.3em)
        #text(size: 2.5em, weight: "bold", fill: rgb("#1e293b"), font: "Roboto")[#it.body]
      ],
      [
        #text(size: 6.5em, weight: "light", fill: colors.primary.lighten(80%), font: "Roboto")[#counter(heading).display(states.num-heading.get())]
      ]
    )
    v(0.5em)
    line(length: 100%, stroke: 1.5pt + colors.primary)
    v(3em)
  }
  
  // Level 2 heading
  show heading.where(level: 2): it => {
    block(above: 1.8em, below: 1em)[
      #grid(
        columns: (auto, 1fr),
        column-gutter: 0.6em,
        align: horizon,
        box(width: 3pt, height: 1.2em, fill: colors.primary, radius: 1.5pt),
        [
          #if it.numbering != none {
            text(weight: "bold", fill: colors.primary, font: "Roboto")[#counter(heading).display()]
            h(0.3em)
          }
          #text(weight: "bold", fill: rgb("#1e293b"), font: "Roboto")[#it.body]
        ]
      )
    ]
  }
  
  // Level 3 heading
  show heading.where(level: 3): it => {
    block(above: 1.4em, below: 0.8em)[
      #if it.numbering != none {
        text(weight: "bold", fill: colors.primary.lighten(20%), font: "Roboto")[#counter(heading).display()]
        h(0.3em)
      }
      #text(weight: "bold", fill: rgb("#334155"), font: "Roboto")[#it.body]
    ]
  }
  
  // Tables
  show table.cell.where(y: 0): set text(weight: "regular", fill: white, font: "Roboto", size: 0.85em)
  show table.cell: set par(justify: false)

  // Block code never justified (inline raw unaffected)
  show raw.where(block: true): it => [#set par(justify: false); #it]
  set table(
    fill: (_, y) => if y == 0 {colors.primary} else if calc.odd(y) {colors.secondary.lighten(60%)},
    stroke: (_, y) => if y == 0 { 1.5pt + colors.primary } else { none }
  )
  
  // Lists
  show: el.default-enum-list
  set list(marker: [#text(fill:colors.primary, size: 1.1em)[#sym.bullet]])
  set enum(numbering: n => text(fill:colors.primary)[#n.])
  
  // Footnotes
  set footnote.entry(separator: line(length: 30% + 0pt, stroke: 0.75pt + colors.primary))
  
  // Bold text: compensate font metric difference vs regular weight
  show strong: set text(size: 0.88em)

  // References
  show ref: set text(fill: colors.primary)

  // QED marker in primary color
  show "∎": text(fill: colors.primary)[∎]
  
  // Page style
  let page-header = context {
    show linebreak: none
    set text(style: "italic", fill: colors.header, size: 0.9em)
    if calc.odd(here().page()) {
      align(right)[
        #hydra(2, display: (_, it) => [
          #let head = if it.numbering != none {
            numbering(it.numbering, ..counter(heading).at(it.location())) + " " + it.body
          } else {
            it.body
          }
          #grid(
            columns: (1fr, auto),
            column-gutter: 0.5em,
            align: horizon,
            [#line(length: 100% - 0.5em, stroke: 0.5pt + colors.primary.lighten(50%))],
            [#head]
          )
        ])
      ]
    } else {
      align(left)[
        #hydra(1, display: (_, it) => [
          #let head = if it.numbering != none {
            counter(heading.where(level:1)).display() + " " + it.body
          } else {
            it.body
          }
          #grid(
            columns: (auto, 1fr),
            column-gutter: 0.5em,
            align: horizon,
            [#head],
            [#line(length: 100% - 0.5em, stroke: 0.5pt + colors.primary.lighten(50%))]
          )
        ])
      ]
    }
  }
  
  let page-footer = context {
    let current-page = counter(page).display()
    set text(fill: rgb("#64748b"), weight: "regular", size: 0.9em)
    v(1em)
    align(center)[#current-page]
  }
  
  set page(
    width: 19.05cm,
    height: 23.5cm,
    margin: (inside: 2.0cm, outside: 1.6cm, top: 1.9cm, bottom: 1.9cm),
    header: page-header,
    footer: page-footer
  )
  
  it
}

#let theme1 = modern + (theme: option1-theme-func)

#show: bookly.with(
  title: "Le monde vu par les nombres",
  author: "Nicolas Priniotakis",
  theme: theme1,
  lang: "fr",
  config-options: (open-right: false),
  title-page: [
    #set page(width: 19.05cm, height: 23.5cm, header: none, footer: none, margin: (top: 0pt, bottom: 0pt, left: 0pt, right: 0pt))
    #image("/Couv.pdf", width: 100%, height: 100%, fit: "stretch")
  ],
)

// ── Page blanche ─────────────────────────────────────────────────────────────
#page(header: none, footer: none)[]

// ── P1.pdf ───────────────────────────────────────────────────────────────────
#page(width: 19.05cm, height: 23.5cm, header: none, footer: none,
      margin: (top: 0pt, bottom: 0pt, left: 0pt, right: 0pt))[
  #image("/P1.pdf", width: 100%, height: 100%, fit: "stretch")
]

// ── P2.pdf ───────────────────────────────────────────────────────────────────
#page(width: 19.05cm, height: 23.5cm, header: none, footer: none,
      margin: (top: 0pt, bottom: 0pt, left: 0pt, right: 0pt))[
  #image("/P2.pdf", width: 100%, height: 100%, fit: "stretch")
]

// ── Page VNStudio ─────────────────────────────────────────────────────────────
#page(header: none, footer: none,
      margin: (top: 2.8cm, bottom: 2.5cm, left: 2.5cm, right: 2.5cm))[

  #set text(size: 10.5pt, lang: "fr")
  #set par(justify: true, leading: 0.75em)

  #text(size: 1.35em, weight: "bold", font: "Roboto", fill: rgb("#1e293b"))[VNStudio : L'Atelier Visuel de la Vision par Ordinateur]

  #v(1.2em)

  La vision par ordinateur est une discipline exigeante qui nécessite de transformer de simples grilles de nombres en décisions fiables. Pour rendre cet apprentissage immédiat et faciliter la conception de pipelines de traitement, la méthode de cet ouvrage s'appuie sur #strong[VNStudio], un studio de vision par ordinateur orienté nœuds.

  #v(0.8em)
  #text(weight: "bold")[Un avantage décisif pour l'apprentissage : l'intuition par l'image]

  Dans VNStudio, #strong[la programmation est d'abord visuelle] : au lieu d'écrire des lignes de code, l'utilisateur construit un graphe en reliant des boîtes (source d'image, binarisation, affichage, etc.) qui se transmettent leurs résultats. Cette approche transforme radicalement la manière d'apprendre :

  - #strong[L'expérience directe des formules :] Les paramètres exposés sur chaque nœud correspondent exactement aux variables des formules mathématiques. Par exemple, pousser le curseur d'un nœud de flou ajuste directement le $sigma$ du noyau gaussien, et l'image se recalcule en direct sous vos yeux. L'intuition s'installe en quelques secondes là où une page d'équations resterait abstraite.
  - #strong[Rendre les choix tangibles :] Un graphe de nœuds matérialise physiquement les principes de la vision. Chaque boîte déposée sur l'établi devient un choix visible et ajustable dont on observe immédiatement les conséquences, permettant de comprendre ce qu'un algorithme décide de regarder et ce qu'il laisse dans l'ombre.

  #v(0.8em)
  #text(weight: "bold")[Un outil structurant pour concevoir des pipelines de vision]

  Pour le concepteur, VNStudio reproduit fidèlement la réalité de la création algorithmique tout en prévenant les erreurs classiques :

  - #strong[Visualisation de l'architecture :] Une chaîne de vision n'est qu'une succession d'opérations enchaînées. Les nœuds et leurs liaisons dessinent cette structure de manière claire et évidente.
  - #strong[Rigueur du flux de données :] Les connexions dans VNStudio sont #strong[strictement typées]. Il est impossible de brancher une image couleur à un port qui attend un masque binaire ou un scalaire. Cette contrainte force le concepteur, sans douleur, à savoir exactement ce qui circule à chaque étape du pipeline.
  - #strong[Le jumeau parfait du code :] Tout tourne en local, et le graphe tracé à la souris est déjà, trait pour trait, le programme que vous écririez en Python. Chaque nœud correspond à l'appel d'une fonction d'une grande bibliothèque (OpenCV, scikit-image, etc.) et chaque liaison au passage d'une variable.

  #v(0.8em)
  #text(weight: "bold")[Conclusion]

  Il ne faut pas s'y tromper : ce livre n'est pas un manuel de VNStudio, mais un manuel de vision par ordinateur, où le logiciel tient le rôle d'un simple établi. L'alliance du texte et de l'outil visuel crée cependant une méthode d'apprentissage redoutable.

  En étudiant ce livre à travers VNStudio, #strong[vous n'apprenez pas à tourner des boutons au hasard, mais à comprendre ce que chaque bouton mesure]. Le logiciel construit votre intuition géométrique et visuelle de manière immédiate, tandis que le livre vous enseigne la théorie et l'angle mort de chaque outil (ce qu'il sacrifie pour pouvoir fonctionner).

  Ensemble, ils vous enseignent que #strong[tout choix de représentation encode une hypothèse sur ce qui compte]. Vous apprenez à choisir le bon point de vue ou le bon espace mathématique qui rendra un problème complexe presque résolu. Une fois cette profonde compréhension acquise, VNStudio n'est plus qu'un « tremplin » : les concepts étant universels, l'objectif final est de vous mener à #strong[une autonomie totale] pour lire, écrire et réemployer ces architectures dans vos propres pipelines Python de haut niveau.

  #v(0.8em)
  #text(weight: "bold")[Télécharger VNStudio]

  #v(0.3em)
  Lien de téléchargement : #link("https://nikos-unilasalle.github.io/VisionNodes/")[nikos-unilasalle.github.io/VisionNodes]

  #v(0.2em)
  Code source (pour programmer vos propres nœuds) : #link("https://github.com/Nikos-Unilasalle/VisionNodes")[github.com/Nikos-Unilasalle/VisionNodes]

  #place(bottom + center)[
    #image("/typst/vnstudio_logo.png", width: 2.8cm)
  ]
]

#front-matter[
  #include "chapters/introduction.typ"
  #outline(title: [Table des matières], depth: 2, indent: 1em)
]

#main-matter[
  #include "chapters/chapitre1_descripteurs_forme.typ"
  #include "chapters/chapitre2_moments_image.typ"
  #include "chapters/chapitre3_distances_similarites.typ"
  #include "chapters/chapitre4_metriques_segmentation.typ"
  #include "chapters/chapitre5_filtrage_convolution.typ"
  #include "chapters/chapitre6_gradients_contours.typ"
  #include "chapters/chapitre7_couleur_photometrie.typ"
  #include "chapters/chapitre8_geometrie_camera.typ"
  #include "chapters/chapitre9_flot_optique.typ"
  #include "chapters/chapitre10_transformees.typ"
  #include "chapters/chapitre11_morphologie_mathematique.typ"
  #include "chapters/chapitre12_seuillage_segmentation.typ"
  #include "chapters/chapitre13_texture.typ"
  #include "chapters/chapitre14_qualite_image.typ"
  #include "chapters/chapitre15_apprentissage_profond.typ"
  #include "chapters/chapitre16_statistiques_robustes.typ"
  #include "chapters/chapitre17_descripteurs_locaux.typ"
]

#back-matter[
  #include "chapters/conclusion.typ"
]

#appendix[
  #include "chapters/annexe_A_lire_une_formule.typ"
]
