import numpy as np

from idp.preprocess.orientation import detect_orientation, rotate_orthogonal

H_BOX = np.array([[0, 0], [100, 0], [100, 20], [0, 20]], np.float32)
V_BOX = np.array([[0, 0], [20, 0], [20, 100], [0, 100]], np.float32)


class FakeDetector:
    def __init__(self, first, second=None, cls_label="0"):
        self.calls = 0
        self.first, self.second, self.cls_label = first, second, cls_label

    def detect(self, img):
        self.calls += 1
        if self.calls == 1 or self.second is None:
            return self.first
        return self.second

    def classify_180(self, crops):
        return [(self.cls_label, 0.99) for _ in crops]


def _img():
    return np.full((300, 200, 3), 255, np.uint8)


def test_rotate_orthogonal_clockwise():
    img = np.zeros((2, 3), np.uint8)
    img[0, 0] = 1  # top-left
    r = rotate_orthogonal(img, 90)  # clockwise: top-left -> top-right
    assert r.shape == (3, 2)
    assert r[0, 1] == 1
    assert np.array_equal(rotate_orthogonal(rotate_orthogonal(img, 90), 270), img)


def test_upright_page():
    assert detect_orientation(_img(), FakeDetector([H_BOX] * 10)) == 0


def test_upside_down_page():
    assert detect_orientation(_img(), FakeDetector([H_BOX] * 10, cls_label="180")) == 180


def test_sideways_page_reading_bottom_to_top_needs_90():
    det = FakeDetector([V_BOX] * 10, second=[H_BOX] * 10, cls_label="0")
    assert detect_orientation(_img(), det) == 90


def test_sideways_page_reading_top_to_bottom_needs_270():
    det = FakeDetector([V_BOX] * 10, second=[H_BOX] * 10, cls_label="180")
    assert detect_orientation(_img(), det) == 270


def test_too_few_boxes_means_no_rotation():
    assert detect_orientation(_img(), FakeDetector([V_BOX])) == 0
