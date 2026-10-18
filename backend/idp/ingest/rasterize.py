"""Turn PDFs / images into page bitmaps (RGB uint8) and classify the PDF text layer."""

from __future__ import annotations

import io
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageOps, ImageSequence


class TextLayerStatus(StrEnum):
    NONE = "none"  # scanned page — OCR required
    CLEAN = "clean"  # usable Unicode text layer
    BROKEN = "broken"  # glyphs without a usable mapping — force OCR


@dataclass
class SourcePage:
    page_number: int
    image: np.ndarray  # RGB uint8
    text: str = ""
    text_status: TextLayerStatus = TextLayerStatus.NONE


_BAD_CHARS = {"�", "□", "■", "\x00"}


def text_layer_status(text: str) -> TextLayerStatus:
    visible = [c for c in text if not c.isspace()]
    if len(visible) < 20:
        return TextLayerStatus.NONE
    bad = sum(1 for c in visible if c in _BAD_CHARS or 0xE000 <= ord(c) <= 0xF8FF or (ord(c) < 32))
    return TextLayerStatus.BROKEN if bad / len(visible) > 0.05 else TextLayerStatus.CLEAN


def iter_pdf_pages(data: bytes, dpi: int = 300) -> Iterator[SourcePage]:
    pdf = pdfium.PdfDocument(data)
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            try:
                textpage = page.get_textpage()
                text = textpage.get_text_range()
                textpage.close()
                bitmap = page.render(scale=dpi / 72)
                img = np.ascontiguousarray(bitmap.to_numpy()[..., :3][..., ::-1]) if bitmap.mode == "BGR" else np.array(bitmap.to_pil().convert("RGB"))
                bitmap.close()
            finally:
                page.close()
            yield SourcePage(page_number=i + 1, image=img, text=text, text_status=text_layer_status(text))
    finally:
        pdf.close()


def pdf_page_count(data: bytes) -> int:
    pdf = pdfium.PdfDocument(data)
    try:
        return len(pdf)
    finally:
        pdf.close()


def iter_image_pages(data: bytes) -> Iterator[SourcePage]:
    with Image.open(io.BytesIO(data)) as im:
        for i, frame in enumerate(ImageSequence.Iterator(im)):
            frame = ImageOps.exif_transpose(frame) if i == 0 else frame
            yield SourcePage(page_number=i + 1, image=np.array(frame.convert("RGB")))


def image_page_count(data: bytes) -> int:
    with Image.open(io.BytesIO(data)) as im:
        return getattr(im, "n_frames", 1)
