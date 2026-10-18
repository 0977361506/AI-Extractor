from idp.assemble.merge_tables import merge_cross_page_tables
from idp.core.ast import Document, DocumentMetadata, Element, ElementType, Page, ReviewReason, TableCell


def table(eid, rows, header=True):
    cells = [TableCell(row=r, col=c, text=t, is_header=header and r == 0) for r, row in enumerate(rows) for c, t in enumerate(row)]
    return Element(element_id=eid, type=ElementType.TABLE, reading_order=0, cells=cells)


def text(eid, t, type_=ElementType.PARAGRAPH):
    return Element(element_id=eid, type=type_, reading_order=0, text=t)


def _doc(p1, p2):
    return Document(
        document_id="d",
        job_id="j",
        metadata=DocumentMetadata(filename="x.pdf", file_type="application/pdf", total_pages=2),
        pages=[Page(page_number=1, width=1, height=1, elements=p1), Page(page_number=2, width=1, height=1, elements=p2)],
    )


HEAD = ["STT", "Hạng mục", "SL", "Đơn giá", "Thành tiền"]


def test_continuation_table_is_merged_with_header_and_totals_checked():
    t1 = table("t1", [HEAD, ["1", "Phân tích", "1", "100", "100"], ["2", "Lập trình", "3", "50", "150"]])
    t2 = table("t2", [["3", "Đào tạo", "2", "25", "50"], ["", "Cộng tiền hàng", "", "", "300"]], header=False)
    doc = _doc(
        [text("h", "ĐIỀU 3"), t1, text("c", "(Bảng 1 được tiếp tục ở trang sau)", ElementType.CAPTION), text("n", "Ghi chú: ...")],
        [text("c2", "(tiếp theo trang trước)", ElementType.CAPTION), t2],
    )
    merge_cross_page_tables(doc)
    assert len(doc.logical_tables) == 1
    lt = doc.logical_tables[0]
    assert [(p.page_number, p.element_id, p.row_start, p.row_end) for p in lt.parts] == [(1, "t1", 1, 2), (2, "t2", 3, 4)]
    assert lt.header_rows == 1
    assert "| 3 | Đào tạo | 2 | 25 | 50 |" in lt.content_markdown
    assert t1.continues_to == "t2" and t2.continues_from == "t1"
    assert not any(c.check_failed for c in t2.cells)  # 300 = 100 + 150 + 50 across pages


def test_cross_page_total_error_flags_part_element():
    t1 = table("t1", [HEAD, ["1", "A", "1", "100", "100"]])
    t2 = table("t2", [["2", "B", "1", "50", "50"], ["", "Cộng tiền hàng", "", "", "170"]], header=False)
    doc = _doc([t1], [t2])
    merge_cross_page_tables(doc)
    failed = [c for c in t2.cells if c.check_failed]
    assert [(c.row, c.col) for c in failed] == [(1, 4)]
    assert ReviewReason.ARITHMETIC_CHECK_FAILED in t2.review_reasons


def test_different_column_counts_are_not_merged():
    t1 = table("t1", [HEAD, ["1", "A", "1", "100", "100"]])
    t2 = table("t2", [["x", "y"], ["1", "2"]])
    doc = _doc([t1], [t2])
    merge_cross_page_tables(doc)
    assert len(doc.logical_tables) == 2
    assert t1.continues_to is None


def test_repeated_header_on_next_page_is_dropped():
    t1 = table("t1", [HEAD, ["1", "A", "1", "100", "100"]])
    t2 = table("t2", [HEAD, ["2", "B", "1", "50", "50"]])
    doc = _doc([t1], [t2])
    merge_cross_page_tables(doc)
    lt = doc.logical_tables[0]
    assert lt.content_markdown.count("STT") == 1
    assert len(lt.parts) == 2
