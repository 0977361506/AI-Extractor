"""Reading order by recursive XY-cut, always splitting at the single widest whitespace gap.

Splitting at the widest gap (rather than "rows first") reads side-by-side header blocks column by column.
"""

from __future__ import annotations

from idp.core.geometry import PixelBox


def _groups(idx: list[int], boxes: list[PixelBox], axis: int, min_gap: float) -> tuple[list[list[int]], list[float]]:
    order = sorted(idx, key=lambda i: boxes[i][axis])
    groups = [[order[0]]]
    gaps: list[float] = []
    end = boxes[order[0]][axis + 2]
    for i in order[1:]:
        start = boxes[i][axis]
        if start > end + min_gap:
            gaps.append(start - end)
            groups.append([i])
        else:
            groups[-1].append(i)
        end = max(end, boxes[i][axis + 2])
    return groups, gaps


def _order(idx: list[int], boxes: list[PixelBox], min_gap: float) -> list[int]:
    if len(idx) <= 1:
        return idx
    gy, gaps_y = _groups(idx, boxes, 1, min_gap)
    gx, gaps_x = _groups(idx, boxes, 0, min_gap)
    best_y, best_x = max(gaps_y, default=0.0), max(gaps_x, default=0.0)
    if best_y == 0.0 and best_x == 0.0:
        return sorted(idx, key=lambda i: (boxes[i][1], boxes[i][0]))
    groups, gaps = (gy, gaps_y) if best_y >= best_x else (gx, gaps_x)
    k = max(range(len(gaps)), key=gaps.__getitem__)
    first = [i for g in groups[: k + 1] for i in g]
    second = [i for g in groups[k + 1 :] for i in g]
    return _order(first, boxes, min_gap) + _order(second, boxes, min_gap)


def xy_cut_order(boxes: list[PixelBox], min_gap: float = 2.0) -> list[int]:
    return _order(list(range(len(boxes))), boxes, min_gap)
