"""Build docs/Final Report.pdf from docs/final_report.md.

The project no longer patches PDF text in place. The Markdown file is the
editable report source, and this script renders a clean academic PDF with a
consistent text layer.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "final_report.md"
OUT = ROOT / "docs" / "Final Report.pdf"
TMP = ROOT / "docs" / "Final Report.tmp.pdf"

PAGE_W, PAGE_H = fitz.paper_size("letter")
LEFT = 72
RIGHT = 72
TOP = 72
BOTTOM = 72
BODY_WIDTH = PAGE_W - LEFT - RIGHT
BODY_SIZE = 11.3

FONT_REG = "Times-Roman"
FONT_BOLD = "Times-Bold"
FONT_ITALIC = "Times-Italic"
FONT_CODE = "Courier"


REG = fitz.Font(fontname=FONT_REG)
BOLD = fitz.Font(fontname=FONT_BOLD)
ITALIC = fitz.Font(fontname=FONT_ITALIC)
CODE = fitz.Font(fontname=FONT_CODE)


def clean_inline(text: str) -> str:
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def wrap_text(text: str, font: fitz.Font, size: float, max_width: float) -> list[str]:
    text = clean_inline(text).strip()
    if not text:
        return [""]
    lines: list[str] = []
    for para in text.split("\n"):
        words = para.split()
        current = ""
        for word in words:
            if font.text_length(word, fontsize=size) > max_width:
                if current:
                    lines.append(current)
                    current = ""
                chunk = ""
                for char in word:
                    candidate = chunk + char
                    if font.text_length(candidate, fontsize=size) <= max_width:
                        chunk = candidate
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = char
                if chunk:
                    current = chunk
                continue
            candidate = word if not current else f"{current} {word}"
            if font.text_length(candidate, fontsize=size) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


class Renderer:
    def __init__(self) -> None:
        self.doc = fitz.open()
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.y = TOP

    def new_page(self) -> None:
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.y = TOP

    def ensure(self, height: float) -> None:
        if self.y + height > PAGE_H - BOTTOM:
            self.new_page()

    def text(
        self,
        text: str,
        *,
        x: float = LEFT,
        size: float = BODY_SIZE,
        font_name: str = FONT_REG,
        font: fitz.Font = REG,
        width: float = BODY_WIDTH,
        leading: float | None = None,
        space_after: float = 6,
    ) -> None:
        leading = leading or size * 1.25
        lines = wrap_text(text, font, size, width)
        self.ensure(len(lines) * leading + space_after)
        for line in lines:
            if line:
                self.page.insert_text((x, self.y + size), line, fontsize=size, fontname=font_name)
            self.y += leading
        self.y += space_after

    def heading(self, text: str, level: int) -> None:
        if level == 1:
            size, before, after = 16, 14, 5
        elif level == 2:
            size, before, after = 13, 12, 6
        else:
            size, before, after = 12, 9, 5
        if self.y <= TOP + 1:
            before = 0
        self.ensure(before + size * 1.5 + after)
        self.y += before
        self.page.insert_text((LEFT, self.y + size), clean_inline(text), fontsize=size, fontname=FONT_BOLD)
        self.y += size * 1.5 + after

    def code_block(self, lines: list[str]) -> None:
        size = 8.8
        leading = 10.8
        for line in lines:
            self.ensure(leading)
            self.page.insert_text((LEFT + 18, self.y + size), line, fontsize=size, fontname=FONT_CODE)
            self.y += leading
        self.y += 6

    def table(self, rows: list[list[str]]) -> None:
        if not rows:
            return
        cols = len(rows[0])
        gap = 0
        col_widths = self._table_widths(rows, cols)
        size = 8.2
        leading = 9.4
        pad_x = 4
        pad_y = 4

        wrapped_rows: list[list[list[str]]] = []
        row_heights: list[float] = []
        for row in rows:
            wrapped_cells = []
            max_lines = 1
            for i in range(cols):
                cell = row[i] if i < len(row) else ""
                font = BOLD if not wrapped_rows else REG
                wrapped = wrap_text(cell, font, size, max(20, col_widths[i] - 2 * pad_x))
                wrapped_cells.append(wrapped)
                max_lines = max(max_lines, len(wrapped))
            wrapped_rows.append(wrapped_cells)
            row_heights.append(max_lines * leading + 2 * pad_y)

        for r, cells in enumerate(wrapped_rows):
            h = row_heights[r]
            self.ensure(h)
            x = LEFT
            for c, lines in enumerate(cells):
                rect = fitz.Rect(x, self.y, x + col_widths[c] - gap, self.y + h)
                self.page.draw_rect(rect, color=(0, 0, 0), width=0.5)
                if r == 0:
                    self.page.draw_rect(rect, color=(0, 0, 0), fill=(0.94, 0.94, 0.94), width=0.5)
                ty = self.y + pad_y + size
                for line in lines:
                    if line:
                        self.page.insert_text(
                            (x + pad_x, ty),
                            line,
                            fontsize=size,
                            fontname=FONT_BOLD if r == 0 else FONT_REG,
                        )
                    ty += leading
                x += col_widths[c]
            self.y += h
        self.y += 8

    def _table_widths(self, rows: list[list[str]], cols: int) -> list[float]:
        weights = []
        for c in range(cols):
            longest = max((len(row[c]) if c < len(row) else 0) for row in rows)
            weights.append(max(8, min(longest, 28)))
        total = sum(weights)
        widths = [BODY_WIDTH * w / total for w in weights]
        min_width = 54
        deficit = sum(max(0, min_width - w) for w in widths)
        if deficit:
            widths = [max(min_width, w) for w in widths]
            scale = BODY_WIDTH / sum(widths)
            widths = [w * scale for w in widths]
        return widths

    def cover(self, meta_lines: list[str]) -> None:
        subtitle = meta_lines[0] if meta_lines else ""
        report_label = meta_lines[1] if len(meta_lines) > 1 else "Final Report"
        details = meta_lines[2:] if len(meta_lines) > 2 else meta_lines

        self.y = 220
        self._center("PuzzleForge", 32, FONT_BOLD, BOLD)
        if subtitle:
            self.y += 14
            self._center(subtitle, 15, FONT_ITALIC, ITALIC)
        if report_label:
            self.y += 18
            self._center(report_label, 14, FONT_BOLD, BOLD)
        self.y += 92
        for line in details:
            if line.startswith("Course: "):
                line = line.replace("Course: ", "", 1)
            self._center(line, 12, FONT_REG, REG)
            self.y += 5
        self.new_page()

    def _center(self, text: str, size: float, font_name: str, font: fitz.Font) -> None:
        text_width = font.text_length(text, fontsize=size)
        x = (PAGE_W - text_width) / 2
        self.page.insert_text((x, self.y + size), text, fontsize=size, fontname=font_name)
        self.y += size * 1.25


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-+:?", cell) for cell in cells)


def flush_paragraph(renderer: Renderer, buf: list[str]) -> None:
    if buf:
        renderer.text(" ".join(line.strip() for line in buf), size=BODY_SIZE)
        buf.clear()


def parse_and_render(md: str, renderer: Renderer) -> None:
    lines = md.splitlines()
    meta: list[str] = []
    i = 0
    if lines and lines[0].startswith("# "):
        i = 1
        while i < len(lines) and not lines[i].startswith("## "):
            stripped = lines[i].strip()
            if stripped:
                meta.append(stripped)
            i += 1
    renderer.cover(meta)

    paragraph: list[str] = []
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            flush_paragraph(renderer, paragraph)
            i += 1
            continue

        if stripped.startswith("```"):
            flush_paragraph(renderer, paragraph)
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i].rstrip())
                i += 1
            renderer.code_block(code_lines)
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and is_table_separator(lines[i + 1]):
            flush_paragraph(renderer, paragraph)
            rows = [split_table_row(stripped)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_table_row(lines[i]))
                i += 1
            renderer.table(rows)
            continue

        heading = re.match(r"^(#{2,4})\s+(.*)$", stripped)
        if heading:
            flush_paragraph(renderer, paragraph)
            level = len(heading.group(1)) - 1
            renderer.heading(heading.group(2), level)
            i += 1
            continue

        bullet = re.match(r"^[-*]\s+(.*)$", stripped)
        if bullet:
            flush_paragraph(renderer, paragraph)
            renderer.text(f"* {bullet.group(1)}", x=LEFT + 12, width=BODY_WIDTH - 12, size=BODY_SIZE)
            i += 1
            continue

        paragraph.append(stripped)
        i += 1

    flush_paragraph(renderer, paragraph)


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing Markdown source: {SOURCE}")
    md = SOURCE.read_text(encoding="utf-8")
    renderer = Renderer()
    parse_and_render(md, renderer)
    if TMP.exists():
        TMP.unlink()
    renderer.doc.save(TMP, garbage=4, deflate=True)
    renderer.doc.close()
    # shutil.copyfile is more reliable than os.replace on Windows when a PDF
    # viewer has recently released the destination file.
    shutil.copyfile(TMP, OUT)
    TMP.unlink()
    print(f"Wrote {OUT} from {SOURCE}")


if __name__ == "__main__":
    main()
