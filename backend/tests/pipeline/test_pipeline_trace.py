"""Stepper events (PLAN / STEP) and per-page traces emitted by the document pipeline, with fake models."""

import io
import json

import docx
import numpy as np
import pytest
from PIL import Image

from idp.core.ast import Element, ElementType, Page, TableCell
from idp.layout.regions import LayoutRegion
from idp.pipeline.document import process_document
from idp.pipeline.trace import NATIVE_PLAN, PAGE_STEPS, SCAN_PLAN, PageTrace
from idp.pipeline.vlm_diff import diff_elements, snapshot_elements
from idp.storage.local import LocalStorage

from .test_digital_pdf import FONT, LINES, _pdf


def _quad(img, x0, y0, x1, y1):
    h, w = img.shape[:2]
    return np.array([[x0 * w, y0 * h], [x1 * w, y0 * h], [x1 * w, y1 * h], [x0 * w, y1 * h]], np.float32)


class _Detector:
    name = "fake_det"

    def detect(self, img):
        return [_quad(img, 0.1, 0.10, 0.7, 0.13), _quad(img, 0.1, 0.20, 0.6, 0.23)]

    def classify_180(self, crops):
        return [("0", 0.99)] * len(crops)


class _Recognizer:
    name = "fake_rec"

    def recognize(self, crops):
        return [("Xin chào quý khách", 0.95)] * len(crops)


class _Layout:
    name = "fake_layout"

    def __init__(self, fail=False):
        self.fail = fail

    def predict(self, rgb):
        if self.fail:
            raise RuntimeError("layout model crashed")
        h, w = rgb.shape[:2]
        return [LayoutRegion("text", 0.91, (0.08 * w, 0.08 * h, 0.75 * w, 0.25 * h))]


class _Models:
    def __init__(self, fail_layout=False):
        self.detector, self.recognizer, self.layout = _Detector(), _Recognizer(), _Layout(fail_layout)


def _png(w=800, h=1100) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.full((h, w, 3), 255, np.uint8)).save(buf, "PNG")
    return buf.getvalue()


def _run(tmp_path, data, name, models=None):
    events = []
    st = LocalStorage(tmp_path)
    doc = process_document(data, name, st, models, on_event=events.append)
    return doc, events, st


def _steps(events):
    return [(e["step"]["page"], e["step"]["step"], e["step"]["status"]) for e in events if e.get("current_stage") == "STEP"]


def _trace(st, doc, n=1):
    return json.loads(st.get_text(f"{doc.document_id}/pages/{n}_trace.json"))


def test_scanned_page_emits_plan_then_each_step_in_order(tmp_path):
    doc, events, st = _run(tmp_path, _png(), "scan.png", _Models())
    assert events[0]["current_stage"] == "PLAN"
    assert events[0]["plan"] == {"kind": "image", "total_pages": 1, "steps": list(SCAN_PLAN)}
    steps = _steps(events)
    assert steps[0] == (None, "ingest", "done")
    page_steps = [(s, status) for p, s, status in steps if p == 1]
    for name in ("preprocess", "layout", "tables", "ocr", "marks"):
        assert page_steps.index((name, "running")) < page_steps.index((name, "done"))
    assert [s for s, status in page_steps if status == "done"] == ["preprocess", "layout", "tables", "ocr", "marks"]
    assert (1, "vlm", "skipped") in steps
    assert steps[-1] == (None, "assemble", "done")


def test_scanned_page_trace_holds_each_steps_result(tmp_path):
    doc, _, st = _run(tmp_path, _png(), "scan.png", _Models())
    steps = _trace(st, doc)["steps"]
    assert list(steps) == list(PAGE_STEPS)
    assert steps["preprocess"]["summary"]["rotation"] == 0
    assert steps["layout"]["summary"]["regions"] == 1 and steps["layout"]["summary"]["text_boxes"] == 2
    region = steps["layout"]["regions"][0]
    assert region["label"] == "text" and all(0 <= v <= 1 for v in region["bbox"])
    assert steps["ocr"]["summary"]["lines"] == 2
    assert steps["ocr"]["lines"][0]["text"] == "Xin chào quý khách" and steps["ocr"]["lines"][0]["conf"] == 0.95
    assert steps["marks"]["summary"]["elements"] == len(doc.pages[0].elements)
    assert steps["vlm"]["status"] == "skipped" and steps["vlm"]["reason"]


def test_failing_step_is_marked_and_document_still_finishes(tmp_path):
    doc, events, st = _run(tmp_path, _png(), "scan.png", _Models(fail_layout=True))
    assert doc.pages[0].status.value == "FAILED"
    steps = _trace(st, doc)["steps"]
    assert steps["preprocess"]["status"] == "done"
    assert steps["layout"]["status"] == "failed" and "layout model crashed" in steps["layout"]["error"]
    assert all(steps[k]["status"] == "skipped" for k in ("tables", "ocr", "marks", "vlm"))
    assert (1, "layout", "failed") in _steps(events)
    assert _steps(events)[-1] == (None, "assemble", "done")


@pytest.mark.skipif(not FONT.exists(), reason="needs a TTF with Vietnamese glyphs")
def test_digital_pdf_skips_cleanup_and_ocr_but_shows_text_layer_lines(tmp_path):
    doc, events, st = _run(tmp_path, _pdf(LINES), "hd.pdf", _Models())
    steps = _trace(st, doc)["steps"]
    assert steps["preprocess"]["status"] == "skipped"
    assert steps["ocr"]["status"] == "skipped" and "lớp chữ" in steps["ocr"]["reason"]
    assert [ln["text"] for ln in steps["ocr"]["lines"]] == LINES and steps["ocr"]["lines"][0]["source"] == "text_layer"
    assert steps["layout"]["status"] == "done" and steps["marks"]["status"] == "done"


def test_office_document_has_three_document_level_steps_and_no_page_trace(tmp_path):
    d = docx.Document()
    d.add_paragraph("Bên vay")
    buf = io.BytesIO()
    d.save(buf)
    doc, events, st = _run(tmp_path, buf.getvalue(), "a.docx")
    assert events[0]["plan"]["steps"] == list(NATIVE_PLAN)
    assert _steps(events) == [(None, "ingest", "done"), (None, "parse", "running"), (None, "parse", "done"), (None, "assemble", "done")]
    assert not st.exists(f"{doc.document_id}/pages/1_trace.json")


def test_abort_skips_whatever_has_not_run():
    tr = PageTrace(1)
    with tr.step("preprocess"):
        pass
    tr.abort()
    steps = tr.to_dict()["steps"]
    assert steps["preprocess"]["status"] == "done"
    assert all(steps[k]["status"] == "skipped" for k in PAGE_STEPS[1:])


def test_vlm_diff_reports_changed_text_and_cells():
    para = Element(element_id="p", type=ElementType.PARAGRAPH, reading_order=0, text="S0 tiền")
    table = Element(element_id="t", type=ElementType.TABLE, reading_order=1, cells=[TableCell(row=0, col=0, text="1.2O0")])
    same = Element(element_id="s", type=ElementType.PARAGRAPH, reading_order=2, text="giữ nguyên")
    page = Page(page_number=1, width=10, height=10, elements=[para, table, same])
    before = snapshot_elements(page)
    para.text = "Số tiền"
    table.cells[0].text = "1.200"
    changes = diff_elements(before, page)
    assert {"element_id": "p", "before": "S0 tiền", "after": "Số tiền"} in changes
    assert {"element_id": "t", "cell": [0, 0], "before": "1.2O0", "after": "1.200"} in changes
    assert all(c["element_id"] != "s" for c in changes)
