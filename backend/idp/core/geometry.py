"""Box / quadrilateral helpers. Pixel boxes are ``(x0, y0, x1, y1)``; quads are 4x2 arrays (tl, tr, br, bl)."""

from __future__ import annotations

from collections.abc import Iterable

import cv2
import numpy as np

PixelBox = tuple[float, float, float, float]


def area(b: PixelBox) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def intersection(a: PixelBox, b: PixelBox) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def iou(a: PixelBox, b: PixelBox) -> float:
    inter = intersection(a, b)
    union = area(a) + area(b) - inter
    return inter / union if union > 0 else 0.0


def containment(inner: PixelBox, outer: PixelBox) -> float:
    """Fraction of ``inner``'s area that lies inside ``outer``."""
    a = area(inner)
    return intersection(inner, outer) / a if a > 0 else 0.0


def union_bbox(boxes: Iterable[PixelBox]) -> PixelBox:
    boxes = list(boxes)
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def center(b: PixelBox) -> tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def quad_wh(quad: np.ndarray) -> tuple[float, float]:
    q = np.asarray(quad, dtype=np.float32)
    w = float((np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2)
    h = float((np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2)
    return w, h


def quad_to_bbox(quad: np.ndarray) -> PixelBox:
    q = np.asarray(quad)
    return (float(q[:, 0].min()), float(q[:, 1].min()), float(q[:, 0].max()), float(q[:, 1].max()))


def normalize_bbox(b: PixelBox, width: int, height: int) -> tuple[float, float, float, float]:
    def clamp(v: float) -> float:
        return round(min(1.0, max(0.0, v)), 5)

    return (clamp(b[0] / width), clamp(b[1] / height), clamp(b[2] / width), clamp(b[3] / height))


def denormalize_bbox(b: tuple[float, float, float, float], width: int, height: int) -> PixelBox:
    return (b[0] * width, b[1] * height, b[2] * width, b[3] * height)


def scale_box(b: PixelBox, factor: float) -> PixelBox:
    return (b[0] * factor, b[1] * factor, b[2] * factor, b[3] * factor)


def crop_box(img: np.ndarray, b: PixelBox, pad: int = 0) -> np.ndarray:
    h, w = img.shape[:2]
    x0 = max(0, int(b[0]) - pad)
    y0 = max(0, int(b[1]) - pad)
    x1 = min(w, int(round(b[2])) + pad)
    y1 = min(h, int(round(b[3])) + pad)
    return img[y0:y1, x0:x1]


def crop_quad(img: np.ndarray, quad: np.ndarray, pad: int = 2) -> np.ndarray:
    """Perspective-crop a text quad into an upright patch (with ``pad`` px margin)."""
    q = np.asarray(quad, dtype=np.float32).copy()
    if pad:
        c = q.mean(axis=0)
        direction = q - c
        norm = np.linalg.norm(direction, axis=1, keepdims=True)
        norm[norm == 0] = 1
        q = q + direction / norm * pad * 1.41
    w, h = quad_wh(q)
    w, h = max(1, int(round(w))), max(1, int(round(h)))
    dst = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(q, dst)
    return cv2.warpPerspective(img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
