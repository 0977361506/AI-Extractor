import io

import numpy as np
import pypdfium2 as pdfium
from PIL import Image

from idp.ingest.rasterize import TextLayerStatus, iter_image_pages, iter_pdf_pages, text_layer_status


def _blank_pdf(n_pages: int = 2) -> bytes:
    pdf = pdfium.PdfDocument.new()
    for _ in range(n_pages):
        pdf.new_page(595, 842)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def test_pdf_pages_are_rendered_at_requested_dpi():
    pages = list(iter_pdf_pages(_blank_pdf(2), dpi=72))
    assert [p.page_number for p in pages] == [1, 2]
    assert pages[0].image.shape == (842, 595, 3)
    assert pages[0].image.dtype == np.uint8
    assert pages[0].text_status == TextLayerStatus.NONE


def test_multi_frame_tiff_is_split():
    frames = [Image.new("RGB", (40, 30), c) for c in ("white", "black", "red")]
    buf = io.BytesIO()
    frames[0].save(buf, format="TIFF", save_all=True, append_images=frames[1:])
    pages = list(iter_image_pages(buf.getvalue()))
    assert len(pages) == 3
    assert pages[2].image[0, 0].tolist() == [255, 0, 0]


def test_grayscale_png_becomes_rgb():
    buf = io.BytesIO()
    Image.new("L", (10, 10), 128).save(buf, format="PNG")
    (page,) = iter_image_pages(buf.getvalue())
    assert page.image.shape == (10, 10, 3)


def test_text_layer_status():
    assert text_layer_status("") == TextLayerStatus.NONE
    assert text_layer_status("   \n ") == TextLayerStatus.NONE
    assert text_layer_status("Báo cáo tài chính năm 2025 của Công ty ABC đã được kiểm toán.") == TextLayerStatus.CLEAN
    assert text_layer_status("��� B�o c�o  t�i ch�nh") == TextLayerStatus.BROKEN
    assert text_layer_status("□□□□ □□□ □□□□□□ □□ □□□□ □□□ abc def") == TextLayerStatus.BROKEN
