import type { TableCell } from "../types";
import { addColumn, addRow, cellAt, deleteColumn, deleteRow, gridShape, mergeRange, splitCell } from "./table";

const C = (row: number, col: number, text = "", rowspan = 1, colspan = 1, is_header = false): TableCell => ({
  row, col, rowspan, colspan, text, is_header, confidence: 1, check_failed: false,
});

const base = () => [C(0, 0, "A", 1, 1, true), C(0, 1, "B", 1, 1, true), C(1, 0, "1"), C(1, 1, "2"), C(2, 0, "3"), C(2, 1, "4")];

describe("table grid operations", () => {
  it("computes shape and finds the cell covering a position", () => {
    const cells = [C(0, 0, "AB", 1, 2), C(1, 0, "x"), C(1, 1, "y")];
    expect(gridShape(cells)).toEqual({ rows: 2, cols: 2 });
    expect(cellAt(cells, 0, 1)?.text).toBe("AB");
  });

  it("adds a row below and shifts later rows", () => {
    const out = addRow(base(), 0);
    expect(gridShape(out)).toEqual({ rows: 4, cols: 2 });
    expect(cellAt(out, 1, 0)?.text).toBe("");
    expect(cellAt(out, 2, 0)?.text).toBe("1");
  });

  it("adds a column right and widens spanning cells crossing it", () => {
    const out = addColumn([C(0, 0, "AB", 1, 2), C(1, 0, "x"), C(1, 1, "y")], 0);
    expect(gridShape(out)).toEqual({ rows: 2, cols: 3 });
    expect(cellAt(out, 0, 0)?.colspan).toBe(3);
    expect(cellAt(out, 1, 1)?.text).toBe("");
    expect(cellAt(out, 1, 2)?.text).toBe("y");
  });

  it("deletes a row and a column", () => {
    expect(gridShape(deleteRow(base(), 1))).toEqual({ rows: 2, cols: 2 });
    expect(cellAt(deleteRow(base(), 1), 1, 0)?.text).toBe("3");
    const noCol = deleteColumn(base(), 0);
    expect(gridShape(noCol)).toEqual({ rows: 3, cols: 1 });
    expect(cellAt(noCol, 1, 0)?.text).toBe("2");
  });

  it("merges a rectangular range joining texts", () => {
    const out = mergeRange(base(), { r0: 1, c0: 0, r1: 2, c1: 0 });
    const merged = cellAt(out, 1, 0)!;
    expect([merged.rowspan, merged.colspan, merged.text]).toEqual([2, 1, "1 3"]);
    expect(out.length).toBe(5);
  });

  it("splits a merged cell back into single cells", () => {
    const out = splitCell([C(0, 0, "AB", 2, 2)], 0, 0);
    expect(out.length).toBe(4);
    expect(cellAt(out, 0, 0)?.text).toBe("AB");
    expect(cellAt(out, 1, 1)?.text).toBe("");
  });
});
