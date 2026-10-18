"""Debug overlay: element boxes drawn on the display image (red = needs review, yellow = low confidence)."""

from __future__ import annotations

import cv2
import numpy as np

from idp.core.ast import ElementType, Page
from idp.core.geometry import denormalize_bbox

TYPE_COLORS = {
    ElementType.TABLE: (0, 140, 255),
    ElementType.TITLE: (160, 0, 200),
    ElementType.HEADING: (160, 0, 200),
    ElementType.FIGURE: (120, 120, 120),
    ElementType.STAMP: (200, 0, 0),
    ElementType.SIGNATURE: (0, 120, 120),
    ElementType.HANDWRITTEN_NOTE: (0, 0, 200),
    ElementType.FORM_FIELD: (0, 150, 0),
    ElementType.CHOICE_GROUP: (0, 150, 0),
}


def draw_overlay(display: np.ndarray, page: Page, ui_threshold: float = 0.80) -> np.ndarray:
    out = display.copy()
    if out.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2RGB)
    h, w = out.shape[:2]
    thick = max(2, w // 600)
    for el in page.elements:
        if not el.bbox_normalized:
            continue
        x0, y0, x1, y1 = (int(v) for v in denormalize_bbox(el.bbox_normalized, w, h))
        color = TYPE_COLORS.get(el.type, (40, 90, 220))
        if el.needs_human_review:
            color = (230, 0, 0)
        elif el.confidence_score < ui_threshold:
            color = (230, 180, 0)
        cv2.rectangle(out, (x0, y0), (x1, y1), color, thick)
        cv2.putText(out, f"{el.reading_order}:{el.type.value}", (x0 + 3, max(12, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4 * thick, color, max(1, thick // 2))
        for c in el.cells:
            if c.bbox and c.check_failed:
                cx0, cy0, cx1, cy1 = (int(v) for v in denormalize_bbox(c.bbox, w, h))
                cv2.rectangle(out, (cx0, cy0), (cx1, cy1), (230, 0, 0), thick)
    return out
