"""
Convert docs/phase3_report.md to docs/phase3_report.docx.

Handles headings (#..####), paragraphs, ordered/unordered lists,
fenced code blocks, pipe tables, horizontal rules, and inline
**bold** / `code` within paragraphs and list items.
"""
from __future__ import annotations
import os
import re
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD_PATH = os.path.join(ROOT, "docs", "phase3_report.md")
OUT_PATH = os.path.join(ROOT, "docs", "phase3_report.docx")

HEADING_COLOR = RGBColor(0x1A, 0x2B, 0x4A)
BODY_SIZE = Pt(11)
CODE_SIZE = Pt(9.5)


def add_hr(paragraph):
    p_pr = paragraph._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "888888")
    pbdr.append(bottom)
    p_pr.append(pbdr)


INLINE_RE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")

def add_inline_runs(paragraph, text: str, base_size=BODY_SIZE):
    """Split text on **bold** and `code`, add runs accordingly."""
    parts = INLINE_RE.split(text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
            run.font.size = base_size
            run.font.color.rgb = HEADING_COLOR
        elif part.startswith("`") and part.endswith("`"):
            run = paragraph.add_run(part[1:-1])
            run.font.name = "Courier New"
            run.font.size = Pt(base_size.pt - 0.5)
        else:
            run = paragraph.add_run(part)
            run.font.size = base_size


def is_table_row(line: str) -> bool:
    return line.strip().startswith("|") and line.strip().endswith("|")

def is_table_separator(line: str) -> bool:
    s = line.strip().strip("|").strip()
    if not s:
        return False
    cells = [c.strip() for c in s.split("|")]
    return all(re.fullmatch(r":?-+:?", c) for c in cells)

def split_row(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def convert(md_text: str) -> Document:
    doc = Document()

    # Base body style
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = BODY_SIZE

    lines = md_text.splitlines()
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.rstrip()

        # Blank line
        if not stripped.strip():
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            i += 1
            code_lines = []
            while i < n and not lines[i].rstrip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.2)
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            run = p.add_run("\n".join(code_lines))
            run.font.name = "Courier New"
            run.font.size = CODE_SIZE
            # Light gray shading
            p_pr = p._p.get_or_add_pPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), "F4F4F4")
            p_pr.append(shd)
            continue

        # Horizontal rule
        if re.fullmatch(r"-{3,}", stripped.strip()):
            p = doc.add_paragraph()
            add_hr(p)
            i += 1
            continue

        # Pipe table
        if is_table_row(stripped) and (i + 1) < n and is_table_separator(lines[i + 1]):
            header = split_row(stripped)
            i += 2  # header + separator
            rows = []
            while i < n and is_table_row(lines[i].rstrip()):
                rows.append(split_row(lines[i].rstrip()))
                i += 1
            tbl = doc.add_table(rows=1 + len(rows), cols=len(header))
            tbl.style = "Light Grid Accent 1"
            hdr = tbl.rows[0].cells
            for c, text in enumerate(header):
                hdr[c].text = ""
                p = hdr[c].paragraphs[0]
                add_inline_runs(p, text, base_size=Pt(10))
                for r in p.runs:
                    r.bold = True
            for ri, row in enumerate(rows):
                cells = tbl.rows[1 + ri].cells
                for c, text in enumerate(row):
                    cells[c].text = ""
                    p = cells[c].paragraphs[0]
                    add_inline_runs(p, text, base_size=Pt(10))
            continue

        # Headings
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2)
            p = doc.add_heading(level=level)
            run = p.add_run(text)
            run.font.color.rgb = HEADING_COLOR
            if level == 1:
                run.font.size = Pt(20)
            elif level == 2:
                run.font.size = Pt(15)
            elif level == 3:
                run.font.size = Pt(12.5)
            else:
                run.font.size = Pt(11.5)
            run.bold = True
            i += 1
            continue

        # Ordered list item
        m = re.match(r"^(\s*)(\d+)\.\s+(.*)$", line)
        if m:
            text = m.group(3)
            p = doc.add_paragraph(style="List Number")
            add_inline_runs(p, text)
            i += 1
            continue

        # Unordered list item
        m = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
        if m:
            text = m.group(2)
            p = doc.add_paragraph(style="List Bullet")
            add_inline_runs(p, text)
            i += 1
            continue

        # Regular paragraph: gather continuation lines until blank / structural
        para_lines = [stripped]
        j = i + 1
        while j < n:
            nxt = lines[j].rstrip()
            if not nxt.strip():
                break
            if re.match(r"^#{1,4}\s", nxt):
                break
            if re.match(r"^\s*(\d+)\.\s", nxt) or re.match(r"^\s*[-*+]\s", nxt):
                break
            if nxt.startswith("```"):
                break
            if is_table_row(nxt):
                break
            if re.fullmatch(r"-{3,}", nxt.strip()):
                break
            para_lines.append(nxt)
            j += 1
        text = " ".join(para_lines)
        p = doc.add_paragraph()
        add_inline_runs(p, text)
        i = j

    return doc


def main() -> None:
    with open(MD_PATH, "r", encoding="utf-8") as f:
        md = f.read()
    doc = convert(md)
    doc.save(OUT_PATH)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
