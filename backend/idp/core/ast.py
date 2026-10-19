"""Unified Document AST (see docs/plans/2026-10-19-banking-idp-design.md §2).

Every string field is normalized to Unicode NFC on validation.
Every bbox is ``(x0, y0, x1, y1)`` normalized to [0, 1] against the page's *display* image.
"""

from __future__ import annotations

import unicodedata
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _check_bbox(value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = value
    if not all(0.0 <= v <= 1.0 for v in value):
        raise ValueError(f"bbox values must be within [0, 1]: {value}")
    if x1 < x0 or y1 < y0:
        raise ValueError(f"bbox must be (x0, y0, x1, y1) with x0<=x1, y0<=y1: {value}")
    return value


NFCStr = Annotated[str, AfterValidator(_nfc)]
BBox = Annotated[tuple[float, float, float, float], AfterValidator(_check_bbox)]


class ElementType(StrEnum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    CAPTION = "caption"
    PAGE_HEADER = "page_header"
    PAGE_FOOTER = "page_footer"
    FORMULA = "formula"
    FIGURE = "figure"
    TABLE = "table"
    FORM_FIELD = "form_field"
    CHOICE_GROUP = "choice_group"
    DIAGRAM = "diagram"
    STAMP = "stamp"
    SIGNATURE = "signature"
    HANDWRITTEN_NOTE = "handwritten_note"


TEXT_TYPES = frozenset(
    {
        ElementType.TITLE,
        ElementType.HEADING,
        ElementType.PARAGRAPH,
        ElementType.LIST_ITEM,
        ElementType.CAPTION,
        ElementType.PAGE_HEADER,
        ElementType.PAGE_FOOTER,
        ElementType.FORMULA,
    }
)


class ReviewReason(StrEnum):
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    STAMP_OVERLAP = "STAMP_OVERLAP"
    INK_OVERLAP = "INK_OVERLAP"
    HANDWRITING = "HANDWRITING"
    OCR_VLM_MISMATCH = "OCR_VLM_MISMATCH"
    ARITHMETIC_CHECK_FAILED = "ARITHMETIC_CHECK_FAILED"
    TABLE_STRUCTURE_INVALID = "TABLE_STRUCTURE_INVALID"
    VLM_UNAVAILABLE = "VLM_UNAVAILABLE"
    VLM_OUTPUT_INVALID = "VLM_OUTPUT_INVALID"


REVIEW_REASON_VI: dict[ReviewReason, str] = {
    ReviewReason.LOW_CONFIDENCE: "Độ tự tin thấp",
    ReviewReason.STAMP_OVERLAP: "Dấu mộc đè lên nội dung",
    ReviewReason.INK_OVERLAP: "Mực màu / vết bẩn đè lên nội dung",
    ReviewReason.HANDWRITING: "Chữ viết tay",
    ReviewReason.OCR_VLM_MISMATCH: "OCR và AI đọc khác nhau",
    ReviewReason.ARITHMETIC_CHECK_FAILED: "Sai kiểm tra số học (tổng cộng)",
    ReviewReason.TABLE_STRUCTURE_INVALID: "Cấu trúc bảng không hợp lệ",
    ReviewReason.VLM_UNAVAILABLE: "Không gọi được AI (VLM)",
    ReviewReason.VLM_OUTPUT_INVALID: "AI trả kết quả sai định dạng",
}


class DocStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class PageStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class _Model(BaseModel):
    model_config = ConfigDict(use_enum_values=False, validate_assignment=True)


class Line(_Model):
    text: NFCStr
    bbox: BBox
    confidence: float


class TableCell(_Model):
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    is_header: bool = False
    text: NFCStr = ""
    numeric_value: float | None = None
    bbox: BBox | None = None
    confidence: float = 1.0
    check_failed: bool = False
    alt_text: str | None = None  # OCR reading kept when the VLM disagreed


class ChoiceOption(_Model):
    label: NFCStr
    checked: bool
    bbox: BBox | None = None
    confidence: float = 1.0


ValueType = Literal["text", "date", "id_number", "phone", "email", "number"]


class Element(_Model):
    element_id: str
    type: ElementType
    reading_order: int
    bbox_normalized: BBox | None = None
    hierarchy_breadcrumb: list[NFCStr] = Field(default_factory=list)
    text: NFCStr = ""
    content_markdown: NFCStr = ""
    confidence_score: float = 1.0
    needs_human_review: bool = False
    review_reasons: list[ReviewReason] = Field(default_factory=list)
    extraction_engine: str = ""
    human_corrected: bool = False
    lines: list[Line] = Field(default_factory=list)

    # heading
    level: int | None = None
    # formula
    latex: str | None = None
    # table
    cells: list[TableCell] = Field(default_factory=list)
    content_html: str | None = None
    continues_from: str | None = None
    continues_to: str | None = None
    # form_field
    label: NFCStr | None = None
    value: NFCStr | None = None
    value_type: ValueType | None = None
    bbox_label: BBox | None = None
    bbox_value: BBox | None = None
    is_handwritten: bool = False
    # choice_group
    question: NFCStr | None = None
    multi_select: bool = False
    options: list[ChoiceOption] = Field(default_factory=list)
    # diagram
    mermaid: str | None = None
    description: NFCStr | None = None
    # stamp
    color: str | None = None
    shape: str | None = None
    # signature
    signer_name: NFCStr | None = None
    # handwritten_note
    ink_color: str | None = None
    attached_to: str | None = None

    def flag(self, reason: ReviewReason) -> None:
        """Mark element for human review (idempotent)."""
        if reason not in self.review_reasons:
            self.review_reasons = [*self.review_reasons, reason]
        self.needs_human_review = True


class PageImages(_Model):
    raw: str
    display: str
    ocr: str


class Page(_Model):
    page_number: int
    status: PageStatus = PageStatus.DONE
    width: int
    height: int
    images: PageImages | None = None
    orientation_applied: int = 0
    deskew_angle: float = 0.0
    elements: list[Element] = Field(default_factory=list)
    error: str | None = None
    processing_time_ms: int = 0


class DocumentMetadata(_Model):
    filename: NFCStr
    file_type: str
    total_pages: int
    detected_charset: str = "UNICODE_NFC"
    has_red_stamp: bool = False
    processing_time_ms: int = 0
    vlm_invocations_count: int = 0
    engine_versions: dict[str, str] = Field(default_factory=dict)


class TablePart(_Model):
    page_number: int
    element_id: str
    row_start: int
    row_end: int


class LogicalTable(_Model):
    logical_table_id: str
    header_rows: int = 0
    cells: list[TableCell] = Field(default_factory=list)
    content_html: str = ""
    content_markdown: NFCStr = ""
    parts: list[TablePart] = Field(default_factory=list)


class SourceRef(_Model):
    page_number: int
    element_id: str
    bbox: BBox | None = None


class Chunk(_Model):
    chunk_id: str
    type: Literal["text", "table"]
    breadcrumb: list[NFCStr] = Field(default_factory=list)
    text: NFCStr
    source_refs: list[SourceRef] = Field(default_factory=list)


class Document(_Model):
    document_id: str
    job_id: str
    status: DocStatus = DocStatus.COMPLETED
    metadata: DocumentMetadata
    pages: list[Page] = Field(default_factory=list)
    logical_tables: list[LogicalTable] = Field(default_factory=list)
    chunks: list[Chunk] = Field(default_factory=list)

    def to_json(self, indent: int | None = 2) -> str:
        return self.model_dump_json(indent=indent, exclude_none=True)

    def iter_elements(self):
        for page in self.pages:
            for element in page.elements:
                yield page, element
