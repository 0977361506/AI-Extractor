"""Before / after view of what the VLM refinement changed on a page (for the stepper's AI step)."""

from __future__ import annotations

from idp.core.ast import Page


def snapshot_elements(page: Page) -> dict[str, tuple[str, dict[tuple[int, int], str]]]:
    return {e.element_id: (e.text or "", {(c.row, c.col): c.text for c in e.cells or []}) for e in page.elements}


def diff_elements(before: dict[str, tuple[str, dict[tuple[int, int], str]]], page: Page) -> list[dict]:
    changes: list[dict] = []
    for e in page.elements:
        if e.element_id not in before:
            continue
        old_text, old_cells = before[e.element_id]
        if e.cells:
            for c in e.cells:
                old = old_cells.get((c.row, c.col))
                if old is not None and old != c.text:
                    changes.append({"element_id": e.element_id, "cell": [c.row, c.col], "before": old, "after": c.text})
        elif (e.text or "") != old_text:
            changes.append({"element_id": e.element_id, "before": old_text, "after": e.text or ""})
    return changes
