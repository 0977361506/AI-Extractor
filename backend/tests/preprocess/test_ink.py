import cv2
import numpy as np

from idp.preprocess.ink import separate_inks

WHITE, BLACK, RED, BLUE = (250, 250, 250), (20, 20, 20), (210, 40, 40), (40, 60, 190)


def _page():
    img = np.full((300, 400, 3), WHITE, np.uint8)
    img[140:160, 40:360] = BLACK  # printed text bar
    cv2.circle(img, (200, 150), 80, RED, 6)  # stamp ring crossing the text bar
    cv2.line(img, (40, 250), (360, 260), BLUE, 4)  # handwriting stroke
    # overlap: red ink printed over black text keeps a dark pixel
    img[145:155, 118:126] = (60, 15, 15)
    return img


def test_masks_identify_inks():
    res = separate_inks(_page())
    assert res.masks["red"][70, 200]  # top of the ring
    assert res.masks["blue"][255, 200]
    assert not res.masks["red"][150, 60]  # black text is not red
    assert res.coverage["red"] > 0.005
    assert res.coverage["blue"] > 0.002


def test_ocr_image_drops_colored_ink_and_keeps_black_text():
    res = separate_inks(_page())
    ocr = res.ocr_gray
    assert ocr.ndim == 2
    assert ocr[150, 60] < 80  # black text kept
    assert ocr[70, 200] > 230  # red ring removed
    assert ocr[255, 200] > 230  # blue stroke removed
    assert ocr[150, 121] < 110  # black text under red ink kept dark


def test_clean_page_has_no_colored_coverage():
    img = np.full((100, 100, 3), WHITE, np.uint8)
    img[40:60, 10:90] = BLACK
    res = separate_inks(img)
    assert res.coverage["red"] == 0 and res.coverage["blue"] == 0


def test_dark_navy_pen_and_dark_red_stamp_are_removed_but_black_under_red_kept():
    img = np.full((100, 300, 3), WHITE, np.uint8)
    img[10:30, 10:100] = (20, 25, 85)  # dark navy ballpoint
    img[40:60, 10:100] = (115, 25, 35)  # dark red stamp ink
    img[70:90, 10:100] = (50, 15, 15)  # black print under red ink
    img[70:90, 150:250] = BLACK
    ocr = separate_inks(img).ocr_gray
    assert ocr[20, 50] > 230
    assert ocr[50, 50] > 230
    assert ocr[80, 50] < 110
    assert ocr[80, 200] < 80


def test_desaturated_blue_gray_ballpoint_is_blue():
    img = np.full((40, 100, 3), WHITE, np.uint8)
    img[10:30, 10:90] = (114, 116, 143)  # measured on scan_test_2 handwriting
    res = separate_inks(img)
    assert res.masks["blue"][20, 50]
    assert res.ocr_gray[20, 50] > 230


def test_yellow_highlighter_becomes_background_keeping_text_and_rulings():
    img = np.full((60, 200, 3), WHITE, np.uint8)
    img[10:50, :] = (240, 228, 120)  # highlighter band
    img[20:40, 20:80] = (60, 58, 30)  # black text under highlighter
    img[29:31, :] = (130, 128, 70)  # gray table ruling under highlighter
    ocr = separate_inks(img).ocr_gray
    assert ocr[15, 150] > 225
    assert ocr[24, 50] < 90
    assert ocr[30, 150] < 160
