"""Heading levels and parent breadcrumbs across the whole document."""

from __future__ import annotations

import re

from idp.assemble.page_builder import text_markdown
from idp.core.ast import Document, ElementType

_PROMOTE = re.compile(r"^(ĐIỀU|Điều|CHƯƠNG|Chương|PHẦN|Phần|MỤC|Mục)\s+([IVXLC]+|\d+)\b")
_ROMAN = re.compile(r"^[IVXLC]+[.)]\s")
_L4 = re.compile(r"^\d+\.\d+\.\d+")
_L3 = re.compile(r"^\d+\.\d+\.?\s")
_L2 = re.compile(r"^\d+[.)]\s")


def heading_level(text: str) -> int:
    t = text.strip()
    if _PROMOTE.match(t) or _ROMAN.match(t):
        return 1
    if _L4.match(t):
        return 4
    if _L3.match(t):
        return 3
    if _L2.match(t):
        return 2
    return 2


def _should_promote(text: str) -> bool:
    t = " ".join(text.split())
    if not _PROMOTE.match(t) or len(t) > 120:
        return False
    letters = [c for c in t if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) >= 0.6


def assign_hierarchy(doc: Document) -> None:
    stack: list[tuple[int, str]] = []
    for page in doc.pages:
        for el in sorted(page.elements, key=lambda e: e.reading_order):
            if el.type in (ElementType.PAGE_HEADER, ElementType.PAGE_FOOTER):
                el.hierarchy_breadcrumb = []
                continue
            if el.type == ElementType.PARAGRAPH and _should_promote(el.text):
                el.type = ElementType.HEADING
            title = " ".join(el.text.split())
            if el.type == ElementType.TITLE:
                el.level = 0
                stack = [(0, title)]
                el.content_markdown = text_markdown(el.type, el.text)
            elif el.type == ElementType.HEADING:
                el.level = heading_level(title)
                while stack and stack[-1][0] >= el.level:
                    stack.pop()
                stack.append((el.level, title))
                el.content_markdown = text_markdown(el.type, el.text, el.level)
            el.hierarchy_breadcrumb = [t for _, t in stack]
