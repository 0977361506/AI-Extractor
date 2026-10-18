from pathlib import Path

from idp.core.config import Settings


def test_defaults_point_inside_repo(monkeypatch):
    s = Settings()
    assert s.data_dir.name == "data"
    assert s.models_dir.name == "models"
    assert s.render_dpi == 300


def test_env_override(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("IDP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("IDP_RENDER_DPI", "200")
    s = Settings()
    assert s.data_dir == tmp_path
    assert s.render_dpi == 200
