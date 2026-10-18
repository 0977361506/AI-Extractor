"""Illumination flattening and speckle removal for scanned pages."""

from __future__ import annotations

import cv2
import numpy as np


def normalize_illumination(img: np.ndarray, scale: int = 4, kernel: int = 9, blur: int = 21) -> np.ndarray:
    """Divide by an estimated background so shadows / uneven lighting become flat white."""
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(1, w // scale), max(1, h // scale)), interpolation=cv2.INTER_AREA)
    bg = cv2.dilate(small, cv2.getStructuringElement(cv2.MORPH_RECT, (kernel, kernel)))
    bg = cv2.medianBlur(bg, blur)
    bg = cv2.resize(bg, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    out = img.astype(np.float32) / np.maximum(bg, 1.0) * 255.0
    return np.clip(out, 0, 255).astype(np.uint8)


def remove_speckles(gray: np.ndarray, max_area: int = 30, keep_radius: int = 15, threshold: int = 140) -> np.ndarray:
    """Whiten tiny dark blobs that are far from any larger ink (keeps diacritics and punctuation)."""
    binary = (gray < threshold).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if n <= 1:
        return gray
    areas = stats[:, cv2.CC_STAT_AREA]
    small_ids = np.nonzero(areas <= max_area)[0]
    small_ids = small_ids[small_ids != 0]
    if small_ids.size == 0:
        return gray
    is_small = np.zeros(n, bool)
    is_small[small_ids] = True
    small_mask = is_small[labels] & (binary > 0)
    big_mask = (binary > 0) & ~small_mask
    k = 2 * keep_radius + 1
    near_big = cv2.dilate(big_mask.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) > 0
    keep_ids = np.unique(labels[small_mask & near_big])
    drop = is_small.copy()
    drop[keep_ids] = False
    out = gray.copy()
    out[drop[labels] & (binary > 0)] = 255
    return out


def remove_streaks(gray: np.ndarray, coverage: float = 0.9, max_width: int = 6, threshold: int = 215) -> np.ndarray:
    """Whiten thin scanner streaks / fold lines that run (almost) the full page height or width.

    Table rulings never span the whole page, so they survive.
    """
    h, w = gray.shape
    dark = (gray < threshold).astype(np.uint8)
    out = gray.copy()
    for axis, length in ((0, h), (1, w)):
        kernel = (1, int(length * coverage)) if axis == 0 else (int(length * coverage), 1)
        lines = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, kernel))
        if not lines.any():
            continue
        n, labels, stats, _ = cv2.connectedComponentsWithStats(lines, connectivity=8)
        for i in range(1, n):
            thickness = stats[i, cv2.CC_STAT_WIDTH] if axis == 0 else stats[i, cv2.CC_STAT_HEIGHT]
            if thickness <= max_width:
                band = labels == i
                band = cv2.dilate(band.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))) > 0
                # only whiten the streak itself, not dark text crossing it
                out[band & (gray >= 60)] = 255
    return out
