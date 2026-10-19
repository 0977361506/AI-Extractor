"""Tier-0 fast path: DOCX / PPTX / XLSX / HTML → AST directly from the file structure (no OCR, no GPU)."""

from __future__ import annotations

import datetime as dt
import io

from idp.assemble.page_builder import table_element, text_markdown
from idp.core.ast import DocStatus, Document, DocumentMetadata, Element, ElementType, Page, TableCell
from idp.ingest.detect import MIME, FileKind
from idp.ingest.legacy_fonts import convert_legacy
from idp.table.builder import finalize_cells


def _text_el(type_: ElementType, text: str, level: int | None = None) -> Element:
    text = " ".join(convert_legacy(text).split()) if type_ != ElementType.PARAGRAPH else convert_legacy(text).strip()
    return Element(
        element_id="",
        type=type_,
        reading_order=0,
        text=text,
        level=level,
        content_markdown=text_markdown(type_, text, level),
        extraction_engine="native",
    )


def _table_el(cells: list[TableCell]) -> Element | None:
    cells = finalize_cells(cells, ocr=False)
    if not cells:
        return None
    return table_element(cells, element_id="", reading_order=0, extraction_engine="native")


def _page(n: int, elements: list[Element]) -> Page:
    for i, el in enumerate(elements):
        el.reading_order = i
        el.element_id = f"el_p{n}_{i + 1:03d}"
    return Page(page_number=n, width=0, height=0, elements=elements)


# DOCX -----------------------------------------------------------------------
def _docx_paragraph_text(par) -> str:
    parts = []
    for run in par.runs:
        font = run.font.name or (par.style.font.name if par.style is not None and par.style.font is not None else None)
        parts.append(convert_legacy(run.text, font) if font else run.text)
    return "".join(parts) if parts else par.text


def _docx_table(tbl, doc) -> list[TableCell]:
    from docx.table import _Cell

    cells: list[TableCell] = []
    active: dict[int, TableCell] = {}  # grid column → cell open for vertical merge
    for r, tr in enumerate(tbl._tbl.tr_lst):
        col = 0
        for tc in tr.tc_lst:
            span = tc.grid_span
            vmerge = tc.vMerge
            if vmerge == "continue" and col in active:
                active[col].rowspan += 1
            else:
                text = "\n".join(_docx_paragraph_text(p) for p in _Cell(tc, tbl).paragraphs).strip()
                cell = TableCell(row=r, col=col, colspan=span, text=convert_legacy(text))
                cells.append(cell)
                for k in range(col, col + span):
                    active.pop(k, None)
                if vmerge == "restart":
                    active[col] = cell
            col += span
    return cells


def _parse_docx(data: bytes) -> list[Page]:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(io.BytesIO(data))
    elements: list[Element] = []
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            par = Paragraph(child, d)
            text = _docx_paragraph_text(par)
            if not text.strip():
                continue
            style = (par.style.name if par.style is not None else "").lower()
            if style.startswith("title"):
                elements.append(_text_el(ElementType.TITLE, text, 0))
            elif style.startswith("heading"):
                digits = "".join(ch for ch in style if ch.isdigit())
                elements.append(_text_el(ElementType.HEADING, text, int(digits) if digits else 1))
            elif "list" in style or par._p.pPr is not None and par._p.pPr.numPr is not None:
                elements.append(_text_el(ElementType.LIST_ITEM, text))
            else:
                elements.append(_text_el(ElementType.PARAGRAPH, text))
        elif tag == "tbl":
            el = _table_el(_docx_table(Table(child, d), d))
            if el:
                elements.append(el)
    return [_page(1, elements)]


# XLSX -----------------------------------------------------------------------
def format_value(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, (int, float)):
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        if isinstance(v, int):
            body = f"{abs(v):,}".replace(",", ".")
        else:
            body = f"{abs(v):,.10f}".rstrip("0").rstrip(".")
            body = body.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
        return f"-{body}" if v < 0 else body
    return convert_legacy(str(v)).strip()


def _parse_xlsx(data: bytes) -> list[Page]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    pages: list[Page] = []
    for ws in wb.worksheets:
        merged = {(m.min_row, m.min_col): (m.max_row - m.min_row + 1, m.max_col - m.min_col + 1) for m in ws.merged_cells.ranges}
        covered = {
            (r, c)
            for m in ws.merged_cells.ranges
            for r in range(m.min_row, m.max_row + 1)
            for c in range(m.min_col, m.max_col + 1)
            if (r, c) != (m.min_row, m.min_col)
        }
        cells = []
        for row in ws.iter_rows(min_row=ws.min_row, max_row=ws.max_row, min_col=ws.min_column, max_col=ws.max_column):
            for cell in row:
                key = (cell.row, cell.column)
                if key in covered:
                    continue
                rs, cs = merged.get(key, (1, 1))
                cells.append(
                    TableCell(row=cell.row - ws.min_row, col=cell.column - ws.min_column, rowspan=rs, colspan=cs, text=format_value(cell.value))
                )
        table = _table_el(cells) if any(c.text for c in cells) else None
        if table is None:
            continue
        pages.append(_page(len(pages) + 1, [_text_el(ElementType.HEADING, ws.title, 1), table]))
    return pages


# PPTX -----------------------------------------------------------------------
def _parse_pptx(data: bytes) -> list[Page]:
    from pptx import Presentation
    from pptx.enum.shapes import PP_PLACEHOLDER

    prs = Presentation(io.BytesIO(data))
    pages = []
    for n, slide in enumerate(prs.slides, start=1):
        elements: list[Element] = []
        shapes = sorted(slide.shapes, key=lambda s: ((s.top or 0), (s.left or 0)))
        for shape in shapes:
            if getattr(shape, "has_table", False) and shape.has_table:
                cells = []
                for r, row in enumerate(shape.table.rows):
                    for c, cell in enumerate(row.cells):
                        if cell.is_spanned:
                            continue
                        rs, cs = (cell.span_height, cell.span_width) if cell.is_merge_origin else (1, 1)
                        cells.append(TableCell(row=r, col=c, rowspan=rs, colspan=cs, text=convert_legacy(cell.text).strip()))
                el = _table_el(cells)
                if el:
                    elements.append(el)
            elif getattr(shape, "has_text_frame", False) and shape.has_text_frame and shape.text_frame.text.strip():
                is_title = shape.is_placeholder and shape.placeholder_format.type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE)
                elements.append(_text_el(ElementType.TITLE if is_title else ElementType.PARAGRAPH, shape.text_frame.text, 0 if is_title else None))
        pages.append(_page(n, elements))
    return pages


# HTML -----------------------------------------------------------------------
_BLOCK_CONTAINERS = {"body", "div", "section", "article", "main", "ul", "ol", "header", "footer", "aside", "form", "center", "blockquote"}


def _html_table(table) -> list[TableCell]:
    cells: list[TableCell] = []
    occupied: set[tuple[int, int]] = set()
    rows = [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]
    for r, tr in enumerate(rows):
        c = 0
        for cell in tr.find_all(["td", "th"], recursive=False):
            while (r, c) in occupied:
                c += 1
            rs, cs = int(cell.get("rowspan", 1) or 1), int(cell.get("colspan", 1) or 1)
            for i in range(r, r + rs):
                for k in range(c, c + cs):
                    occupied.add((i, k))
            cells.append(TableCell(row=r, col=c, rowspan=rs, colspan=cs, text=" ".join(cell.get_text(" ").split())))
            c += cs
    return cells


def _parse_html(data: bytes) -> list[Page]:
    from bs4 import BeautifulSoup, NavigableString

    soup = BeautifulSoup(data, "lxml")
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    elements: list[Element] = []
    seen_h1 = False

    def text_of(node) -> str:
        return " ".join(node.get_text(" ").split())

    def walk(node) -> None:
        nonlocal seen_h1
        for child in node.children:
            if isinstance(child, NavigableString):
                t = " ".join(str(child).split())
                if t and node.name in _BLOCK_CONTAINERS:
                    elements.append(_text_el(ElementType.PARAGRAPH, t))
                continue
            name = child.name
            if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(name[1])
                t = text_of(child)
                if not t:
                    continue
                if level == 1 and not seen_h1:
                    seen_h1 = True
                    elements.append(_text_el(ElementType.TITLE, t, 0))
                else:
                    elements.append(_text_el(ElementType.HEADING, t, max(1, level - 1)))
            elif name == "table":
                el = _table_el(_html_table(child))
                if el:
                    elements.append(el)
            elif name == "li":
                if t := text_of(child):
                    elements.append(_text_el(ElementType.LIST_ITEM, t))
            elif name in ("p", "pre", "address", "dd", "dt", "figcaption"):
                if t := text_of(child):
                    elements.append(_text_el(ElementType.PARAGRAPH, t))
            elif name in _BLOCK_CONTAINERS or name in ("span", "a", "b", "strong", "i", "em", "font"):
                if name in _BLOCK_CONTAINERS:
                    walk(child)
                elif t := text_of(child):
                    elements.append(_text_el(ElementType.PARAGRAPH, t))

    walk(soup.body or soup)
    return [_page(1, elements)]


_PARSERS = {FileKind.DOCX: _parse_docx, FileKind.XLSX: _parse_xlsx, FileKind.PPTX: _parse_pptx, FileKind.HTML: _parse_html}


def parse_office(data: bytes, filename: str, kind: FileKind, document_id: str, job_id: str) -> Document:
    if kind not in _PARSERS:
        raise ValueError(f"không phải tài liệu Office/HTML: {kind}")
    pages = _PARSERS[kind](data)
    return Document(
        document_id=document_id,
        job_id=job_id,
        status=DocStatus.COMPLETED,
        metadata=DocumentMetadata(filename=filename, file_type=MIME[kind], total_pages=len(pages), engine_versions={"parser": f"native-{kind.value}"}),
        pages=pages,
    )
