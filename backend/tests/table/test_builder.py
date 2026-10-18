import cv2
import numpy as np

from idp.table.builder import OcrLine, build_borderless_table, build_ruled_table, sanitize_ocr, segment_text_lines


class FakeRecognizer:
    """Returns a deterministic text per crop based on the crop's width (stand-in for VietOCR)."""

    def __init__(self, texts=None):
        self.calls = 0
        self.texts = texts or {}

    def recognize(self, crops):
        out = []
        for c in crops:
            self.calls += 1
            out.append((self.texts.get(self.calls, f"t{self.calls}"), 0.9))
        return out


def _text_block(img, x, y, w, h=24):
    """Glyph-like texture: thin vertical strokes (solid blocks would look like ruling lines)."""
    for cx in range(x, x + w, 6):
        img[y : y + h, cx : cx + 3] = 30


def test_segment_text_lines_merges_diacritics_and_drops_noise():
    img = np.full((120, 300), 255, np.uint8)
    _text_block(img, 10, 20, 200)  # line 1
    img[12:16, 40:50] = 30  # diacritic above line 1
    _text_block(img, 10, 70, 150)  # line 2
    img[110:112, 280:282] = 30  # noise dot
    segs = segment_text_lines(img, line_height=30)
    assert len(segs) == 2
    y0, y1, x0, x1 = segs[0]
    assert y0 <= 12 and y1 >= 44 and x0 <= 10 and x1 >= 210


def _ruled_table_img():
    img = np.full((240, 620), 255, np.uint8)
    for y in (10, 80, 150, 230):
        cv2.line(img, (10, y), (610, y), 0, 3)
    for x in (10, 300, 610):
        cv2.line(img, (x, 10), (x, 230), 0, 3)
    _text_block(img, 40, 30, 120)  # (0,0)
    _text_block(img, 330, 30, 120)  # (0,1)
    _text_block(img, 40, 100, 120)  # (1,0)
    _text_block(img, 330, 100, 90)  # (1,1)
    _text_block(img, 40, 165, 150)  # (2,0) two lines
    _text_block(img, 40, 195, 100)
    return img


def test_build_ruled_table_reads_each_cell():
    rec = FakeRecognizer({1: "Chỉ tiêu", 2: "Số tiền", 3: "Doanh thu", 4: "12.45O", 5: "Lợi nhuận", 6: "gộp", 7: "5.030"})
    _text_block_img = _ruled_table_img()
    _text_block(_text_block_img, 330, 170, 90)  # (2,1)
    cells = build_ruled_table(_text_block_img, (0, 0), 620, 240, line_height=30, recognizer=rec)
    assert cells is not None
    texts = {(c.row, c.col): c.text for c in cells}
    assert texts[(0, 0)] == "Chỉ tiêu"
    assert texts[(2, 0)] == "Lợi nhuận gộp"
    assert texts[(1, 1)] == "12.450"  # OCR fix applied in numeric column
    num = {(c.row, c.col): c.numeric_value for c in cells}
    assert num[(1, 1)] == 12450
    assert all(c.is_header for c in cells if c.row == 0)
    assert not any(c.is_header for c in cells if c.row > 0)
    assert all(c.bbox is not None and 0 <= c.bbox[0] <= 1 for c in cells)


def test_build_ruled_table_returns_none_for_unruled():
    img = np.full((200, 400), 255, np.uint8)
    _text_block(img, 20, 20, 200)
    assert build_ruled_table(img, (0, 0), 400, 200, 30, FakeRecognizer()) is None


def test_borderless_table_from_lines():
    def L(text, x0, y0, x1, y1):
        return OcrLine(text=text, confidence=0.9, bbox=(x0, y0, x1, y1))

    lines = [
        L("Khoản mục", 10, 10, 120, 30), L("Số tiền", 300, 10, 380, 30),
        L("Lương", 10, 50, 80, 70), L("620", 330, 50, 370, 70),
        L("Thưởng", 10, 90, 90, 110), L("210", 330, 90, 370, 110),
    ]
    cells = build_borderless_table(lines, page_w=1000, page_h=1000)
    grid = {(c.row, c.col): c.text for c in cells}
    assert grid == {(0, 0): "Khoản mục", (0, 1): "Số tiền", (1, 0): "Lương", (1, 1): "620", (2, 0): "Thưởng", (2, 1): "210"}


def test_segments_split_far_apart_words_and_drop_specks():
    img = np.full((60, 600), 255, np.uint8)
    img[25:28, 15:18] = 30  # speck far left
    _text_block(img, 300, 15, 120)  # the number
    _text_block(img, 470, 15, 60)  # another word after a big gap
    segs = segment_text_lines(img, line_height=30)
    assert len(segs) == 2
    assert segs[0][2] >= 290 and segs[1][2] >= 460


def test_degenerate_repeated_output_is_rejected():
    from idp.table.builder import sanitize_ocr

    assert sanitize_ocr("STRANSKING THE THI THI THI THỊ THỊ THỊ THỊ", 0.3) == ("", 0.0)
    assert sanitize_ocr("Tổng cộng", 0.9) == ("Tổng cộng", 0.9)


def test_formula_and_date_repairs():
    from idp.table.builder import repair_cell_text

    assert repair_cell_text("3. Doanh thu thuần (10 - 01 - 02)") == "3. Doanh thu thuần (10 = 01 - 02)"
    assert repair_cell_text("14. Tổng (50 - 30 + 40)") == "14. Tổng (50 = 30 + 40)"
    assert repair_cell_text("05/0712026") == "05/07/2026"
    assert repair_cell_text("12/07/2026") == "12/07/2026"


def test_empty_rows_and_columns_are_dropped():
    from idp.core.ast import TableCell
    from idp.table.builder import drop_empty_lines

    cells = [
        TableCell(row=0, col=0, text=""), TableCell(row=0, col=1, text=""), TableCell(row=0, col=2, text=""),
        TableCell(row=1, col=0, text="a"), TableCell(row=1, col=1, text=""), TableCell(row=1, col=2, text="b"),
        TableCell(row=2, col=0, text="c"), TableCell(row=2, col=1, text=""), TableCell(row=2, col=2, text="d"),
    ]
    out = drop_empty_lines(cells)
    assert sorted((c.row, c.col, c.text) for c in out) == [(0, 0, "a"), (0, 1, "b"), (1, 0, "c"), (1, 1, "d")]


def test_faint_gray_digit_is_segmented():
    img = np.full((80, 70), 250, np.uint8)
    img[25:55, 30:34] = 140  # light-gray printed "1"
    assert len(segment_text_lines(img, line_height=34)) == 1


def test_ruling_broken_by_pen_stroke_is_restored_from_presence_image():
    img = _ruled_table_img()
    presence = img.copy()
    img[75:86, 290:312] = 255  # the ink-removal step erased the ruling where a pen crossed it
    from idp.table.grid import detect_grid

    grid = detect_grid(img, 30, presence_gray=presence)
    assert len(grid.cells) == 6


def test_binary_noise_tokens_removed():
    assert sanitize_ocr("Kết chuyển giá vốn 7/2026 001000000100", 0.8) == ("Kết chuyển giá vốn 7/2026", 0.8)
