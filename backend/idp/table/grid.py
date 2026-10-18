"""Ruled-table structure recovery: find ruling lines, build the base grid, merge cells across missing separators."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class GridCell:
    row: int
    col: int
    rowspan: int
    colspan: int
    bbox: tuple[int, int, int, int]  # pixels, crop coordinates


@dataclass
class Grid:
    xs: list[int]
    ys: list[int]
    cells: list[GridCell] = field(default_factory=list)

    @property
    def n_rows(self) -> int:
        return len(self.ys) - 1

    @property
    def n_cols(self) -> int:
        return len(self.xs) - 1


def _positions(profile: np.ndarray, min_len: float, merge_gap: int, max_thick: int) -> list[int]:
    """Centres of ruling lines from a projection profile.

    Runs thicker than ``max_thick`` (a real line next to a noise band) are reduced to their strong core.
    """
    idx = np.nonzero(profile >= min_len)[0]
    if idx.size == 0:
        return []
    groups: list[list[int]] = [[int(idx[0])]]
    for i in idx[1:]:
        if i - groups[-1][-1] <= merge_gap:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    centres = []
    for g in groups:
        if g[-1] - g[0] + 1 > max_thick:
            vals = profile[g[0] : g[-1] + 1]
            core = np.nonzero(vals >= 0.5 * vals.max())[0] + g[0]
            # a wide band whose core is still wide is not a line (e.g. a bold text row)
            sub: list[list[int]] = [[int(core[0])]]
            for i in core[1:]:
                if i - sub[-1][-1] <= 2:
                    sub[-1].append(int(i))
                else:
                    sub.append([int(i)])
            for c in sub:
                if c[-1] - c[0] + 1 <= max_thick:
                    centres.append(int(round((c[0] + c[-1]) / 2)))
        else:
            centres.append(int(round((g[0] + g[-1]) / 2)))
    return centres


def ruling_masks(gray: np.ndarray, line_height: float) -> tuple[np.ndarray, np.ndarray]:
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)
    hk = max(15, int(2.0 * line_height))
    vk = max(10, int(1.3 * line_height))
    horiz = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (hk, 1)))
    vert = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, vk)))
    gap = max(3, int(line_height * 0.3))
    horiz = cv2.morphologyEx(horiz, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (gap, 1)))
    vert = cv2.morphologyEx(vert, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, gap)))
    return horiz, vert


def detect_grid(gray: np.ndarray, line_height: float, presence_gray: np.ndarray | None = None) -> Grid | None:
    """Return the cell grid of a ruled table, or ``None`` if the crop is not ruled.

    Line *positions* come from ``gray``; separator *presence* (cell merging) also accepts ``presence_gray``.
    """
    horiz, vert = ruling_masks(gray, line_height)
    if presence_gray is not None:
        ph, pv = ruling_masks(presence_gray, line_height)
        p_horiz, p_vert = cv2.bitwise_or(horiz, ph), cv2.bitwise_or(vert, pv)
    else:
        p_horiz, p_vert = horiz, vert
    hk = max(15, int(2.0 * line_height))
    vk = max(10, int(1.3 * line_height))
    merge = max(2, int(line_height * 0.4))
    max_thick = max(4, int(line_height * 0.35))
    ys = _positions(horiz.sum(axis=1) / 255.0, hk * 0.9, merge, max_thick)
    xs = _positions(vert.sum(axis=0) / 255.0, vk * 0.9, merge, max_thick)
    if len(xs) < 2 or len(ys) < 2:
        return None
    t0 = max(3, int(line_height / 6))

    def v_cover(x: int, y0: int, y1: int) -> float:
        band = vert[y0:y1, max(0, x - t0) : x + t0 + 1]
        return float((band.max(axis=1) > 0).mean()) if band.size else 0.0

    def h_cover(y: int, x0: int, x1: int) -> float:
        band = horiz[max(0, y - t0) : y + t0 + 1, x0:x1]
        return float((band.max(axis=0) > 0).mean()) if band.size else 0.0

    # a ruling must span at least one full grid cell side (glyph strokes do not)
    for _ in range(2):
        xs = [x for x in xs if any(v_cover(x, ys[i], ys[i + 1]) >= 0.7 for i in range(len(ys) - 1))]
        if len(xs) < 2:
            return None
        ys = [y for y in ys if any(h_cover(y, xs[j], xs[j + 1]) >= 0.7 for j in range(len(xs) - 1))]
        if len(ys) < 2:
            return None
    if (len(xs) - 1) * (len(ys) - 1) < 2:
        return None

    t = max(3, int(line_height / 6))
    m = max(2 * t, int(line_height * 0.25))
    n_rows, n_cols = len(ys) - 1, len(xs) - 1

    def has_vertical(x: int, y0: int, y1: int) -> bool:
        band = p_vert[y0 + m : max(y0 + m + 1, y1 - m), max(0, x - t) : x + t + 1]
        return band.size > 0 and (band.max(axis=1) > 0).mean() >= 0.5

    def has_horizontal(y: int, x0: int, x1: int) -> bool:
        band = p_horiz[max(0, y - t) : y + t + 1, x0 + m : max(x0 + m + 1, x1 - m)]
        return band.size > 0 and (band.max(axis=0) > 0).mean() >= 0.5

    parent = list(range(n_rows * n_cols))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    for i in range(n_rows):
        for j in range(n_cols):
            if j + 1 < n_cols and not has_vertical(xs[j + 1], ys[i], ys[i + 1]):
                union(i * n_cols + j, i * n_cols + j + 1)
            if i + 1 < n_rows and not has_horizontal(ys[i + 1], xs[j], xs[j + 1]):
                union(i * n_cols + j, (i + 1) * n_cols + j)

    groups: dict[int, list[tuple[int, int]]] = {}
    for i in range(n_rows):
        for j in range(n_cols):
            groups.setdefault(find(i * n_cols + j), []).append((i, j))

    cells = []
    for members in groups.values():
        r0 = min(i for i, _ in members)
        r1 = max(i for i, _ in members)
        c0 = min(j for _, j in members)
        c1 = max(j for _, j in members)
        cells.append(GridCell(r0, c0, r1 - r0 + 1, c1 - c0 + 1, (xs[c0], ys[r0], xs[c1 + 1], ys[r1 + 1])))
    cells.sort(key=lambda c: (c.row, c.col))
    return Grid(xs=xs, ys=ys, cells=cells)
