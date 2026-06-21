#!/usr/bin/env python3
"""Génère les .typ (template ch1) depuis les chapitres V3. Figures pleine largeur,
placeholder figtodo si absente. Markdown V3 -> Typst bookly 4.0.0."""
import re
from pathlib import Path

TYPST = Path(__file__).parent
BASE = TYPST.parent
SRC = BASE / "chapitres V3"
FIG = BASE / "figures"
ILL = BASE / "illustrations"
OUT = TYPST / "chapters"

ORDER = [
    "chapitre1_descripteurs_forme.md", "chapitre2_moments_image.md",
    "chapitre3_distances_similarites.md", "chapitre4_metriques_segmentation.md",
    "chapitre5_filtrage_convolution.md", "chapitre6_gradients_contours.md",
    "chapitre7_couleur_photometrie.md", "chapitre8_geometrie_camera.md",
    "chapitre9_flot_optique.md", "chapitre10_transformees.md",
    "chapitre11_morphologie_mathematique.md", "chapitre12_seuillage_segmentation.md",
    "chapitre13_texture.md", "chapitre14_qualite_image.md",
    "chapitre15_apprentissage_profond.md", "chapitre16_statistiques_robustes.md",
    "chapitre17_descripteurs_locaux.md",
]

HEADER = '''#import "@preview/bookly:4.0.0": *

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

'''

# ── inline ────────────────────────────────────────────────────────────────
_B, _b, _I, _i = "\x00B\x01", "\x00b\x01", "\x00I\x01", "\x00i\x01"

def inline(text: str) -> str:
    text = re.sub(r'\\([()\[\].\\,;:\-*#@<>{}|])', r'\1', text)
    codes = []
    text = re.sub(r'`[^`\n]+`', lambda m: codes.append(m.group(0)) or f"\x00C{len(codes)-1}\x01", text)
    text = text.replace('@', r'\@').replace('<', r'\<')
    text = text.replace('[', r'\[').replace(']', r'\]')
    text = re.sub(r'\*\*([^*\n]+)\*\*', lambda m: _B + m.group(1) + _b, text)
    text = re.sub(r'(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)', lambda m: _I + m.group(1) + _i, text)
    text = text.replace('*', r'\*')
    text = text.replace(_B, '*').replace(_b, '*').replace(_I, '_').replace(_i, '_')
    text = re.sub(r'\x00C(\d+)\x01', lambda m: codes[int(m.group(1))], text)
    return text

def strip_num(title: str) -> str:
    title = re.sub(r'^\d+(?:\.\d+)*\s*[—–-]?\s*', '', title)
    return title.strip()

# ── table ──────────────────────────────────────────────────────────────────
def conv_table(lines):
    headers = [c.strip() for c in re.split(r'(?<!\\)\|', lines[0].strip('|'))]
    n = len(headers)
    rows = []
    for ln in lines[2:]:
        cells = [c.strip() for c in re.split(r'(?<!\\)\|', ln.strip('|'))]
        cells += [''] * (n - len(cells))
        rows.append(cells[:n])
    out = ["#table(", f"  columns: {n},", "  table.header(",
           "    " + ", ".join(f"[*{inline(h)}*]" for h in headers), "  ),"]
    for r in rows:
        out.append("  " + ", ".join(f"[{inline(c)}]" for c in r) + ",")
    out.append(")")
    return "\n".join(out)

# ── render a block of md lines (no headings) into typst body ────────────────
def render_block(lines):
    out, i, n = [], 0, len(lines)
    while i < n:
        ln = lines[i]
        # headings (## -> ==, ### -> ===, #### -> ====)
        mh = re.match(r'^(#{2,4})\s+(.*)', ln)
        if mh:
            lvl = len(mh.group(1))
            out.append("=" * lvl + " " + inline(strip_num(mh.group(2).strip())))
            i += 1
            continue
        # fenced code
        if ln.startswith("```"):
            lang = ln[3:].strip()
            buf = []
            i += 1
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            body = "\n".join(buf)
            out.append("```" + (lang if lang else "") + "\n" + body + "\n```")
            continue
        # table
        if ln.startswith("|"):
            buf = []
            while i < n and lines[i].startswith("|"):
                buf.append(lines[i]); i += 1
            out.append(conv_table(buf))
            continue
        # blockquote
        if ln.startswith(">"):
            buf = []
            while i < n and (lines[i].startswith(">") or (buf and lines[i].strip() and not lines[i].startswith(("#", "|", "```")))):
                buf.append(re.sub(r'^>\s?', '', lines[i])); i += 1
            qbody = "\n".join(x for x in buf).strip()
            m = re.match(r'^\*\*([^*]+)\*\*\s*(.*)', qbody, re.S)
            if m:
                title = inline(m.group(1).strip().rstrip(':').strip())
                rest = inline(m.group(2).strip())
                out.append(f'#info-box(title: "{title}")[\n{rest}\n]')
            else:
                out.append(f'#quote(block: true)[{inline(qbody)}]')
            continue
        # list items
        if re.match(r'^\s*[-*]\s+', ln):
            out.append("- " + inline(re.sub(r'^\s*[-*]\s+', '', ln)))
            i += 1
            continue
        if re.match(r'^\s*\d+\.\s+', ln):
            while i < n and re.match(r'^\s*\d+\.\s+', lines[i]):
                out.append("+ " + inline(re.sub(r'^\s*\d+\.\s+', '', lines[i]))); i += 1
            continue
        if ln.strip() == "":
            out.append(""); i += 1; continue
        # bold-label line **X** rest  -> *X* rest
        out.append(inline(ln)); i += 1
    return "\n".join(out).strip()

# ── figure handling ─────────────────────────────────────────────────────────
def emit_figure(alt, path):
    fname = path.split("/")[-1]
    stem = fname.rsplit(".", 1)[0]
    if (FIG / fname).exists():
        return f'#figfull("/figures/{fname}")'
    return f'#figtodo("{stem}", [{inline(alt) if alt else "illustration"}])'

# figures obs existantes mais non référencées dans le markdown → placées par section
SECTION_FIG = {
    ("2", "2.3"): ["fig_ch2_obs2_mu30_asymmetry.pdf"],
    ("3", "3.1"): ["fig_ch3_obs3_lp_balls.pdf"],
    ("3", "3.2"): ["fig_ch3_obs1_mahalanobis.pdf"],
    ("3", "3.5"): ["fig_ch3_obs2_wasserstein_chi2.pdf"],
    ("4", "4.4"): ["fig_ch4_obs1_pr_curve.pdf", "fig_ch4_obs2_ap_area.pdf"],
    ("5", "5.1"): ["fig_ch5_obs3_conv_vs_corr.pdf"],
    ("5", "5.3"): ["fig_ch5_obs1_dog_bandpass.pdf"],
    ("5", "5.5"): ["fig_ch5_obs2_gabor.pdf"],
    ("6", "6.3"): ["fig_ch6_obs3_canny_nms.pdf"],
    ("6", "6.4"): ["fig_ch6_obs1_structure_tensor.pdf"],
    ("7", "7.3"): ["fig_ch7_obs2_deltaE.pdf"],
    ("7", "7.6"): ["fig_ch7_obs1_gamma.pdf", "fig_ch7_obs3_white_balance.pdf"],
    ("9", "9.4"): ["fig_ch9_obs2_horn_schunck.pdf"],
    # ch13 — texture
    ("13", "13.2"): ["fig_ch13_obs1_glcm.svg"],
    ("13", "13.4"): ["fig_ch13_obs2_lbp.svg"],
    ("13", "13.5"): ["fig_ch13_obs3_gabor.svg"],
    # ch14 — qualité image
    ("14", "14.2"): ["fig_ch14_obs1_mse_shift.svg"],
    ("14", "14.3"): ["fig_ch14_obs2_ssim.svg"],
    ("14", "14.5"): ["fig_ch14_obs3_sharpness.svg"],
    # ch15 — apprentissage profond
    ("15", "15.1"): ["fig_ch15_obs1_crossentropy.svg"],
    ("15", "15.5"): ["fig_ch15_obs2_giou.svg"],
    # ch16 — statistiques robustes
    ("16", "16.1"): ["fig_ch16_obs1_median.svg"],
    ("16", "16.3"): ["fig_ch16_obs2_mestimators.svg"],
    ("16", "16.5"): ["fig_ch16_obs3_ransac.svg"],
    # ch17 — descripteurs locaux
    ("17", "17.1"): ["fig_ch17_01_ssd_vs_descripteur.svg"],
    ("17", "17.2"): ["fig_ch17_02_echelle_caracteristique.svg"],
    ("17", "17.3"): ["fig_ch17_03_hog_glyphes.svg"],
    ("17", "17.4"): ["fig_ch17_04_sift_orientation.svg"],
}

def section_illustration(sec_num):
    for ext in ("png", "jpeg", "jpg"):
        if (ILL / f"chap{sec_num}.{ext}").exists():
            return f'#figfull("/illustrations/chap{sec_num}.{ext}")'
    return None

SHORT_TITLE = {
    "1":  "Décrire une forme",
    "2":  "Les moments d'image",
    "3":  "Distances et similarités",
    "4":  "Métriques de segmentation",
    "5":  "Filtrage et convolution",
    "6":  "Gradients et contours",
    "7":  "Couleur et photométrie",
    "8":  "Géométrie de la caméra",
    "9":  "Le flot optique",
    "10": "Les transformées",
    "11": "Morphologie mathématique",
    "12": "Seuillage et segmentation",
    "13": "La texture",
    "14": "Mesure de qualité",
    "15": "Fonctions de coût",
    "16": "Statistiques robustes",
    "17": "Descripteurs locaux",
}

def cover_image(ch_num):
    for ext in ("jpeg", "jpg", "png"):
        p = ILL / f"chap{ch_num}.{ext}"
        if p.exists():
            return f'#block(above: 0pt, below: 2em, width: 100%)[#image("/illustrations/chap{ch_num}.{ext}", width: 100%)]'
    return f'#figtodo("chap{ch_num}", [Illustration de couverture du chapitre {ch_num}])'

# ── section (### ...) categorisation ────────────────────────────────────────
def render_subsection(title, body_lines):
    t = title.strip()
    low = t.lower()
    body = render_block(body_lines)
    if low.startswith("exemple"):
        return f'#question-box(title: "{inline(t)}")[\n{body}\n]'
    if low.startswith("piège"):
        return f'#warning-box(title: "{inline(t)}")[\n{body}\n]'
    if low.startswith("dans vnstudio"):
        return f'#canvas[\n{body}\n]'
    if low.split(" ")[0] in ("subtilité", "différence", "réglage", "limite", "sensibilité", "domaine", "paramètres"):
        return f'#info-box(title: "{inline(t)}")[\n{body}\n]'
    if low == "la formule" or low.startswith("la formule") or low.startswith("les formule") or "et la formule" in low:
        # info-box autour des blocs de code ; prose autour, dans l'ordre
        parts, i, n = [], 0, len(body_lines)
        while i < n:
            if body_lines[i].startswith("```"):
                buf = []; i += 1
                while i < n and not body_lines[i].startswith("```"):
                    buf.append(body_lines[i]); i += 1
                i += 1
                code = "\n".join(buf)
                parts.append(f'#info-box(title: "{inline(t)}")[\n```\n{code}\n```\n]')
            else:
                buf = []
                while i < n and not body_lines[i].startswith("```"):
                    buf.append(body_lines[i]); i += 1
                seg = render_block(buf)
                if seg:
                    parts.append(seg)
        return "\n\n".join(parts)
    # heading ordinaire
    return f'=== {inline(t)}\n{body}'

# ── chapter ─────────────────────────────────────────────────────────────────
def convert(md_path: Path) -> str:
    raw = md_path.read_text(encoding="utf-8").split("\n")
    ch_num = re.search(r'chapitre(\d+)', md_path.stem).group(1)
    # title
    title = "Chapitre"
    for l in raw:
        m = re.match(r'^#\s+Chapitre\s*\d*\s*[—–-]\s*(.+)$', l)
        if m:
            title = m.group(1).strip(); break
    # cover caption = first italic line after the cover image
    caption = ""
    for idx, l in enumerate(raw):
        if l.startswith("!["):
            for j in range(idx + 1, min(idx + 4, len(raw))):
                s = raw[j].strip()
                if s.startswith("*") and s.endswith("*") and len(s) > 2:
                    caption = s.strip("*").strip(); break
            break

    # locate body start: after the first '---' that follows the chapeau
    # build a linear token stream skipping the H1, cover image, caption, and chapeau '---'
    body = []
    i, n = 0, len(raw)
    # skip until after first '---'
    while i < n and raw[i].strip() != "---":
        i += 1
    i += 1  # past the chapeau separator
    # intro paragraphs until first '## '
    intro = []
    while i < n and not raw[i].startswith("## "):
        intro.append(raw[i]); i += 1
    # strip stray cover refs / captions from intro
    intro = [x for x in intro if not x.startswith("![") and not (x.strip().startswith("*") and x.strip().endswith("*"))]
    intro_typ = render_block(intro)

    # process sections
    sections = []
    while i < n:
        line = raw[i]
        if line.startswith("## "):
            sec_title = line[3:].strip()
            i += 1
            sec_lines = []
            while i < n and not raw[i].startswith("## "):
                sec_lines.append(raw[i]); i += 1
            sections.append((sec_title, sec_lines))
        else:
            i += 1

    parts = []
    for sec_title, sec_lines in sections:
        low = sec_title.lower()
        if low.startswith("figures à créer"):
            continue  # artefact d'auteur, non imprimé
        clean_title = strip_num(re.sub(r'^Encadré\s*(final\s*)?\s*[—–-]?\s*', '', sec_title, flags=re.I))
        parts.append("// " + "=" * 60)
        parts.append(f"== {inline(clean_title)}")
        # within a section: optional subtitle (> *metaphor* OR italic line), inline figs, ### subsections
        j, m = 0, len(sec_lines)
        # leading subtitle: a '> *...*' or blockquote-italic right after heading
        # collect content until first ### into "lead"
        lead = []
        while j < m and not sec_lines[j].startswith("### "):
            lead.append(sec_lines[j]); j += 1
        # extract subtitle from lead (first '> *...*' or '> ...')
        lead2 = []
        sub_done = False
        k = 0
        while k < len(lead):
            s = lead[k].strip()
            if not sub_done and s.startswith(">"):
                q = re.sub(r'^>\s?', '', lead[k]).strip().strip("*").strip()
                parts.append(f"#subtitle[{inline(q)}]")
                sub_done = True; k += 1; continue
            lead2.append(lead[k]); k += 1
        # illustration de section (chapX.Y) + figure obs mappée
        sec_num_m = re.match(r'^(\d+\.\d+)', sec_title)
        if sec_num_m:
            sec_num = sec_num_m.group(1)
            illo = section_illustration(sec_num)
            if illo:
                parts.append(illo)
            for fig in SECTION_FIG.get((ch_num, sec_num), []):
                if (FIG / fig).exists():
                    parts.append(f'#figfull("/figures/{fig}")')
        # inline figures + prose in lead2
        kk = 0
        buf = []
        def flush_buf():
            if buf:
                seg = render_block(buf)
                if seg: parts.append(seg)
                buf.clear()
        while kk < len(lead2):
            mfig = re.match(r'^!\[([^]]*)\]\(\.\./figures/([^)]+)\)', lead2[kk].strip())
            if mfig:
                flush_buf()
                parts.append(emit_figure(mfig.group(1), mfig.group(2)))
            else:
                buf.append(lead2[kk])
            kk += 1
        flush_buf()
        # ### subsections
        while j < m:
            assert sec_lines[j].startswith("### ")
            sub_title = sec_lines[j][4:].strip()
            j += 1
            sub_lines = []
            while j < m and not sec_lines[j].startswith("### "):
                sub_lines.append(sec_lines[j]); j += 1
            # pull inline figures out of sub_lines, render rest
            # (figures inside subsections are rare; handle inline)
            parts.append(render_subsection(sub_title, sub_lines))

    body_typ = "\n\n".join(parts)

    doc = [HEADER]
    short = SHORT_TITLE.get(ch_num, title)
    doc.append(f"#chapter(title: [{inline(short)}], toc: false)[\n")
    doc.append(cover_image(ch_num))
    doc.append("\n#pagebreak()")
    doc.append('#block(above: 0em, below: 1em)[')
    doc.append('  #grid(columns: (auto, 1fr), column-gutter: 0.6em, align: horizon,')
    doc.append('    box(width: 3pt, height: 1.2em, fill: rgb("#c1002a"), radius: 1.5pt),')
    doc.append('    text(weight: "bold", font: "Roboto", fill: rgb("#1e293b"))[Table des matières])')
    doc.append(']')
    doc.append('#suboutline(target: heading.where(outlined: true, level: 2))')
    doc.append('#pagebreak()\n')
    if caption:
        doc.append(f"#subtitle[{inline(caption)}]\n")
    if intro_typ:
        doc.append(intro_typ + "\n")
    doc.append(body_typ)
    doc.append("\n]\n")
    return "\n".join(doc)

def convert_prose(md_path: Path) -> str:
    """Convertit introduction.md ou conclusion.md → Typst sans #chapter numéroté."""
    raw = md_path.read_text(encoding="utf-8").split("\n")
    parts = []
    title_rendered = False
    i = 0
    while i < len(raw):
        line = raw[i]
        # Skip leading cover image / italic caption
        if line.startswith("![") or (line.startswith("*") and line.endswith("*") and i < 5):
            i += 1; continue
        # h1 → titre personnalisé (pas de #heading pour éviter numérotation bookly)
        m1 = re.match(r'^#\s+(.+)$', line)
        if m1 and not line.startswith('##'):
            raw_title = m1.group(1).strip()
            # Strip "Introduction —" / "Conclusion —" prefixes
            raw_title = re.sub(r'^(Introduction|Conclusion)\s*[—–-]\s*', '', raw_title, flags=re.I).strip()
            # Capitalize first letter
            display = raw_title[0].upper() + raw_title[1:] if raw_title else raw_title
            parts.append(
                '#v(2em)\n'
                '#block(breakable: false)[\n'
                f'  #text(size: 2.2em, weight: "bold", fill: rgb("#1e293b"), font: "Roboto")[{inline(display)}]\n'
                '  #v(0.4em)\n'
                '  #line(length: 100%, stroke: 1.5pt + rgb("#c1002a"))\n'
                ']\n'
                '#v(1.5em)'
            )
            title_rendered = True
            i += 1; continue
        # h2 → ==
        m2 = re.match(r'^##\s+(.+)$', line)
        if m2:
            parts.append(f'== {inline(strip_num(m2.group(1).strip()))}\n')
            i += 1; continue
        # h3 → ===
        m3 = re.match(r'^###\s+(.+)$', line)
        if m3:
            parts.append(f'=== {inline(strip_num(m3.group(1).strip()))}\n')
            i += 1; continue
        # horizontal rule
        if re.match(r'^---+$', line.strip()):
            i += 1; continue
        # blockquote → info-box
        if line.startswith('> '):
            bq = [line[2:]]
            i += 1
            while i < len(raw) and raw[i].startswith('> '):
                bq.append(raw[i][2:]); i += 1
            parts.append(f'#info-box[\n{render_block(bq)}\n]')
            continue
        # bullet list
        if re.match(r'^[-*]\s+', line):
            items = []
            while i < len(raw) and re.match(r'^[-*]\s+', raw[i]):
                items.append(f'- {inline(re.sub(r"^[-*]\s+","",raw[i]))}')
                i += 1
            parts.append('\n'.join(items))
            continue
        # paragraph
        para = []
        while i < len(raw) and raw[i].strip() and not raw[i].startswith('#') and not raw[i].startswith('>') and not raw[i].startswith('- ') and not raw[i].startswith('* ') and not re.match(r'^---+$', raw[i].strip()):
            para.append(raw[i]); i += 1
        if para:
            parts.append(inline(' '.join(para)))
            continue
        i += 1
    return HEADER + '\n\n'.join(p for p in parts if p.strip()) + '\n'


def main():
    OUT.mkdir(exist_ok=True)
    includes = []
    for fn in ORDER:
        md = SRC / fn
        if not md.exists():
            print("  ⚠ absent:", fn); continue
        typ = convert(md)
        outp = OUT / (md.stem + ".typ")
        outp.write_text(typ, encoding="utf-8")
        includes.append(f'  #include "chapters/{md.stem}.typ"')
        print("  ✓", fn)
    # intro + conclusion
    for prose_fn in ("introduction.md", "conclusion.md"):
        md = SRC / prose_fn
        if md.exists():
            typ = convert_prose(md)
            outp = OUT / (md.stem + ".typ")
            outp.write_text(typ, encoding="utf-8")
            print("  ✓", prose_fn)
    # patch book.typ includes
    book = (TYPST / "book.typ").read_text(encoding="utf-8")
    book = re.sub(r'#main-matter\[\n.*?\n\]', "#main-matter[\n" + "\n".join(includes) + "\n]", book, flags=re.S)
    (TYPST / "book.typ").write_text(book, encoding="utf-8")
    print("✓ book.typ includes mis à jour (17 chapitres V3)")

if __name__ == "__main__":
    main()
