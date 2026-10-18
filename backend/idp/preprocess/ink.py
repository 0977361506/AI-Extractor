"""Colour-ink separation: red/blue/brown masks + an OCR image with coloured ink removed.

Coloured ink is *not* discarded downstream: masks feed stamp / handwriting detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass(frozen=True)
class InkParams:
    red_s: int = 80
    red_v: int = 60
    blue_s: int = 30
    blue_v: int = 50
    stain_s: int = 30
    stain_v: int = 90
    # A coloured pixel is kept (as black print under the ink) only if it is dark in the channel where that ink
    # is bright: red ink is bright in R, so black-under-red has a low R; pens are kept only when nearly black.
    red_keep_r: int = 90
    blue_keep_max: int = 60
    fringe: int = 1  # dilate masks to also remove anti-aliased ink edges


@dataclass
class InkResult:
    ocr_gray: np.ndarray
    masks: dict[str, np.ndarray] = field(default_factory=dict)
    coverage: dict[str, float] = field(default_factory=dict)


def separate_inks(rgb: np.ndarray, params: InkParams = InkParams()) -> InkResult:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    red = ((h <= 10) | (h >= 160)) & (s >= params.red_s) & (v >= params.red_v)
    blue = (h >= 95) & (h <= 135) & (s >= params.blue_s) & (v >= params.blue_v)
    stain = (h > 10) & (h <= 30) & (s >= params.stain_s) & (v >= params.stain_v)
    colored = red | blue | stain

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    max_channel = rgb.max(axis=2)
    r_channel = rgb[..., 0]
    if params.fringe:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * params.fringe + 1, 2 * params.fringe + 1))

        def grow(m: np.ndarray) -> np.ndarray:
            return cv2.dilate(m.astype(np.uint8), k) > 0

        red_zone, blue_zone, stain_zone = grow(red), grow(blue), grow(stain)
    else:
        red_zone, blue_zone, stain_zone = red, blue, stain
    keep = np.ones(gray.shape, bool)
    keep &= ~(red_zone & (r_channel >= params.red_keep_r))
    keep &= ~(blue_zone & (max_channel >= params.blue_keep_max))
    ocr = np.where(keep, gray, 255)
    # stains / highlighter: the brightest channel turns the tint into background but keeps print and rulings
    ocr = np.where(stain_zone & keep, np.maximum(gray, max_channel), ocr).astype(np.uint8)

    masks = {"red": red, "blue": blue, "stain": stain}
    coverage = {k: float(m.mean()) for k, m in masks.items()}
    return InkResult(ocr_gray=ocr, masks=masks, coverage=coverage)
