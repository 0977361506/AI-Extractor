import { useState } from "react";
import { addColumn, addRow, deleteColumn, deleteRow, mergeRange, splitCell } from "../../lib/table";
import type { TableCell } from "../../types";

interface Props {
  cells: TableCell[];
  uiThreshold: number;
  selected: { row: number; col: number } | null;
  onSelectCell: (row: number, col: number) => void;
  onEditCell: (row: number, col: number, text: string) => void;
  onStructure: (cells: TableCell[]) => void;
}

export function TableEditor({ cells, uiThreshold, selected, onSelectCell, onEditCell, onStructure }: Props) {
  const [anchor, setAnchor] = useState<{ row: number; col: number } | null>(null);
  const [focus, setFocus] = useState<{ row: number; col: number } | null>(null);
  const [editing, setEditing] = useState<{ row: number; col: number; text: string } | null>(null);
  const current = focus ?? selected;

  const rows = new Map<number, TableCell[]>();
  for (const c of cells) rows.set(c.row, [...(rows.get(c.row) ?? []), c]);
  const rowIds = [...rows.keys()].sort((a, b) => a - b);

  const inRange = (c: TableCell) => {
    if (!anchor || !focus) return false;
    const r0 = Math.min(anchor.row, focus.row), r1 = Math.max(anchor.row, focus.row);
    const c0 = Math.min(anchor.col, focus.col), c1 = Math.max(anchor.col, focus.col);
    return c.row >= r0 && c.row <= r1 && c.col >= c0 && c.col <= c1;
  };

  const click = (c: TableCell, shift: boolean) => {
    if (shift && anchor) setFocus({ row: c.row, col: c.col });
    else {
      setAnchor({ row: c.row, col: c.col });
      setFocus({ row: c.row, col: c.col });
    }
    onSelectCell(c.row, c.col);
  };

  const commit = () => {
    if (editing) onEditCell(editing.row, editing.col, editing.text);
    setEditing(null);
  };

  const structural = (fn: (cells: TableCell[]) => TableCell[]) => () => current && onStructure(fn(cells));

  return (
    <div className="table-editor">
      <div className="toolbar" role="toolbar" aria-label="Sửa cấu trúc bảng">
        <button type="button" disabled={!current} onClick={structural((cs) => addRow(cs, current!.row))}>+ Thêm hàng</button>
        <button type="button" disabled={!current} onClick={structural((cs) => addColumn(cs, current!.col))}>+ Thêm cột</button>
        <button type="button" disabled={!current} onClick={structural((cs) => deleteRow(cs, current!.row))}>− Xóa hàng</button>
        <button type="button" disabled={!current} onClick={structural((cs) => deleteColumn(cs, current!.col))}>− Xóa cột</button>
        <button
          type="button"
          disabled={!anchor || !focus || (anchor.row === focus.row && anchor.col === focus.col)}
          onClick={() => anchor && focus && onStructure(mergeRange(cells, { r0: anchor.row, c0: anchor.col, r1: focus.row, c1: focus.col }))}
        >
          Gộp ô
        </button>
        <button type="button" disabled={!current} onClick={structural((cs) => splitCell(cs, current!.row, current!.col))}>Tách ô</button>
        <span className="hint">Shift+click để chọn vùng · nhấp đúp để sửa</span>
      </div>
      <div className="table-scroll">
        <table>
          <tbody>
            {rowIds.map((r) => (
              <tr key={r}>
                {rows
                  .get(r)!
                  .sort((a, b) => a.col - b.col)
                  .map((c) => {
                    const Tag = c.is_header ? "th" : "td";
                    const cls = [
                      c.check_failed ? "cell-failed" : "",
                      c.text && c.confidence < uiThreshold ? "cell-low" : "",
                      selected && selected.row === c.row && selected.col === c.col ? "cell-sel" : "",
                      inRange(c) ? "cell-range" : "",
                      c.numeric_value != null ? "num" : "",
                    ].filter(Boolean).join(" ");
                    const isEditing = editing && editing.row === c.row && editing.col === c.col;
                    return (
                      <Tag
                        key={`${c.row}-${c.col}`}
                        rowSpan={c.rowspan}
                        colSpan={c.colspan}
                        className={cls}
                        title={[c.alt_text ? `OCR đọc: ${c.alt_text}` : "", c.check_failed ? "Sai kiểm tra số học" : "", `Độ tự tin ${(c.confidence * 100).toFixed(0)}%`].filter(Boolean).join(" · ")}
                        onClick={(e) => click(c, e.shiftKey)}
                        onDoubleClick={() => setEditing({ row: c.row, col: c.col, text: c.text })}
                      >
                        {isEditing ? (
                          <input
                            autoFocus
                            value={editing!.text}
                            onChange={(e) => setEditing({ ...editing!, text: e.target.value })}
                            onBlur={commit}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") commit();
                              if (e.key === "Escape") setEditing(null);
                            }}
                          />
                        ) : (
                          c.text
                        )}
                      </Tag>
                    );
                  })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
