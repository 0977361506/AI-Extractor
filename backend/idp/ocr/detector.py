"""Text-line detection (PP-OCR DB detector via RapidOCR / ONNX Runtime) + 0/180 line classifier."""

from __future__ import annotations

import cv2
import numpy as np


def _to_bgr(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


class RapidLineDetector:
    name = "rapidocr_ppocr_det"

    def __init__(self):
        from rapidocr import RapidOCR

        self._eng = RapidOCR()

    def detect(self, img: np.ndarray) -> list[np.ndarray]:
        # Always pass all three flags: RapidOCR keeps the flags of the previous call otherwise.
        out = self._eng(_to_bgr(img), use_det=True, use_cls=False, use_rec=False)
        boxes = getattr(out, "boxes", None)
        if boxes is None:
            return []
        return [np.asarray(b, dtype=np.float32) for b in boxes]

    def classify_180(self, crops: list[np.ndarray]) -> list[tuple[str, float]]:
        votes = []
        for c in crops:
            out = self._eng(_to_bgr(c), use_det=False, use_cls=True, use_rec=False)
            res = getattr(out, "cls_res", None)
            votes.append((str(res[0][0]), float(res[0][1])) if res else ("0", 0.0))
        return votes
