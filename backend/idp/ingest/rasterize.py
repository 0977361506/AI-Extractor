"""Turn PDFs / images into page bitmaps (RGB uint8) and classify the PDF text layer."""

from __future__ import annotations

import io
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageOps, ImageSequence

from idp.ingest.legacy_fonts import Charset, convert_legacy, detect_charset
from idp.table.builder import OcrLine


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
    lines: list[OcrLine] = field(default_factory=list)  # text-layer lines in image pixels (digital PDFs)
    charset: str = Charset.UNICODE.value


_BAD_CHARS = {"�", "□", "■", "\x00"}


def text_layer_status(text: str) -> TextLayerStatus:
    visible = [c for c in text if not c.isspace()]
    if len(visible) < 20:
        return TextLayerStatus.NONE
    bad = sum(1 for c in visible if c in _BAD_CHARS or 0xE000 <= ord(c) <= 0xF8FF or (ord(c) < 32))
    return TextLayerStatus.BROKEN if bad / len(visible) > 0.05 else TextLayerStatus.CLEAN


def _text_lines(textpage, page_height_pt: float, scale: float) -> list[OcrLine]:
    """Text-layer runs (pdfium rects) merged into lines, in rendered-image pixel coordinates."""
    runs = []
    for i in range(textpage.count_rects()):
        left, bottom, right, top = textpage.get_rect(i)
        text = " ".join(textpage.get_text_bounded(left, bottom, right, top).split())
        if text.strip():
            runs.append([text, left * scale, (page_height_pt - top) * scale, right * scale, (page_height_pt - bottom) * scale])
    runs.sort(key=lambda r: ((r[2] + r[4]) / 2, r[1]))
    lines: list[list] = []
    for text, x0, y0, x1, y1 in runs:
        if lines:
            last = lines[-1]
            h = max(1.0, last[4] - last[2])
            same_row = min(y1, last[4]) - max(y0, last[2]) > 0.5 * min(h, y1 - y0)
            gap = x0 - last[3]
            if same_row and -0.5 * h < gap < 1.5 * h:
                last[0] = last[0] + (" " if gap > 0.25 * h and not last[0].endswith(" ") else "") + text
                last[1], last[2], last[3], last[4] = min(last[1], x0), min(last[2], y0), max(last[3], x1), max(last[4], y1)
                continue
        lines.append([text, x0, y0, x1, y1])
    return [OcrLine(text=" ".join(t.split()), confidence=1.0, bbox=(x0, y0, x1, y1)) for t, x0, y0, x1, y1 in lines]


def iter_pdf_pages(data: bytes, dpi: int = 300) -> Iterator[SourcePage]:
    pdf = pdfium.PdfDocument(data)
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            try:
                textpage = page.get_textpage()
                text = textpage.get_text_range()
                status = text_layer_status(text)
                lines = _text_lines(textpage, page.get_height(), dpi / 72) if status == TextLayerStatus.CLEAN else []
                textpage.close()
                charset = detect_charset(text).value if lines else Charset.UNICODE.value
                if charset != Charset.UNICODE.value:
                    lines = [OcrLine(text=convert_legacy(ln.text), confidence=1.0, bbox=ln.bbox) for ln in lines]
                bitmap = page.render(scale=dpi / 72)
                img = np.ascontiguousarray(bitmap.to_numpy()[..., :3][..., ::-1]) if bitmap.mode == "BGR" else np.array(bitmap.to_pil().convert("RGB"))
                bitmap.close()
            finally:
                page.close()
            yield SourcePage(page_number=i + 1, image=img, text=text, text_status=status, lines=lines, charset=charset)
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
