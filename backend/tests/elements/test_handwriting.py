from idp.core.ast import ElementType, ReviewReason
from idp.elements.handwriting import HandwrittenText, build_ink_elements
from idp.elements.ink_regions import InkBlob, InkKind
from idp.table.builder import OcrLine


def L(text, x0, y0, x1, y1):
    return OcrLine(text=text, confidence=0.9, bbox=(x0, y0, x1, y1))


W, H = 1000, 1400


def test_handwriting_right_of_label_becomes_form_field_and_continuation_merges():
    lines = [L("1. Họ và tên (chữ in hoa):", 50, 100, 300, 130), L("6. Địa chỉ liên hệ:", 50, 300, 260, 330)]
    blobs = [
        InkBlob(InkKind.HANDWRITING, "blue", (400, 95, 800, 135)),
        InkBlob(InkKind.HANDWRITING, "blue", (400, 295, 900, 335)),
        InkBlob(InkKind.HANDWRITING, "blue", (60, 360, 500, 395)),  # 2nd address line under the value
    ]
    texts = [HandwrittenText("LÊ HOÀNG MINH", 0.7), HandwrittenText("Số 12, ngõ 45 Tô Hiệu", 0.7), HandwrittenText("Q. Cầu Giấy, Hà Nội", 0.7)]
    els, consumed = build_ink_elements(blobs, texts, lines, W, H, line_height=30)
    fields = [e for e in els if e.type == ElementType.FORM_FIELD]
    assert [(f.label, f.value) for f in fields] == [
        ("Họ và tên (chữ in hoa)", "LÊ HOÀNG MINH"),
        ("Địa chỉ liên hệ", "Số 12, ngõ 45 Tô Hiệu, Q. Cầu Giấy, Hà Nội"),
    ]
    assert all(f.is_handwritten and ReviewReason.HANDWRITING in f.review_reasons for f in fields)
    assert consumed == {0, 1}


def test_free_note_and_stamp_and_signature():
    lines = [L("Giám đốc", 700, 600, 850, 630), L("(Ký, họ tên)", 700, 640, 850, 665), L("Trần Thị Thu Hằng", 680, 820, 900, 850)]
    blobs = [
        InkBlob(InkKind.HANDWRITING, "blue", (60, 1000, 600, 1040)),  # free note
        InkBlob(InkKind.STAMP, "red", (650, 650, 900, 900), shape="round"),
        InkBlob(InkKind.HANDWRITING, "blue", (700, 690, 880, 780)),  # signature under "(Ký, họ tên)"
        InkBlob(InkKind.MARK, "red", (100, 200, 300, 260)),
    ]
    texts = [HandwrittenText("Đã đối chiếu - OK", 0.6), HandwrittenText("MST 0109876543", 0.6), HandwrittenText("", 0.0), HandwrittenText("", 0.0)]
    els, _ = build_ink_elements(blobs, texts, lines, W, H, line_height=30)
    types = sorted(e.type for e in els)
    assert types == sorted([ElementType.HANDWRITTEN_NOTE, ElementType.STAMP, ElementType.SIGNATURE, ElementType.HANDWRITTEN_NOTE])
    sig = next(e for e in els if e.type == ElementType.SIGNATURE)
    assert sig.signer_name == "Trần Thị Thu Hằng"
    stamp = next(e for e in els if e.type == ElementType.STAMP)
    assert stamp.text == "MST 0109876543" and stamp.color == "red" and stamp.shape == "round"
    mark = next(e for e in els if e.type == ElementType.HANDWRITTEN_NOTE and e.text == "")
    assert mark.description == "Khoanh tròn đánh dấu"


def test_title_containing_dang_ky_is_not_a_signature_anchor():
    lines = [L("PHIẾU ĐĂNG KÝ SỬ DỤNG DỊCH VỤ", 300, 100, 700, 140)]
    blobs = [InkBlob(InkKind.HANDWRITING, "blue", (350, 180, 650, 220))]
    els, _ = build_ink_elements(blobs, [HandwrittenText("ghi chú", 0.8)], lines, W, H, line_height=30)
    assert els[0].type == ElementType.HANDWRITTEN_NOTE


def test_large_red_scribble_near_signature_line_is_a_stamp():
    lines = [L("(Ký, ghi rõ họ tên, đóng dấu)", 100, 600, 400, 630)]
    blobs = [InkBlob(InkKind.HANDWRITING, "red", (120, 640, 380, 900))]
    els, _ = build_ink_elements(blobs, [HandwrittenText("", 0.0)], lines, W, H, line_height=30)
    assert els[0].type == ElementType.STAMP


def test_handwritten_name_under_signature_is_signer_name():
    lines = [L("(Ký, ghi rõ họ tên)", 700, 600, 900, 630)]
    blobs = [
        InkBlob(InkKind.HANDWRITING, "blue", (700, 650, 900, 720)),  # signature scribble
        InkBlob(InkKind.HANDWRITING, "blue", (720, 740, 880, 770)),  # handwritten name below
    ]
    texts = [HandwrittenText("", 0.1), HandwrittenText("Lê Hoàng Minh", 0.8)]
    els, _ = build_ink_elements(blobs, texts, lines, W, H, line_height=30)
    assert len(els) == 1 and els[0].type == ElementType.SIGNATURE and els[0].signer_name == "Lê Hoàng Minh"


def test_label_too_far_left_is_not_paired():
    lines = [L("NHẬN", 50, 700, 120, 730)]
    blobs = [InkBlob(InkKind.HANDWRITING, "blue", (700, 695, 900, 735))]
    els, consumed = build_ink_elements(blobs, [HandwrittenText("ghi chú", 0.8)], lines, W, H, line_height=30)
    assert els[0].type == ElementType.HANDWRITTEN_NOTE and not consumed
