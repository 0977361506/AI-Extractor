"""Turn classified ink blobs (+ their recognised text) into stamp / signature / form-field / note elements."""

from __future__ import annotations

import re
from dataclasses import dataclass

from idp.core.ast import Element, ElementType, ReviewReason
from idp.core.geometry import normalize_bbox, union_bbox
from idp.elements.choices import clean_question
from idp.elements.ink_regions import InkBlob, InkKind
from idp.table.builder import OcrLine


@dataclass
class HandwrittenText:
    text: str
    confidence: float


def infer_value_type(value: str) -> str:
    v = value.strip()
    compact = re.sub(r"[\s.\-]", "", v)
    if "@" in v:
        return "email"
    if re.fullmatch(r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}", v) or re.fullmatch(r"\d{2}\s+\d{2}\s+\d{4}", v):
        return "date"
    if re.fullmatch(r"0\d{9,10}", compact):
        return "phone"
    if re.fullmatch(r"\d{9,12}", compact):
        return "id_number"
    if re.fullmatch(r"[\d.,]+", compact) and compact:
        return "number"
    return "text"


_SIGN_ANCHOR = re.compile(r"\(\s*ký|ký\s*,|ký\s+(và\s+)?(ghi|họ|tên)|ký tên|chữ ký", re.IGNORECASE)


def is_signature_anchor(text: str) -> bool:
    return bool(_SIGN_ANCHOR.search(text))


def _x_overlap(a, b) -> float:
    return min(a[2], b[2]) - max(a[0], b[0])


def build_ink_elements(
    blobs: list[InkBlob],
    texts: list[HandwrittenText],
    lines: list[OcrLine],
    width: int,
    height: int,
    line_height: float,
) -> tuple[list[Element], set[int]]:
    lh = line_height
    consumed: set[int] = set()
    elements: list[Element] = []
    fields: list[Element] = []
    signatures: list[tuple[Element, tuple]] = []

    def norm(b):
        return normalize_bbox(b, width, height)

    order = sorted(range(len(blobs)), key=lambda i: (blobs[i].bbox[1], blobs[i].bbox[0]))
    for i in order:
        blob, ht = blobs[i], texts[i]
        b = blob.bbox
        base = dict(element_id="", reading_order=0, bbox_normalized=norm(b), confidence_score=round(ht.confidence, 4), extraction_engine="ink_vietocr")
        if blob.kind == InkKind.STAMP:
            elements.append(Element(type=ElementType.STAMP, text=ht.text, color=blob.color, shape=blob.shape, **base))
            continue
        if blob.kind == InkKind.MARK:
            elements.append(Element(type=ElementType.HANDWRITTEN_NOTE, text="", ink_color=blob.color, description="Khoanh tròn đánh dấu", **base))
            continue

        # handwritten name right under a signature
        owner = next((sig for sig, sb in signatures if 0 <= b[1] - sb[3] < 3 * lh and _x_overlap(sb, b) > 0), None)
        if owner is not None and ht.text:
            owner.signer_name = ht.text
            continue

        # signature: under a printed "(Ký, họ tên)" style line
        sign_line = next(
            (
                ln
                for ln in lines
                if is_signature_anchor(ln.text) and ln.bbox[3] <= b[1] + lh and b[1] - ln.bbox[3] < 4 * lh and _x_overlap(ln.bbox, b) > 0
            ),
            None,
        )
        if sign_line is not None and blob.color == "red" and min(b[2] - b[0], b[3] - b[1]) >= 3 * lh:
            elements.append(Element(type=ElementType.STAMP, text=ht.text, color=blob.color, shape="unknown", **base))
            continue
        if sign_line is not None:
            below = [
                ln
                for ln in lines
                if ln.bbox[1] >= b[3] - lh and ln.bbox[1] - b[3] < 5 * lh and _x_overlap(ln.bbox, b) > 0 and not is_signature_anchor(ln.text)
            ]
            name = min(below, key=lambda ln: ln.bbox[1]).text if below else None
            sig = Element(type=ElementType.SIGNATURE, signer_name=name, **base)
            elements.append(sig)
            signatures.append((sig, b))
            continue


        # form field: printed label on the same row, to the left
        cy = (b[1] + b[3]) / 2
        candidates = [
            (j, ln)
            for j, ln in enumerate(lines)
            if j not in consumed
            and ln.bbox[2] <= b[0] + 0.5 * lh
            and b[0] - ln.bbox[2] <= 0.3 * width
            and (b[1] <= (ln.bbox[1] + ln.bbox[3]) / 2 <= b[3] or ln.bbox[1] <= cy <= ln.bbox[3])
        ]
        if candidates and ht.text:
            j, label_line = max(candidates, key=lambda c: c[1].bbox[2])
            consumed.add(j)
            el = Element(
                type=ElementType.FORM_FIELD,
                label=clean_question(label_line.text),
                value=ht.text,
                value_type=infer_value_type(ht.text),
                bbox_label=norm(label_line.bbox),
                bbox_value=norm(b),
                is_handwritten=True,
                **{**base, "bbox_normalized": norm(union_bbox([label_line.bbox, b]))},
            )
            el.flag(ReviewReason.HANDWRITING)
            elements.append(el)
            fields.append(el)
            continue

        # continuation line of the previous field's value
        prev = fields[-1] if fields else None
        if prev is not None and ht.text and prev.bbox_value is not None:
            pv = (prev.bbox_value[0] * width, prev.bbox_value[1] * height, prev.bbox_value[2] * width, prev.bbox_value[3] * height)
            if 0 <= b[1] - pv[3] < 2 * lh and _x_overlap(pv, b) > 0:
                prev.value = f"{prev.value}, {ht.text}"
                merged_value = union_bbox([pv, b])
                prev.bbox_value = norm(merged_value)
                prev.bbox_normalized = norm(union_bbox([merged_value, (prev.bbox_normalized[0] * width, prev.bbox_normalized[1] * height, prev.bbox_normalized[2] * width, prev.bbox_normalized[3] * height)]))
                continue

        el = Element(type=ElementType.HANDWRITTEN_NOTE, text=ht.text, ink_color=blob.color, **base)
        if ht.text:
            el.flag(ReviewReason.HANDWRITING)
        elements.append(el)
    return elements, consumed
