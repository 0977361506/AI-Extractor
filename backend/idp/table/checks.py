"""Arithmetic consistency checks for financial tables.

Catches OCR digit errors without ground truth: BCTC code formulas ``(20 = 10 - 11)``, group / grand totals,
row-total columns, ``Thành tiền = SL × Đơn giá`` and percentage rows (VAT). A failing result cell gets
``check_failed = True``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from idp.core.ast import TableCell
from idp.table.numbers import fix_numeric_ocr, parse_vn_number
from idp.table.render import grid_shape


@dataclass
class CheckReport:
    checked: int = 0
    failed: int = 0


_FORMULA = re.compile(r"\(\s*(\d{2,3})\s*=\s*((?:\s*[+\-–−]?\s*\d{2,3})+)\s*\)")
_TERM = re.compile(r"([+\-–−]?)\s*(\d{2,3})")
_TOTAL = re.compile(r"^(cộng|tổng cộng)\b")
_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_NUMBERING = re.compile(r"^\s*(?:[ivxlc]+|\d+|[a-z])[.)]\s*", re.IGNORECASE)


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip().lower()


def _close(a: float, b: float, rel: float = 0.0005) -> bool:
    return abs(a - b) <= max(1.0, rel * abs(b))


class _Table:
    def __init__(self, cells: list[TableCell]):
        self.n_rows, self.n_cols = grid_shape(cells)
        self.origin: dict[tuple[int, int], TableCell] = {(c.row, c.col): c for c in cells}
        self.header_rows = {r for c in cells if c.is_header for r in range(c.row, c.row + c.rowspan)}
        self.body = [r for r in range(self.n_rows) if r not in self.header_rows]

    def text(self, r: int, k: int) -> str:
        c = self.origin.get((r, k))
        return c.text if c else ""

    def value(self, r: int, k: int) -> float | None:
        c = self.origin.get((r, k))
        return parse_vn_number(fix_numeric_ocr(c.text)) if c and c.text.strip() else None

    def label(self, r: int) -> str:
        parts = [self.text(r, k) for k in range(self.n_cols) if self.text(r, k).strip() and self.value(r, k) is None]
        return _norm(" ".join(parts))

    def header(self, k: int) -> str:
        texts = []
        for c in self.origin.values():
            if c.is_header and c.col <= k < c.col + c.colspan:
                texts.append(c.text)
        return _norm(" ".join(texts))

    def numeric_cols(self) -> list[int]:
        cols = []
        for k in range(self.n_cols):
            filled = [r for r in self.body if self.text(r, k).strip()]
            nums = [r for r in filled if self.value(r, k) is not None]
            if len(nums) >= 2 and len(nums) >= 0.5 * len(filled):
                cols.append(k)
        return cols

    def code_col(self) -> int | None:
        """Column holding BCTC line codes: header says "mã", or it contains every code cited in formulas."""
        for k in range(self.n_cols):
            if "mã" in self.header(k):
                return k
        cited = {code for r in self.body for m in _FORMULA.finditer(self.label(r)) for _, code in _TERM.findall(m.group(0))}
        if not cited:
            return None
        for k in range(self.n_cols):
            vals = {self.text(r, k).strip() for r in self.body}
            if cited <= vals:
                return k
        return None

    def fail(self, r: int, k: int) -> None:
        c = self.origin.get((r, k))
        if c is not None:
            c.check_failed = True


def run_arithmetic_checks(cells: list[TableCell]) -> CheckReport:
    report = CheckReport()
    if not cells:
        return report
    t = _Table(cells)
    for c in cells:
        c.check_failed = False
    code_col = t.code_col()
    value_cols = [k for k in t.numeric_cols() if k != code_col and t.header(k) not in {"stt", "tt"}]
    if not value_cols:
        return report

    def record(ok: bool, r: int, k: int) -> None:
        report.checked += 1
        if not ok:
            report.failed += 1
            t.fail(r, k)

    # a cell with digits that is not a valid number (e.g. "1211.567") is itself an error
    for k in value_cols:
        for r in t.body:
            text = t.text(r, k).strip()
            if text and any(ch.isdigit() for ch in text) and t.value(r, k) is None:
                record(False, r, k)

    labels = {r: t.label(r) for r in t.body}
    stripped = {r: _NUMBERING.sub("", labels[r]) for r in t.body}
    formula_rows: set[int] = set()

    # 1) code formulas, e.g. "(20 = 10 - 11)"
    if code_col is not None:
        code_row = {t.text(r, code_col).strip(): r for r in t.body if t.text(r, code_col).strip()}
        for r in t.body:
            m = _FORMULA.search(labels[r])
            if not m:
                continue
            target = code_row.get(m.group(1), r)
            terms = [(-1 if s and s in "-–−" else 1, code) for s, code in _TERM.findall(m.group(2))]
            if any(code not in code_row for _, code in terms):
                continue
            formula_rows.add(target)
            for k in value_cols:
                lhs = t.value(target, k)
                vals = [t.value(code_row[code], k) for _, code in terms]
                if lhs is None or any(v is None for v in vals):
                    continue
                signed = sum(s * v for (s, _), v in zip(terms, vals))
                absolute = sum(s * abs(v) for (s, _), v in zip(terms, vals))
                ok = any(_close(x, y) for x in (lhs, abs(lhs)) for y in (signed, absolute))
                record(ok, target, k)

    # 2) group / grand totals and percentage rows
    total_rows = [r for r in t.body if _TOTAL.match(stripped[r]) and r not in formula_rows]
    for idx, r in enumerate(t.body):
        if r in formula_rows:
            continue
        is_total = r in total_rows
        pct = _PERCENT.search(labels[r]) if not is_total else None
        if not is_total and not pct:
            continue
        above = t.body[:idx]
        prev_total = max((p for p in total_rows if p < r), default=None)
        since = [p for p in above if p not in total_rows and (prev_total is None or p > prev_total)]
        subtotals = [p for p in total_rows if p < r]
        for k in value_cols:
            target = t.value(r, k)
            if target is None:
                continue
            col_vals = {p: t.value(p, k) for p in above}
            if pct:
                prev = next((col_vals[p] for p in reversed(above) if col_vals[p] is not None), None)
                if prev is not None:
                    rate = float(pct.group(1).replace(",", ".")) / 100
                    # tax/expense rows are often printed negative "(336)": compare magnitudes
                    record(_close(abs(target), abs(prev) * rate, rel=0.002), r, k)
                continue
            hypotheses = []
            for rows in (since, subtotals, [p for p in above if p not in total_rows]):
                vals = [col_vals[p] for p in rows if col_vals[p] is not None]
                if vals:
                    hypotheses.append(sum(vals))
            last_two = [v for v in (col_vals[p] for p in above[-2:]) if v is not None]
            if len(last_two) == 2:
                hypotheses.append(sum(last_two))
            if hypotheses:
                record(any(_close(target, h) for h in hypotheses), r, k)

    # 3) row-total column ("Cộng" / "Tổng cộng")
    for k in value_cols:
        if t.header(k).split(" - ")[-1].strip() not in {"cộng", "tổng cộng", "tổng"}:
            continue
        parts = [j for j in value_cols if j < k]
        if not parts:
            continue
        for r in t.body:
            target = t.value(r, k)
            vals = [t.value(r, j) for j in parts]
            vals = [v for v in vals if v is not None]
            if target is None or not vals:
                continue
            record(_close(target, sum(vals)), r, k)

    # 4) Thành tiền = SL × Đơn giá
    def find(*names: str) -> int | None:
        for k in range(t.n_cols):
            h = t.header(k)
            if any(h == n or h.startswith(n) for n in names):
                return k
        return None

    qty, price, amount = find("sl", "số lượng"), find("đơn giá"), find("thành tiền")
    if None not in (qty, price, amount):
        for r in t.body:
            q, p, a = t.value(r, qty), t.value(r, price), t.value(r, amount)
            if None in (q, p, a) or r in total_rows:
                continue
            record(_close(a, q * p, rel=0.001), r, amount)
    return report
