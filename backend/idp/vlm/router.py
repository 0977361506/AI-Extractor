"""Which elements of a page go to the VLM tier (lowest confidence first, within the per-page budget)."""

from __future__ import annotations

from idp.core.ast import TEXT_TYPES, Element, ElementType, ReviewReason
from idp.vlm.settings import VlmSettings

_NEVER = {ElementType.PAGE_HEADER, ElementType.PAGE_FOOTER}
_OVERLAP = {ReviewReason.INK_OVERLAP, ReviewReason.STAMP_OVERLAP, ReviewReason.TABLE_STRUCTURE_INVALID}


def needs_vlm(el: Element, settings: VlmSettings) -> bool:
    if el.type in _NEVER or not el.bbox_normalized:
        return False
    if any(r in _OVERLAP for r in el.review_reasons):
        return True
    if el.type.value in settings.always_types:
        return True
    if el.type == ElementType.TABLE:
        return (
            el.confidence_score < settings.vlm_threshold
            or any(c.check_failed for c in el.cells)
            or any(c.text and c.confidence < settings.vlm_threshold for c in el.cells)
        )
    if el.type == ElementType.CHOICE_GROUP:
        return any(not o.label for o in el.options)
    if el.type in TEXT_TYPES:
        return el.confidence_score < settings.vlm_threshold
    return el.confidence_score < settings.vlm_threshold


def route(elements: list[Element], settings: VlmSettings) -> list[Element]:
    picked = [el for el in elements if needs_vlm(el, settings)]
    picked.sort(key=lambda e: e.confidence_score)
    return picked[: settings.max_calls_per_page]
