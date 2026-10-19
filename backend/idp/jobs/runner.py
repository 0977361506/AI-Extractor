"""Background job execution: one document per job, worker processes keep the ML models loaded."""

from __future__ import annotations

import traceback
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

_MODELS = None  # per worker process


def _models(settings):
    global _MODELS
    if _MODELS is None:
        from idp.pipeline.models import PageModels

        _MODELS = PageModels.load(settings=settings)
    return _MODELS


def run_job(document_id: str, job_id: str, filename: str, data_dir: str, db_path: str) -> str:
    """Process one stored upload; progress goes to SQLite (read by the SSE endpoint)."""
    from idp.core.config import Settings
    from idp.jobs.db import Database
    from idp.pipeline.document import process_document
    from idp.storage.local import LocalStorage
    from idp.vlm.client import VlmClient
    from idp.vlm.settings import SettingsStore

    settings = Settings(data_dir=Path(data_dir), db_path=Path(db_path))
    db = Database(Path(db_path))
    storage = LocalStorage(Path(data_dir))
    db.update_document(document_id, status="IN_PROGRESS", error=None)
    try:
        data = storage.get_bytes(f"{document_id}/raw/{filename}")
        vs = SettingsStore(db).load()
        vlm = VlmClient(vs, db=db) if vs.enabled and vs.base_url and vs.model else None
        done = {"n": 0}

        def emit(ev: dict) -> None:
            db.add_event(document_id, ev)

        def on_page(out) -> None:
            storage.put_text(document_id, f"pages/{out.page.page_number}.json", out.page.model_dump_json(exclude_none=True))
            done["n"] += 1
            db.update_document(document_id, done_pages=done["n"])

        doc = process_document(
            data,
            filename,
            storage,
            None if _is_office(data, filename) else _models(settings),
            settings,
            review_threshold=vs.ui_threshold,
            on_event=emit,
            document_id=document_id,
            job_id=job_id,
            on_page=on_page,
            vlm=vlm,
            vlm_settings=vs if vlm else None,
        )
        db.update_document(document_id, status=doc.status.value, done_pages=len(doc.pages), total_pages=doc.metadata.total_pages)
        return doc.status.value
    except Exception as exc:
        db.update_document(document_id, status="FAILED", error=f"{type(exc).__name__}: {exc}")
        db.add_event(
            document_id,
            {"job_id": job_id, "document_id": document_id, "status": "FAILED", "progress_percentage": 100, "current_stage": "FAILED",
             "message_vi": f"Lỗi xử lý: {exc}", "trace": traceback.format_exc(limit=5)},
        )
        return "FAILED"


def _is_office(data: bytes, filename: str) -> bool:
    from idp.ingest.detect import FileKind, detect_file_kind

    return detect_file_kind(data, filename) in (FileKind.DOCX, FileKind.PPTX, FileKind.XLSX, FileKind.HTML)


class JobRunner:
    def __init__(self, workers: int = 2, job_fn=run_job, threads: bool = False):
        self.job_fn = job_fn
        self.pool = ThreadPoolExecutor(workers) if threads else ProcessPoolExecutor(workers)

    def submit(self, **kwargs) -> Future:
        return self.pool.submit(self.job_fn, **kwargs)

    def shutdown(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)


class InlineRunner:
    """Runs jobs synchronously (tests)."""

    def __init__(self, job_fn=run_job):
        self.job_fn = job_fn

    def submit(self, **kwargs):
        return self.job_fn(**kwargs)

    def shutdown(self) -> None:
        pass
