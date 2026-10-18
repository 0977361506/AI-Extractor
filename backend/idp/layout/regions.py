"""Layout regions and the clean-up of raw detector output (duplicates, containers, nesting)."""

from __future__ import annotations

from dataclasses import dataclass

from idp.core.geometry import PixelBox, containment, iou

CONTAINER_LABELS = frozenset({"form", "key_value_region", "document_index"})
ATOMIC_LABELS = frozenset({"table", "picture"})
CHECKBOX_LABELS = frozenset({"checkbox_selected", "checkbox_unselected"})


@dataclass(frozen=True)
class LayoutRegion:
    label: str
    score: float
    bbox: PixelBox  # pixels in the analysed image


def _priority(r: LayoutRegion) -> tuple[int, float]:
    return (2 if r.label in CHECKBOX_LABELS else 1 if r.label in ATOMIC_LABELS else 0, r.score)


def postprocess_regions(
    regions: list[LayoutRegion],
    min_score: float = 0.4,
    iou_threshold: float = 0.6,
    absorb_containment: float = 0.8,
) -> list[LayoutRegion]:
    rs = [r for r in regions if r.score >= min_score and r.label not in CONTAINER_LABELS]

    # 1) class-agnostic NMS, checkboxes and atomic blocks win ties
    kept: list[LayoutRegion] = []
    for r in sorted(rs, key=_priority, reverse=True):
        if all(iou(r.bbox, k.bbox) < iou_threshold for k in kept):
            kept.append(r)

    # 2) regions inside a table / picture are part of it
    atomic = [r for r in kept if r.label in ATOMIC_LABELS]
    kept = [
        r
        for r in kept
        if r.label in ATOMIC_LABELS
        or r.label in CHECKBOX_LABELS
        or not any(containment(r.bbox, a.bbox) >= absorb_containment for a in atomic)
    ]

    # 3) a (non-atomic) box that wraps >= 2 finer regions is redundant
    result = []
    for r in kept:
        if r.label not in ATOMIC_LABELS:
            inner = [o for o in kept if o is not r and containment(o.bbox, r.bbox) >= absorb_containment]
            if len(inner) >= 2:
                continue
        result.append(r)
    return result
