"""Static engine settings (paths, image resolution, model choices). Overridable via ``IDP_*`` env vars.

Runtime-editable settings (VLM connection, routing thresholds) live in SQLite — see ``idp.vlm.settings``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IDP_", env_file=REPO_ROOT / ".env", extra="ignore")

    data_dir: Path = REPO_ROOT / "data"
    models_dir: Path = REPO_ROOT / "models"
    db_path: Path | None = None

    render_dpi: int = 300
    analysis_long_side: int = 1600  # downscaled size for orientation / skew analysis

    layout_threshold: float = 0.4
    vietocr_model: str = "vgg_seq2seq"
    ocr_batch_size: int = 16
    torch_threads: int = 4
    workers: int = 2

    editor_name: str = "rm.local"

    @property
    def database(self) -> Path:
        return self.db_path or self.data_dir / "idp.sqlite"


@lru_cache
def get_settings() -> Settings:
    return Settings()
