"""Apply the VLM tier to routed elements of a page: crop the region, send it with the OCR draft, merge the answer."""

from __future__ import annotations

import numpy as np

from idp.assemble.page_builder import text_markdown
from idp.core.ast import Element, ElementType, Page, ReviewReason
from idp.core.geometry import crop_box, denormalize_bbox
from idp.elements.handwriting import infer_value_type, normalize_comb_value
from idp.table.checks import run_arithmetic_checks
from idp.table.numbers import fix_numeric_ocr, parse_vn_number
from idp.table.render import cells_to_html, cells_to_markdown
from idp.vlm import schemas
from idp.vlm.client import VlmClient, VlmError, VlmUnavailable
from idp.vlm.router import route
from idp.vlm.settings import VlmSettings

_RESOLVED = {ReviewReason.LOW_CONFIDENCE}


def _crop(display: np.ndarray, el: Element) -> np.ndarray:
    h, w = display.shape[:2]
    pad = max(10, int(0.004 * max(h, w)))
    return crop_box(display, denormalize_bbox(el.bbox_normalized, w, h), pad=pad)


def _finish(el: Element, client: VlmClient) -> None:
    el.extraction_engine = f"vlm:{client.model}"
    el.review_reasons = [r for r in el.review_reasons if r not in _RESOLVED]
    el.needs_human_review = bool(el.review_reasons)


def _refine_table(el: Element, img: np.ndarray, client: VlmClient, settings: VlmSettings) -> None:
    draft = [{"row": c.row, "col": c.col, "rowspan": c.rowspan, "colspan": c.colspan, "text": c.text} for c in el.cells]
    out: schemas.TableOut = client.ask(schemas.table_prompt(draft), schemas.TableOut, image=img)
    answer = {(c.row, c.col): c.text.strip() for c in out.cells}
    mismatch = False
    for cell in el.cells:
        new = answer.get((cell.row, cell.col))
        if new is None or new == cell.text:
            if new is not None:
                cell.confidence = max(cell.confidence, 0.95)
            continue
        old_num = parse_vn_number(fix_numeric_ocr(cell.text)) if cell.text else None
        new_num = parse_vn_number(fix_numeric_ocr(new))
        if old_num is not None and new_num is not None and old_num != new_num:
            cell.alt_text = cell.text
            mismatch = True
        cell.text = new
        cell.numeric_value = new_num
        cell.confidence = 0.95
    run_arithmetic_checks(el.cells)
    el.review_reasons = [r for r in el.review_reasons if r != ReviewReason.ARITHMETIC_CHECK_FAILED]
    if any(c.check_failed for c in el.cells):
        el.flag(ReviewReason.ARITHMETIC_CHECK_FAILED)
    if mismatch:
        el.flag(ReviewReason.OCR_VLM_MISMATCH)
    el.content_html = cells_to_html(el.cells)
    el.content_markdown = cells_to_markdown(el.cells)
    el.text = "\n".join(" | ".join(c.text for c in el.cells if c.row == r) for r in sorted({c.row for c in el.cells}))
    el.confidence_score = max(el.confidence_score, 0.95 if not mismatch else el.confidence_score)
    _finish(el, client)


def _refine_text(el: Element, img: np.ndarray, client: VlmClient, settings: VlmSettings) -> None:
    out: schemas.TextOut = client.ask(schemas.text_prompt(el.type.value, el.text), schemas.TextOut, image=img)
    if not out.text.strip():
        return
    el.text = out.text.strip()
    el.confidence_score = round(out.confidence, 4)
    if el.type in (ElementType.STAMP, ElementType.HANDWRITTEN_NOTE):
        el.description = None if el.type == ElementType.HANDWRITTEN_NOTE else el.description
        if el.type == ElementType.HANDWRITTEN_NOTE and out.confidence >= settings.ui_threshold:
            el.review_reasons = [r for r in el.review_reasons if r != ReviewReason.HANDWRITING]
    else:
        el.content_markdown = text_markdown(el.type, el.text, el.level)
    _finish(el, client)


def _refine_field(el: Element, img: np.ndarray, client: VlmClient, settings: VlmSettings) -> None:
    out: schemas.FieldOut = client.ask(schemas.field_prompt(el.label or "", el.value or ""), schemas.FieldOut, image=img)
    el.label = out.label.strip() or el.label
    el.value = normalize_comb_value(out.value.strip(), el.label or "")
    el.value_type = infer_value_type(el.value)
    el.confidence_score = max(el.confidence_score, 0.9)
    _finish(el, client)


def _refine_signature(el: Element, img: np.ndarray, client: VlmClient, settings: VlmSettings) -> None:
    out: schemas.SignatureOut = client.ask(schemas.signature_prompt(), schemas.SignatureOut, image=img)
    if out.signer_name:
        el.signer_name = out.signer_name.strip()
    _finish(el, client)


def _refine_choice(el: Element, img: np.ndarray, client: VlmClient, settings: VlmSettings) -> None:
    draft = [{"label": o.label, "checked": o.checked} for o in el.options]
    out: schemas.ChoiceOut = client.ask(schemas.choice_prompt(el.question, draft), schemas.ChoiceOut, image=img)
    if len(out.options) == len(el.options):
        for opt, new in zip(el.options, out.options):
            if opt.checked != new.checked:
                el.flag(ReviewReason.OCR_VLM_MISMATCH)
            opt.label = new.label.strip() or opt.label
        el.question = out.question or el.question
    _finish(el, client)


def _refine_figure(el: Element, img: np.ndarray, client: VlmClient, settings: VlmSettings) -> None:
    out: schemas.DiagramOut = client.ask(schemas.diagram_prompt(el.text), schemas.DiagramOut, image=img)
    if out.is_diagram and out.mermaid.strip():
        el.type = ElementType.DIAGRAM
        el.mermaid = out.mermaid.strip()
    el.description = out.description.strip() or el.description
    _finish(el, client)


_HANDLERS = {
    ElementType.TABLE: _refine_table,
    ElementType.FORM_FIELD: _refine_field,
    ElementType.SIGNATURE: _refine_signature,
    ElementType.CHOICE_GROUP: _refine_choice,
    ElementType.FIGURE: _refine_figure,
}


def refine_page(page: Page, display: np.ndarray, client: VlmClient, settings: VlmSettings) -> dict:
    calls0, hits0 = client.calls, client.cache_hits
    failed = 0
    for el in route(page.elements, settings):
        handler = _HANDLERS.get(el.type, _refine_text)
        try:
            handler(el, _crop(display, el), client, settings)
        except VlmUnavailable:
            el.flag(ReviewReason.VLM_UNAVAILABLE)
            failed += 1
        except VlmError:
            el.flag(ReviewReason.VLM_OUTPUT_INVALID)
            failed += 1
    return {"calls": client.calls - calls0, "cache_hits": client.cache_hits - hits0, "failed": failed}
