"""Find coloured-ink blobs (red / blue) and classify them: stamp, pen mark (circle), handwriting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import cv2
import numpy as np

from idp.core.geometry import containment


class InkKind(StrEnum):
    STAMP = "stamp"
    MARK = "mark"
    HANDWRITING = "handwriting"


@dataclass
class InkBlob:
    kind: InkKind
    color: str
    bbox: tuple[int, int, int, int]
    shape: str | None = None


def _radial(ink: np.ndarray) -> np.ndarray:
    h, w = ink.shape
    yy, xx = np.nonzero(ink)
    return np.sqrt(((xx + 0.5 - w / 2) / (w / 2)) ** 2 + ((yy + 0.5 - h / 2) / (h / 2)) ** 2)


def _rectangle_outline(ink: np.ndarray) -> bool:
    h, w = ink.shape
    b = max(3, int(0.12 * min(w, h)))
    edges = [ink[:b].any(axis=0), ink[-b:].any(axis=0), ink[:, :b].any(axis=1), ink[:, -b:].any(axis=1)]
    return all(e.mean() >= 0.6 for e in edges)


def classify(ink: np.ndarray, line_height: float) -> tuple[InkKind, str | None]:
    h, w = ink.shape
    aspect = w / max(h, 1)
    if min(w, h) >= 2 * line_height and 0.3 <= aspect <= 3.5 and ink.any():
        r = _radial(ink)
        ring = float(((r >= 0.75) & (r <= 1.12)).mean())
        inner = float((r < 0.7).mean())
        if ring >= 0.45:
            if 0.7 <= aspect <= 1.4 and min(w, h) >= 3 * line_height and inner >= 0.08:
                return InkKind.STAMP, "round"
            if inner < 0.08:
                return InkKind.MARK, "ellipse"
    if min(w, h) >= 1.5 * line_height and _rectangle_outline(ink):
        b = max(3, int(0.12 * min(w, h)))
        inner = ink[b:-b, b:-b].sum() / max(ink.sum(), 1)
        return (InkKind.STAMP if inner >= 0.08 else InkKind.MARK), "rectangle"
    return InkKind.HANDWRITING, None


def find_ink_blobs(masks: dict[str, np.ndarray], line_height: float, colors: tuple[str, ...] = ("red", "blue")) -> list[InkBlob]:
    blobs: list[InkBlob] = []
    min_ink = 0.3 * line_height * line_height
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(1.2 * line_height)), max(3, int(0.5 * line_height))))
    for color in colors:
        mask = masks[color].astype(np.uint8)
        if not mask.any():
            continue
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
        comps = []
        for i in range(1, n):
            x, y, w, h, _ = stats[i]
            ink = mask[y : y + h, x : x + w].astype(bool) & (labels[y : y + h, x : x + w] == i)
            if ink.sum() >= min_ink:
                comps.append([x, y, x + w, y + h])
        # merge components lying inside a larger one (text inside a stamp ring)
        comps.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
        merged: list[list[int]] = []
        for b in comps:
            host = next((m for m in merged if containment(tuple(b), tuple(m)) >= 0.8), None)
            if host is None:
                merged.append(b)
        for x0, y0, x1, y1 in merged:
            ink = mask[y0:y1, x0:x1].astype(bool)
            kind, shape = classify(ink, line_height)
            blobs.append(InkBlob(kind=kind, color=color, bbox=(int(x0), int(y0), int(x1), int(y1)), shape=shape))
    return blobs
