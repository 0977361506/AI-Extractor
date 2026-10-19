import pytest

from idp.core.ast import ChoiceOption, Document, DocumentMetadata, Element, ElementType, Page, ReviewReason, TableCell
from idp.jobs.corrections import CorrectionError, apply_corrections, apply_one, read_path


def _doc():
    cells = [
        TableCell(row=0, col=0, text="Chỉ tiêu", is_header=True),
        TableCell(row=0, col=1, text="Số tiền", is_header=True),
        TableCell(row=1, col=0, text="Tiền"),
        TableCell(row=1, col=1, text="15.250.0O0", confidence=0.6),
        TableCell(row=2, col=0, text="Cộng"),
        TableCell(row=2, col=1, text="15.250.000"),
    ]
    els = [
        Element(element_id="p", type=ElementType.PARAGRAPH, reading_order=0, text="Hôm nay", content_markdown="Hôm nay"),
        Element(element_id="t", type=ElementType.TABLE, reading_order=1, cells=cells, needs_human_review=True, review_reasons=[ReviewReason.LOW_CONFIDENCE]),
        Element(element_id="c", type=ElementType.CHOICE_GROUP, reading_order=2, options=[ChoiceOption(label="Nam", checked=False)]),
        Element(element_id="f", type=ElementType.FORM_FIELD, reading_order=3, label="Họ tên", value="LE HOANG"),
    ]
    return Document(
        document_id="d", job_id="j", metadata=DocumentMetadata(filename="a.pdf", file_type="application/pdf", total_pages=1),
        pages=[Page(page_number=1, width=10, height=10, elements=els)],
    )


def test_text_cell_option_and_field_corrections():
    doc = _doc()
    apply_one(doc, "p", "text", "Hôm nay, ngày 12")
    apply_one(doc, "t", "cells[1][1].text", "15.250.000")
    apply_one(doc, "c", "options[0].checked", True)
    apply_one(doc, "f", "value", "LÊ HOÀNG MINH")
    els = {e.element_id: e for _, e in doc.iter_elements()}
    assert els["p"].text == "Hôm nay, ngày 12" and els["p"].content_markdown == "Hôm nay, ngày 12" and els["p"].human_corrected
    cell = next(c for c in els["t"].cells if (c.row, c.col) == (1, 1))
    assert cell.text == "15.250.000" and cell.numeric_value == 15250000 and cell.confidence == 1.0
    assert "15.250.000" in els["t"].content_html
    assert els["c"].options[0].checked is True
    assert els["f"].value == "LÊ HOÀNG MINH"


def test_review_marks_element_as_checked():
    doc = _doc()
    apply_one(doc, "t", "review", True)
    t = next(e for _, e in doc.iter_elements() if e.element_id == "t")
    assert not t.needs_human_review and t.review_reasons == [] and t.human_corrected


def test_structure_replacement_rerenders_and_rechecks():
    doc = _doc()
    new_cells = [
        {"row": 0, "col": 0, "colspan": 2, "text": "Tổng hợp", "is_header": True},
        {"row": 1, "col": 0, "text": "A"},
        {"row": 1, "col": 1, "text": "1"},
    ]
    apply_one(doc, "t", "cells", new_cells)
    t = next(e for _, e in doc.iter_elements() if e.element_id == "t")
    assert len(t.cells) == 3 and 'colspan="2"' in t.content_html


def test_invalid_paths_rejected():
    doc = _doc()
    with pytest.raises(CorrectionError):
        apply_one(doc, "nope", "text", "x")
    with pytest.raises(CorrectionError):
        apply_one(doc, "p", "__class__", "x")
    with pytest.raises(CorrectionError):
        apply_one(doc, "t", "cells[9][9].text", "x")


def test_apply_corrections_in_order_and_read_path():
    doc = _doc()
    rows = [
        {"element_id": "p", "path": "text", "new_value": "A"},
        {"element_id": "p", "path": "text", "new_value": "B"},
    ]
    apply_corrections(doc, rows)
    assert read_path(doc, "p", "text") == "B"
    assert read_path(doc, "t", "cells[1][1].text") == "15.250.0O0"
