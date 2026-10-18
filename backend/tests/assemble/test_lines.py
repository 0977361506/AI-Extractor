from idp.assemble.lines import cluster_paragraphs, group_rows, join_lines
from idp.table.builder import OcrLine


def L(text, x0, y0, x1, y1, conf=0.9):
    return OcrLine(text=text, confidence=conf, bbox=(x0, y0, x1, y1))


def test_group_rows_orders_by_y_then_x():
    lines = [L("b", 300, 10, 400, 40), L("a", 10, 12, 200, 42), L("c", 10, 60, 200, 90)]
    rows = group_rows(lines)
    assert [[l.text for l in r] for r in rows] == [["a", "b"], ["c"]]


def test_join_lines_uses_space_within_row_newline_between_rows():
    lines = [L("Mã số thuế: 0109876543", 10, 10, 300, 40), L("Điện thoại: 024", 320, 10, 500, 40), L("Đại diện", 10, 60, 200, 90)]
    assert join_lines(lines) == "Mã số thuế: 0109876543 Điện thoại: 024\nĐại diện"


def test_cluster_paragraphs_splits_on_large_gap():
    lines = [
        L("dòng 1", 10, 100, 500, 130),
        L("dòng 2", 10, 140, 480, 170),
        L("đoạn mới", 10, 300, 500, 330),
    ]
    groups = cluster_paragraphs(lines, line_height=30)
    assert [[l.text for l in g] for g in groups] == [["dòng 1", "dòng 2"], ["đoạn mới"]]


def test_cluster_paragraphs_splits_horizontally_disjoint_blocks():
    lines = [L("trái", 10, 100, 200, 130), L("phải", 800, 140, 1000, 170)]
    assert len(cluster_paragraphs(lines, line_height=30)) == 2
