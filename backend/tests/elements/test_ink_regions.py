import cv2
import numpy as np

from idp.elements.ink_regions import InkKind, find_ink_blobs


def _masks(shape=(1000, 1000)):
    return {"red": np.zeros(shape, bool), "blue": np.zeros(shape, bool), "stain": np.zeros(shape, bool)}


def _draw(mask, fn):
    canvas = np.zeros(mask.shape, np.uint8)
    fn(canvas)
    mask |= canvas > 0


def test_round_stamp_with_inner_text():
    m = _masks()
    _draw(m["red"], lambda c: cv2.circle(c, (500, 500), 120, 255, 8))
    _draw(m["red"], lambda c: cv2.putText(c, "HA NOI", (420, 510), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 255, 3))
    blobs = find_ink_blobs(m, line_height=30)
    assert len(blobs) == 1
    assert blobs[0].kind == InkKind.STAMP and blobs[0].color == "red" and blobs[0].shape == "round"


def test_rectangular_stamp():
    m = _masks()
    _draw(m["red"], lambda c: cv2.rectangle(c, (300, 300), (650, 420), 255, 7))
    _draw(m["red"], lambda c: cv2.putText(c, "DA TIEP NHAN", (320, 375), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 255, 3))
    (blob,) = find_ink_blobs(m, line_height=30)
    assert blob.kind == InkKind.STAMP and blob.shape == "rectangle"


def test_pen_circle_without_content_is_a_mark():
    m = _masks()
    _draw(m["red"], lambda c: cv2.ellipse(c, (500, 500), (200, 90), 0, 0, 360, 255, 4))
    (blob,) = find_ink_blobs(m, line_height=30)
    assert blob.kind == InkKind.MARK


def test_blue_handwriting_line():
    m = _masks()
    _draw(m["blue"], lambda c: cv2.putText(c, "Da doi chieu OK", (100, 600), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.5, 255, 3))
    (blob,) = find_ink_blobs(m, line_height=30)
    assert blob.kind == InkKind.HANDWRITING and blob.color == "blue"
    x0, y0, x1, y1 = blob.bbox
    assert x0 < 110 and x1 > 400 and y0 < 600 < y1


def test_tiny_specks_ignored():
    m = _masks()
    m["blue"][10:13, 10:13] = True
    assert find_ink_blobs(m, line_height=30) == []


def test_rotated_rectangular_stamp():
    m = _masks()
    box = cv2.boxPoints(((480, 400), (360, 120), -6)).astype(np.int32)
    _draw(m["red"], lambda c: cv2.polylines(c, [box], True, 255, 7))
    _draw(m["red"], lambda c: cv2.putText(c, "DA TIEP NHAN", (340, 410), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 255, 3))
    (blob,) = find_ink_blobs(m, line_height=30)
    assert blob.kind == InkKind.STAMP and blob.shape == "rectangle"


def test_tall_narrow_pen_circle_is_a_mark():
    m = _masks()
    _draw(m["red"], lambda c: cv2.ellipse(c, (500, 500), (40, 170), 0, 0, 360, 255, 4))
    (blob,) = find_ink_blobs(m, line_height=30)
    assert blob.kind == InkKind.MARK


def test_blobs_inside_ignore_boxes_are_skipped():
    m = _masks()
    _draw(m["blue"], lambda c: cv2.rectangle(c, (100, 100), (300, 300), 255, -1))
    assert find_ink_blobs(m, line_height=30, ignore_boxes=[(50, 50, 400, 400)]) == []


def test_comb_box_letters_on_one_row_merge_into_one_blob():
    m = _masks()
    for i, x in enumerate(range(100, 700, 50)):  # one handwritten letter per comb box
        if i in (2, 7):
            continue  # empty boxes between words
        _draw(m["blue"], lambda c, x=x: cv2.putText(c, "A", (x, 520), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 255, 3))
    blobs = find_ink_blobs(m, line_height=30)
    assert len(blobs) == 1 and blobs[0].kind == InkKind.HANDWRITING
