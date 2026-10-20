"""Build a self-contained Windows bundle that runs on an air-gapped machine with nothing installed.

    backend\\.venv\\Scripts\\python packaging\\build_windows.py [--no-zip]

Layout of dist/AI-Extractor-win64/ (mirrors the repo, so idp's REPO_ROOT logic works unchanged):

    python/            official CPython embeddable build + every installed package (Lib/site-packages)
    backend/idp/       application source
    frontend/dist/     built web UI
    models/            Heron layout + VietOCR weights (RapidOCR ONNX models ship inside site-packages)
    data/              documents, SQLite (created empty)
    run.bat, idp.bat, .env.example, README.md, VERSION

Needs internet only on the build machine, once, to fetch the embeddable Python zip (cached in dist/cache/).
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
NAME = "AI-Extractor-win64"
OUT = DIST / NAME
VENV_SITE = ROOT / "backend" / ".venv" / "Lib" / "site-packages"
# Visual C++ runtime, deployed app-locally next to python.exe (allowed by the VC++ redistributable licence)
VC_RUNTIME = ["msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll", "vcomp140.dll"]
SKIP_SITE = ("__editable__", "idp-", "__pycache__")

RUN_BAT = r"""@echo off
rem AI-Extractor: start the API + web UI.  Usage: run.bat [--host 0.0.0.0] [--port 8000]
setlocal
cd /d "%~dp0"
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set HF_HUB_DISABLE_TELEMETRY=1
set PYTHONUTF8=1
set PYTHONDONTWRITEBYTECODE=1
echo AI-Extractor dang khoi dong... Mo trinh duyet tai http://127.0.0.1:8000 (Ctrl+C de dung)
"%~dp0python\python.exe" -m idp.cli serve %*
if errorlevel 1 pause
"""

IDP_BAT = r"""@echo off
rem AI-Extractor command line, e.g.  idp.bat process hoso.pdf --out ketqua   ^|   idp.bat vlm-test
setlocal
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set PYTHONUTF8=1
set PYTHONDONTWRITEBYTECODE=1
"%~dp0python\python.exe" -m idp.cli %*
"""

ENV_EXAMPLE = """# Copy to .env (same folder as run.bat) to override defaults. All keys are optional.
# IDP_DATA_DIR=D:\\AI-Extractor-data      # where uploads, results and the SQLite database live
# IDP_WORKERS=2                           # documents processed in parallel (each ~2-3 GB RAM)
# IDP_RENDER_DPI=300
# MB LLM Gateway (can also be set in the UI: Cai dat VLM)
# IDP_VLM_ENABLED=true
# IDP_VLM_BASE_URL=https://llm-gateway.example/v1
# IDP_VLM_API_KEY=...
# IDP_VLM_MODEL=...
"""


def log(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def check_inputs() -> None:
    must = {
        "dev venv site-packages (backend/.venv)": VENV_SITE,
        "Heron layout model (run: idp.cli fetch-models)": ROOT / "models" / "layout-heron" / "model.safetensors",
        "VietOCR weights (run: idp.cli fetch-models)": ROOT / "models" / "vietocr",
        "built web UI (run: npm run build in frontend/)": ROOT / "frontend" / "dist" / "index.html",
        "RapidOCR ONNX models (run the app once online)": VENV_SITE / "rapidocr" / "models",
    }
    missing = [f"  - {what}: {path}" for what, path in must.items() if not path.exists()]
    if missing:
        sys.exit("Missing inputs:\n" + "\n".join(missing))
    if not list((VENV_SITE / "rapidocr" / "models").glob("*.onnx")):
        sys.exit("RapidOCR has not downloaded its ONNX models yet: process one document online first.")


def embeddable_python() -> Path:
    ver = platform.python_version()
    cache = DIST / "cache" / f"python-{ver}-embed-amd64.zip"
    if not cache.exists():
        url = f"https://www.python.org/ftp/python/{ver}/python-{ver}-embed-amd64.zip"
        log(f"downloading {url}")
        cache.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, cache)
    return cache


def copy_tree(src: Path, dst: Path, skip=("__pycache__",)) -> None:
    shutil.copytree(src, dst, ignore=lambda d, names: [n for n in names if n.startswith(skip)], dirs_exist_ok=True)


def build() -> None:
    check_inputs()
    if OUT.exists():
        log(f"removing old {OUT}")
        shutil.rmtree(OUT)
    py = OUT / "python"
    py.mkdir(parents=True)

    log("unpacking embeddable Python")
    with zipfile.ZipFile(embeddable_python()) as z:
        z.extractall(py)
    pth = next(py.glob("python3*._pth"))
    stdlib_zip = next(py.glob("python3*.zip")).name
    # ._pth fixes sys.path (PYTHONPATH is ignored); "import site" turns on Lib\site-packages and its .pth files
    pth.write_text(f"{stdlib_zip}\n.\n..\\backend\nimport site\n", encoding="ascii")

    log("copying installed packages (~1.2 GB)")
    copy_tree(VENV_SITE, py / "Lib" / "site-packages", skip=SKIP_SITE)

    system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    for dll in VC_RUNTIME:
        if (system32 / dll).exists() and not (py / dll).exists():
            shutil.copy2(system32 / dll, py / dll)

    log("copying application, UI and models")
    copy_tree(ROOT / "backend" / "idp", OUT / "backend" / "idp")
    copy_tree(ROOT / "frontend" / "dist", OUT / "frontend" / "dist")
    copy_tree(ROOT / "models", OUT / "models")
    (OUT / "data").mkdir()

    (OUT / "run.bat").write_text(RUN_BAT.replace("\n", "\r\n"), encoding="ascii")
    (OUT / "idp.bat").write_text(IDP_BAT.replace("\n", "\r\n"), encoding="ascii")
    (OUT / ".env.example").write_text(ENV_EXAMPLE, encoding="utf-8")
    shutil.copy2(ROOT / "README.md", OUT / "README.md")
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or "dev"
    (OUT / "VERSION").write_text(f"{sha}\nPython {platform.python_version()}\n", encoding="ascii")

    smoke_test(py / "python.exe")
    log(f"bundle ready: {OUT}")


def clean_env() -> dict[str, str]:
    """No dev Python on PATH, no user caches, no network: what an air-gapped machine looks like to the bundle."""
    keep = {k: v for k, v in os.environ.items() if k.upper() in ("SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE")}
    sysroot = keep.get("SYSTEMROOT", r"C:\Windows")
    empty_home = str(DIST / "cache" / "empty-home")
    Path(empty_home).mkdir(parents=True, exist_ok=True)
    return {
        **keep,
        "PATH": rf"{sysroot}\System32;{sysroot}",
        "USERPROFILE": empty_home, "HOME": empty_home, "APPDATA": empty_home, "LOCALAPPDATA": empty_home,
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9", "NO_PROXY": "",
    }


def smoke_test(python: Path) -> None:
    log("smoke test: imports + model loading with a clean, offline environment")
    code = (
        "import sys, idp, torch, fastapi;"
        "from idp.pipeline.models import PageModels;"
        "from idp.core.config import get_settings;"
        "m = PageModels.load(settings=get_settings());"
        "assert 'site-packages' in torch.__file__ and str(sys.prefix) in torch.__file__, torch.__file__;"
        "print('ok', sys.version.split()[0], torch.__version__, m.layout.name, m.detector.name, m.recognizer.name)"
    )
    r = subprocess.run([str(python), "-c", code], cwd=OUT, env=clean_env(), capture_output=True, text=True, timeout=900)
    if r.returncode != 0 or "ok " not in r.stdout:
        sys.exit(f"smoke test failed:\n{r.stdout}\n{r.stderr}")
    log(r.stdout.strip().splitlines()[-1])


def make_zip() -> Path:
    version = (OUT / "VERSION").read_text(encoding="ascii").split()[0]
    target = DIST / f"{NAME}-{version}.zip"
    log(f"zipping to {target} (several minutes)")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(OUT.rglob("*")):
            if f.is_file():
                z.write(f, Path(NAME) / f.relative_to(OUT))
    log(f"zip ready: {target} ({target.stat().st_size / 1e9:.2f} GB)")
    return target


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-zip", action="store_true", help="only build the folder")
    args = ap.parse_args()
    if sys.platform != "win32":
        sys.exit("This builds the Windows bundle; run it on Windows.")
    build()
    if not args.no_zip:
        make_zip()
