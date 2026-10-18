"""Checkbox / radio groups from Heron ``checkbox_selected`` / ``checkbox_unselected`` regions."""

from __future__ import annotations

import re
import statistics

from idp.core.ast import ChoiceOption, Element, ElementType
from idp.core.geometry import containment, normalize_bbox, union_bbox
from idp.layout.regions import CHECKBOX_LABELS, LayoutRegion
from idp.table.builder import OcrLine

_MARKER = re.compile(r"^[\s□☐☑☒✓✔✗✘■▪●○◯◉•\[\]]+")
_NUMBERING = re.compile(r"^\s*(?:\d+|[a-zA-Z])[.)]\s*")


def clean_label(text: str) -> str:
    return " ".join(_MARKER.sub("", text).split())


def clean_question(text: str) -> str:
    return " ".join(_NUMBERING.sub("", text).split()).rstrip(":：").strip()


def build_choice_groups(
    regions: list[LayoutRegion], lines: list[OcrLine], width: int, height: int
) -> tuple[list[Element], set[int]]:
    boxes = sorted((r for r in regions if r.label in CHECKBOX_LABELS), key=lambda r: (r.bbox[1] + r.bbox[3]) / 2)
    consumed: set[int] = set()
    options: list[tuple[LayoutRegion, list[int]]] = []
    for r in boxes:
        members = [i for i, ln in enumerate(lines) if i not in consumed and containment(ln.bbox, r.bbox) >= 0.5]
        consumed.update(members)
        options.append((r, members))

    rows: list[list[tuple[LayoutRegion, list[int]]]] = []
    for opt in options:
        cy = (opt[0].bbox[1] + opt[0].bbox[3]) / 2
        if rows:
            top = min(o[0].bbox[1] for o in rows[-1])
            bottom = max(o[0].bbox[3] for o in rows[-1])
            if top <= cy <= bottom:
                rows[-1].append(opt)
                continue
        rows.append([opt])

    groups: list[Element] = []
    for row in rows:
        row.sort(key=lambda o: o[0].bbox[0])
        top = min(o[0].bbox[1] for o in row)
        bottom = max(o[0].bbox[3] for o in row)
        first_x = row[0][0].bbox[0]
        q_idx = [
            i
            for i, ln in enumerate(lines)
            if i not in consumed and top <= (ln.bbox[1] + ln.bbox[3]) / 2 <= bottom and ln.bbox[2] <= first_x + 5
        ]
        q_idx.sort(key=lambda i: lines[i].bbox[0])
        consumed.update(q_idx)
        opts = []
        for r, members in row:
            label = clean_label(" ".join(lines[i].text for i in sorted(members, key=lambda i: lines[i].bbox[0])))
            opts.append(
                ChoiceOption(
                    label=label,
                    checked=r.label == "checkbox_selected",
                    bbox=normalize_bbox(r.bbox, width, height),
                    confidence=round(r.score, 4),
                )
            )
        all_boxes = [o[0].bbox for o in row] + [lines[i].bbox for i in q_idx]
        groups.append(
            Element(
                element_id="",
                type=ElementType.CHOICE_GROUP,
                reading_order=0,
                bbox_normalized=normalize_bbox(union_bbox(all_boxes), width, height),
                question=clean_question(" ".join(lines[i].text for i in q_idx)) or None,
                options=opts,
                multi_select=sum(o.checked for o in opts) > 1,
                confidence_score=round(statistics.fmean(o[0].score for o in row), 4),
                extraction_engine="docling_heron_checkbox",
            )
        )
    return groups, consumed
