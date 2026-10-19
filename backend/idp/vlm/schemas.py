"""Output schemas (JSON-schema constrained) and task prompts for the VLM tier."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field


class TextOut(BaseModel):
    text: str
    confidence: float = Field(ge=0, le=1)


class CellOut(BaseModel):
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    text: str


class TableOut(BaseModel):
    header_rows: int = 0
    cells: list[CellOut]


class FieldOut(BaseModel):
    label: str
    value: str


class SignatureOut(BaseModel):
    signer_name: str | None = None


class OptionOut(BaseModel):
    label: str
    checked: bool


class ChoiceOut(BaseModel):
    question: str | None = None
    options: list[OptionOut]


class DiagramOut(BaseModel):
    is_diagram: bool
    mermaid: str = ""
    description: str = ""


def table_prompt(draft_cells: list[dict]) -> str:
    return (
        "Ảnh là một bảng trong hồ sơ ngân hàng. Dưới đây là bản nháp OCR dạng danh sách ô (row, col, rowspan, colspan, text). "
        "Hãy đối chiếu với ảnh và trả về danh sách ô đã sửa: giữ nguyên chỉ số hàng/cột của bản nháp nếu cấu trúc đúng, "
        "sửa lỗi chữ và số (đặc biệt số bị dấu mộc/vết bẩn/nét bút che), không thêm hàng/cột không có trong ảnh.\n"
        f"Bản nháp: {json.dumps(draft_cells, ensure_ascii=False)}"
    )


def text_prompt(kind: str, draft: str) -> str:
    what = {
        "handwritten_note": "chữ viết tay",
        "stamp": "nội dung con dấu (kể cả chữ chạy vòng cung)",
    }.get(kind, "đoạn văn bản in")
    return (
        f"Đọc chính xác {what} trong ảnh. Bản nháp OCR (có thể sai): {draft!r}. "
        "Trả về text đúng và confidence (0-1) thể hiện mức chắc chắn."
    )


def field_prompt(label: str, value: str) -> str:
    return (
        "Ảnh là một trường trong biểu mẫu: nhãn in sẵn và giá trị (thường viết tay, có thể viết trong các ô kẻ từng ký tự). "
        f"Bản nháp: nhãn={label!r}, giá trị={value!r}. Trả về nhãn và giá trị đọc đúng; ghép các ký tự trong ô kẻ thành từ."
    )


def signature_prompt() -> str:
    return "Ảnh là vùng chữ ký. Nếu có họ tên người ký (in hoặc viết tay) gần chữ ký, trả về signer_name; nếu không, trả về null."


def choice_prompt(question: str | None, options: list[dict]) -> str:
    return (
        "Ảnh là một nhóm ô chọn (checkbox/radio). "
        f"Bản nháp: câu hỏi={question!r}, lựa chọn={json.dumps(options, ensure_ascii=False)}. "
        "Trả về câu hỏi và từng lựa chọn với nhãn đúng và trạng thái checked (đã đánh dấu/tô hay chưa)."
    )


def diagram_prompt(draft_text: str) -> str:
    return (
        "Ảnh là một hình trong tài liệu. Nếu là sơ đồ (quy trình, tổ chức, quan hệ thực thể), đặt is_diagram=true và "
        "chuyển thành mã Mermaid (flowchart TD / graph TD / erDiagram) với nhãn tiếng Việt đúng như trong ảnh, kèm mô tả ngắn. "
        f"Nếu là biểu đồ số liệu hoặc ảnh khác, is_diagram=false và mô tả nội dung chính. Chữ OCR trong hình: {draft_text!r}"
    )
