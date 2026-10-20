"""Whole-document processing: route by file kind, process pages, assemble, persist ast.json / doc.md / chunks."""

from __future__ import annotations

import time
import traceback
import uuid
from collections.abc import Callable

import orjson

from idp.assemble.chunker import build_chunks
from idp.assemble.hierarchy import assign_hierarchy
from idp.assemble.markdown import render_markdown
from idp.assemble.merge_tables import merge_cross_page_tables
from idp.core.ast import DocStatus, Document, DocumentMetadata, Page, PageStatus
from idp.core.config import Settings, get_settings
from idp.ingest.detect import MIME, FileKind, detect_file_kind
from idp.ingest.rasterize import image_page_count, iter_image_pages, iter_pdf_pages, pdf_page_count
from idp.pipeline.trace import NATIVE_PLAN, SCAN_PLAN, PageTrace

EventFn = Callable[[dict], None]

STEP_VI = {
    "ingest": "Nhận file",
    "parse": "Đọc cấu trúc",
    "preprocess": "Làm sạch ảnh",
    "layout": "Phân tích bố cục",
    "tables": "Dựng bảng",
    "ocr": "Đọc chữ",
    "marks": "Con dấu, chữ ký & ghép trang",
    "vlm": "AI chuyên sâu",
    "assemble": "Hoàn tất tài liệu",
}
_STATUS_VI = {"running": "đang chạy", "done": "xong", "skipped": "bỏ qua", "failed": "lỗi"}


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _event(doc_id: str, job_id: str, status: str, pct: int, stage: str, msg: str, page: int | None = None) -> dict:
    ev = {
        "job_id": job_id,
        "document_id": doc_id,
        "status": status,
        "progress_percentage": pct,
        "current_stage": stage,
        "message_vi": msg,
    }
    if page is not None:
        ev["completed_page_preview"] = {"page_number": page, "is_ready": True, "api_fetch_url": f"/api/v1/documents/{doc_id}/pages/{page}"}
    return ev


def _step_event(doc_id: str, job_id: str, pct: int, step: dict) -> dict:
    """Stepper update: ``step`` = {page, step, status, ms?, summary?, error?, reason?}; ``page`` None = whole document."""
    where = f"Trang {step['page']}: " if step.get("page") else ""
    msg = f"{where}{STEP_VI.get(step['step'], step['step'])} {_STATUS_VI.get(step['status'], step['status'])}"
    return {**_event(doc_id, job_id, "IN_PROGRESS", pct, "STEP", msg), "step": step}


def finalize_document(doc: Document, storage) -> Document:
    assign_hierarchy(doc)
    merge_cross_page_tables(doc)
    doc.chunks = build_chunks(doc)
    storage.put_text(doc.document_id, "ast.json", doc.to_json())
    storage.put_text(doc.document_id, "doc.md", render_markdown(doc))
    storage.put_text(
        doc.document_id,
        "chunks.jsonl",
        "\n".join(orjson.dumps(c.model_dump(mode="json", exclude_none=True)).decode() for c in doc.chunks) + "\n",
    )
    return doc


def _assemble(doc: Document, storage, emit_step: Callable[[dict], None]) -> None:
    t0 = time.perf_counter()
    finalize_document(doc, storage)
    elements = [e for p in doc.pages for e in p.elements]
    emit_step(
        {
            "page": None,
            "step": "assemble",
            "status": "done",
            "ms": int((time.perf_counter() - t0) * 1000),
            "summary": {
                "pages": len(doc.pages),
                "elements": len(elements),
                "needs_review": sum(e.needs_human_review for e in elements),
                "chunks": len(doc.chunks),
            },
        }
    )


def process_document(
    data: bytes,
    filename: str,
    storage,
    models=None,
    settings: Settings | None = None,
    review_threshold: float = 0.80,
    on_event: EventFn | None = None,
    document_id: str | None = None,
    job_id: str | None = None,
    pages: list[int] | None = None,
    on_page: Callable[[object], None] | None = None,
    vlm=None,
    vlm_settings=None,
) -> Document:
    """``vlm``: optional ``VlmClient``; routed regions are re-read by the MB LLM Gateway."""
    s = settings or get_settings()
    t0 = time.perf_counter()
    doc_id = document_id or new_id("doc")
    job_id = job_id or new_id("job")
    emit = on_event or (lambda ev: None)
    pct_now = {"v": 0}

    def emit_step(step: dict) -> None:
        emit(_step_event(doc_id, job_id, pct_now["v"], step))

    def ingest_done(total: int) -> None:
        emit_step({"page": None, "step": "ingest", "status": "done", "ms": int((time.perf_counter() - t0) * 1000),
                   "summary": {"kind": kind.value, "pages": total, "size_bytes": len(data)}})

    kind = detect_file_kind(data, filename)
    storage.put_bytes(doc_id, f"raw/{filename}", data)

    if kind in (FileKind.DOCX, FileKind.PPTX, FileKind.XLSX, FileKind.HTML):
        from idp.ingest.office import parse_office_with_previews

        emit({**_event(doc_id, job_id, "IN_PROGRESS", 1, "PLAN", "Bắt đầu đọc tài liệu"),
              "plan": {"kind": kind.value, "total_pages": None, "steps": list(NATIVE_PLAN)}})
        ingest_done(0)
        pct_now["v"] = 10
        emit({**_event(doc_id, job_id, "IN_PROGRESS", 10, "FAST_PARSE", "Đang đọc cấu trúc tài liệu Office/HTML...")})
        emit_step({"page": None, "step": "parse", "status": "running"})
        t_parse = time.perf_counter()
        doc, previews = parse_office_with_previews(data, filename, kind, doc_id, job_id)
        for n, html in previews.items():  # no page raster for these formats: the UI shows this instead
            storage.put_text(doc_id, f"pages/{n}_preview.html", html)
        emit_step({"page": None, "step": "parse", "status": "done", "ms": int((time.perf_counter() - t_parse) * 1000),
                   "summary": {"pages": len(doc.pages), "elements": sum(len(p.elements) for p in doc.pages)}})
        doc.metadata.processing_time_ms = int((time.perf_counter() - t0) * 1000)
        pct_now["v"] = 90
        _assemble(doc, storage, emit_step)
        emit(_event(doc_id, job_id, doc.status.value, 100, "DONE", "Hoàn tất", page=1))
        return doc
    if kind not in (FileKind.PDF, FileKind.IMAGE):
        raise ValueError(f"Định dạng không được hỗ trợ: {filename}")

    from idp.pipeline.page import process_page

    if models is None:
        from idp.pipeline.models import PageModels

        models = PageModels.load(settings=s)
    total = pdf_page_count(data) if kind == FileKind.PDF else image_page_count(data)
    emit({**_event(doc_id, job_id, "IN_PROGRESS", 1, "PLAN", f"Bắt đầu xử lý {total} trang..."),
          "plan": {"kind": kind.value, "total_pages": total, "steps": list(SCAN_PLAN)}})
    ingest_done(total)
    source = iter_pdf_pages(data, s.render_dpi) if kind == FileKind.PDF else iter_image_pages(data)
    wanted = set(pages) if pages else None
    doc_pages: list[Page] = []
    red_stamp = False
    charsets: set[str] = set()
    emit(_event(doc_id, job_id, "IN_PROGRESS", 1, "PREPROCESS", f"Bắt đầu xử lý {total} trang..."))
    for src in source:
        if wanted and src.page_number not in wanted:
            continue
        pct = int(100 * (len(doc_pages)) / max(1, len(wanted) if wanted else total))
        pct_now["v"] = pct
        emit(_event(doc_id, job_id, "IN_PROGRESS", pct, "LAYOUT_OCR", f"Đang xử lý trang {src.page_number}/{total}..."))
        trace = PageTrace(src.page_number, storage=storage, document_id=doc_id, on_step=emit_step)
        try:
            charsets.add(src.charset)
            out = process_page(src, models, storage, doc_id, s, review_threshold, trace=trace)
            if vlm is not None and vlm_settings is not None:
                from idp.pipeline.vlm_diff import diff_elements, snapshot_elements
                from idp.vlm.refine import refine_page

                emit(_event(doc_id, job_id, "IN_PROGRESS", pct, "VLM_REFINE", f"Đang dùng AI chuyên sâu đọc vùng khó trang {src.page_number}..."))
                with trace.step("vlm") as st:
                    before = snapshot_elements(out.page)
                    stats = refine_page(out.page, out.display, vlm, vlm_settings)
                    changes = diff_elements(before, out.page)
                    st.summary(**stats, changed=len(changes))
                    st.data(changes=changes)
            else:
                trace.skip("vlm", "Chưa bật AI chuyên sâu (LLM Gateway) trong Cài đặt")
            red_stamp |= out.has_red_stamp
            doc_pages.append(out.page)
            if on_page:
                on_page(out)
        except Exception as exc:  # isolate page failures
            trace.abort()
            doc_pages.append(
                Page(
                    page_number=src.page_number,
                    status=PageStatus.FAILED,
                    width=int(src.image.shape[1]),
                    height=int(src.image.shape[0]),
                    error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}",
                )
            )
        pct = int(100 * len(doc_pages) / max(1, len(wanted) if wanted else total))
        pct_now["v"] = min(pct, 99)
        emit(_event(doc_id, job_id, "IN_PROGRESS", min(pct, 99), "PAGE_DONE", f"Đã xong trang {src.page_number}", page=src.page_number))

    failed = sum(p.status == PageStatus.FAILED for p in doc_pages)
    status = DocStatus.COMPLETED if failed == 0 else DocStatus.FAILED if failed == len(doc_pages) else DocStatus.PARTIAL
    doc = Document(
        document_id=doc_id,
        job_id=job_id,
        status=status,
        metadata=DocumentMetadata(
            filename=filename,
            file_type=MIME[kind],
            total_pages=total,
            detected_charset=next((c for c in charsets if c != "UNICODE_NFC"), "UNICODE_NFC"),
            has_red_stamp=red_stamp,
            processing_time_ms=int((time.perf_counter() - t0) * 1000),
            vlm_invocations_count=vlm.calls if vlm is not None else 0,
            engine_versions={
                "layout": models.layout.name,
                "detector": models.detector.name,
                "recognizer": models.recognizer.name,
                **({"vlm": vlm.model} if vlm is not None else {}),
            },
        ),
        pages=doc_pages,
    )
    _assemble(doc, storage, emit_step)
    emit(_event(doc_id, job_id, status.value, 100, "DONE", "Hoàn tất xử lý tài liệu"))
    return doc
