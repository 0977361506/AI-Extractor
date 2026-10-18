"""Download / vendor model artefacts into ``models/`` so the engine runs offline (air-gapped)."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import requests

HERON_REPO = "docling-project/docling-layout-heron"


def heron_dir(models_dir: Path) -> Path:
    return models_dir / "layout-heron"


def vietocr_paths(models_dir: Path, name: str) -> tuple[Path, Path]:
    d = models_dir / "vietocr"
    return d / f"{name}.yml", d / f"{name}.pth"


def fetch_heron(models_dir: Path) -> Path:
    from huggingface_hub import snapshot_download

    target = heron_dir(models_dir)
    if (target / "model.safetensors").exists():
        return target
    snapshot_download(repo_id=HERON_REPO, local_dir=target)
    return target


def fetch_vietocr(models_dir: Path, name: str = "vgg_seq2seq") -> tuple[Path, Path]:
    from vietocr.tool.config import Cfg

    cfg_path, weights_path = vietocr_paths(models_dir, name)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    if cfg_path.exists() and weights_path.exists():
        return cfg_path, weights_path
    cfg = Cfg.load_config_from_name(name)
    url = cfg["weights"]
    cached = Path(tempfile.gettempdir()) / Path(url).name
    if cached.exists() and cached.stat().st_size > 1_000_000:
        shutil.copyfile(cached, weights_path)
    else:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(weights_path, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    cfg["weights"] = weights_path.name
    cfg["device"] = "cpu"
    cfg.setdefault("cnn", {})["pretrained"] = False
    cfg.save(str(cfg_path))
    return cfg_path, weights_path


def fetch_all(models_dir: Path) -> dict[str, Path]:
    cfg, weights = fetch_vietocr(models_dir)
    return {"heron": fetch_heron(models_dir), "vietocr_cfg": cfg, "vietocr_weights": weights}
