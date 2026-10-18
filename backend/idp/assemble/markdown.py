"""Whole-document Markdown (tables with merged cells are emitted as HTML to keep their structure)."""

from __future__ import annotations

from idp.assemble.render_text import element_markdown
from idp.core.ast import Document, ElementType
from idp.table.render import cells_to_html

_SKIP = {ElementType.PAGE_HEADER, ElementType.PAGE_FOOTER}


def render_markdown(doc: Document) -> str:
    out: list[str] = []
    for page in doc.pages:
        out.append(f"<!-- page {page.page_number} -->")
        for el in sorted(page.elements, key=lambda e: e.reading_order):
            if el.type in _SKIP:
                continue
            if el.type == ElementType.TABLE and any(c.rowspan > 1 or c.colspan > 1 for c in el.cells):
                out.append(cells_to_html(el.cells))
            else:
                md = element_markdown(el)
                if md:
                    out.append(md)
    return "\n\n".join(out) + "\n"
