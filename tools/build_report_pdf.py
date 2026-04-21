"""
Regenerate phase3_report.pdf and final_report.pdf from phase3_report.md.
Uses markdown -> HTML -> PyMuPDF Story/DocumentWriter.
"""
from __future__ import annotations
import os
import shutil
import markdown
import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(ROOT, "docs", "phase3_report.md")
OUT_PHASE3 = os.path.join(ROOT, "docs", "phase3_report.pdf")
OUT_FINAL = os.path.join(ROOT, "docs", "final_report.pdf")

CSS = """
* { font-family: sans-serif; }
body { font-size: 10pt; color: #222; }
h1 { font-size: 18pt; color: #1a2b4a; margin-top: 12pt; }
h2 { font-size: 14pt; color: #1a2b4a; margin-top: 10pt; }
h3 { font-size: 12pt; color: #2a4373; margin-top: 8pt; }
h4 { font-size: 11pt; color: #2a4373; }
p, li { font-size: 10pt; line-height: 1.35; }
code { font-family: monospace; font-size: 9pt; background: #f0f0f0; padding: 1px 3px; }
pre { font-family: monospace; font-size: 8.5pt; background: #f4f4f4; padding: 6px; }
table { border-collapse: collapse; margin: 6pt 0; }
th, td { border: 1px solid #888; padding: 3pt 5pt; font-size: 9pt; text-align: left; }
th { background: #e6ecf5; }
hr { border: 0; border-top: 1px solid #aaa; margin: 8pt 0; }
strong { color: #1a2b4a; }
"""

def md_to_html(md_text: str) -> str:
    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    return f"<html><head><style>{CSS}</style></head><body>{html_body}</body></html>"

def render_pdf(html: str, out_path: str) -> None:
    PAGE_W, PAGE_H = fitz.paper_size("letter")
    MARGIN = 54  # 0.75 inch
    MEDIABOX = fitz.Rect(0, 0, PAGE_W, PAGE_H)
    WHERE = fitz.Rect(MARGIN, MARGIN, PAGE_W - MARGIN, PAGE_H - MARGIN)

    story = fitz.Story(html=html)
    writer = fitz.DocumentWriter(out_path)
    more = True
    while more:
        dev = writer.begin_page(MEDIABOX)
        more, _ = story.place(WHERE)
        story.draw(dev)
        writer.end_page()
    writer.close()

def main() -> None:
    with open(MD, "r", encoding="utf-8") as f:
        md_text = f.read()
    html = md_to_html(md_text)
    render_pdf(html, OUT_PHASE3)
    shutil.copyfile(OUT_PHASE3, OUT_FINAL)
    print(f"Wrote {OUT_PHASE3}")
    print(f"Wrote {OUT_FINAL}")

if __name__ == "__main__":
    main()
