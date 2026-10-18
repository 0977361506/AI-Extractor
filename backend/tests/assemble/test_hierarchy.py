from idp.assemble.hierarchy import assign_hierarchy
from idp.core.ast import Document, DocumentMetadata, Element, ElementType, Page


def E(i, type_, text):
    return Element(element_id=f"e{i}", type=type_, reading_order=i, text=text, content_markdown=text)


def _doc(*pages):
    return Document(
        document_id="d",
        job_id="j",
        metadata=DocumentMetadata(filename="x.pdf", file_type="application/pdf", total_pages=len(pages)),
        pages=[Page(page_number=n + 1, width=100, height=100, elements=list(els)) for n, els in enumerate(pages)],
    )


def test_breadcrumbs_follow_heading_levels_across_pages():
    doc = _doc(
        [
            E(0, ElementType.TITLE, "HỢP ĐỒNG CUNG CẤP DỊCH VỤ"),
            E(1, ElementType.PARAGRAPH, "ĐIỀU 1. NỘI DUNG CÔNG VIỆC"),
            E(2, ElementType.PARAGRAPH, "1.1. Bên A cam kết..."),
            E(3, ElementType.PAGE_FOOTER, "Trang 1/4"),
        ],
        [
            E(0, ElementType.HEADING, "ĐIỀU 3. GIÁ TRỊ HỢP ĐỒNG"),
            E(1, ElementType.TABLE, "bảng"),
        ],
    )
    assign_hierarchy(doc)
    p1, p2 = doc.pages
    assert p1.elements[1].type == ElementType.HEADING  # promoted
    assert p1.elements[1].level == 1
    assert p1.elements[1].content_markdown == "## ĐIỀU 1. NỘI DUNG CÔNG VIỆC"
    assert p1.elements[2].hierarchy_breadcrumb == ["HỢP ĐỒNG CUNG CẤP DỊCH VỤ", "ĐIỀU 1. NỘI DUNG CÔNG VIỆC"]
    assert p1.elements[3].hierarchy_breadcrumb == []
    assert p2.elements[1].hierarchy_breadcrumb == ["HỢP ĐỒNG CUNG CẤP DỊCH VỤ", "ĐIỀU 3. GIÁ TRỊ HỢP ĐỒNG"]
    assert p1.elements[0].content_markdown == "# HỢP ĐỒNG CUNG CẤP DỊCH VỤ"


def test_long_paragraph_is_not_promoted():
    text = "Điều 5 của hợp đồng này quy định rằng các bên phải thực hiện đầy đủ nghĩa vụ " * 3
    doc = _doc([E(0, ElementType.PARAGRAPH, text)])
    assign_hierarchy(doc)
    assert doc.pages[0].elements[0].type == ElementType.PARAGRAPH


def test_numbered_heading_levels():
    doc = _doc(
        [
            E(0, ElementType.HEADING, "I. TÀI SẢN NGẮN HẠN"),
            E(1, ElementType.HEADING, "1. Tiền"),
            E(2, ElementType.HEADING, "1.1. Tiền mặt"),
            E(3, ElementType.PARAGRAPH, "nội dung"),
            E(4, ElementType.HEADING, "2. Đầu tư"),
            E(5, ElementType.PARAGRAPH, "nội dung 2"),
        ]
    )
    assign_hierarchy(doc)
    els = doc.pages[0].elements
    assert [e.level for e in els if e.type == ElementType.HEADING] == [1, 2, 3, 2]
    assert els[3].hierarchy_breadcrumb == ["I. TÀI SẢN NGẮN HẠN", "1. Tiền", "1.1. Tiền mặt"]
    assert els[5].hierarchy_breadcrumb == ["I. TÀI SẢN NGẮN HẠN", "2. Đầu tư"]
