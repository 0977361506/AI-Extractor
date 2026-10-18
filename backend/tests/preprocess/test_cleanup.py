import numpy as np

from idp.preprocess.cleanup import normalize_illumination, remove_speckles


def test_normalize_illumination_flattens_shadow():
    h, w = 400, 400
    gradient = np.tile(np.linspace(255, 140, w, dtype=np.float32), (h, 1))  # shadow on the right
    img = np.stack([gradient] * 3, axis=-1).astype(np.uint8)
    img[190:210, 50:350] = (gradient[190:210, 50:350, None] * 0.2).astype(np.uint8)  # dark text bar
    out = normalize_illumination(img)
    bg_left, bg_right = out[50, 20].mean(), out[50, 380].mean()
    assert abs(bg_left - bg_right) < 15
    assert bg_right > 230
    assert out[200, 300].mean() < 100  # text stays dark


def test_remove_speckles_keeps_text_and_diacritics_but_drops_isolated_dots():
    img = np.full((200, 300), 255, np.uint8)
    img[100:130, 50:60] = 0  # glyph stem
    img[92:95, 52:56] = 0  # diacritic dot just above the glyph (keep)
    img[20:22, 250:252] = 0  # isolated noise dot (drop)
    out = remove_speckles(img, max_area=20, keep_radius=12)
    assert out[110, 55] == 0
    assert out[93, 54] == 0
    assert out[21, 251] == 255
