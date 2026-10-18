"""Local-disk object storage. Keys look like ``{document_id}/{relpath}`` and are relative to ``root``."""

from __future__ import annotations

import shutil
from pathlib import Path

import cv2
import numpy as np


class LocalStorage:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError(f"key escapes storage root: {key!r}")
        return p

    def _target(self, document_id: str, relpath: str) -> tuple[str, Path]:
        key = f"{document_id}/{relpath}".replace("\\", "/")
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        return key, p

    def put_bytes(self, document_id: str, relpath: str, data: bytes) -> str:
        key, p = self._target(document_id, relpath)
        p.write_bytes(data)
        return key

    def put_text(self, document_id: str, relpath: str, text: str) -> str:
        return self.put_bytes(document_id, relpath, text.encode("utf-8"))

    def put_image(self, document_id: str, relpath: str, img: np.ndarray) -> str:
        """Store an RGB (HxWx3) or grayscale (HxW) uint8 image; format from extension."""
        key, p = self._target(document_id, relpath)
        bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR) if img.ndim == 3 else img
        ok, buf = cv2.imencode(p.suffix or ".png", bgr)
        if not ok:
            raise ValueError(f"cannot encode image as {p.suffix}")
        p.write_bytes(buf.tobytes())
        return key

    def get_bytes(self, key: str) -> bytes:
        return self.path(key).read_bytes()

    def get_text(self, key: str) -> str:
        return self.get_bytes(key).decode("utf-8")

    def get_image(self, key: str) -> np.ndarray:
        arr = np.frombuffer(self.get_bytes(key), np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"cannot decode image {key!r}")
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img.ndim == 3 else img

    def exists(self, key: str) -> bool:
        return self.path(key).exists()

    def delete_document(self, document_id: str) -> None:
        shutil.rmtree(self.path(document_id), ignore_errors=True)
