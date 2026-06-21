#import "@preview/bookly:4.0.0": *
#import "@preview/hydra:0.6.2": hydra

#let option1-theme-func(colors: default-colors, it) = {
  show heading.where(level: 1): it => context {
    pagebreak(weak: true)
    reset-counters
    let type-chapter = if states.isappendix.get() { states.localization.get().appendix } else { states.localization.get().chapter }
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
      [#text(size: 6.5em, weight: "light", fill: colors.primary.lighten(80%), font: "Roboto")[#counter(heading).display(states.num-heading.get())]]
    )
    v(0.5em)
    line(length: 100%, stroke: 1.5pt + colors.primary)
    v(1.5em)
  }
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
  show heading.where(level: 3): it => {
    block(above: 1.4em, below: 0.8em)[
      #if it.numbering != none {
        text(weight: "bold", fill: colors.primary.lighten(20%), font: "Roboto")[#counter(heading).display()]
        h(0.3em)
      }
      #text(weight: "bold", fill: rgb("#334155"), font: "Roboto")[#it.body]
    ]
  }
  it
}

#let theme1 = modern + (theme: option1-theme-func)

#show: bookly.with(
  title: "Chapitre 1",
  author: "VNStudio",
  theme: theme1,
  lang: "fr",
  title-page: [],
  config-options: (open-right: false),
)

#main-matter[
  #include "/typst/chapters/chapitre1_descripteurs_forme.typ"
]
