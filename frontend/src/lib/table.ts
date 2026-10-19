// Pure grid operations for the table editor (cells carry row/col/rowspan/colspan like the backend AST).
import type { TableCell } from "../types";

export interface Range {
  r0: number;
  c0: number;
  r1: number;
  c1: number;
}

const blank = (row: number, col: number, is_header = false): TableCell => ({
  row, col, rowspan: 1, colspan: 1, is_header, text: "", confidence: 1, check_failed: false,
});

const sorted = (cells: TableCell[]) => [...cells].sort((a, b) => a.row - b.row || a.col - b.col);

export function gridShape(cells: TableCell[]): { rows: number; cols: number } {
  return {
    rows: cells.reduce((m, c) => Math.max(m, c.row + c.rowspan), 0),
    cols: cells.reduce((m, c) => Math.max(m, c.col + c.colspan), 0),
  };
}

export function cellAt(cells: TableCell[], r: number, c: number): TableCell | undefined {
  return cells.find((x) => x.row <= r && r < x.row + x.rowspan && x.col <= c && c < x.col + x.colspan);
}

export function addRow(cells: TableCell[], after: number): TableCell[] {
  const at = after + 1;
  const out = cells.map((c) => {
    if (c.row >= at) return { ...c, row: c.row + 1 };
    if (c.row < at && at < c.row + c.rowspan) return { ...c, rowspan: c.rowspan + 1 };
    return { ...c };
  });
  const { cols } = gridShape(cells);
  for (let k = 0; k < cols; k++) if (!cellAt(out, at, k)) out.push(blank(at, k));
  return sorted(out);
}

export function addColumn(cells: TableCell[], after: number): TableCell[] {
  const at = after + 1;
  const out = cells.map((c) => {
    if (c.col >= at) return { ...c, col: c.col + 1 };
    if (c.col < at && at < c.col + c.colspan) return { ...c, colspan: c.colspan + 1 };
    return { ...c };
  });
  const { rows } = gridShape(cells);
  for (let r = 0; r < rows; r++) if (!cellAt(out, r, at)) out.push(blank(r, at, out.some((c) => c.row === r && c.is_header)));
  return sorted(out);
}

export function deleteRow(cells: TableCell[], r: number): TableCell[] {
  const out: TableCell[] = [];
  for (const c of cells) {
    const covers = c.row <= r && r < c.row + c.rowspan;
    if (covers && c.rowspan === 1) continue;
    if (covers) out.push({ ...c, rowspan: c.rowspan - 1 });
    else if (c.row > r) out.push({ ...c, row: c.row - 1 });
    else out.push({ ...c });
  }
  return sorted(out);
}

export function deleteColumn(cells: TableCell[], k: number): TableCell[] {
  const out: TableCell[] = [];
  for (const c of cells) {
    const covers = c.col <= k && k < c.col + c.colspan;
    if (covers && c.colspan === 1) continue;
    if (covers) out.push({ ...c, colspan: c.colspan - 1 });
    else if (c.col > k) out.push({ ...c, col: c.col - 1 });
    else out.push({ ...c });
  }
  return sorted(out);
}

export function mergeRange(cells: TableCell[], range: Range): TableCell[] {
  const r0 = Math.min(range.r0, range.r1), r1 = Math.max(range.r0, range.r1);
  const c0 = Math.min(range.c0, range.c1), c1 = Math.max(range.c0, range.c1);
  const inside = (c: TableCell) => c.row >= r0 && c.row + c.rowspan - 1 <= r1 && c.col >= c0 && c.col + c.colspan - 1 <= c1;
  const members = sorted(cells.filter(inside));
  if (members.length < 2) return sorted(cells);
  const merged: TableCell = {
    ...members[0],
    row: r0, col: c0, rowspan: r1 - r0 + 1, colspan: c1 - c0 + 1,
    text: members.map((c) => c.text.trim()).filter(Boolean).join(" "),
    confidence: 1, check_failed: false,
  };
  return sorted([...cells.filter((c) => !inside(c)), merged]);
}

export function splitCell(cells: TableCell[], r: number, c: number): TableCell[] {
  const target = cellAt(cells, r, c);
  if (!target || (target.rowspan === 1 && target.colspan === 1)) return sorted(cells);
  const out = cells.filter((x) => x !== target);
  for (let i = target.row; i < target.row + target.rowspan; i++)
    for (let k = target.col; k < target.col + target.colspan; k++)
      out.push(i === target.row && k === target.col ? { ...target, rowspan: 1, colspan: 1 } : blank(i, k, target.is_header));
  return sorted(out);
}
