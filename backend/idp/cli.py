"""Command line: ``idp process``, ``idp fetch-models``, ``idp eval``, ``idp serve``."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import typer

app = typer.Typer(add_completion=False, help="Banking IDP engine")


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


@app.command("fetch-models")
def fetch_models() -> None:
    """Tải/vendor model về thư mục models/ để chạy offline."""
    from idp.core.config import get_settings
    from idp.models_fetch import fetch_all

    for name, path in fetch_all(get_settings().models_dir).items():
        typer.echo(f"{name}: {path}")


@app.command()
def process(
    files: list[Path] = typer.Argument(..., exists=True, readable=True),
    out: Path = typer.Option(None, help="Thư mục kết quả (mặc định: data/)"),
    overlay: bool = typer.Option(True, help="Lưu ảnh overlay bbox để kiểm tra"),
    pages: str = typer.Option("", help="Chỉ xử lý các trang, vd '1,3'"),
) -> None:
    """Xử lý tài liệu → ast.json, doc.md, chunks.jsonl (+ overlay)."""
    _utf8_console()
    from idp.core.ast import PageStatus
    from idp.core.config import get_settings
    from idp.pipeline.document import process_document
    from idp.pipeline.models import PageModels
    from idp.storage.local import LocalStorage
    from idp.viz.overlay import draw_overlay

    settings = get_settings()
    storage = LocalStorage(out or settings.data_dir)
    models = PageModels.load(settings=settings)
    wanted = [int(p) for p in pages.split(",") if p.strip()] or None
    for f in files:
        t0 = time.perf_counter()
        doc_id = f.stem

        def save_overlay(output, doc_id=doc_id):
            if overlay:
                storage.put_image(doc_id, f"pages/{output.page.page_number}_overlay.jpg", draw_overlay(output.display, output.page))

        storage.delete_document(doc_id)
        doc = process_document(
            f.read_bytes(),
            f.name,
            storage,
            models,
            settings,
            document_id=doc_id,
            pages=wanted,
            on_page=save_overlay,
            on_event=lambda ev: typer.echo(f"  [{ev['progress_percentage']:3d}%] {ev['message_vi']}"),
        )
        n_el = sum(len(p.elements) for p in doc.pages)
        n_review = sum(e.needs_human_review for _, e in doc.iter_elements())
        failed = [p.page_number for p in doc.pages if p.status == PageStatus.FAILED]
        typer.echo(
            f"{f.name}: {doc.status.value} | {len(doc.pages)} trang | {n_el} phần tử | {n_review} cần duyệt | "
            f"{len(doc.chunks)} chunk | {time.perf_counter() - t0:.1f}s" + (f" | LỖI trang {failed}" if failed else "")
        )
        typer.echo(f"  → {storage.path(doc_id)}")


if __name__ == "__main__":
    app()
