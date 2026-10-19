import { fireEvent, render, screen } from "@testing-library/react";
import type { TableCell } from "../../types";
import { TableEditor } from "./TableEditor";

const C = (row: number, col: number, text: string, extra: Partial<TableCell> = {}): TableCell => ({
  row, col, rowspan: 1, colspan: 1, is_header: row === 0, text, confidence: 0.95, check_failed: false, ...extra,
});

const cells = [
  C(0, 0, "Chỉ tiêu"), C(0, 1, "Số tiền"),
  C(1, 0, "Tiền"), C(1, 1, "15.250.0O0", { confidence: 0.5, alt_text: "15.250.0O0" }),
  C(2, 0, "Cộng"), C(2, 1, "15.250.000", { check_failed: true }),
];

function setup() {
  const handlers = { onSelectCell: vi.fn(), onEditCell: vi.fn(), onStructure: vi.fn() };
  render(<TableEditor cells={cells} uiThreshold={0.8} selected={null} {...handlers} />);
  return handlers;
}

describe("TableEditor", () => {
  it("renders headers and marks low-confidence and failed cells", () => {
    setup();
    expect(screen.getByText("Chỉ tiêu").tagName).toBe("TH");
    expect(screen.getByText("15.250.0O0").closest("td")).toHaveClass("cell-low");
    expect(screen.getByText("15.250.000").closest("td")).toHaveClass("cell-failed");
  });

  it("selects a cell on click and edits it on double click", () => {
    const h = setup();
    const td = screen.getByText("15.250.0O0").closest("td")!;
    fireEvent.click(td);
    expect(h.onSelectCell).toHaveBeenCalledWith(1, 1);
    fireEvent.doubleClick(td);
    const input = screen.getByDisplayValue("15.250.0O0");
    fireEvent.change(input, { target: { value: "15.250.000" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(h.onEditCell).toHaveBeenCalledWith(1, 1, "15.250.000");
  });

  it("adds a row below the selected cell", () => {
    const h = setup();
    fireEvent.click(screen.getByText("Tiền").closest("td")!);
    fireEvent.click(screen.getByRole("button", { name: /thêm hàng/i }));
    const out: TableCell[] = h.onStructure.mock.calls[0][0];
    expect(Math.max(...out.map((c) => c.row + c.rowspan))).toBe(4);
  });

  it("merges a shift-selected range", () => {
    const h = setup();
    fireEvent.click(screen.getByText("Tiền").closest("td")!);
    fireEvent.click(screen.getByText("Cộng").closest("td")!, { shiftKey: true });
    fireEvent.click(screen.getByRole("button", { name: /gộp ô/i }));
    const out: TableCell[] = h.onStructure.mock.calls[0][0];
    expect(out.find((c) => c.row === 1 && c.col === 0)?.rowspan).toBe(2);
  });
});
