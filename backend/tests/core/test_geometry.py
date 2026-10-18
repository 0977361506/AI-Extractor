import numpy as np
import pytest

from idp.core.geometry import (
    containment,
    crop_quad,
    iou,
    normalize_bbox,
    quad_to_bbox,
    quad_wh,
    union_bbox,
)


def test_iou_identical_and_disjoint():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(50 / 150)


def test_containment_is_fraction_of_first_box_inside_second():
    assert containment((2, 2, 4, 4), (0, 0, 10, 10)) == pytest.approx(1.0)
    assert containment((0, 0, 10, 10), (0, 0, 5, 10)) == pytest.approx(0.5)
    assert containment((0, 0, 0, 0), (0, 0, 5, 5)) == 0.0


def test_quad_helpers():
    quad = np.array([[10, 20], [110, 20], [110, 50], [10, 50]], dtype=np.float32)
    w, h = quad_wh(quad)
    assert (w, h) == pytest.approx((100, 30))
    assert quad_to_bbox(quad) == (10, 20, 110, 50)


def test_normalize_bbox_clamps():
    assert normalize_bbox((-5, 10, 110, 50), 100, 100) == (0.0, 0.1, 1.0, 0.5)


def test_union_bbox():
    assert union_bbox([(0, 0, 1, 1), (2, 3, 4, 5)]) == (0, 0, 4, 5)


def test_crop_quad_returns_upright_patch():
    img = np.full((100, 200, 3), 255, np.uint8)
    img[20:50, 10:110] = 0
    quad = np.array([[10, 20], [110, 20], [110, 50], [10, 50]], dtype=np.float32)
    patch = crop_quad(img, quad, pad=0)
    assert patch.shape[:2] == (30, 100)
    assert patch.mean() < 10
