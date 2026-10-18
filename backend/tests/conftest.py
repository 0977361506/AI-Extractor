from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "docs" / "examples"
MODELS_DIR = REPO_ROOT / "models"


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES_DIR


@pytest.fixture(scope="session")
def models_dir() -> Path:
    from idp.models_fetch import fetch_all

    try:
        fetch_all(MODELS_DIR)
    except Exception as exc:  # pragma: no cover - offline machine without cached models
        pytest.skip(f"models unavailable: {exc}")
    return MODELS_DIR


@pytest.fixture(scope="session")
def page_models(models_dir):
    from idp.pipeline.models import PageModels

    return PageModels.load(models_dir)


def render_example(name: str, page: int, dpi: int = 300):
    from idp.ingest.rasterize import iter_pdf_pages

    data = (EXAMPLES_DIR / name).read_bytes()
    for p in iter_pdf_pages(data, dpi=dpi):
        if p.page_number == page:
            return p.image
    raise ValueError(page)
