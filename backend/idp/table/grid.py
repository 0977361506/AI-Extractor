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


def _positions(profile: np.ndarray, min_len: float, merge_gap: int) -> list[int]:
    idx = np.nonzero(profile >= min_len)[0]
    if idx.size == 0:
        return []
    groups: list[list[int]] = [[int(idx[0])]]
    for i in idx[1:]:
        if i - groups[-1][-1] <= merge_gap:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    return [int(round((g[0] + g[-1]) / 2)) for g in groups]


def ruling_masks(gray: np.ndarray, line_height: float) -> tuple[np.ndarray, np.ndarray]:
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15)
    hk = max(15, int(2.0 * line_height))
    vk = max(10, int(1.0 * line_height))
    horiz = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (hk, 1)))
    vert = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, vk)))
    gap = max(3, int(line_height * 0.3))
    horiz = cv2.morphologyEx(horiz, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (gap, 1)))
    vert = cv2.morphologyEx(vert, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, gap)))
    return horiz, vert


def detect_grid(gray: np.ndarray, line_height: float) -> Grid | None:
    """Return the cell grid of a ruled table, or ``None`` if the crop is not ruled."""
    horiz, vert = ruling_masks(gray, line_height)
    hk = max(15, int(2.0 * line_height))
    vk = max(10, int(1.0 * line_height))
    merge = max(2, int(line_height * 0.4))
    ys = _positions(horiz.sum(axis=1) / 255.0, hk * 0.9, merge)
    xs = _positions(vert.sum(axis=0) / 255.0, vk * 0.9, merge)
    if len(xs) < 2 or len(ys) < 2 or (len(xs) - 1) * (len(ys) - 1) < 2:
        return None

    t = max(3, int(line_height / 6))
    m = max(2 * t, int(line_height * 0.25))
    n_rows, n_cols = len(ys) - 1, len(xs) - 1

    def has_vertical(x: int, y0: int, y1: int) -> bool:
        band = vert[y0 + m : max(y0 + m + 1, y1 - m), max(0, x - t) : x + t + 1]
        return band.size > 0 and (band.max(axis=1) > 0).mean() >= 0.5

    def has_horizontal(y: int, x0: int, x1: int) -> bool:
        band = horiz[max(0, y - t) : y + t + 1, x0 + m : max(x0 + m + 1, x1 - m)]
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
