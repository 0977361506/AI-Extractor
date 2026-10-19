import json

import pytest

from idp.core.ast import Document, DocumentMetadata, Element, ElementType, Page, TableCell
from idp.evaluation.metrics import cer, normalize_text, teds
from idp.evaluation.runner import evaluate_documents
from idp.table.render import cells_to_html


def test_normalize_text_collapses_whitespace_and_nfc():
    assert normalize_text("Hòa  \n bình ") == "Hòa bình"


def test_cer():
    assert cer("Hà Nội", "Hà Nội") == 0.0
    assert cer("Ha Nội", "Hà Nội") == pytest.approx(1 / 6)
    assert cer("", "") == 0.0
    assert cer("abc", "") == 1.0


def _cells(rows):
    return [TableCell(row=r, col=c, text=t, is_header=r == 0) for r, row in enumerate(rows) for c, t in enumerate(row)]


def test_teds_identical_is_one_and_structure_errors_cost():
    ref = cells_to_html(_cells([["A", "B"], ["1", "2"]]))
    assert teds(ref, ref) == pytest.approx(1.0)
    worse = cells_to_html(_cells([["A", "B"], ["1", "3"]]))
    assert 0.8 < teds(worse, ref) < 1.0
    merged = cells_to_html([TableCell(row=0, col=0, colspan=2, text="AB", is_header=True), *_cells([["x", "y"], ["1", "2"]])[2:]])
    assert teds(merged, ref) < teds(worse, ref)


def _doc(text, table_rows):
    els = [Element(element_id="p", type=ElementType.PARAGRAPH, reading_order=0, text=text)]
    if table_rows:
        cells = _cells(table_rows)
        els.append(Element(element_id="t", type=ElementType.TABLE, reading_order=1, cells=cells, content_html=cells_to_html(cells)))
    return Document(
        document_id="d", job_id="j", metadata=DocumentMetadata(filename="a.pdf", file_type="application/pdf", total_pages=1),
        pages=[Page(page_number=1, width=10, height=10, elements=els)],
    )


def test_evaluate_documents_reports_per_page_and_summary(tmp_path):
    gt = tmp_path / "gt" / "a"
    pred = tmp_path / "pred" / "a"
    gt.mkdir(parents=True)
    pred.mkdir(parents=True)
    (gt / "ast.json").write_text(_doc("Hợp đồng số 1", [["A", "B"], ["1", "2"]]).to_json(), encoding="utf-8")
    (pred / "ast.json").write_text(_doc("Hợp đồng sô 1", [["A", "B"], ["1", "2"]]).to_json(), encoding="utf-8")
    report = evaluate_documents(tmp_path / "gt", tmp_path / "pred")
    assert report["documents"][0]["name"] == "a"
    page = report["documents"][0]["pages"][0]
    assert page["cer"] > 0 and page["teds"] == pytest.approx(1.0)
    assert report["summary"]["pages"] == 1
    json.dumps(report)
