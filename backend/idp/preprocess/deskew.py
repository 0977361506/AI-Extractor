"""Small-angle skew estimation from detected text-line quads and bound-preserving rotation."""

from __future__ import annotations

import math

import cv2
import numpy as np

from idp.core.geometry import quad_wh


def estimate_skew(quads: list[np.ndarray], max_angle: float = 45.0) -> float:
    """Return the text baseline angle in degrees (positive = sloping down to the right in image coords)."""
    angles: list[float] = []
    weights: list[float] = []
    for q in quads:
        q = np.asarray(q, dtype=np.float64)
        w, h = quad_wh(q)
        if w < 3 * h or w < 30:
            continue
        top = math.degrees(math.atan2(q[1, 1] - q[0, 1], q[1, 0] - q[0, 0]))
        bottom = math.degrees(math.atan2(q[2, 1] - q[3, 1], q[2, 0] - q[3, 0]))
        a = (top + bottom) / 2
        if abs(a) <= max_angle:
            angles.append(a)
            weights.append(w)
    if not angles:
        return 0.0
    order = np.argsort(angles)
    a = np.asarray(angles)[order]
    cw = np.cumsum(np.asarray(weights)[order])
    median = float(a[np.searchsorted(cw, cw[-1] / 2)])
    return round(median, 2)


def rotate_bound(img: np.ndarray, angle: float, min_angle: float = 0.05) -> np.ndarray:
    """Rotate counter-clockwise by ``angle`` degrees, enlarging the canvas, filling with white."""
    if abs(angle) < min_angle:
        return img
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(math.ceil(h * sin + w * cos)), int(math.ceil(h * cos + w * sin))
    m[0, 2] += nw / 2 - w / 2
    m[1, 2] += nh / 2 - h / 2
    border = (255, 255, 255) if img.ndim == 3 else 255
    return cv2.warpAffine(img, m, (nw, nh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=border)
