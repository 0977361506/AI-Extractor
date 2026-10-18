"""Heavy ML models for page processing, loaded once per worker process."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from idp.core.config import Settings, get_settings


@dataclass
class PageModels:
    detector: object
    recognizer: object
    layout: object

    @classmethod
    def load(cls, models_dir: Path | None = None, settings: Settings | None = None) -> "PageModels":
        from idp.layout.heron import HeronLayoutEngine
        from idp.models_fetch import fetch_all, heron_dir, vietocr_paths
        from idp.ocr.detector import RapidLineDetector
        from idp.ocr.recognizer import VietOcrRecognizer

        settings = settings or get_settings()
        models_dir = models_dir or settings.models_dir
        cfg_path, weights_path = vietocr_paths(models_dir, settings.vietocr_model)
        if not (cfg_path.exists() and weights_path.exists() and (heron_dir(models_dir) / "model.safetensors").exists()):
            fetch_all(models_dir)
        return cls(
            detector=RapidLineDetector(),
            recognizer=VietOcrRecognizer(cfg_path, weights_path, settings.ocr_batch_size, settings.torch_threads),
            layout=HeronLayoutEngine(heron_dir(models_dir), settings.layout_threshold, settings.torch_threads),
        )
