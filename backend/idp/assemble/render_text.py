"""Plain/markdown text of a single element, shared by the Markdown renderer and the RAG chunker."""

from __future__ import annotations

from idp.core.ast import Element, ElementType
from idp.table.render import cells_to_markdown


def choices_text(el: Element) -> str:
    opts = " · ".join(f"[{'x' if o.checked else ' '}] {o.label}" for o in el.options)
    return f"**{el.question}**: {opts}" if el.question else opts


def element_markdown(el: Element) -> str:
    t = el.type
    if t == ElementType.TABLE:
        return cells_to_markdown(el.cells) if el.cells else el.content_markdown
    if t == ElementType.CHOICE_GROUP:
        return choices_text(el)
    if t == ElementType.FORM_FIELD:
        return f"**{el.label or ''}**: {el.value or ''}"
    if t == ElementType.FIGURE:
        return f"> [Hình] {' / '.join(el.text.splitlines())}".rstrip() if el.text else "> [Hình]"
    if t == ElementType.DIAGRAM:
        desc = f"> [Sơ đồ] {el.description}\n\n" if el.description else ""
        return f"{desc}```mermaid\n{el.mermaid}\n```" if el.mermaid else f"> [Sơ đồ] {el.text}"
    if t == ElementType.STAMP:
        return f"> [Dấu {el.color or ''}] {el.text}".rstrip()
    if t == ElementType.SIGNATURE:
        return f"> [Chữ ký] {el.signer_name or ''}".rstrip()
    if t == ElementType.HANDWRITTEN_NOTE:
        return f"> ✍ {el.text}"
    return el.content_markdown or el.text
