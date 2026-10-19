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


def _upright(ink: np.ndarray) -> np.ndarray:
    """Rotate the blob so its minimum-area rectangle is axis aligned (handles tilted stamps)."""
    pts = cv2.findNonZero(ink.astype(np.uint8))
    if pts is None:
        return ink
    (cx, cy), (rw, rh), angle = cv2.minAreaRect(pts)
    if rw < rh:
        angle, rw, rh = angle - 90, rh, rw
    if abs(angle) < 1.0:
        return ink
    m = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    m[0, 2] += rw / 2 - cx
    m[1, 2] += rh / 2 - cy
    out = cv2.warpAffine(ink.astype(np.uint8), m, (max(1, int(rw)), max(1, int(rh))), flags=cv2.INTER_NEAREST)
    return out > 0


def _rectangle_outline(ink: np.ndarray) -> bool:
    h, w = ink.shape
    if min(h, w) < 6:
        return False
    b = max(3, int(0.12 * min(w, h)))
    edges = [ink[:b].any(axis=0), ink[-b:].any(axis=0), ink[:, :b].any(axis=1), ink[:, -b:].any(axis=1)]
    return all(e.mean() >= 0.6 for e in edges)


def classify(ink: np.ndarray, line_height: float) -> tuple[InkKind, str | None]:
    h, w = ink.shape
    aspect = w / max(h, 1)
    if min(w, h) >= line_height and max(w, h) >= 3 * line_height and 0.15 <= aspect <= 6.0 and ink.any():
        r = _radial(ink)
        ring = float(((r >= 0.75) & (r <= 1.12)).mean())
        inner = float((r < 0.7).mean())
        if ring >= 0.45:
            if 0.7 <= aspect <= 1.4 and min(w, h) >= 3 * line_height and inner >= 0.08:
                return InkKind.STAMP, "round"
            if inner < 0.08:
                return InkKind.MARK, "ellipse"
    rect = _upright(ink)
    rh, rw = rect.shape
    if min(rw, rh) >= 1.5 * line_height and _rectangle_outline(rect):
        b = max(3, int(0.12 * min(rw, rh)))
        inner = rect[b:-b, b:-b].sum() / max(rect.sum(), 1)
        return (InkKind.STAMP if inner >= 0.08 else InkKind.MARK), "rectangle"
    return InkKind.HANDWRITING, None


def _find_rings(mask: np.ndarray, line_height: float) -> list[tuple[float, float, float]]:
    """Circular stamps (possibly overlapping handwriting / signatures) via Hough on a downscaled mask."""
    scale = 0.5
    small = cv2.resize(mask.astype(np.uint8) * 255, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if small.max() == 0:
        return []
    blur = cv2.GaussianBlur(small, (7, 7), 1.5)
    lh = line_height * scale
    circles = cv2.HoughCircles(
        blur, cv2.HOUGH_GRADIENT, dp=1.5, minDist=4 * lh, param1=80, param2=30, minRadius=int(2 * lh), maxRadius=int(7 * lh)
    )
    if circles is None:
        return []
    rings = []
    h, w = mask.shape
    angles = np.linspace(0, 2 * np.pi, 144, endpoint=False)
    for cx, cy, r in circles[0]:
        cx, cy, r = cx / scale, cy / scale, r / scale
        hit = 0
        for t in angles:
            found = False
            for k in np.linspace(0.9, 1.06, 6):
                x, y = int(cx + k * r * np.cos(t)), int(cy + k * r * np.sin(t))
                if 0 <= x < w and 0 <= y < h and mask[y, x]:
                    found = True
                    break
            hit += found
        if hit / len(angles) < 0.75:
            continue
        yy, xx = np.ogrid[:h, :w]
        d2 = (xx - cx) ** 2 + (yy - cy) ** 2
        disk_ink = mask[d2 <= (1.1 * r) ** 2].sum()
        band_ink = mask[(d2 >= (0.85 * r) ** 2) & (d2 <= (1.1 * r) ** 2)].sum()
        if disk_ink and band_ink / disk_ink >= 0.35:
            rings.append((float(cx), float(cy), float(r)))
    # one stamp may yield several concentric / shifted circles: keep the largest
    rings.sort(key=lambda c: -c[2])
    kept: list[tuple[float, float, float]] = []
    for c in rings:
        if all((c[0] - k[0]) ** 2 + (c[1] - k[1]) ** 2 > (max(c[2], k[2])) ** 2 for k in kept):
            kept.append(c)
    return kept


def find_ink_blobs(
    masks: dict[str, np.ndarray],
    line_height: float,
    colors: tuple[str, ...] = ("red", "blue"),
    ignore_boxes: list[tuple[float, float, float, float]] | None = None,
) -> list[InkBlob]:
    """``ignore_boxes``: areas where coloured ink is content, not annotation (charts, checkboxes)."""
    ignore_boxes = ignore_boxes or []
    blobs: list[InkBlob] = []
    min_ink = 0.3 * line_height * line_height
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(1.2 * line_height)), max(3, int(0.5 * line_height))))
    for color in colors:
        mask = masks[color].astype(np.uint8)
        if not mask.any():
            continue
        ring_blobs: list[InkBlob] = []
        for cx, cy, r in _find_rings(mask > 0, line_height):
            box = (max(0, int(cx - 1.06 * r)), max(0, int(cy - 1.06 * r)), min(mask.shape[1], int(cx + 1.06 * r)), min(mask.shape[0], int(cy + 1.06 * r)))
            if any(containment(box, ib) >= 0.6 for ib in ignore_boxes):
                continue
            yy, xx = np.ogrid[: mask.shape[0], : mask.shape[1]]
            disk = (xx - cx) ** 2 + (yy - cy) ** 2 <= (1.06 * r) ** 2
            inner = mask[disk & ((xx - cx) ** 2 + (yy - cy) ** 2 <= (0.75 * r) ** 2)].sum()
            kind = InkKind.STAMP if inner >= 0.08 * max(1, mask[disk].sum()) else InkKind.MARK
            ring_blobs.append(InkBlob(kind=kind, color=color, bbox=box, shape="round" if kind == InkKind.STAMP else "ellipse"))
            mask = mask.copy()
            mask[disk] = 0
        blobs.extend(ring_blobs)
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
        color_blobs: list[InkBlob] = []
        for x0, y0, x1, y1 in merged:
            if any(containment((x0, y0, x1, y1), ib) >= 0.6 for ib in ignore_boxes):
                continue
            ink = mask[y0:y1, x0:x1].astype(bool)
            kind, shape = classify(ink, line_height)
            color_blobs.append(InkBlob(kind=kind, color=color, bbox=(int(x0), int(y0), int(x1), int(y1)), shape=shape))
        blobs.extend(_merge_rows(color_blobs, line_height))
    return blobs


def _merge_rows(blobs: list[InkBlob], line_height: float) -> list[InkBlob]:
    """Join handwriting pieces on one row (letters in comb boxes, words split by a printed rule)."""
    hand = sorted((b for b in blobs if b.kind == InkKind.HANDWRITING), key=lambda b: b.bbox[0])
    others = [b for b in blobs if b.kind != InkKind.HANDWRITING]
    out: list[InkBlob] = []
    for b in hand:
        for o in out:
            ox0, oy0, ox1, oy1 = o.bbox
            x0, y0, x1, y1 = b.bbox
            overlap = min(oy1, y1) - max(oy0, y0)
            if overlap >= 0.5 * min(oy1 - oy0, y1 - y0) and x0 - ox1 < 3 * line_height and max(oy1 - oy0, y1 - y0) < 3 * line_height:
                o.bbox = (min(ox0, x0), min(oy0, y0), max(ox1, x1), max(oy1, y1))
                break
        else:
            out.append(InkBlob(kind=b.kind, color=b.color, bbox=b.bbox, shape=b.shape))
    return others + out
