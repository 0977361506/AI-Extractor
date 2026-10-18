import io
import zipfile

import pytest

from idp.ingest.detect import FileKind, detect_file_kind


def _zip(names: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in names:
            z.writestr(n, "x")
    return buf.getvalue()


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        (b"%PDF-1.7\n...", FileKind.PDF),
        (b"\x89PNG\r\n\x1a\n....", FileKind.IMAGE),
        (b"\xff\xd8\xff\xe0....", FileKind.IMAGE),
        (b"II*\x00....", FileKind.IMAGE),
        (b"MM\x00*....", FileKind.IMAGE),
        (b"\xef\xbb\xbf  <!DOCTYPE html><html>", FileKind.HTML),
        (b"<html><body>x</body></html>", FileKind.HTML),
        (b"random bytes", FileKind.UNKNOWN),
    ],
)
def test_magic_bytes(data, kind):
    assert detect_file_kind(data, "whatever.bin") == kind


def test_office_zip_containers():
    assert detect_file_kind(_zip(["[Content_Types].xml", "word/document.xml"]), "a.docx") == FileKind.DOCX
    assert detect_file_kind(_zip(["[Content_Types].xml", "ppt/presentation.xml"]), "a.pptx") == FileKind.PPTX
    assert detect_file_kind(_zip(["[Content_Types].xml", "xl/workbook.xml"]), "a.xlsx") == FileKind.XLSX
    assert detect_file_kind(_zip(["foo.txt"]), "a.zip") == FileKind.UNKNOWN


def test_extension_is_not_trusted():
    assert detect_file_kind(b"%PDF-1.4", "evil.docx") == FileKind.PDF
