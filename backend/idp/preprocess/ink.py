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
    blue_s: int = 70
    blue_v: int = 50
    stain_s: int = 30
    stain_v: int = 90
    dark_keep: int = 110  # coloured pixels darker than this (max channel) are black text under ink


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
    ocr = np.where(colored, max_channel, gray)
    ocr = np.where(colored & (ocr > params.dark_keep), 255, ocr).astype(np.uint8)

    masks = {"red": red, "blue": blue, "stain": stain}
    coverage = {k: float(m.mean()) for k, m in masks.items()}
    return InkResult(ocr_gray=ocr, masks=masks, coverage=coverage)
