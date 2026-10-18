"""Docling Heron layout model (RT-DETRv2) run directly through ``transformers``."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from idp.layout.regions import LayoutRegion


class HeronLayoutEngine:
    name = "docling_heron"

    def __init__(self, model_dir: Path, threshold: float = 0.4, num_threads: int = 4):
        import torch
        from transformers import AutoImageProcessor, AutoModelForObjectDetection

        torch.set_num_threads(num_threads)
        self._torch = torch
        self.threshold = threshold
        self.processor = AutoImageProcessor.from_pretrained(model_dir)
        self.model = AutoModelForObjectDetection.from_pretrained(model_dir).eval()
        self.id2label = self.model.config.id2label

    def predict(self, rgb: np.ndarray) -> list[LayoutRegion]:
        img = Image.fromarray(rgb)
        with self._torch.inference_mode():
            inputs = self.processor(images=img, return_tensors="pt")
            outputs = self.model(**inputs)
        res = self.processor.post_process_object_detection(
            outputs, target_sizes=[(img.height, img.width)], threshold=self.threshold
        )[0]
        regions = []
        for score, label, box in zip(res["scores"], res["labels"], res["boxes"]):
            x0, y0, x1, y1 = (float(v) for v in box.tolist())
            regions.append(
                LayoutRegion(
                    label=self.id2label[int(label)],
                    score=float(score),
                    bbox=(max(0.0, x0), max(0.0, y0), min(float(img.width), x1), min(float(img.height), y1)),
                )
            )
        return regions
