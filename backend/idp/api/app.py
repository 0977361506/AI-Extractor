"""FastAPI service: upload, progress (SSE), verification data, corrections, export, VLM settings."""

from __future__ import annotations

import asyncio
import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path, PurePath

import orjson
from fastapi import Body, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from idp.assemble.chunker import build_chunks
from idp.assemble.markdown import render_markdown
from idp.assemble.merge_tables import merge_cross_page_tables
from idp.core.ast import Document, Page
from idp.core.config import Settings, get_settings
from idp.ingest.detect import FileKind, detect_file_kind
from idp.jobs.corrections import CorrectionError, apply_corrections, apply_one, read_path
from idp.jobs.db import Database
from idp.jobs.runner import JobRunner
from idp.pipeline.document import new_id
from idp.storage.local import LocalStorage
from idp.vlm.settings import SettingsStore

FINAL = {"COMPLETED", "PARTIAL", "FAILED"}
_IMAGE_KINDS = {"display", "raw", "ocr", "overlay"}
# previews embed user-supplied markup: nothing may run, load or navigate (the UI frame is sandboxed too)
_PREVIEW_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'self'",
    "X-Content-Type-Options": "nosniff",
}


def create_app(settings: Settings | None = None, runner=None, vlm_transport=None) -> FastAPI:
    s = settings or get_settings()
    db = Database(s.database)
    storage = LocalStorage(s.data_dir)
    store = SettingsStore(db)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runner = runner or JobRunner(s.workers)
        # resume documents interrupted by a restart
        for row in db.list_documents():
            if row["status"] in ("PENDING", "IN_PROGRESS") and storage.exists(f"{row['document_id']}/raw/{row['filename']}"):
                _submit(app, row["document_id"], row["job_id"], row["filename"])
        yield
        app.state.runner.shutdown()

    app = FastAPI(title="Banking IDP Engine", version="0.1.0", lifespan=lifespan)

    def _submit(app_, document_id: str, job_id: str, filename: str) -> None:
        app_.state.runner.submit(document_id=document_id, job_id=job_id, filename=filename, data_dir=str(s.data_dir), db_path=str(s.database))

    def _row(document_id: str) -> dict:
        row = db.get_document(document_id)
        if row is None:
            raise HTTPException(404, "không tìm thấy tài liệu")
        return row

    def _load(document_id: str) -> Document | None:
        key = f"{document_id}/ast.json"
        if not storage.exists(key):
            return None
        doc = Document.model_validate_json(storage.get_text(key))
        return apply_corrections(doc, db.list_corrections(document_id))

    def _partial_pages(document_id: str) -> list[dict]:
        pages_dir = storage.path(f"{document_id}/pages")
        if not pages_dir.exists():
            return []
        files = sorted(pages_dir.glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0)
        return [json.loads(p.read_text(encoding="utf-8")) for p in files if p.stem.isdigit()]

    # documents ----------------------------------------------------------------
    @app.post("/api/v1/documents")
    async def upload(files: list[UploadFile] = File(...)):
        out = []
        for f in files:
            filename = PurePath(f.filename or "upload.bin").name
            head = await f.read(4096)
            await f.seek(0)
            if detect_file_kind(head + (await _peek_zip(f, head)), filename) == FileKind.UNKNOWN:
                out.append({"filename": filename, "error": "Định dạng không được hỗ trợ"})
                continue
            document_id, job_id = new_id("doc"), new_id("job")
            target = storage.path(f"{document_id}/raw/{filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "wb") as dst:  # streamed to disk: large files never sit in RAM
                shutil.copyfileobj(f.file, dst, length=1 << 20)
            db.create_document(document_id, job_id, filename)
            db.add_event(document_id, {"job_id": job_id, "document_id": document_id, "status": "PENDING", "progress_percentage": 0,
                                       "current_stage": "QUEUED", "message_vi": "Đã tiếp nhận, đang chờ xử lý"})
            out.append({"document_id": document_id, "job_id": job_id, "filename": filename, "status": "PENDING"})
            _submit(app, document_id, job_id, filename)
        return {"documents": out}

    async def _peek_zip(f: UploadFile, head: bytes) -> bytes:
        # office files are zip containers: the kind is in the central directory, so read the whole (small) file
        if not head.startswith(b"PK\x03\x04"):
            return b""
        data = await f.read()
        await f.seek(0)
        return data[len(head) :]

    @app.get("/api/v1/documents")
    def list_documents():
        return db.list_documents()

    @app.get("/api/v1/documents/{document_id}")
    def get_document(document_id: str):
        row = _row(document_id)
        doc = _load(document_id)
        return {**row, "ast": doc.model_dump(mode="json", exclude_none=True) if doc else None, "partial_pages": [] if doc else _partial_pages(document_id)}

    @app.delete("/api/v1/documents/{document_id}")
    def delete_document(document_id: str):
        _row(document_id)
        db.delete_document(document_id)
        storage.delete_document(document_id)
        return {"deleted": document_id}

    @app.get("/api/v1/documents/{document_id}/pages/{page_number}")
    def get_page(document_id: str, page_number: int):
        _row(document_id)
        doc = _load(document_id)
        if doc:
            for p in doc.pages:
                if p.page_number == page_number:
                    return p.model_dump(mode="json", exclude_none=True)
        key = f"{document_id}/pages/{page_number}.json"
        if storage.exists(key):
            return json.loads(storage.get_text(key))
        raise HTTPException(404, "trang chưa sẵn sàng")

    @app.get("/api/v1/documents/{document_id}/pages/{page_number}/image")
    def get_page_image(document_id: str, page_number: int, kind: str = "display"):
        if kind not in _IMAGE_KINDS:
            raise HTTPException(400, "kind không hợp lệ")
        _row(document_id)
        for ext in ("jpg", "png"):
            key = f"{document_id}/pages/{page_number}_{kind}.{ext}"
            if storage.exists(key):
                return FileResponse(storage.path(key), media_type=f"image/{'jpeg' if ext == 'jpg' else 'png'}")
        raise HTTPException(404, "không có ảnh")

    @app.get("/api/v1/documents/{document_id}/pages/{page_number}/trace")
    def get_page_trace(document_id: str, page_number: int):
        """Per-step intermediate results of a page (rewritten after every step, so it may be partial)."""
        _row(document_id)
        key = f"{document_id}/pages/{page_number}_trace.json"
        if not storage.exists(key):
            raise HTTPException(404, "trang chưa có dữ liệu từng bước")
        return Response(storage.get_text(key), media_type="application/json", headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/documents/{document_id}/pages/{page_number}/preview")
    def get_page_preview(document_id: str, page_number: int):
        """HTML rendering of the original Office/HTML file (these formats have no page image)."""
        row = _row(document_id)
        key = f"{document_id}/pages/{page_number}_preview.html"
        if not storage.exists(key):
            _backfill_previews(document_id, row["filename"])
        if not storage.exists(key):
            raise HTTPException(404, "không có bản xem trước")
        return Response(storage.get_text(key), media_type="text/html; charset=utf-8", headers=_PREVIEW_HEADERS)

    def _backfill_previews(document_id: str, filename: str) -> None:
        """Documents processed before previews existed: re-render from the stored upload."""
        raw = f"{document_id}/raw/{filename}"
        if not storage.exists(raw):
            return
        data = storage.get_bytes(raw)
        kind = detect_file_kind(data, filename)
        if kind not in (FileKind.DOCX, FileKind.PPTX, FileKind.XLSX, FileKind.HTML):
            return
        from idp.ingest.office import parse_office_with_previews

        _, previews = parse_office_with_previews(data, filename, kind, document_id, "")
        for n, html in previews.items():
            storage.put_text(document_id, f"pages/{n}_preview.html", html)

    @app.get("/api/v1/documents/{document_id}/events")
    async def events(document_id: str, request: Request):
        _row(document_id)
        last = int(request.headers.get("last-event-id") or request.query_params.get("last_event_id") or 0)

        async def gen():
            nonlocal last
            while True:
                batch = db.events_after(document_id, last)
                for ev in batch:
                    last = ev["event_id"]
                    yield {"id": str(last), "event": "progress", "data": json.dumps(ev, ensure_ascii=False)}
                row = db.get_document(document_id)
                if row is None or (row["status"] in FINAL and not batch):
                    yield {"event": "end", "data": json.dumps({"status": row["status"] if row else "DELETED"})}
                    return
                if await request.is_disconnected():
                    return
                await asyncio.sleep(0.15)

        return EventSourceResponse(gen())

    # corrections / export ------------------------------------------------------
    @app.post("/api/v1/documents/{document_id}/corrections")
    def add_correction(document_id: str, payload: dict = Body(...)):
        _row(document_id)
        doc = _load(document_id)
        if doc is None:
            raise HTTPException(409, "tài liệu chưa xử lý xong")
        element_id, path, value = payload.get("element_id"), payload.get("path"), payload.get("value")
        try:
            old = read_path(doc, element_id, path)
            apply_one(doc, element_id, path, value)
        except CorrectionError as exc:
            raise HTTPException(400, str(exc)) from exc
        cid = db.add_correction(document_id, element_id, path, old, value, payload.get("editor") or s.editor_name)
        element = next(e for _, e in doc.iter_elements() if e.element_id == element_id)
        return {"correction_id": cid, "element": element.model_dump(mode="json", exclude_none=True)}

    @app.get("/api/v1/documents/{document_id}/corrections")
    def list_corrections(document_id: str):
        _row(document_id)
        return db.list_corrections(document_id)

    def _export_doc(document_id: str) -> Document:
        _row(document_id)
        doc = _load(document_id)
        if doc is None:
            raise HTTPException(409, "tài liệu chưa xử lý xong")
        merge_cross_page_tables(doc)
        doc.chunks = build_chunks(doc)
        return doc

    @app.get("/api/v1/documents/{document_id}/export")
    def export(document_id: str, format: str = "json"):
        doc = _export_doc(document_id)
        stem = PurePath(doc.metadata.filename).stem
        if format == "md":
            return PlainTextResponse(render_markdown(doc), media_type="text/markdown; charset=utf-8",
                                     headers={"Content-Disposition": f'attachment; filename="{stem}.md"'})
        if format == "jsonl":
            body = "\n".join(orjson.dumps(c.model_dump(mode="json", exclude_none=True)).decode() for c in doc.chunks) + "\n"
            return PlainTextResponse(body, media_type="application/x-ndjson; charset=utf-8",
                                     headers={"Content-Disposition": f'attachment; filename="{stem}.chunks.jsonl"'})
        return Response(doc.to_json(), media_type="application/json; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{stem}.json"'})

    @app.post("/api/v1/documents/{document_id}/ground-truth")
    def save_ground_truth(document_id: str):
        doc = _export_doc(document_id)
        target = Path(s.gt_dir) / PurePath(doc.metadata.filename).stem / "ast.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(doc.to_json(), encoding="utf-8")
        return {"path": str(target)}

    # VLM settings ----------------------------------------------------------------
    @app.get("/api/v1/settings/vlm")
    def get_vlm_settings():
        return store.public()

    @app.put("/api/v1/settings/vlm")
    def put_vlm_settings(payload: dict = Body(...)):
        merged = store.merge(payload)
        store.save(merged)
        return store.public(merged)

    @app.post("/api/v1/settings/vlm/test")
    def test_vlm(payload: dict | None = Body(None)):
        from idp.vlm.connection_test import run_connection_test

        candidate = store.merge(payload or {})
        result = run_connection_test(candidate, transport=vlm_transport)
        db.add_connection_test(result)
        return result

    @app.get("/api/v1/settings/vlm/tests")
    def vlm_test_history():
        return db.list_connection_tests()

    @app.get("/api/v1/settings/vlm/models")
    def vlm_models():
        from idp.vlm.client import build_http_client

        try:
            r = build_http_client(store.load(), vlm_transport).get("/models")
            r.raise_for_status()
            return [m.get("id") for m in r.json().get("data", [])]
        except Exception as exc:
            raise HTTPException(502, f"không lấy được danh sách model: {exc}") from exc

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    @app.exception_handler(CorrectionError)
    async def _correction_error(_, exc: CorrectionError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    if Path(s.frontend_dir).is_dir():
        app.mount("/", StaticFiles(directory=s.frontend_dir, html=True), name="ui")
    return app


__all__ = ["Page", "create_app"]
