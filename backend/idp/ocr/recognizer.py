"""Vietnamese text-line recognition with VietOCR (local config + weights, CPU)."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image


class VietOcrRecognizer:
    def __init__(self, config_path: Path, weights_path: Path, batch_size: int = 16, num_threads: int = 4):
        import torch
        from vietocr.tool.config import Cfg
        from vietocr.tool.predictor import Predictor

        torch.set_num_threads(num_threads)
        cfg = Cfg.load_config_from_file(str(config_path))
        cfg["weights"] = str(weights_path)
        cfg["device"] = "cpu"
        cfg.setdefault("cnn", {})["pretrained"] = False
        cfg["predictor"]["beamsearch"] = False
        self.name = f"vietocr_{Path(config_path).stem}"
        self.batch_size = batch_size
        self._pred = Predictor(cfg)

    def recognize(self, crops: list[np.ndarray]) -> list[tuple[str, float]]:
        results: list[tuple[str, float]] = []
        images = [Image.fromarray(c).convert("RGB") for c in crops]
        for i in range(0, len(images), self.batch_size):
            batch = images[i : i + self.batch_size]
            texts, probs = self._pred.predict_batch(batch, return_prob=True)
            results.extend((unicodedata.normalize("NFC", t.strip()), float(p)) for t, p in zip(texts, probs))
        return results
