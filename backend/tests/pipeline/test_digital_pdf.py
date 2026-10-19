import io
from pathlib import Path

import pytest

from idp.core.ast import ElementType
from idp.ingest.rasterize import TextLayerStatus, iter_pdf_pages
from idp.layout.regions import LayoutRegion
from idp.pipeline.document import process_document
from idp.storage.local import LocalStorage

FONT = Path("C:/Windows/Fonts/arial.ttf")
pytestmark = pytest.mark.skipif(not FONT.exists(), reason="needs a TTF with Vietnamese glyphs")


def _pdf(lines: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    pdfmetrics.registerFont(TTFont("Arial", str(FONT)))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Arial", 14)
    y = 780
    for line in lines:
        c.drawString(72, y, line)
        y -= 30
    c.save()
    return buf.getvalue()


LINES = ["HỢP ĐỒNG CUNG CẤP DỊCH VỤ PHẦN MỀM", "Bên A: Công ty TNHH Giải pháp số Bình Minh", "Giá trị hợp đồng: 929.940.000 đồng"]


def test_text_layer_lines_carry_pixel_boxes():
    (page,) = list(iter_pdf_pages(_pdf(LINES), dpi=150))
    assert page.text_status == TextLayerStatus.CLEAN
    assert [ln.text for ln in page.lines] == LINES
    x0, y0, x1, y1 = page.lines[0].bbox
    assert 140 < x0 < 160 and y0 < y1 < 200  # 72pt * 150/72 = 150 px from the left, near the top


def test_legacy_tcvn3_text_layer_is_converted():
    (page,) = list(iter_pdf_pages(_pdf(["B¸o c¸o tµi chÝnh n¨m 2025 cña C«ng ty"]), dpi=72))
    assert page.lines[0].text == "Báo cáo tài chính năm 2025 của Công ty"
    assert page.charset == "TCVN3"


class _NoOcr:
    name = "forbidden"

    def detect(self, img):
        raise AssertionError("OCR detector must not run on digital PDF pages")

    def recognize(self, crops):
        raise AssertionError("OCR recognizer must not run on digital PDF pages")

    def classify_180(self, crops):
        raise AssertionError("no orientation on digital pages")


class _Layout:
    name = "fake_layout"

    def predict(self, rgb):
        h, w = rgb.shape[:2]
        return [LayoutRegion("title", 0.9, (0, 0, w, h * 0.08))]


class _Models:
    detector = _NoOcr()
    recognizer = _NoOcr()
    layout = _Layout()


def test_digital_pdf_skips_ocr(tmp_path):
    doc = process_document(_pdf(LINES), "hd.pdf", LocalStorage(tmp_path), _Models())
    els = doc.pages[0].elements
    assert els[0].type == ElementType.TITLE and els[0].text == LINES[0]
    assert any(e.text == LINES[2] for e in els)
    assert all(e.extraction_engine.startswith("pdf_text") for e in els)
