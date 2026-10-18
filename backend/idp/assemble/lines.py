"""Grouping recognised text lines into rows and paragraphs."""

from __future__ import annotations

from idp.table.builder import OcrLine


def group_rows(lines: list[OcrLine]) -> list[list[OcrLine]]:
    rows: list[list[OcrLine]] = []
    for ln in sorted(lines, key=lambda l: (l.bbox[1] + l.bbox[3]) / 2):
        cy = (ln.bbox[1] + ln.bbox[3]) / 2
        if rows:
            top = min(l.bbox[1] for l in rows[-1])
            bottom = max(l.bbox[3] for l in rows[-1])
            if top <= cy <= bottom:
                rows[-1].append(ln)
                continue
        rows.append([ln])
    return [sorted(r, key=lambda l: l.bbox[0]) for r in rows]


def join_lines(lines: list[OcrLine]) -> str:
    return "\n".join(" ".join(l.text for l in row if l.text) for row in group_rows(lines)).strip()


def cluster_paragraphs(lines: list[OcrLine], line_height: float) -> list[list[OcrLine]]:
    """Consecutive rows that are close vertically and overlap horizontally form one paragraph."""
    groups: list[list[OcrLine]] = []
    spans: list[tuple[float, float, float]] = []  # (x0, x1, bottom) per group
    for row in group_rows(lines):
        x0 = min(l.bbox[0] for l in row)
        x1 = max(l.bbox[2] for l in row)
        top = min(l.bbox[1] for l in row)
        bottom = max(l.bbox[3] for l in row)
        target = None
        for gi in range(len(groups) - 1, -1, -1):
            gx0, gx1, gbottom = spans[gi]
            if top - gbottom < 0.8 * line_height and min(x1, gx1) > max(x0, gx0):
                target = gi
                break
        if target is None:
            groups.append(list(row))
            spans.append((x0, x1, bottom))
        else:
            groups[target].extend(row)
            gx0, gx1, _ = spans[target]
            spans[target] = (min(gx0, x0), max(gx1, x1), bottom)
    return groups
