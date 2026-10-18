import pytest

from idp.core.geometry import crop_quad
from tests.conftest import render_example

pytestmark = pytest.mark.slow


def test_detector_finds_lines_and_classifier_votes(page_models):
    img = render_example("scan_test_hard.pdf", 1, dpi=150)
    quads = page_models.detector.detect(img)
    assert len(quads) > 20
    votes = page_models.detector.classify_180([crop_quad(img, q) for q in quads[:5]])
    assert all(label in {"0", "180"} for label, _ in votes)


def test_recognizer_reads_vietnamese_title(page_models):
    img = render_example("scan_test_hard.pdf", 1, dpi=300)
    quads = page_models.detector.detect(img)
    texts = [t for t, _ in page_models.recognizer.recognize([crop_quad(img, q) for q in quads])]
    assert any("HỢP ĐỒNG CUNG CẤP DỊCH VỤ PHẦN MỀM" in t for t in texts)


def test_layout_finds_table_on_income_statement(page_models):
    img = render_example("scan_test_2_bang_phuc_tap.pdf", 1, dpi=150)
    regions = page_models.layout.predict(img)
    assert any(r.label == "table" and r.score > 0.8 for r in regions)
