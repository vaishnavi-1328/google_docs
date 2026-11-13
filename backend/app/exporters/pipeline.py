"""Export a document (title + HTML body) to one of several formats.

Strategy:
  - Frontend sends TipTap's HTML output in the request body. Rendering HTML
    server-side from Yjs state would require running the full ProseMirror
    schema in Python — vastly more surface area than we need for the MVP.
  - Server converts HTML → the requested format using small, well-known libs.

Returned tuple: (bytes, mime_type, filename).
"""
from __future__ import annotations

import io
import re
from typing import Literal

Format = Literal["pdf", "md", "txt", "docx", "epub", "html"]


def _safe_filename(title: str, ext: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_") or "document"
    return f"{slug[:120]}.{ext}"


def _wrap_html(title: str, body_html: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 7in; margin: 0.75in auto; line-height: 1.5; }}
  h1 {{ font-size: 24pt; }} h2 {{ font-size: 18pt; }} h3 {{ font-size: 14pt; }}
  blockquote {{ border-left: 3px solid #999; padding-left: 12px; color: #444; }}
  table {{ border-collapse: collapse; }} table td, table th {{ border: 1px solid #999; padding: 4px 8px; }}
  code {{ background: #f4f4f4; padding: 1px 4px; }}
  pre code {{ display: block; padding: 8px; }}
</style></head>
<body><h1>{title}</h1>{body_html}</body></html>"""


def _to_pdf(title: str, html: str) -> tuple[bytes, str, str]:
    from bs4 import BeautifulSoup
    from fpdf import FPDF

    class PDF(FPDF):
        pass

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.multi_cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    soup = BeautifulSoup(html, "html.parser")

    def add_block(el):
        name = getattr(el, "name", None)
        if name is None:
            return
        text = el.get_text()
        if not text.strip():
            return
        if name in ("h1",):
            pdf.set_font("Helvetica", "B", 16)
        elif name in ("h2",):
            pdf.set_font("Helvetica", "B", 14)
        elif name in ("h3", "h4", "h5", "h6"):
            pdf.set_font("Helvetica", "B", 12)
        elif name == "pre":
            pdf.set_font("Courier", "", 10)
        else:
            pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    for child in soup.children:
        add_block(child)

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue(), "application/pdf", _safe_filename(title, "pdf")


def _to_md(title: str, html: str) -> tuple[bytes, str, str]:
    import html2text

    h = html2text.HTML2Text()
    h.body_width = 0
    md = f"# {title}\n\n" + h.handle(html)
    return md.encode("utf-8"), "text/markdown; charset=utf-8", _safe_filename(title, "md")


def _to_txt(title: str, html: str) -> tuple[bytes, str, str]:
    from bs4 import BeautifulSoup

    text = BeautifulSoup(html, "html.parser").get_text("\n")
    out = f"{title}\n{'=' * len(title)}\n\n{text}\n"
    return out.encode("utf-8"), "text/plain; charset=utf-8", _safe_filename(title, "txt")


def _to_docx(title: str, html: str) -> tuple[bytes, str, str]:
    from bs4 import BeautifulSoup
    from docx import Document as DocxDocument

    doc = DocxDocument()
    doc.add_heading(title, level=0)
    soup = BeautifulSoup(html, "html.parser")

    def walk(el):
        for child in el.children:
            name = getattr(child, "name", None)
            if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                doc.add_heading(child.get_text(strip=True), level=int(name[1]))
            elif name == "p":
                doc.add_paragraph(child.get_text())
            elif name in ("ul", "ol"):
                style = "List Bullet" if name == "ul" else "List Number"
                for li in child.find_all("li", recursive=False):
                    doc.add_paragraph(li.get_text(), style=style)
            elif name == "blockquote":
                doc.add_paragraph(child.get_text(), style="Intense Quote")
            elif name == "hr":
                doc.add_paragraph("―" * 20)
            elif name == "pre":
                p = doc.add_paragraph()
                r = p.add_run(child.get_text())
                r.font.name = "Courier New"
            elif name is not None:
                # Fallback: recurse so nested block structure still produces text.
                walk(child)

    walk(soup)
    buf = io.BytesIO()
    doc.save(buf)
    return (
        buf.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _safe_filename(title, "docx"),
    )


def _to_epub(title: str, html: str) -> tuple[bytes, str, str]:
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier(f"collab-docs:{_safe_filename(title, 'epub')}")
    book.set_title(title)
    book.set_language("en")
    chapter = epub.EpubHtml(title=title, file_name="chap.xhtml", lang="en")
    chapter.content = f"<h1>{title}</h1>{html}"
    book.add_item(chapter)
    book.toc = (chapter,)
    book.spine = ["nav", chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    buf = io.BytesIO()
    epub.write_epub(buf, book)
    return buf.getvalue(), "application/epub+zip", _safe_filename(title, "epub")


def _to_html(title: str, html: str) -> tuple[bytes, str, str]:
    return _wrap_html(title, html).encode("utf-8"), "text/html; charset=utf-8", _safe_filename(title, "html")


_DISPATCH = {
    "pdf": _to_pdf,
    "md": _to_md,
    "txt": _to_txt,
    "docx": _to_docx,
    "epub": _to_epub,
    "html": _to_html,
}


def export_document(fmt: Format, title: str, html: str) -> tuple[bytes, str, str]:
    if fmt not in _DISPATCH:
        raise ValueError(f"unsupported format: {fmt}")
    return _DISPATCH[fmt](title or "Untitled document", html or "")
