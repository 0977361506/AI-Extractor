"""Page orientation (0/90/180/270) from text-line geometry + a 0/180 text-line classifier.

Returned angle = clockwise rotation needed to make the page upright.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from idp.core.geometry import crop_quad, quad_wh


class LineDetector(Protocol):
    def detect(self, img: np.ndarray) -> list[np.ndarray]: ...
    def classify_180(self, crops: list[np.ndarray]) -> list[tuple[str, float]]: ...


def rotate_orthogonal(img: np.ndarray, degrees_clockwise: int) -> np.ndarray:
    k = (degrees_clockwise // 90) % 4
    return img if k == 0 else np.ascontiguousarray(np.rot90(img, k=-k))


def detect_orientation(img: np.ndarray, detector: LineDetector, max_lines: int = 24, min_lines: int = 3) -> int:
    quads = detector.detect(img)
    if len(quads) < min_lines:
        return 0
    sizes = [quad_wh(q) for q in quads]
    vertical = sum(1 for w, h in sizes if h > 1.5 * w)
    horizontal = sum(1 for w, h in sizes if w > 1.5 * h)
    base = 90 if vertical > horizontal else 0

    rotated = rotate_orthogonal(img, base)
    if base:
        quads = detector.detect(rotated)
    quads = [q for q in quads if (lambda wh: wh[0] > 1.5 * wh[1])(quad_wh(q))]
    if not quads:
        return base
    quads.sort(key=lambda q: quad_wh(q)[0] * quad_wh(q)[1], reverse=True)
    crops = [crop_quad(rotated, q) for q in quads[:max_lines]]
    votes = detector.classify_180(crops)
    flipped = sum(score for label, score in votes if label == "180")
    upright = sum(score for label, score in votes if label != "180")
    return (base + 180) % 360 if flipped > upright else base
