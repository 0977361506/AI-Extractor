"""Build ``TableCell`` lists: ruled tables via grid detection + per-cell OCR, borderless via line clustering."""

from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np

from idp.core.ast import TableCell
from idp.core.geometry import PixelBox, normalize_bbox
from idp.table.grid import detect_grid, ruling_masks
from idp.table.numbers import fix_numeric_ocr, parse_vn_number


@dataclass
class OcrLine:
    text: str
    confidence: float
    bbox: PixelBox  # page pixels
    quad: np.ndarray | None = None


def segment_text_lines(img: np.ndarray, line_height: float, ink_threshold: int = 185) -> list[tuple[int, int, int, int]]:
    """Split a (cell) image into text-line bands via row projection. Returns ``(y0, y1, x0, x1)``."""
    ink = img < ink_threshold
    if not ink.any():
        return []
    rows = ink.sum(axis=1) >= 2
    runs: list[list[int]] = []
    y = 0
    n = len(rows)
    while y < n:
        if rows[y]:
            start = y
            while y < n and rows[y]:
                y += 1
            runs.append([start, y])
        else:
            y += 1
    # attach thin bands (diacritics / descenders) to the nearest neighbour
    small = 0.4 * line_height
    merged = True
    while merged and len(runs) > 1:
        merged = False
        for i, (a, b) in enumerate(runs):
            if b - a < small:
                gaps = []
                if i > 0:
                    gaps.append((a - runs[i - 1][1], i - 1))
                if i + 1 < len(runs):
                    gaps.append((runs[i + 1][0] - b, i + 1))
                gap, j = min(gaps)
                if gap <= 0.5 * line_height:
                    lo, hi = min(i, j), max(i, j)
                    runs[lo] = [min(runs[lo][0], runs[hi][0]), max(runs[lo][1], runs[hi][1])]
                    del runs[hi]
                    merged = True
                    break
    segments = []
    gap_split = 0.8 * line_height
    for a, b in runs:
        band = ink[a:b]
        if b - a < 0.3 * line_height or band.sum() < 0.5 * line_height:
            continue
        cols = np.nonzero(band.any(axis=0))[0]
        # split the band at wide horizontal gaps; drop specks / slivers
        groups: list[list[int]] = [[int(cols[0]), int(cols[0])]]
        for c in cols[1:]:
            if c - groups[-1][1] > gap_split:
                groups.append([int(c), int(c)])
            else:
                groups[-1][1] = int(c)
        for c0, c1 in groups:
            part = band[:, c0 : c1 + 1]
            rows_ink = np.nonzero(part.any(axis=1))[0]
            h = rows_ink[-1] - rows_ink[0] + 1
            w = c1 - c0 + 1
            if part.sum() < 25 or (h < 0.45 * line_height and w < 0.4 * line_height):
                continue
            segments.append((a + int(rows_ink[0]), a + int(rows_ink[-1]) + 1, c0, c1 + 1))
    return segments


_FORMULA_MISREAD = re.compile(r"\((\s*\d{2,3}\s*)[-–−](\s*\d{2,3}(?:\s*[+\-–−]\s*\d{2,3})+\s*)\)")
_DATE_MISREAD = re.compile(r"^(\d{1,2})[/\-.](\d{1,2})[1lI|](\d{4})$")


def repair_cell_text(text: str) -> str:
    """Fix systematic OCR slips: '=' read as '-' in BCTC code formulas, '/' read as '1' in dates."""
    text = _FORMULA_MISREAD.sub(lambda m: f"({m.group(1).strip()} = {m.group(2).strip()})", text)
    m = _DATE_MISREAD.match(text.strip())
    if m and int(m.group(2)) <= 12:
        text = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    return text


def sanitize_ocr(text: str, confidence: float) -> tuple[str, float]:
    """Reject degenerate recogniser output (the same token repeated, typical on blank / sparse crops)."""
    tokens = text.split()
    if len(tokens) >= 4:
        run = best = 1
        for a, b in zip(tokens, tokens[1:]):
            run = run + 1 if a.lower() == b.lower() else 1
            best = max(best, run)
        if best >= 3:
            return "", 0.0
    return text, confidence


def drop_empty_lines(cells: list[TableCell]) -> list[TableCell]:
    """Remove grid rows / columns whose cells are all empty (spurious rulings) and renumber."""
    if not cells:
        return cells
    n_rows = max(c.row + c.rowspan for c in cells)
    n_cols = max(c.col + c.colspan for c in cells)
    filled_rows = {r for c in cells if c.text.strip() for r in range(c.row, c.row + c.rowspan)}
    filled_cols = {k for c in cells if c.text.strip() for k in range(c.col, c.col + c.colspan)}
    keep_rows = [r for r in range(n_rows) if r in filled_rows]
    keep_cols = [k for k in range(n_cols) if k in filled_cols]
    if len(keep_rows) == n_rows and len(keep_cols) == n_cols:
        return cells
    rmap = {r: i for i, r in enumerate(keep_rows)}
    cmap = {k: i for i, k in enumerate(keep_cols)}
    out = []
    for c in cells:
        rows = [rmap[r] for r in range(c.row, c.row + c.rowspan) if r in rmap]
        cols = [cmap[k] for k in range(c.col, c.col + c.colspan) if k in cmap]
        if not rows or not cols:
            continue
        out.append(c.model_copy(update={"row": rows[0], "col": cols[0], "rowspan": len(rows), "colspan": len(cols)}))
    return out


def _finalize(cells: list[TableCell]) -> list[TableCell]:
    """Repair text, drop empty grid lines, infer header rows, clean numeric columns."""
    for c in cells:
        c.text = repair_cell_text(c.text)
    cells = drop_empty_lines(cells)
    if not cells:
        return cells
    n_cols = max(c.col + c.colspan for c in cells)
    row0 = [c for c in cells if c.row == 0]
    body_numeric = any(parse_vn_number(fix_numeric_ocr(c.text)) is not None for c in cells if c.row > 0)
    row0_numeric = any(parse_vn_number(fix_numeric_ocr(c.text)) is not None for c in row0 if c.col > 0)
    header_rows = max((c.rowspan for c in row0), default=1) if body_numeric and not row0_numeric else 0
    for c in cells:
        c.is_header = c.row < header_rows
    for k in range(n_cols):
        body = [c for c in cells if c.col == k and not c.is_header and c.text.strip()]
        nums = [c for c in body if parse_vn_number(fix_numeric_ocr(c.text)) is not None]
        if body and len(nums) >= max(1, 0.5 * len(body)):
            for c in nums:
                c.text = fix_numeric_ocr(c.text)
                c.numeric_value = parse_vn_number(c.text)
    return cells


def _weighted(parts: list[tuple[str, float]]) -> float:
    if not parts:
        return 1.0
    total = sum(max(1, len(t)) for t, _ in parts)
    return round(sum(p * max(1, len(t)) for t, p in parts) / total, 4)


def build_ruled_table(
    gray: np.ndarray,
    offset: tuple[int, int],
    page_w: int,
    page_h: int,
    line_height: float,
    recognizer,
    presence_gray: np.ndarray | None = None,
) -> list[TableCell] | None:
    """``gray`` is the table crop (OCR image); ``offset`` its top-left in page pixels.

    ``presence_gray`` (same crop before ink removal) keeps rulings continuous where pen strokes crossed them.
    """
    grid = detect_grid(gray, line_height, presence_gray=presence_gray)
    if grid is None:
        return None
    horiz, vert = ruling_masks(gray, line_height)
    clean = gray.copy()
    rulings = cv2.dilate(((horiz > 0) | (vert > 0)).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    clean[rulings > 0] = 255
    t = max(3, int(line_height / 6))
    pad = 4
    crops: list[np.ndarray] = []
    owners: list[int] = []
    for idx, cell in enumerate(grid.cells):
        x0, y0, x1, y1 = cell.bbox
        inner = clean[y0 + t : max(y0 + t + 1, y1 - t), x0 + t : max(x0 + t + 1, x1 - t)]
        for a, b, c0, c1 in segment_text_lines(inner, line_height):
            crop = inner[max(0, a - pad) : b + pad, max(0, c0 - pad) : c1 + pad]
            crops.append(np.pad(crop, pad, constant_values=255))
            owners.append(idx)
    results = recognizer.recognize(crops) if crops else []
    texts: dict[int, list[tuple[str, float]]] = {}
    for idx, (text, prob) in zip(owners, results):
        texts.setdefault(idx, []).append(sanitize_ocr(text, prob))
    ox, oy = offset
    cells = []
    for idx, cell in enumerate(grid.cells):
        parts = texts.get(idx, [])
        x0, y0, x1, y1 = cell.bbox
        cells.append(
            TableCell(
                row=cell.row,
                col=cell.col,
                rowspan=cell.rowspan,
                colspan=cell.colspan,
                text=" ".join(p[0] for p in parts if p[0]).strip(),
                confidence=_weighted(parts),
                bbox=normalize_bbox((x0 + ox, y0 + oy, x1 + ox, y1 + oy), page_w, page_h),
            )
        )
    return _finalize(cells)


def build_borderless_table(lines: list[OcrLine], page_w: int, page_h: int) -> list[TableCell]:
    """Cluster recognised lines into rows (vertical overlap) and columns (horizontal interval union)."""
    if not lines:
        return []
    rows: list[list[OcrLine]] = []
    for ln in sorted(lines, key=lambda l: (l.bbox[1] + l.bbox[3]) / 2):
        cy = (ln.bbox[1] + ln.bbox[3]) / 2
        if rows:
            last = rows[-1]
            top = min(l.bbox[1] for l in last)
            bottom = max(l.bbox[3] for l in last)
            if top <= cy <= bottom:
                last.append(ln)
                continue
        rows.append([ln])
    intervals = sorted((l.bbox[0], l.bbox[2]) for l in lines)
    bands: list[list[float]] = []
    for a, b in intervals:
        if bands and a <= bands[-1][1]:
            bands[-1][1] = max(bands[-1][1], b)
        else:
            bands.append([a, b])

    def band_of(ln: OcrLine) -> int:
        cx = (ln.bbox[0] + ln.bbox[2]) / 2
        return min(range(len(bands)), key=lambda i: 0 if bands[i][0] <= cx <= bands[i][1] else min(abs(cx - bands[i][0]), abs(cx - bands[i][1])))

    cells = []
    for r, row in enumerate(rows):
        per_col: dict[int, list[OcrLine]] = {}
        for ln in row:
            per_col.setdefault(band_of(ln), []).append(ln)
        for k, members in per_col.items():
            members.sort(key=lambda l: (l.bbox[1], l.bbox[0]))
            box = (
                min(m.bbox[0] for m in members),
                min(m.bbox[1] for m in members),
                max(m.bbox[2] for m in members),
                max(m.bbox[3] for m in members),
            )
            cells.append(
                TableCell(
                    row=r,
                    col=k,
                    text=" ".join(m.text for m in members),
                    confidence=min(m.confidence for m in members),
                    bbox=normalize_bbox(box, page_w, page_h),
                )
            )
    return _finalize(cells)
