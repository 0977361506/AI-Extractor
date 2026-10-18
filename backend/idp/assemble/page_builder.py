"""Turn layout regions + recognised lines (+ pre-built tables / special elements) into ordered AST elements."""

from __future__ import annotations

import statistics

from idp.assemble.lines import cluster_paragraphs, join_lines
from idp.assemble.reading_order import xy_cut_order
from idp.core.ast import Element, ElementType, Line, ReviewReason, TableCell
from idp.core.geometry import PixelBox, area, containment, denormalize_bbox, normalize_bbox, union_bbox
from idp.layout.regions import CHECKBOX_LABELS, LayoutRegion
from idp.table.builder import OcrLine, build_borderless_table
from idp.table.render import cells_to_html, cells_to_markdown

LABEL_TYPE = {
    "title": ElementType.TITLE,
    "section_header": ElementType.HEADING,
    "text": ElementType.PARAGRAPH,
    "list_item": ElementType.LIST_ITEM,
    "caption": ElementType.CAPTION,
    "footnote": ElementType.PARAGRAPH,
    "page_header": ElementType.PAGE_HEADER,
    "page_footer": ElementType.PAGE_FOOTER,
    "formula": ElementType.FORMULA,
    "code": ElementType.PARAGRAPH,
    "picture": ElementType.FIGURE,
    "table": ElementType.TABLE,
}


def _weighted_conf(lines: list[OcrLine]) -> float:
    if not lines:
        return 1.0
    total = sum(max(1, len(l.text)) for l in lines)
    return round(sum(l.confidence * max(1, len(l.text)) for l in lines) / total, 4)


def text_markdown(type_: ElementType, text: str, level: int | None = None) -> str:
    one_line = " ".join(text.split())
    if type_ == ElementType.TITLE:
        return f"# {one_line}"
    if type_ == ElementType.HEADING:
        return f"{'#' * ((level or 1) + 1)} {one_line}"
    return text


def table_element(cells: list[TableCell], **kw) -> Element:
    el = Element(type=ElementType.TABLE, cells=cells, content_html=cells_to_html(cells), content_markdown=cells_to_markdown(cells), **kw)
    el.text = "\n".join(" | ".join(c.text for c in cells if c.row == r) for r in sorted({c.row for c in cells}))
    if cells:
        el.confidence_score = round(statistics.fmean(c.confidence for c in cells), 4)
    if any(c.check_failed for c in cells):
        el.flag(ReviewReason.ARITHMETIC_CHECK_FAILED)
    return el


def build_elements(
    page_number: int,
    width: int,
    height: int,
    regions: list[LayoutRegion],
    lines: list[OcrLine],
    tables: dict[int, list[TableCell]],
    extra: list[Element],
    review_threshold: float,
    line_height: float = 30.0,
    engine: str = "",
) -> list[Element]:
    usable = [i for i, r in enumerate(regions) if r.label not in CHECKBOX_LABELS]
    assigned: dict[int, list[OcrLine]] = {i: [] for i in usable}
    orphans: list[OcrLine] = []
    for ln in lines:
        best = None
        for i in usable:
            c = containment(ln.bbox, regions[i].bbox)
            if c >= 0.5 and (best is None or (c, -area(regions[i].bbox)) > best[0]):
                best = ((c, -area(regions[i].bbox)), i)
        if best is None:
            orphans.append(ln)
        else:
            assigned[best[1]].append(ln)

    drafts: list[tuple[PixelBox, Element]] = []

    def norm(b: PixelBox):
        return normalize_bbox(b, width, height)

    def add_text(type_: ElementType, box: PixelBox, members: list[OcrLine]) -> None:
        text = join_lines(members)
        if not text and type_ != ElementType.FIGURE:
            return
        el = Element(
            element_id="",
            type=type_,
            reading_order=0,
            bbox_normalized=norm(box),
            text=text,
            content_markdown="" if type_ == ElementType.FIGURE else text_markdown(type_, text),
            confidence_score=_weighted_conf(members),
            extraction_engine=engine,
            lines=[Line(text=l.text, bbox=norm(l.bbox), confidence=round(l.confidence, 4)) for l in members],
        )
        if members and el.confidence_score < review_threshold:
            el.flag(ReviewReason.LOW_CONFIDENCE)
        drafts.append((box, el))

    for i in usable:
        region = regions[i]
        type_ = LABEL_TYPE.get(region.label, ElementType.PARAGRAPH)
        members = assigned[i]
        if type_ == ElementType.TABLE:
            cells = tables.get(i) or build_borderless_table(members, width, height)
            if not cells:
                add_text(ElementType.PARAGRAPH, region.bbox, members)
                continue
            el = table_element(cells, element_id="", reading_order=0, bbox_normalized=norm(region.bbox), extraction_engine=engine)
            if el.confidence_score < review_threshold:
                el.flag(ReviewReason.LOW_CONFIDENCE)
            drafts.append((region.bbox, el))
        else:
            add_text(type_, region.bbox, members)

    for group in cluster_paragraphs(orphans, line_height):
        add_text(ElementType.PARAGRAPH, union_bbox(l.bbox for l in group), group)

    for el in extra:
        box = denormalize_bbox(el.bbox_normalized, width, height) if el.bbox_normalized else (0, 0, 0, 0)
        drafts.append((box, el))

    order = xy_cut_order([b for b, _ in drafts])
    elements = []
    for n, idx in enumerate(order):
        el = drafts[idx][1]
        el.reading_order = n
        el.element_id = f"el_p{page_number}_{n + 1:03d}"
        elements.append(el)
    return elements
