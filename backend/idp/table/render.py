"""Table cells → expanded grid / HTML (exact spans) / Markdown (spans flattened for RAG)."""

from __future__ import annotations

import html

from idp.core.ast import TableCell


def grid_shape(cells: list[TableCell]) -> tuple[int, int]:
    if not cells:
        return 0, 0
    return max(c.row + c.rowspan for c in cells), max(c.col + c.colspan for c in cells)


def expand_grid(cells: list[TableCell]) -> list[list[str]]:
    n_rows, n_cols = grid_shape(cells)
    grid = [[""] * n_cols for _ in range(n_rows)]
    for c in cells:
        for r in range(c.row, c.row + c.rowspan):
            for k in range(c.col, c.col + c.colspan):
                grid[r][k] = c.text
    return grid


def header_row_count(cells: list[TableCell]) -> int:
    header = [c for c in cells if c.is_header]
    return max((c.row + c.rowspan for c in header), default=0)


def _attrs(c: TableCell) -> str:
    parts = []
    if c.rowspan > 1:
        parts.append(f' rowspan="{c.rowspan}"')
    if c.colspan > 1:
        parts.append(f' colspan="{c.colspan}"')
    if c.bbox is not None:
        parts.append(f" data-bbox='[{','.join(f'{v:.4f}' for v in c.bbox)}]' data-conf='{c.confidence:.2f}'")
    if c.check_failed:
        parts.append(' class="check-failed"')
    return "".join(parts)


def cells_to_html(cells: list[TableCell]) -> str:
    n_rows, _ = grid_shape(cells)
    n_header = header_row_count(cells)
    by_row: dict[int, list[TableCell]] = {}
    for c in cells:
        by_row.setdefault(c.row, []).append(c)
    out = ["<table>"]
    for section, rows in (("thead", range(0, n_header)), ("tbody", range(n_header, n_rows))):
        if not rows:
            continue
        out.append(f"<{section}>")
        for r in rows:
            out.append("<tr>")
            for c in sorted(by_row.get(r, []), key=lambda c: c.col):
                tag = "th" if section == "thead" else "td"
                text = html.escape(c.text, quote=False).replace("\n", "<br>")
                out.append(f"<{tag}{_attrs(c)}>{text}</{tag}>")
            out.append("</tr>")
        out.append(f"</{section}>")
    out.append("</table>")
    return "".join(out)


def _md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def header_labels(cells: list[TableCell]) -> list[str]:
    grid = expand_grid(cells)
    n_header = header_row_count(cells)
    if not grid:
        return []
    labels = []
    for k in range(len(grid[0])):
        parts: list[str] = []
        for r in range(n_header):
            t = grid[r][k].strip()
            if t and (not parts or parts[-1] != t):
                parts.append(t)
        labels.append(" - ".join(parts))
    return labels


def cells_to_markdown(cells: list[TableCell], body_rows: list[int] | None = None) -> str:
    grid = expand_grid(cells)
    if not grid:
        return ""
    n_header = header_row_count(cells)
    n_cols = len(grid[0])
    header = header_labels(cells) if n_header else [""] * n_cols
    lines = ["| " + " | ".join(_md(h) for h in header) + " |", "|" + "---|" * n_cols]
    rows = body_rows if body_rows is not None else range(n_header, len(grid))
    for r in rows:
        lines.append("| " + " | ".join(_md(t) for t in grid[r]) + " |")
    return "\n".join(lines)
