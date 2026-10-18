"""Contextual RAG chunks: breadcrumb prefix on every chunk, table header repeated in every table chunk."""

from __future__ import annotations

from pathlib import PurePath

from idp.assemble.render_text import element_markdown
from idp.core.ast import Chunk, Document, Element, ElementType, SourceRef
from idp.table.render import cells_to_markdown, expand_grid, header_row_count

_SKIP = {ElementType.PAGE_HEADER, ElementType.PAGE_FOOTER}


def build_chunks(doc: Document, max_chars: int = 1800) -> list[Chunk]:
    stem = PurePath(doc.metadata.filename).stem
    chunks: list[Chunk] = []

    def context(breadcrumb: list[str]) -> str:
        return f"[Bối cảnh: {' > '.join([stem, *breadcrumb])}]"

    def emit(type_: str, breadcrumb: list[str], body: str, refs: list[SourceRef]) -> None:
        chunks.append(
            Chunk(
                chunk_id=f"{doc.document_id}_c{len(chunks):04d}",
                type=type_,
                breadcrumb=breadcrumb,
                text=f"{context(breadcrumb)}\n{body}",
                source_refs=refs,
            )
        )

    buf: list[str] = []
    buf_refs: list[SourceRef] = []
    buf_crumb: list[str] | None = None

    def flush() -> None:
        nonlocal buf, buf_refs, buf_crumb
        if buf:
            emit("text", buf_crumb or [], "\n\n".join(buf), buf_refs)
        buf, buf_refs, buf_crumb = [], [], None

    logical_by_first = {lt.parts[0].element_id: lt for lt in doc.logical_tables if lt.parts}
    elements_by_id: dict[str, tuple[int, Element]] = {
        el.element_id: (p.page_number, el) for p in doc.pages for el in p.elements
    }

    for page in doc.pages:
        for el in sorted(page.elements, key=lambda e: e.reading_order):
            if el.type in _SKIP:
                continue
            ref = SourceRef(page_number=page.page_number, element_id=el.element_id, bbox=el.bbox_normalized)
            if el.type == ElementType.TABLE:
                flush()
                lt = logical_by_first.get(el.element_id)
                if lt is None:
                    continue
                n_header = header_row_count(lt.cells)
                header_md = cells_to_markdown(lt.cells, body_rows=[])
                grid = expand_grid(lt.cells)
                rows = list(range(n_header, len(grid)))
                start = 0
                while start < len(rows):
                    size = len(header_md)
                    end = start
                    while end < len(rows):
                        line = cells_to_markdown(lt.cells, body_rows=[rows[end]]).splitlines()[-1]
                        if end > start and size + len(line) + 1 > max_chars:
                            break
                        size += len(line) + 1
                        end += 1
                    chunk_rows = rows[start:end]
                    refs = []
                    for part in lt.parts:
                        if part.row_start <= chunk_rows[-1] and part.row_end >= chunk_rows[0]:
                            pnum, pel = elements_by_id[part.element_id]
                            refs.append(SourceRef(page_number=pnum, element_id=pel.element_id, bbox=pel.bbox_normalized))
                    emit("table", el.hierarchy_breadcrumb, cells_to_markdown(lt.cells, body_rows=chunk_rows), refs)
                    start = end
                continue
            text = element_markdown(el)
            if not text:
                continue
            crumb = el.hierarchy_breadcrumb
            if buf and (crumb != buf_crumb or sum(len(b) for b in buf) + len(text) > max_chars):
                flush()
            if buf_crumb is None:
                buf_crumb = crumb
            buf.append(text)
            buf_refs.append(ref)
    flush()
    return chunks
