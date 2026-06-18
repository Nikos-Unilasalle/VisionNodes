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

#let figtodo(id, desc) = figure(
  block(width: 100%, inset: 14pt, radius: 6pt,
    fill: luma(246), stroke: (dash: "dashed", thickness: 0.8pt, paint: luma(170)))[
    #align(center)[#text(fill: luma(110), style: "italic", size: 0.9em)[
      Figure à créer — #raw(id)\\
      #desc
    ]]
  ]
)

#let figfull(path) = block(above: 1em, below: 1.4em, width: 100%)[#image(path, width: 100%)]
#let canvas(body) = tip-box(title: "Dans VNStudio")[#body]

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
    if (FIG / fname).exists():
        return f'#figfull("/figures/{fname}")'
    return f'#figtodo("{fname}", [{inline(alt) if alt else "illustration"}])'

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
}

def section_illustration(sec_num):
    for ext in ("png", "jpeg", "jpg"):
        if (ILL / f"chap{sec_num}.{ext}").exists():
            return f'#figfull("/illustrations/chap{sec_num}.{ext}")'
    return None

def cover_image(ch_num):
    for ext in ("png", "jpeg", "jpg"):
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
    doc.append(f"#chapter(title: [{inline(title)}], toc: false)[\n")
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
    # patch book.typ includes
    book = (TYPST / "book.typ").read_text(encoding="utf-8")
    book = re.sub(r'#main-matter\[\n.*?\n\]', "#main-matter[\n" + "\n".join(includes) + "\n]", book, flags=re.S)
    (TYPST / "book.typ").write_text(book, encoding="utf-8")
    print("✓ book.typ includes mis à jour (17 chapitres V3)")

if __name__ == "__main__":
    main()
