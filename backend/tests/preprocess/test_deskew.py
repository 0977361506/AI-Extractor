import math

import cv2
import numpy as np
import pytest

from idp.preprocess.deskew import estimate_skew, rotate_bound


def _quad(angle_deg: float, length=300, height=20, x=50, y=100):
    a = math.radians(angle_deg)
    dx, dy = math.cos(a), math.sin(a)
    tl = np.array([x, y])
    tr = tl + length * np.array([dx, dy])
    bl = tl + height * np.array([-dy, dx])
    br = tr + height * np.array([-dy, dx])
    return np.array([tl, tr, br, bl], np.float32)


@pytest.mark.parametrize("angle", [0.0, 2.5, -4.0, 12.0])
def test_estimate_skew_from_text_quads(angle):
    quads = [_quad(angle, y=50 + 40 * i) for i in range(8)] + [_quad(0, length=15, height=15)]  # tiny box ignored
    assert estimate_skew(quads) == pytest.approx(angle, abs=0.3)


def test_estimate_skew_without_lines_is_zero():
    assert estimate_skew([]) == 0.0


def test_rotate_bound_straightens_a_sloped_line():
    img = np.full((400, 600), 255, np.uint8)
    angle = 6.0
    x0, y0 = 50, 100
    x1 = 550
    y1 = int(y0 + (x1 - x0) * math.tan(math.radians(angle)))
    cv2.line(img, (x0, y0), (x1, y1), 0, 3)
    out = rotate_bound(img, angle)
    assert out.shape[0] >= img.shape[0] and out.shape[1] >= img.shape[1]
    ys, xs = np.nonzero(out < 128)
    slope = np.polyfit(xs, ys, 1)[0]
    assert abs(math.degrees(math.atan(slope))) < 0.5
    assert out[0, 0] == 255  # white fill


def test_rotate_bound_zero_is_identity():
    img = np.random.randint(0, 255, (50, 80, 3), np.uint8)
    assert np.array_equal(rotate_bound(img, 0.0), img)
