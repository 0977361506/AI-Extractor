"""Split the offline bundle zip into git-friendly parts (< GitHub's 50 MB warning) under release/.

    backend\\.venv\\Scripts\\python packaging\\split_release.py dist\\AI-Extractor-win64-<commit>.zip

Writes release/<zip>.001, .002, ... + SHA256SUMS.txt + ghep.bat (joins the parts and checks the hash with
Windows' built-in certutil, so the target machine needs nothing installed). Old parts in release/ are removed.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
PART = 45 * 1024 * 1024

GHEP_BAT = r"""@echo off
rem Ghep cac phan thanh {zip} va kiem tra ma SHA256. Chay: bam dup ghep.bat
setlocal
cd /d "%~dp0"
if exist "{zip}" del "{zip}"
echo Dang ghep {n} phan thanh {zip} ...
copy /b {parts} "{zip}" >nul || goto :fail
echo Dang kiem tra ma SHA256 ...
for /f "delims=" %%h in ('certutil -hashfile "{zip}" SHA256 ^| findstr /v ":"') do (set "GOT=%%h" & goto :check)
:check
set "GOT=%GOT: =%"
if /i "%GOT%"=="{sha}" (
  echo OK - file {zip} nguyen ven. Giai nen file nay roi chay run.bat ^(xem README.md^).
  pause
  exit /b 0
)
echo LOI: ma SHA256 khong khop ^(%GOT%^). Tai lai cac phan .0xx roi chay lai ghep.bat.
:fail
pause
exit /b 1
"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(zip_path: Path) -> None:
    RELEASE.mkdir(exist_ok=True)
    for old in RELEASE.iterdir():
        if old.is_file():
            old.unlink()
    parts: list[Path] = []
    with open(zip_path, "rb") as src:
        while chunk := src.read(PART):
            part = RELEASE / f"{zip_path.name}.{len(parts) + 1:03d}"
            part.write_bytes(chunk)
            parts.append(part)
    zip_sha = sha256(zip_path)
    sums = [f"{zip_sha}  {zip_path.name}"] + [f"{sha256(p)}  {p.name}" for p in parts]
    (RELEASE / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="ascii")
    bat = GHEP_BAT.format(zip=zip_path.name, n=len(parts), sha=zip_sha, parts="+".join(f'"{p.name}"' for p in parts))
    (RELEASE / "ghep.bat").write_text(bat.replace("\n", "\r\n"), encoding="ascii")
    print(f"{len(parts)} parts of <= {PART // 2**20} MB in {RELEASE}; zip sha256 {zip_sha}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_file():
        sys.exit(__doc__)
    main(Path(sys.argv[1]).resolve())
