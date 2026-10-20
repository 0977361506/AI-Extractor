import json

import pytest

from idp.pipeline.trace import PAGE_STEPS, PageTrace
from idp.storage.local import LocalStorage


def _trace(tmp_path, events):
    st = LocalStorage(tmp_path)
    return PageTrace(2, storage=st, document_id="doc_x", on_step=events.append), st


def _saved(st):
    return json.loads(st.get_text("doc_x/pages/2_trace.json"))


def test_all_page_steps_start_pending_and_file_is_written(tmp_path):
    tr, st = _trace(tmp_path, [])
    tr.flush()
    saved = _saved(st)
    assert saved["page"] == 2
    assert list(saved["steps"]) == list(PAGE_STEPS)
    assert all(s["status"] == "pending" for s in saved["steps"].values())


def test_step_records_running_then_done_with_summary_data_and_timing(tmp_path):
    events = []
    tr, st = _trace(tmp_path, events)
    tr.set_size(200, 100)
    with tr.step("layout") as s:
        s.summary(regions=1)
        s.data(regions=[{"label": "table", "score": 0.9, "bbox": tr.norm((20, 10, 100, 50))}])
    assert [(e["step"], e["status"]) for e in events] == [("layout", "running"), ("layout", "done")]
    assert events[-1]["page"] == 2 and events[-1]["summary"] == {"regions": 1} and events[-1]["ms"] >= 0
    layout = _saved(st)["steps"]["layout"]
    assert layout["status"] == "done" and layout["summary"] == {"regions": 1}
    assert layout["regions"][0]["bbox"] == [0.1, 0.1, 0.5, 0.5]


def test_failure_marks_step_failed_and_later_steps_skipped_then_reraises(tmp_path):
    events = []
    tr, st = _trace(tmp_path, events)
    with tr.step("preprocess"):
        pass
    with pytest.raises(ZeroDivisionError):
        with tr.step("layout"):
            1 / 0
    steps = _saved(st)["steps"]
    assert steps["preprocess"]["status"] == "done"
    assert steps["layout"]["status"] == "failed" and "ZeroDivisionError" in steps["layout"]["error"]
    assert all(steps[k]["status"] == "skipped" for k in PAGE_STEPS[PAGE_STEPS.index("layout") + 1 :])
    assert events[-1]["status"] == "failed" and events[-1]["error"]


def test_skip_records_reason_and_data(tmp_path):
    events = []
    tr, st = _trace(tmp_path, events)
    tr.skip("ocr", "Đọc trực tiếp từ lớp chữ PDF", lines=[{"text": "a"}])
    ocr = _saved(st)["steps"]["ocr"]
    assert ocr["status"] == "skipped" and ocr["reason"].startswith("Đọc") and ocr["lines"] == [{"text": "a"}]
    assert events[-1]["status"] == "skipped"


def test_trace_write_errors_never_break_processing(tmp_path):
    class Broken:
        def put_text(self, *a, **k):
            raise OSError("disk full")

    events = []
    tr = PageTrace(1, storage=Broken(), document_id="d", on_step=events.append)
    with tr.step("layout") as s:
        s.summary(regions=0)
    assert events[-1]["status"] == "done"


def test_trace_without_storage_or_listener_is_a_noop_recorder():
    tr = PageTrace(1)
    with tr.step("tables") as s:
        s.summary(tables=0)
    assert tr.to_dict()["steps"]["tables"]["status"] == "done"
