"""Single scanned page → AST ``Page`` (preprocess → layout → tables → OCR → special elements → assembly)."""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from idp.assemble.lines import group_rows
from idp.assemble.page_builder import build_elements
from idp.core.ast import Element, ElementType, Page, PageImages
from idp.core.config import Settings, get_settings
from idp.core.geometry import PixelBox, containment, crop_quad, denormalize_bbox, intersection, quad_to_bbox, quad_wh
from idp.elements.choices import build_choice_groups
from idp.elements.handwriting import HandwrittenText, build_ink_elements
from idp.elements.ink_regions import InkKind, find_ink_blobs
from idp.ingest.rasterize import SourcePage
from idp.layout.regions import CHECKBOX_LABELS, postprocess_regions
from idp.preprocess.cleanup import normalize_illumination, remove_speckles, remove_streaks
from idp.preprocess.deskew import estimate_skew, rotate_bound
from idp.preprocess.ink import separate_inks
from idp.preprocess.orientation import detect_orientation, rotate_orthogonal
from idp.table.builder import OcrLine, build_ruled_table, sanitize_ocr
from idp.table.checks import run_arithmetic_checks


@dataclass
class PageOutput:
    page: Page
    display: np.ndarray
    has_red_stamp: bool = False
    stats: dict = field(default_factory=dict)


def downscale(img: np.ndarray, long_side: int) -> tuple[np.ndarray, float]:
    h, w = img.shape[:2]
    scale = long_side / max(h, w)
    if scale >= 1.0:
        return img, 1.0
    return cv2.resize(img, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_AREA), scale


def attach_notes(elements: list[Element]) -> None:
    """Link marks / handwritten notes to the element they annotate."""
    targets = [e for e in elements if e.type not in (ElementType.HANDWRITTEN_NOTE, ElementType.STAMP, ElementType.SIGNATURE) and e.bbox_normalized]
    for note in elements:
        if note.type != ElementType.HANDWRITTEN_NOTE or not note.bbox_normalized or not targets:
            continue
        nb = note.bbox_normalized
        overlapping = max(targets, key=lambda t: intersection(nb, t.bbox_normalized))
        if intersection(nb, overlapping.bbox_normalized) > 0:
            note.attached_to = overlapping.element_id
            continue
        above = [t for t in targets if t.bbox_normalized[3] <= nb[1] + 0.01]
        if above:
            note.attached_to = min(above, key=lambda t: nb[1] - t.bbox_normalized[3]).element_id


def _line_height(quads: list[np.ndarray], default: float) -> float:
    hs = [quad_wh(q)[1] for q in quads if quad_wh(q)[0] > 2 * quad_wh(q)[1]]
    return float(statistics.median(hs)) if len(hs) >= 5 else default


def accept_ink_text(text: str, confidence: float, min_conf: float) -> bool:
    """Digit strings (comb boxes, dates, phone numbers) get a lower bar: the recogniser is unsure but right."""
    compact = "".join(text.split())
    if len(compact) >= 6 and sum(c.isdigit() for c in compact) >= 0.8 * len(compact):
        return confidence >= min(min_conf, 0.3)
    return confidence >= min_conf


def _ink_text(gray: np.ndarray, mask: np.ndarray, box: PixelBox, models, min_conf: float) -> HandwrittenText:
    """Read coloured ink: keep only that ink (mask grown to its anti-aliased edges), detect lines, recognise."""
    x0, y0, x1, y1 = (int(v) for v in box)
    zone = cv2.dilate(mask[y0:y1, x0:x1].astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) > 0
    crop = np.where(zone, gray[y0:y1, x0:x1], 255).astype(np.uint8)
    # stretch contrast so light ink reads like print
    ink_vals = crop[zone]
    if ink_vals.size:
        lo = float(np.percentile(ink_vals, 5))
        crop = np.clip((crop.astype(np.float32) - lo) / max(1.0, 235 - lo) * 255, 0, 255).astype(np.uint8)
    crop = np.pad(crop, 16, constant_values=255)
    quads = models.detector.detect(crop)
    if not quads:
        return HandwrittenText("", 0.0)
    raw = [sanitize_ocr(t, p) for t, p in models.recognizer.recognize([crop_quad(crop, q) for q in quads])]
    found = [OcrLine(text=t, confidence=p, bbox=quad_to_bbox(q)) for q, (t, p) in zip(quads, raw) if t]
    results = [(ln.text, ln.confidence) for row in group_rows(found) for ln in row]
    if not results:
        return HandwrittenText("", 0.0)
    total = sum(len(t) for t, _ in results)
    conf = sum(p * len(t) for t, p in results) / total
    text = " ".join(t for t, _ in results)
    if not accept_ink_text(text, conf, min_conf):
        return HandwrittenText("", round(conf, 4))
    return HandwrittenText(text, round(conf, 4))


def process_page(
    src: SourcePage,
    models,
    storage,
    document_id: str,
    settings: Settings | None = None,
    review_threshold: float = 0.80,
) -> PageOutput:
    t0 = time.perf_counter()
    s = settings or get_settings()
    pn = src.page_number
    scale_dpi = s.render_dpi / 300
    raw_key = storage.put_image(document_id, f"pages/{pn}_raw.jpg", src.image)

    # orientation + skew on a downscaled, ink-cleaned copy
    small, _ = downscale(src.image, s.analysis_long_side)
    small_gray = separate_inks(normalize_illumination(small)).ocr_gray
    angle = detect_orientation(small_gray, models.detector)
    small_gray = rotate_orthogonal(small_gray, angle)
    skew = estimate_skew(models.detector.detect(small_gray))
    display = rotate_orthogonal(src.image, angle)
    if abs(skew) >= 0.15:
        display = rotate_bound(display, skew)
    height, width = display.shape[:2]

    flat = normalize_illumination(display)
    flat_gray = cv2.cvtColor(flat, cv2.COLOR_RGB2GRAY)
    ink = separate_inks(flat)
    ocr_gray = remove_speckles(remove_streaks(ink.ocr_gray), max_area=int(30 * scale_dpi**2), keep_radius=int(15 * scale_dpi))
    display_key = storage.put_image(document_id, f"pages/{pn}_display.jpg", display)
    ocr_key = storage.put_image(document_id, f"pages/{pn}_ocr.png", ocr_gray)

    regions = postprocess_regions(models.layout.predict(display), min_score=s.layout_threshold)
    quads = models.detector.detect(ocr_gray)
    line_height = _line_height(quads, 34 * scale_dpi)

    # ruled tables: grid + per-cell OCR
    tables: dict[int, list] = {}
    ruled_boxes: list[PixelBox] = []
    for i, r in enumerate(regions):
        if r.label != "table":
            continue
        pad = int(12 * scale_dpi)
        x0, y0 = max(0, int(r.bbox[0]) - pad), max(0, int(r.bbox[1]) - pad)
        x1, y1 = min(width, int(r.bbox[2]) + pad), min(height, int(r.bbox[3]) + pad)
        cells = build_ruled_table(
            ocr_gray[y0:y1, x0:x1], (x0, y0), width, height, line_height, models.recognizer, presence_gray=flat_gray[y0:y1, x0:x1]
        )
        if cells:
            run_arithmetic_checks(cells)
            tables[i] = cells
            ruled_boxes.append(r.bbox)

    # text lines outside ruled tables
    keep = [q for q in quads if not any(containment(quad_to_bbox(q), b) >= 0.5 for b in ruled_boxes)]
    results = models.recognizer.recognize([crop_quad(ocr_gray, q) for q in keep]) if keep else []
    results = [sanitize_ocr(t, p) for t, p in results]
    lines = [OcrLine(text=t, confidence=p, bbox=quad_to_bbox(q), quad=q) for q, (t, p) in zip(keep, results) if t]

    # checkbox / radio groups
    choices, used = build_choice_groups(regions, lines, width, height)
    lines = [ln for i, ln in enumerate(lines) if i not in used]

    # coloured ink: stamps, marks, signatures, handwriting
    # coloured ink inside charts / checkboxes is content, not annotation
    ignore = [r.bbox for r in regions if r.label in CHECKBOX_LABELS]
    for r in regions:
        if r.label == "picture":
            inside = sum(1 for ln in lines if containment(ln.bbox, r.bbox) >= 0.5)
            if (r.bbox[2] - r.bbox[0]) * (r.bbox[3] - r.bbox[1]) > 0.05 * width * height and inside >= 3:
                ignore.append(r.bbox)
    blobs = find_ink_blobs(ink.masks, line_height, ignore_boxes=ignore)
    texts = [
        _ink_text(flat_gray, ink.masks[b.color], b.bbox, models, min_conf=0.5 if b.kind == InkKind.STAMP else 0.6)
        if b.kind in (InkKind.STAMP, InkKind.HANDWRITING)
        else HandwrittenText("", 0.0)
        for b in blobs
    ]
    ink_elements, used = build_ink_elements(blobs, texts, lines, width, height, line_height)
    lines = [ln for i, ln in enumerate(lines) if i not in used]

    # pictures that are really stamps / signatures
    ink_boxes = [b.bbox for b in blobs]
    regions_kept = {
        i
        for i, r in enumerate(regions)
        if not (r.label == "picture" and any(containment(r.bbox, ib) >= 0.5 or containment(ib, r.bbox) >= 0.5 for ib in ink_boxes))
    }
    filtered = [r for i, r in enumerate(regions) if i in regions_kept]
    remap = {old: new for new, old in enumerate(i for i in range(len(regions)) if i in regions_kept)}
    tables = {remap[i]: c for i, c in tables.items() if i in remap}

    elements = build_elements(
        pn,
        width,
        height,
        filtered,
        lines,
        tables,
        extra=choices + ink_elements,
        review_threshold=review_threshold,
        line_height=line_height,
        engine=f"{models.layout.name}+{models.detector.name}+{models.recognizer.name}",
    )
    attach_notes(elements)
    page = Page(
        page_number=pn,
        width=width,
        height=height,
        images=PageImages(raw=raw_key, display=display_key, ocr=ocr_key),
        orientation_applied=angle,
        deskew_angle=skew,
        elements=elements,
        processing_time_ms=int((time.perf_counter() - t0) * 1000),
    )
    has_red_stamp = any(b.kind == InkKind.STAMP and b.color == "red" for b in blobs)
    return PageOutput(page=page, display=display, has_red_stamp=has_red_stamp, stats={"line_height": line_height, "lines": len(lines)})


__all__ = ["PageOutput", "attach_notes", "denormalize_bbox", "downscale", "process_page"]
