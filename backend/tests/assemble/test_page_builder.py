import pytest

from idp.assemble.page_builder import build_elements
from idp.core.ast import ElementType, ReviewReason, TableCell
from idp.layout.regions import LayoutRegion
from idp.table.builder import OcrLine


def L(text, x0, y0, x1, y1, conf=0.9):
    return OcrLine(text=text, confidence=conf, bbox=(x0, y0, x1, y1))


W, H = 1000, 1400


def test_lines_are_assigned_to_regions_and_typed():
    regions = [
        LayoutRegion("title", 0.9, (100, 100, 900, 150)),
        LayoutRegion("text", 0.9, (50, 200, 950, 300)),
        LayoutRegion("page_footer", 0.9, (400, 1350, 600, 1390)),
    ]
    lines = [
        L("HỢP ĐỒNG", 300, 110, 700, 140),
        L("Hôm nay, ngày 12", 60, 210, 900, 240),
        L("chúng tôi gồm:", 60, 250, 300, 280),
        L("Trang 1/4", 420, 1355, 580, 1385),
    ]
    els = build_elements(1, W, H, regions, lines, tables={}, extra=[], review_threshold=0.8)
    assert [e.type for e in els] == [ElementType.TITLE, ElementType.PARAGRAPH, ElementType.PAGE_FOOTER]
    assert els[0].content_markdown == "# HỢP ĐỒNG"
    assert els[1].text == "Hôm nay, ngày 12\nchúng tôi gồm:"
    assert [e.element_id for e in els] == ["el_p1_001", "el_p1_002", "el_p1_003"]
    assert [e.reading_order for e in els] == [0, 1, 2]
    assert els[1].bbox_normalized == pytest.approx((0.05, 200 / H, 0.95, 300 / H), abs=1e-4)
    assert len(els[1].lines) == 2


def test_orphan_lines_become_paragraphs():
    lines = [L("ghi chú lẻ", 100, 500, 400, 530)]
    els = build_elements(2, W, H, [], lines, tables={}, extra=[], review_threshold=0.8)
    assert len(els) == 1 and els[0].type == ElementType.PARAGRAPH and els[0].text == "ghi chú lẻ"


def test_low_confidence_is_flagged():
    regions = [LayoutRegion("text", 0.9, (50, 200, 950, 300))]
    els = build_elements(1, W, H, regions, [L("mờ", 60, 210, 200, 240, conf=0.5)], tables={}, extra=[], review_threshold=0.8)
    assert els[0].needs_human_review and ReviewReason.LOW_CONFIDENCE in els[0].review_reasons
    assert els[0].confidence_score == 0.5


def test_table_region_uses_given_cells_and_absorbs_lines():
    regions = [LayoutRegion("table", 0.95, (50, 400, 950, 800))]
    cells = [
        TableCell(row=0, col=0, text="Chỉ tiêu", is_header=True),
        TableCell(row=0, col=1, text="Số tiền", is_header=True),
        TableCell(row=1, col=0, text="Doanh thu"),
        TableCell(row=1, col=1, text="12.450", numeric_value=12450),
    ]
    lines = [L("Doanh thu", 60, 500, 200, 530)]
    els = build_elements(1, W, H, regions, lines, tables={0: cells}, extra=[], review_threshold=0.8)
    assert len(els) == 1
    t = els[0]
    assert t.type == ElementType.TABLE
    assert "<th>Chỉ tiêu</th>" in t.content_html
    assert t.content_markdown.splitlines()[0] == "| Chỉ tiêu | Số tiền |"


def test_table_with_failed_check_is_flagged():
    regions = [LayoutRegion("table", 0.95, (50, 400, 950, 800))]
    cells = [TableCell(row=0, col=0, text="Tổng", check_failed=True)]
    (t,) = build_elements(1, W, H, regions, [], tables={0: cells}, extra=[], review_threshold=0.8)
    assert ReviewReason.ARITHMETIC_CHECK_FAILED in t.review_reasons


def test_checkbox_regions_are_skipped_and_picture_keeps_text():
    regions = [LayoutRegion("checkbox_selected", 0.9, (100, 100, 200, 130)), LayoutRegion("picture", 0.9, (100, 300, 900, 900))]
    lines = [L("Bắt đầu", 400, 350, 600, 380)]
    els = build_elements(1, W, H, regions, lines, tables={}, extra=[], review_threshold=0.8)
    assert [e.type for e in els] == [ElementType.FIGURE]
    assert els[0].text == "Bắt đầu"


def test_long_section_header_is_demoted_to_paragraph():
    regions = [LayoutRegion("section_header", 0.9, (50, 200, 950, 240))]
    text = "Bằng chữ: Chín trăm hai mươi chín triệu chín trăm bốn mươi nghìn đồng chẵn."
    (el,) = build_elements(1, W, H, regions, [L(text, 60, 205, 940, 235)], tables={}, extra=[], review_threshold=0.8)
    assert el.type == ElementType.PARAGRAPH
