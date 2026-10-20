"""Per-page processing trace: step status, timing, summary and intermediate results for the stepper UI.

Each step change is emitted (``on_step``) and the trace is rewritten to ``pages/N_trace.json`` so a step's result
is viewable while later steps are still running. Recording is best effort: a failed write never breaks processing.
"""

from __future__ import annotations

import logging
import time
import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import orjson

log = logging.getLogger(__name__)

PAGE_STEPS = ("preprocess", "layout", "tables", "ocr", "marks", "vlm")
SCAN_PLAN = ("ingest", *PAGE_STEPS, "assemble")
NATIVE_PLAN = ("ingest", "parse", "assemble")

StepFn = Callable[[dict], None]


class _Step:
    def __init__(self, record: dict):
        self._record = record

    def summary(self, **kw) -> None:
        self._record.setdefault("summary", {}).update(kw)

    def data(self, **kw) -> None:
        self._record.update(kw)


class PageTrace:
    def __init__(self, page_number: int, storage=None, document_id: str | None = None, on_step: StepFn | None = None):
        self.page_number = page_number
        self.storage = storage
        self.document_id = document_id
        self.on_step = on_step
        self.width, self.height = 1, 1
        self.steps: dict[str, dict] = {name: {"status": "pending"} for name in PAGE_STEPS}

    def set_size(self, width: int, height: int) -> None:
        self.width, self.height = max(1, width), max(1, height)

    def norm(self, box) -> list[float]:
        x0, y0, x1, y1 = box
        w, h = self.width, self.height
        return [round(min(1.0, max(0.0, v)), 5) for v in (x0 / w, y0 / h, x1 / w, y1 / h)]

    @contextmanager
    def step(self, name: str) -> Iterator[_Step]:
        record = {"status": "running"}
        self.steps[name] = record
        self._changed(name)
        t0 = time.perf_counter()
        try:
            yield _Step(record)
        except Exception as exc:
            record.update(status="failed", ms=_ms(t0), error=f"{type(exc).__name__}: {exc}", trace=traceback.format_exc(limit=4))
            for later in PAGE_STEPS[PAGE_STEPS.index(name) + 1 :] if name in PAGE_STEPS else ():
                if self.steps[later]["status"] == "pending":
                    self.steps[later] = {"status": "skipped", "reason": "Bỏ qua do bước trước bị lỗi"}
            self._changed(name)
            raise
        record.update(status="done", ms=_ms(t0))
        self._changed(name)

    def skip(self, name: str, reason: str, **data) -> None:
        self.steps[name] = {"status": "skipped", "reason": reason, **data}
        self._changed(name)

    def abort(self, reason: str = "Bỏ qua do trang bị lỗi") -> None:
        """Page failed outside a step: whatever has not run will not run."""
        for name, rec in self.steps.items():
            if rec["status"] in ("pending", "running"):
                self.steps[name] = {"status": "skipped", "reason": reason}
                self._changed(name)

    def to_dict(self) -> dict:
        return {"page": self.page_number, "steps": self.steps}

    def flush(self) -> None:
        if self.storage is None or self.document_id is None:
            return
        try:
            self.storage.put_text(self.document_id, f"pages/{self.page_number}_trace.json", orjson.dumps(self.to_dict()).decode())
        except Exception:  # best effort: tracing must never fail a document
            log.warning("could not write trace for %s page %s", self.document_id, self.page_number, exc_info=True)

    def _changed(self, name: str) -> None:
        self.flush()
        if self.on_step is None:
            return
        rec = self.steps[name]
        ev = {"page": self.page_number, "step": name, "status": rec["status"]}
        for key in ("ms", "summary", "error", "reason"):
            if key in rec:
                ev[key] = rec[key]
        try:
            self.on_step(ev)
        except Exception:
            log.warning("step listener failed", exc_info=True)


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)
