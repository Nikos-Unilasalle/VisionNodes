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
  show table.cell.where(y: 0): set text(weight: "bold", fill: white)
  set table(
    fill: (_, y) => if y == 0 {colors.primary} else if calc.odd(y) {colors.secondary.lighten(60%)},
    stroke: none
  )
  
  // Lists
  show: el.default-enum-list
  set list(marker: [#text(fill:colors.primary, size: 1.1em)[#sym.bullet]])
  set enum(numbering: n => text(fill:colors.primary)[#n.])
  
  // Footnotes
  set footnote.entry(separator: line(length: 30% + 0pt, stroke: 0.75pt + colors.primary))
  
  // References
  show ref: set text(fill: colors.primary)
  
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
  title: "Fondamentaux de la vision par ordinateur",
  author: "VNStudio",
  theme: theme1,
  lang: "fr",
  config-options: (open-right: false),
  title-page: [
    #set page(width: 19.05cm, height: 23.5cm, header: none, footer: none, margin: auto)
    #align(center + horizon)[
      #text(size: 2.6em, fill: rgb("#c1002a"), weight: "bold", font: "Roboto")[Fondamentaux de la vision par ordinateur]
      #v(1.2em)
      #text(size: 1.2em, fill: rgb("#334155"))[VNStudio]
    ]
  ],
)

#front-matter[
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
