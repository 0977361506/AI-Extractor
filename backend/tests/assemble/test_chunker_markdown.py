from idp.assemble.chunker import build_chunks
from idp.assemble.markdown import render_markdown
from idp.assemble.merge_tables import merge_cross_page_tables
from idp.core.ast import ChoiceOption, Document, DocumentMetadata, Element, ElementType, Page, TableCell


def _doc():
    rows = [["Chỉ tiêu", "Số tiền"]] + [[f"Dòng {i}", f"{i}.000"] for i in range(1, 41)]
    cells = [TableCell(row=r, col=c, text=t, is_header=r == 0) for r, row in enumerate(rows) for c, t in enumerate(row)]
    els = [
        Element(element_id="h", type=ElementType.HEADING, reading_order=0, level=1, text="ĐIỀU 3", content_markdown="## ĐIỀU 3", hierarchy_breadcrumb=["ĐIỀU 3"]),
        Element(element_id="p", type=ElementType.PARAGRAPH, reading_order=1, text="Giá trị hợp đồng.", content_markdown="Giá trị hợp đồng.", hierarchy_breadcrumb=["ĐIỀU 3"]),
        Element(element_id="t", type=ElementType.TABLE, reading_order=2, cells=cells, hierarchy_breadcrumb=["ĐIỀU 3"], bbox_normalized=(0.1, 0.2, 0.9, 0.8)),
        Element(element_id="f", type=ElementType.PAGE_FOOTER, reading_order=3, text="Trang 1", content_markdown="Trang 1"),
        Element(
            element_id="c",
            type=ElementType.CHOICE_GROUP,
            reading_order=4,
            question="Giới tính",
            options=[ChoiceOption(label="Nam", checked=True), ChoiceOption(label="Nữ", checked=False)],
            hierarchy_breadcrumb=["ĐIỀU 3"],
        ),
    ]
    doc = Document(
        document_id="doc_x",
        job_id="j",
        metadata=DocumentMetadata(filename="HopDong.pdf", file_type="application/pdf", total_pages=1),
        pages=[Page(page_number=1, width=100, height=100, elements=els)],
    )
    merge_cross_page_tables(doc)
    return doc


def test_table_chunks_repeat_header_and_carry_context():
    chunks = build_chunks(_doc(), max_chars=300)
    table_chunks = [c for c in chunks if c.type == "table"]
    assert len(table_chunks) > 1
    for c in table_chunks:
        assert c.text.startswith("[Bối cảnh: HopDong > ĐIỀU 3]")
        assert "| Chỉ tiêu | Số tiền |" in c.text
        assert c.source_refs[0].element_id == "t"
    all_rows = "".join(c.text for c in table_chunks)
    assert all(f"| Dòng {i} |" in all_rows for i in range(1, 41))


def test_text_chunk_skips_footer_and_includes_choices():
    chunks = build_chunks(_doc(), max_chars=300)
    text_chunks = [c for c in chunks if c.type == "text"]
    joined = "\n".join(c.text for c in text_chunks)
    assert "Giá trị hợp đồng." in joined
    assert "Trang 1" not in joined
    assert "[x] Nam" in joined
    assert [c.chunk_id for c in chunks] == [f"doc_x_c{i:04d}" for i in range(len(chunks))]


def test_render_markdown():
    md = render_markdown(_doc())
    assert "<!-- page 1 -->" in md
    assert "## ĐIỀU 3" in md
    assert "| Chỉ tiêu | Số tiền |" in md
    assert "Trang 1" not in md
    assert "**Giới tính**: [x] Nam · [ ] Nữ" in md
