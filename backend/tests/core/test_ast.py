import unicodedata

import pytest
from pydantic import ValidationError

from idp.core.ast import (
    REVIEW_REASON_VI,
    ChoiceOption,
    Document,
    DocumentMetadata,
    Element,
    ElementType,
    Page,
    PageImages,
    ReviewReason,
    TableCell,
)


def _decomposed(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def test_strings_are_normalized_to_nfc():
    el = Element(
        element_id="el_p1_001",
        type=ElementType.PARAGRAPH,
        reading_order=0,
        text=_decomposed("Cộng hòa"),
        hierarchy_breadcrumb=[_decomposed("BÁO CÁO")],
    )
    assert el.text == unicodedata.normalize("NFC", "Cộng hòa")
    assert unicodedata.is_normalized("NFC", el.text)
    assert unicodedata.is_normalized("NFC", el.hierarchy_breadcrumb[0])


def test_table_cell_text_is_nfc():
    cell = TableCell(row=0, col=0, text=_decomposed("Chỉ tiêu"))
    assert unicodedata.is_normalized("NFC", cell.text)


def test_bbox_must_be_normalized_and_ordered():
    with pytest.raises(ValidationError):
        Element(element_id="e", type=ElementType.PARAGRAPH, reading_order=0, bbox_normalized=(0.1, 0.1, 1.5, 0.2))
    with pytest.raises(ValidationError):
        Element(element_id="e", type=ElementType.PARAGRAPH, reading_order=0, bbox_normalized=(0.5, 0.1, 0.2, 0.2))
    el = Element(element_id="e", type=ElementType.PARAGRAPH, reading_order=0, bbox_normalized=(0.1, 0.1, 0.9, 0.2))
    assert el.bbox_normalized == (0.1, 0.1, 0.9, 0.2)


def test_every_review_reason_has_vietnamese_label():
    for reason in ReviewReason:
        assert REVIEW_REASON_VI[reason]


def test_document_json_roundtrip_keeps_vietnamese():
    doc = Document(
        document_id="doc_1",
        job_id="job_1",
        metadata=DocumentMetadata(filename="BCTC.pdf", file_type="application/pdf", total_pages=1),
        pages=[
            Page(
                page_number=1,
                width=2480,
                height=3508,
                images=PageImages(raw="doc_1/pages/1_raw.png", display="doc_1/pages/1_display.png", ocr="doc_1/pages/1_ocr.png"),
                elements=[
                    Element(
                        element_id="el_p1_001",
                        type=ElementType.CHOICE_GROUP,
                        reading_order=0,
                        question="Giới tính",
                        options=[ChoiceOption(label="Nam", checked=True), ChoiceOption(label="Nữ", checked=False)],
                        review_reasons=[ReviewReason.LOW_CONFIDENCE],
                        needs_human_review=True,
                    )
                ],
            )
        ],
    )
    raw = doc.to_json()
    assert "Giới tính" in raw  # not \u-escaped
    again = Document.model_validate_json(raw)
    assert again == doc


def test_to_json_omits_unset_optional_fields():
    el = Element(element_id="e", type=ElementType.PARAGRAPH, reading_order=0, text="x")
    dumped = el.model_dump(mode="json", exclude_none=True)
    assert "mermaid" not in dumped
    assert "signer_name" not in dumped
