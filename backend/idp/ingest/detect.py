"""File-type detection from content (magic bytes) — the filename extension is never trusted."""

from __future__ import annotations

import io
import zipfile
from enum import StrEnum


class FileKind(StrEnum):
    PDF = "pdf"
    IMAGE = "image"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    HTML = "html"
    UNKNOWN = "unknown"


MIME = {
    FileKind.PDF: "application/pdf",
    FileKind.IMAGE: "image/*",
    FileKind.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    FileKind.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    FileKind.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    FileKind.HTML: "text/html",
    FileKind.UNKNOWN: "application/octet-stream",
}

_IMAGE_MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"II*\x00", b"MM\x00*", b"BM", b"RIFF")


def _office_kind(data: bytes) -> FileKind:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = z.namelist()
    except zipfile.BadZipFile:
        return FileKind.UNKNOWN
    if any(n.startswith("word/") for n in names):
        return FileKind.DOCX
    if any(n.startswith("ppt/") for n in names):
        return FileKind.PPTX
    if any(n.startswith("xl/") for n in names):
        return FileKind.XLSX
    return FileKind.UNKNOWN


def detect_file_kind(data: bytes, filename: str = "") -> FileKind:
    head = data[:1024]
    if head.startswith(b"%PDF"):
        return FileKind.PDF
    if head.startswith(_IMAGE_MAGIC):
        return FileKind.IMAGE
    if head.startswith(b"PK\x03\x04"):
        return _office_kind(data)
    text = head.lstrip(b"\xef\xbb\xbf").lstrip().lower()
    if text.startswith((b"<!doctype html", b"<html")) or (text.startswith(b"<") and b"<html" in text):
        return FileKind.HTML
    return FileKind.UNKNOWN
