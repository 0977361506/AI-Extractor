"""RM corrections: stored separately (audit trail) and replayed onto the engine's AST on read / export."""

from __future__ import annotations

import re

from idp.assemble.page_builder import text_markdown
from idp.core.ast import Document, Element, ElementType, TableCell
from idp.elements.handwriting import infer_value_type
from idp.table.checks import run_arithmetic_checks
from idp.table.numbers import fix_numeric_ocr, parse_vn_number
from idp.table.render import cells_to_html, cells_to_markdown


class CorrectionError(ValueError):
    pass


_SIMPLE = {"text", "value", "label", "question", "signer_name", "mermaid", "description", "latex"}
_CELL = re.compile(r"^cells\[(\d+)\]\[(\d+)\]\.text$")
_OPTION = re.compile(r"^options\[(\d+)\]\.(label|checked)$")


def _find(doc: Document, element_id: str) -> Element:
    for _, el in doc.iter_elements():
        if el.element_id == element_id:
            return el
    raise CorrectionError(f"không tìm thấy phần tử {element_id!r}")


def _cell(el: Element, row: int, col: int) -> TableCell:
    for c in el.cells:
        if c.row == row and c.col == col:
            return c
    raise CorrectionError(f"không có ô [{row}][{col}] trong {el.element_id}")


def _rerender_table(el: Element) -> None:
    for c in el.cells:
        c.numeric_value = parse_vn_number(fix_numeric_ocr(c.text)) if c.text.strip() else None
    run_arithmetic_checks(el.cells)
    el.content_html = cells_to_html(el.cells)
    el.content_markdown = cells_to_markdown(el.cells)
    el.text = "\n".join(" | ".join(c.text for c in el.cells if c.row == r) for r in sorted({c.row for c in el.cells}))


def read_path(doc: Document, element_id: str, path: str):
    el = _find(doc, element_id)
    if path in _SIMPLE:
        return getattr(el, path)
    if m := _CELL.match(path):
        return _cell(el, int(m.group(1)), int(m.group(2))).text
    if m := _OPTION.match(path):
        return getattr(el.options[int(m.group(1))], m.group(2))
    if path == "cells":
        return [c.model_dump(mode="json") for c in el.cells]
    if path == "review":
        return not el.needs_human_review
    raise CorrectionError(f"đường dẫn không hợp lệ: {path!r}")


def apply_one(doc: Document, element_id: str, path: str, value) -> None:
    el = _find(doc, element_id)
    if path in _SIMPLE:
        if not isinstance(value, str):
            raise CorrectionError("giá trị phải là chuỗi")
        setattr(el, path, value)
        if path == "text" and el.type not in (ElementType.TABLE,):
            el.content_markdown = text_markdown(el.type, value, el.level)
        if path == "value":
            el.value_type = infer_value_type(value)
    elif m := _CELL.match(path):
        cell = _cell(el, int(m.group(1)), int(m.group(2)))
        cell.text = str(value)
        cell.confidence = 1.0
        cell.alt_text = None
        _rerender_table(el)
    elif m := _OPTION.match(path):
        idx = int(m.group(1))
        if idx >= len(el.options):
            raise CorrectionError(f"không có lựa chọn {idx}")
        setattr(el.options[idx], m.group(2), bool(value) if m.group(2) == "checked" else str(value))
    elif path == "cells":
        try:
            el.cells = [TableCell.model_validate({**c, "confidence": 1.0}) for c in value]
        except Exception as exc:  # pydantic validation
            raise CorrectionError(f"cấu trúc bảng không hợp lệ: {exc}") from exc
        _rerender_table(el)
    elif path == "review":
        if value:
            el.review_reasons = []
            el.needs_human_review = False
    else:
        raise CorrectionError(f"đường dẫn không hợp lệ: {path!r}")
    el.human_corrected = True


def apply_corrections(doc: Document, rows: list[dict]) -> Document:
    for row in rows:
        try:
            apply_one(doc, row["element_id"], row["path"], row["new_value"])
        except CorrectionError:
            continue  # element vanished after a re-run; keep the audit row but skip it
    return doc
