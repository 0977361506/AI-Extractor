from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "docs" / "examples"


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES_DIR
