#!/usr/bin/env python3
"""Convert VNStudio CV manual chapters from Markdown to Typst (bookly 4.0.0)."""

import re
import os
from pathlib import Path

BASE = Path(__file__).parent.parent
CHAPTERS_DIR = BASE / "chapitres"
OUTPUT_DIR = Path(__file__).parent

CHAPTER_ORDER = [
    "chapitre1_descripteurs_forme.md",
    "chapitre_moments_image.md",
    "chapitre_distances_similarites.md",
    "chapitre4_metriques_segmentation.md",
    "chapitre5_filtrage_convolution.md",
    "chapitre6_gradients_contours.md",
    "chapitre7_couleur_photometrie.md",
    "chapitre8_geometrie_camera.md",
    "chapitre9_flot_optique.md",
    "chapitre10_transformees.md",
    "chapitre_morphologie_mathematique.md",
    "chapitre12_seuillage_segmentation.md",
    "chapitre13_texture.md",
    "chapitre14_qualite_image.md",
    "chapitre15_apprentissage_profond.md",
    "chapitre16_statistiques_robustes.md",
]

# Labels → (typst-function, display-title)
BOXED_LABELS = {
    "Définition":                  ("info-box",      "Définition"),
    "Piège d'implémentation":      ("important-box", "Piège d'implémentation"),
    "Pièges d'implémentation":     ("important-box", "Piège d'implémentation"),
    "Piège":                       ("important-box", "Piège d'implémentation"),
    "Exemple numérique":           ("question-box",  "Exemple numérique"),
    "Code Python":                 ("proof-box",     "Code Python"),
}

# ── inline conversion ────────────────────────────────────────────────────────

_B_OPEN  = "\x00B\x01"
_B_CLOSE = "\x00b\x01"
_I_OPEN  = "\x00I\x01"
_I_CLOSE = "\x00i\x01"

def clean_inline(text: str) -> str:
    # Strip footnote refs like " 1\" "2,3\" etc.
    text = re.sub(r'\s+\d+(?:,\s*\d+)*\\(?=\s|$)', '', text)
    # Unescape all markdown/latex backslash escapes
    text = re.sub(r'\\([()[\].\\,;:\-*#@<>{}|])', r'\1', text)
    
    # Protect backticked inline code blocks from formatting replacements
    code_blocks = []
    def protect_code(m):
        code_blocks.append(m.group(0))
        return f"\x00C{len(code_blocks)-1}\x01"
    
    text = re.sub(r'`[^`\n]+`', protect_code, text)
    
    # Escape Typst special chars in plain text
    text = text.replace('@', r'\@').replace('<', r'\<')
    # Escape literal brackets (used as math notation) so they don't break content delimiters
    text = text.replace('[', r'\[').replace(']', r'\]')
    # Protect bold **text** with placeholders before escaping *
    text = re.sub(r'\*\*([^*\n]+)\*\*', lambda m: _B_OPEN + m.group(1) + _B_CLOSE, text)
    # Protect italic *text* with placeholders
    text = re.sub(r'(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)',
                  lambda m: _I_OPEN + m.group(1) + _I_CLOSE, text)
    # Escape remaining literal * (multiplication signs, etc.)
    text = text.replace('*', r'\*')
    # Restore Typst bold/italic from placeholders
    text = (text
            .replace(_B_OPEN, '*').replace(_B_CLOSE, '*')
            .replace(_I_OPEN, '_').replace(_I_CLOSE, '_'))
            
    # Restore protected code blocks
    def restore_code(m):
        idx = int(m.group(1))
        return code_blocks[idx]
        
    text = re.sub(r'\x00C(\d+)\x01', restore_code, text)
    return text


def clean_heading_title(title: str) -> str:
    # Strip leading section numbers like 1.1, 1.1.1, etc.
    title = re.sub(r'^\d+(?:\.\d+)*\.?\s*', '', title)
    # Strip "Encadré final" / "Encadré" prefix
    title = re.sub(r'^Encadré\s*(final\s*)?[—–-]?\s*', '', title, flags=re.IGNORECASE).strip()
    return clean_inline(title)



# ── table conversion ─────────────────────────────────────────────────────────

def convert_table(lines: list[str]) -> str:
    if len(lines) < 2:
        return "\n".join(lines)
    headers = [c.strip() for c in re.split(r'(?<!\\)\|', lines[0].strip("|"))]
    ncols = len(headers)
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in re.split(r'(?<!\\)\|', line.strip("|"))]
        while len(cells) < ncols:
            cells.append("")
        rows.append(cells)

    out = ["#table(", f"  columns: {ncols},", "  table.header("]
    out.append("    " + ", ".join(f"[*{clean_inline(h)}*]" for h in headers))
    out.append("  ),")
    for row in rows:
        out.append("  " + ", ".join(f"[{clean_inline(c)}]" for c in row) + ",")
    out.append(")")
    return "\n".join(out)


# ── chapter title extraction ──────────────────────────────────────────────────

def extract_title(content: str) -> str:
    m = re.search(r'^#\s+Chapitre\s*[—–-]\s*(.+?)(?:\s*:\s*dérivations.*)?$',
                  content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    m = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    return m.group(1).strip() if m else "Chapitre"


# ── main converter ───────────────────────────────────────────────────────────

class Converter:
    def __init__(self):
        self.output: list[str] = []
        # code block state
        self.in_code = False
        self.code_lang = ""
        self.code_buf: list[str] = []
        # table state
        self.in_table = False
        self.table_buf: list[str] = []
        # labeled box state
        self.box_func: str | None = None
        self.box_title: str = ""
        self.box_buf: list[str] = []
        # encadré state (tip-box wrapping entire section)
        self.encadre = False
        self.encadre_title = ""
        self.encadre_buf: list[str] = []

    # ── emit helpers ──────────────────────────────────────────────────────────

    def emit(self, line: str):
        if self.encadre:
            self.encadre_buf.append(line)
        elif self.box_func:
            self.box_buf.append(line)
        else:
            self.output.append(line)

    def flush_box(self):
        if not self.box_func:
            return
        content = "\n".join(self.box_buf).rstrip()
        if self.box_func == "proof-box":
            block = f'#proof-box(title: "{self.box_title}")[\n{content}\n]'
        else:
            block = f'#{self.box_func}(title: "{self.box_title}")[\n{content}\n]'
        # emit to encadre or output
        if self.encadre:
            self.encadre_buf.append(block)
        else:
            self.output.append(block)
        self.box_func = None
        self.box_title = ""
        self.box_buf = []

    def flush_encadre(self):
        if not self.encadre:
            return
        content = "\n".join(self.encadre_buf).rstrip()
        self.output.append(
            f'#tip-box(title: "{self.encadre_title}")[\n{content}\n]'
        )
        self.encadre = False
        self.encadre_title = ""
        self.encadre_buf = []

    def flush_table(self):
        if not self.in_table:
            return
        block = convert_table(self.table_buf)
        self.emit(block)
        self.in_table = False
        self.table_buf = []

    # ── line processing ───────────────────────────────────────────────────────

    def process(self, line: str):
        # ── fenced code block ──────────────────────────────────────────────
        if line.startswith("```"):
            if self.in_code:
                code = "\n".join(self.code_buf)
                lang = self.code_lang
                raw = f"```{lang}\n{code}\n```" if lang else f"```\n{code}\n```"
                self.in_code = False
                self.code_buf = []
                self.code_lang = ""
                self.emit(raw)
            else:
                self.flush_table()
                self.in_code = True
                self.code_lang = line[3:].strip()
            return
        if self.in_code:
            self.code_buf.append(line)
            return

        # ── table ──────────────────────────────────────────────────────────
        if line.startswith("|"):
            # skip pure separator lines
            if re.match(r'^[\|\s\-:]+$', line):
                if self.in_table:
                    self.table_buf.append(line)
                return
            if not self.in_table:
                self.in_table = True
            self.table_buf.append(line)
            return
        elif self.in_table:
            self.flush_table()

        # ── horizontal rule ────────────────────────────────────────────────
        if line.strip() in ("---", "***", "___"):
            self.emit("#line(length: 100%)")
            return

        # ── chapter title (h1) ─────────────────────────────────────────────
        if line.startswith("# "):
            return  # handled by convert_chapter()

        # ── h2 ─────────────────────────────────────────────────────────────
        if line.startswith("## "):
            self.flush_box()
            title = line[3:].strip()
            if re.match(r'Encadré', title):
                self.flush_encadre()
                nice = re.sub(r'^Encadré\s*(final\s*)?[—–-]?\s*', '', title).strip()
                self.encadre = True
                self.encadre_title = nice if nice else "Fil conducteur"
            else:
                self.flush_encadre()
                self.output.append(f"== {clean_heading_title(title)}")
            return

        # ── h3 ─────────────────────────────────────────────────────────────
        if line.startswith("### "):
            self.flush_box()
            self.flush_encadre()
            self.output.append(f"== {clean_heading_title(line[4:].strip())}")
            return

        # ── h4 (main content sections) ─────────────────────────────────────
        if line.startswith("#### "):
            self.flush_box()
            self.flush_encadre()
            self.output.append(f"== {clean_heading_title(line[5:].strip())}")
            return

        # ── labeled block (**Label**content or **Label**  \n content) ──────
        m = re.match(r'^\*\*([^*\n]+)\*\*\s*(.*)', line)
        if m:
            label = m.group(1).strip()
            rest  = m.group(2).strip()
            self.flush_box()
            if label in BOXED_LABELS:
                func, display = BOXED_LABELS[label]
                self.box_func  = func
                self.box_title = display
                if rest:
                    self.box_buf.append(clean_inline(rest))
            else:
                converted = f"*{clean_inline(label)}*"
                if rest:
                    converted += " " + clean_inline(rest)
                self.emit(converted)
            return

        # ── blank line ─────────────────────────────────────────────────────
        if line.strip() == "":
            self.emit("")
            return

        # ── regular paragraph line ─────────────────────────────────────────
        self.emit(clean_inline(line))

    def finalize(self):
        self.flush_box()
        self.flush_table()
        self.flush_encadre()
        if self.in_code:
            raw = f"```{self.code_lang}\n" + "\n".join(self.code_buf) + "\n```"
            self.output.append(raw)

    def run(self, content: str) -> str:
        for line in content.splitlines():
            self.process(line)
        self.finalize()
        return "\n".join(self.output)


# ── file-level entry points ──────────────────────────────────────────────────

def convert_chapter(md_path: Path, out_path: Path):
    text = md_path.read_text(encoding="utf-8")
    title = extract_title(text)
    body  = Converter().run(text)
    header = '#import "@preview/bookly:4.0.0": *\n\n'
    out_path.write_text(f"{header}#chapter(title: [{clean_inline(title)}])[\n{body}\n]\n",
                        encoding="utf-8")
    print(f"  ✓  {md_path.name}")


BOOK_TEMPLATE = '''\
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
        #text(size: 1.1em, fill: colors.primary, weight: "bold", font: "Helvetica Neue")[#upper(type-chapter)]
        #v(0.3em)
        #text(size: 2.5em, weight: "bold", fill: rgb("#1e293b"), font: "Georgia")[#it.body]
      ],
      [
        #text(size: 6.5em, weight: "light", fill: colors.primary.lighten(80%), font: "Georgia")[#counter(heading).display(states.num-heading.get())]
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
            text(weight: "bold", fill: colors.primary, font: "Helvetica Neue")[#counter(heading).display()]
            h(0.3em)
          }
          #text(weight: "bold", fill: rgb("#1e293b"), font: "Helvetica Neue")[#it.body]
        ]
      )
    ]
  }
  
  // Level 3 heading
  show heading.where(level: 3): it => {
    block(above: 1.4em, below: 0.8em)[
      #if it.numbering != none {
        text(weight: "bold", fill: colors.primary.lighten(20%), font: "Helvetica Neue")[#counter(heading).display()]
        h(0.3em)
      }
      #text(weight: "bold", fill: rgb("#334155"), font: "Helvetica Neue")[#it.body]
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
    paper: paper-size,
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
)

#front-matter[
  #tableofcontents
]

#main-matter[
{includes}
]
'''

def main():
    chapters_out = OUTPUT_DIR / "chapters"
    chapters_out.mkdir(parents=True, exist_ok=True)

    includes = []
    for fname in CHAPTER_ORDER:
        md = CHAPTERS_DIR / fname
        if not md.exists():
            print(f"  ⚠  {fname} introuvable, ignoré")
            continue
        stem = md.stem
        out  = chapters_out / f"{stem}.typ"
        convert_chapter(md, out)
        includes.append(f'  #include "chapters/{stem}.typ"')

    book = BOOK_TEMPLATE.replace("{includes}", "\n".join(includes))
    (OUTPUT_DIR / "book.typ").write_text(book, encoding="utf-8")
    print("\n✓  book.typ généré")
    print(f"→  cd '{OUTPUT_DIR}' && typst compile book.typ")


if __name__ == "__main__":
    main()
