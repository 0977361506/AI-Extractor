import numpy as np

from idp.ocr.recognizer import widen


def test_widen_pads_narrow_crops_only():
    narrow = np.zeros((40, 20), np.uint8)
    assert widen(narrow).shape == (40, 80)
    wide = np.zeros((40, 200), np.uint8)
    assert widen(wide).shape == (40, 200)
