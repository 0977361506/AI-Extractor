import pytest

from idp.core.ast import DocStatus, ElementType
from idp.pipeline.document import process_document
from idp.storage.local import LocalStorage

pytestmark = pytest.mark.slow


def test_rotated_allocation_table_page_is_made_upright(page_models, examples_dir, tmp_path):
    data = (examples_dir / "scan_test_2_bang_phuc_tap.pdf").read_bytes()
    doc = process_document(data, "scan_test_2_bang_phuc_tap.pdf", LocalStorage(tmp_path), page_models, pages=[2])
    page = doc.pages[0]
    assert page.orientation_applied == 90
    tables = [e for e in page.elements if e.type == ElementType.TABLE]
    assert tables and len(tables[0].cells) > 40


def test_contract_first_page(page_models, examples_dir, tmp_path):
    data = (examples_dir / "scan_test_hard.pdf").read_bytes()
    doc = process_document(data, "scan_test_hard.pdf", LocalStorage(tmp_path), page_models, pages=[1])
    assert doc.status == DocStatus.COMPLETED
    text = "\n".join(e.text for _, e in doc.iter_elements())
    assert "HỢP ĐỒNG CUNG CẤP DỊCH VỤ PHẦN MỀM" in text
    assert any(e.type == ElementType.STAMP for _, e in doc.iter_elements())
    assert doc.chunks
