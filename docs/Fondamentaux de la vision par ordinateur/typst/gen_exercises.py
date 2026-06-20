#!/usr/bin/env python3
"""
gen_exercises.py — Appends exercises from exercices_chN_*.md to existing chapter .typ files.
Safe: never rewrites chapter content, only appends the exercise section.
If the chapter already contains '// EXERCICES', the section is replaced.
"""
import re
from pathlib import Path

TYPST = Path(__file__).parent
BASE  = TYPST.parent
SRC   = BASE / "chapitres V3"
FIG   = BASE / "figures"
OUT   = TYPST / "chapters"

CHAPTER_FILES = {int(re.search(r'chapitre(\d+)', p.stem).group(1)): p
                 for p in OUT.glob("chapitre*.typ")}

# ── inline markdown → typst ──────────────────────────────────────────────────
_B, _b, _I, _i = "\x00B\x01", "\x00b\x01", "\x00I\x01", "\x00i\x01"

def inline(text: str) -> str:
    text = re.sub(r'\\([()\[\].\\,;:\-*#@<>{}|])', r'\1', text)
    codes = []
    text = re.sub(r'`[^`\n]+`',
                  lambda m: codes.append(m.group(0)) or f"\x00C{len(codes)-1}\x01", text)
    text = text.replace('@', r'\@').replace('<', r'\<')
    text = text.replace('[', r'\[').replace(']', r'\]')
    text = re.sub(r'\*\*([^*\n]+)\*\*', lambda m: _B + m.group(1) + _b, text)
    text = re.sub(r'(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)',
                  lambda m: _I + m.group(1) + _i, text)
    text = text.replace('*', r'\*')
    text = text.replace(_B, '*').replace(_b, '*').replace(_I, '_').replace(_i, '_')
    text = re.sub(r'\x00C(\d+)\x01', lambda m: codes[int(m.group(1))], text)
    return text

def emit_figure(alt: str, path: str) -> str:
    fname = Path(path).name
    if (FIG / fname).exists():
        return f'#figfull("/figures/{fname}")'
    # missing image → pink "IMAGE" box showing the file name to use
    return f'#figtodo("{Path(path).stem}", [{inline(alt[:80])}])'

# ── render a block of md lines ───────────────────────────────────────────────
def render_block(lines: list[str]) -> str:
    out, i, n = [], 0, len(lines)
    while i < n:
        ln = lines[i]
        # image
        m = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)', ln)
        if m:
            out.append(emit_figure(m.group(1), m.group(2)))
            i += 1
            continue
        # fenced code
        if ln.startswith("```"):
            lang = ln[3:].strip()
            buf = []; i += 1
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append("```" + (lang if lang else "") + "\n" + "\n".join(buf) + "\n```")
            continue
        # table
        if ln.startswith("|"):
            buf = []
            while i < n and lines[i].startswith("|"):
                buf.append(lines[i]); i += 1
            headers = [c.strip() for c in re.split(r'(?<!\\)\|', buf[0].strip('|'))]
            ncols = len(headers)
            rows = []
            for row in buf[2:]:
                cells = [c.strip() for c in re.split(r'(?<!\\)\|', row.strip('|'))]
                cells += [''] * (ncols - len(cells))
                rows.append(cells[:ncols])
            tbl = ["#table(", f"  columns: {ncols},", "  table.header(",
                   "    " + ", ".join(f"[*{inline(h)}*]" for h in headers), "  ),"]
            for r in rows:
                tbl.append("  " + ", ".join(f"[{inline(c)}]" for c in r) + ",")
            tbl.append(")")
            out.append("\n".join(tbl))
            continue
        # numbered list
        if re.match(r'^\s*\d+\.\s+', ln):
            while i < n and re.match(r'^\s*\d+\.\s+', lines[i]):
                out.append("+ " + inline(re.sub(r'^\s*\d+\.\s+', '', lines[i]))); i += 1
            continue
        # bullet list
        if re.match(r'^\s*[-*]\s+', ln):
            out.append("- " + inline(re.sub(r'^\s*[-*]\s+', '', ln)))
            i += 1; continue
        # separator
        if ln.strip() == "---":
            out.append(""); i += 1; continue
        # blank
        if ln.strip() == "":
            out.append(""); i += 1; continue
        # paragraph
        out.append(inline(ln)); i += 1
    return "\n".join(out).strip()

# ── convert one exercise file → typst section ────────────────────────────────
def convert_exercises(md_path: Path, ch_num: int) -> str:
    lines = md_path.read_text(encoding="utf-8").split("\n")
    # skip H1 and first ---
    i = 0
    while i < len(lines) and not lines[i].strip() == "---":
        i += 1
    i += 1  # past the ---

    parts = [
        f"// EXERCICES — CHAPITRE {ch_num}",
        "// ============================================================",
        "",
        "#pagebreak()",
        "== Exercices pratiques",
        "",
    ]

    remaining = lines[i:]
    n = len(remaining)
    j = 0
    while j < n:
        ln = remaining[j]
        # ## Exercice N · Title
        m = re.match(r'^##\s+(.+)', ln)
        if m:
            title = m.group(1).strip()
            j += 1
            body = []
            while j < n and not remaining[j].startswith("## "):
                if "disponibles en annexe" not in remaining[j]:
                    body.append(remaining[j])
                j += 1
            # remove leading/trailing blank lines
            while body and body[0].strip() == "":
                body.pop(0)
            while body and body[-1].strip() == "":
                body.pop()
            parts.append(f"=== {inline(title)}")
            parts.append("")
            parts.append(render_block(body))
            parts.append("")
            parts.append("")
            continue
        j += 1

    return "\n".join(parts)

# ── append (or replace) exercises in chapter .typ ────────────────────────────
MARKER = "// EXERCICES — CHAPITRE"

# QR code at the end of every exercise series (last page of the section).
QR_BLOCK = """#v(2em)
#align(center)[
  #image("/QR Code.png", width: 60pt)
  #v(4pt)
  #text(size: 0.8em, style: "italic", fill: rgb("#64748b"))[Télécharger les images de référence]
]"""

def process(ch_num: int, ex_file: Path):
    typ_path = CHAPTER_FILES.get(ch_num)
    if typ_path is None:
        print(f"  ⚠  no .typ for ch{ch_num}"); return

    existing = typ_path.read_text(encoding="utf-8")

    if MARKER in existing:
        # a block was inserted before; everything from MARKER to EOF
        # (block + closing ']') is dropped → remainder IS the chapter body
        chapter_body = existing[:existing.index(MARKER)].rstrip()
    else:
        # fresh chapter: strip the chapter-closing ']' to insert inside
        base = existing.rstrip()
        if not base.endswith("]"):
            print(f"  ⚠  ch{ch_num}: no chapter-closing ] found, skipped"); return
        chapter_body = base[:-1].rstrip()

    block = convert_exercises(ex_file, ch_num) + "\n\n" + QR_BLOCK
    new_content = chapter_body + "\n\n" + block + "\n\n]\n"

    typ_path.write_text(new_content, encoding="utf-8")
    print(f"  ✓  ch{ch_num:02d} → {typ_path.name}")

# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ex_files = sorted(SRC.glob("exercices_ch*.md"))
    if not ex_files:
        print("No exercise files found in", SRC); raise SystemExit(1)

    for ex in ex_files:
        m = re.search(r'exercices_ch(\d+)', ex.stem)
        if not m:
            print(f"  ⚠  cannot parse ch number from {ex.name}"); continue
        process(int(m.group(1)), ex)

    print(f"\n{len(ex_files)} exercise files processed.")
