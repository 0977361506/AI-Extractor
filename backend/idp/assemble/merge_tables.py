"""Join tables split across pages into logical tables; re-run arithmetic checks on the joined table."""

from __future__ import annotations

from idp.core.ast import Document, Element, ElementType, LogicalTable, ReviewReason, TableCell, TablePart
from idp.table.checks import run_arithmetic_checks
from idp.table.render import cells_to_html, cells_to_markdown, grid_shape, header_row_count

_PASSIVE = {ElementType.PAGE_HEADER, ElementType.PAGE_FOOTER, ElementType.CAPTION}


def _ordered(page) -> list[Element]:
    return sorted(page.elements, key=lambda e: e.reading_order)


def _header_texts(el: Element) -> list[str]:
    n = header_row_count(el.cells)
    return [c.text.strip().lower() for c in sorted(el.cells, key=lambda c: (c.row, c.col)) if c.row < n]


def _first_row_texts(el: Element) -> list[str]:
    return [c.text.strip().lower() for c in sorted(el.cells, key=lambda c: c.col) if c.row == 0]


def _continues(doc: Document, pi: int, t1: Element, t2: Element) -> bool:
    if grid_shape(t1.cells)[1] != grid_shape(t2.cells)[1]:
        return False
    nxt = _ordered(doc.pages[pi + 1])
    before = nxt[: nxt.index(t2)]
    if any(e.type not in _PASSIVE and not (e.type == ElementType.PARAGRAPH and len(e.text) < 80) for e in before):
        return False
    cur = _ordered(doc.pages[pi])
    after = cur[cur.index(t1) + 1 :]
    hint = any("tiếp" in e.text.lower() for e in after + before)
    head1 = _header_texts(t1)
    no_header = header_row_count(t2.cells) == 0
    same_header = bool(head1) and _first_row_texts(t2) == head1[: len(_first_row_texts(t2))]
    return hint or no_header or same_header


def merge_cross_page_tables(doc: Document) -> None:
    by_page = {p.page_number: [e for e in _ordered(p) if e.type == ElementType.TABLE and e.cells] for p in doc.pages}
    # chain: last table of page i + first table of page i+1
    chains: list[list[tuple[int, Element]]] = []
    linked: set[str] = set()
    for pi, page in enumerate(doc.pages):
        for el in by_page.get(page.page_number, []):
            if el.element_id in linked:
                continue
            chain = [(page.page_number, el)]
            cur_pi, cur = pi, el
            while cur_pi + 1 < len(doc.pages):
                tables_here = by_page.get(doc.pages[cur_pi].page_number, [])
                tables_next = by_page.get(doc.pages[cur_pi + 1].page_number, [])
                if not tables_next or tables_here[-1] is not cur or not _continues(doc, cur_pi, cur, tables_next[0]):
                    break
                cur_pi, cur = cur_pi + 1, tables_next[0]
                chain.append((doc.pages[cur_pi].page_number, cur))
                linked.add(cur.element_id)
            chains.append(chain)

    doc.logical_tables = []
    for n, chain in enumerate(chains):
        first = chain[0][1]
        n_header = header_row_count(first.cells)
        logical: list[TableCell] = []
        origin: list[tuple[TableCell, Element]] = []
        parts: list[TablePart] = []
        offset = n_header
        for idx, (page_number, el) in enumerate(chain):
            own_header = header_row_count(el.cells)
            if idx == 0:
                for c in el.cells:
                    if c.row < n_header:
                        logical.append(c.model_copy())
                        origin.append((logical[-1], c))
            skip = own_header if idx == 0 or own_header else 0
            if idx > 0 and not own_header and _first_row_texts(el) == _header_texts(first)[: len(_first_row_texts(el))]:
                skip = 1
            body = [c for c in el.cells if c.row >= skip]
            if not body:
                continue
            rows = sorted({c.row for c in body})
            for c in body:
                copy = c.model_copy(update={"row": c.row - skip + offset, "is_header": False})
                logical.append(copy)
                origin.append((copy, c))
            parts.append(TablePart(page_number=page_number, element_id=el.element_id, row_start=offset, row_end=offset + rows[-1] - skip))
            offset += rows[-1] - skip + 1
        for (_, a), (_, b) in zip(chain, chain[1:]):
            a.continues_to = b.element_id
            b.continues_from = a.element_id
        if len(chain) > 1:
            run_arithmetic_checks(logical)
            for copy, orig in origin:
                orig.check_failed = copy.check_failed
            for _, el in chain:
                reasons = [r for r in el.review_reasons if r != ReviewReason.ARITHMETIC_CHECK_FAILED]
                if any(c.check_failed for c in el.cells):
                    reasons.append(ReviewReason.ARITHMETIC_CHECK_FAILED)
                el.review_reasons = reasons
                el.needs_human_review = bool(reasons)
                el.content_html = cells_to_html(el.cells)
        doc.logical_tables.append(
            LogicalTable(
                logical_table_id=f"lt_{n + 1:03d}",
                header_rows=n_header,
                cells=logical,
                content_html=cells_to_html(logical),
                content_markdown=cells_to_markdown(logical),
                parts=parts,
            )
        )
