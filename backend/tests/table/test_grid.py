import cv2
import numpy as np

from idp.table.grid import detect_grid


def _draw_table():
    """3 columns x 4 rows; header cell (0,1)-(0,2) merged horizontally; cell (2,0)-(3,0) merged vertically."""
    img = np.full((460, 640), 255, np.uint8)
    xs = [20, 220, 420, 620]
    ys = [20, 120, 220, 320, 440]
    t = 3
    for y in ys:
        cv2.line(img, (xs[0], y), (xs[-1], y), 0, t)
    for x in (xs[0], xs[-1]):
        cv2.line(img, (x, ys[0]), (x, ys[-1]), 0, t)
    # inner vertical x=220 everywhere except it's fine; x=420 missing in header row (merge)
    cv2.line(img, (220, ys[0]), (220, ys[-1]), 0, t)
    cv2.line(img, (420, ys[1]), (420, ys[-1]), 0, t)
    # remove horizontal y=320 inside column 0 (vertical merge rows 2-3)
    cv2.line(img, (xs[0] + 3, 320), (220 - 3, 320), 255, t + 2)
    return img


def test_detects_rows_cols_and_spans():
    grid = detect_grid(_draw_table(), line_height=30)
    assert grid is not None
    assert grid.n_rows == 4 and grid.n_cols == 3
    spans = {(c.row, c.col): (c.rowspan, c.colspan) for c in grid.cells}
    assert spans[(0, 1)] == (1, 2)
    assert spans[(2, 0)] == (2, 1)
    assert (0, 2) not in spans and (3, 0) not in spans
    assert len(grid.cells) == 12 - 1 - 1


def test_cell_boxes_are_inside_table():
    grid = detect_grid(_draw_table(), line_height=30)
    c = next(c for c in grid.cells if (c.row, c.col) == (0, 0))
    x0, y0, x1, y1 = c.bbox
    assert 15 <= x0 <= 30 and 15 <= y0 <= 30 and 210 <= x1 <= 230 and 110 <= y1 <= 130


def test_returns_none_without_ruling():
    img = np.full((300, 300), 255, np.uint8)
    cv2.putText(img, "no lines here", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, 0, 2)
    assert detect_grid(img, line_height=30) is None


def test_noise_band_below_a_line_does_not_shift_it():
    img = _draw_table()
    for x in range(30, 600, 90):  # band of short horizontal dashes right below y=220
        for y in range(232, 262, 4):
            img[y, x : x + 70] = 120
    grid = detect_grid(img, line_height=30)
    assert any(abs(y - 220) <= 3 for y in grid.ys)


def test_aligned_glyph_strokes_are_not_a_column():
    img = _draw_table()
    for y0 in (135, 235):  # 40px strokes at the same x inside two rows (like tall glyphs)
        img[y0 : y0 + 40, 110:113] = 0
    grid = detect_grid(img, line_height=30)
    assert grid.n_cols == 3
