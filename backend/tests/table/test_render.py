from idp.core.ast import TableCell
from idp.table.render import cells_to_html, cells_to_markdown, expand_grid, header_row_count


def _cells():
    return [
        TableCell(row=0, col=0, rowspan=2, text="Chỉ tiêu", is_header=True),
        TableCell(row=0, col=1, colspan=2, text="Năm 2026", is_header=True),
        TableCell(row=1, col=1, text="Quý I", is_header=True),
        TableCell(row=1, col=2, text="Quý II", is_header=True),
        TableCell(row=2, col=0, text="Doanh thu"),
        TableCell(row=2, col=1, text="12.450"),
        TableCell(row=2, col=2, text="13.870"),
    ]


def test_expand_grid_repeats_spanning_text():
    g = expand_grid(_cells())
    assert g == [
        ["Chỉ tiêu", "Năm 2026", "Năm 2026"],
        ["Chỉ tiêu", "Quý I", "Quý II"],
        ["Doanh thu", "12.450", "13.870"],
    ]


def test_html_has_spans_and_thead():
    html = cells_to_html(_cells())
    assert '<th rowspan="2">Chỉ tiêu</th>' in html
    assert '<th colspan="2">Năm 2026</th>' in html
    assert "<thead>" in html and "<tbody>" in html
    assert "<td>12.450</td>" in html


def test_html_escapes_text():
    html = cells_to_html([TableCell(row=0, col=0, text="a<b & c")])
    assert "a&lt;b &amp; c" in html


def test_markdown_flattens_multi_row_header():
    md = cells_to_markdown(_cells())
    lines = md.splitlines()
    assert lines[0] == "| Chỉ tiêu | Năm 2026 - Quý I | Năm 2026 - Quý II |"
    assert lines[1] == "|---|---|---|"
    assert lines[2] == "| Doanh thu | 12.450 | 13.870 |"


def test_markdown_escapes_pipes_and_newlines():
    md = cells_to_markdown([TableCell(row=0, col=0, text="a|b\nc", is_header=True)])
    assert "a\\|b c" in md


def test_header_row_count():
    assert header_row_count(_cells()) == 2
