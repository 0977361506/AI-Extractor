from idp.jobs.db import Database
from idp.vlm.settings import SettingsStore, VlmSettings, mask_key


def test_mask_key():
    assert mask_key("sk-1234567890abcd") == "sk-****abcd"
    assert mask_key("") == ""
    assert mask_key("abc") == "****"


def test_defaults_and_roundtrip(tmp_path):
    store = SettingsStore(Database(tmp_path / "db.sqlite"))
    s = store.load()
    assert s.enabled is False and s.structured_output == "auto"
    s.base_url = "https://llm-gw.mb.local/v1"
    s.api_key = "sk-secret-0001"
    store.save(s)
    assert store.load().api_key == "sk-secret-0001"


def test_public_view_masks_key_and_update_keeps_masked_key(tmp_path):
    store = SettingsStore(Database(tmp_path / "db.sqlite"))
    store.save(VlmSettings(api_key="sk-secret-0001", model="qwen2.5-vl"))
    public = store.public()
    assert public["api_key"] == "sk-****0001"
    merged = store.merge({**public, "model": "qwen3-vl"})
    assert merged.api_key == "sk-secret-0001" and merged.model == "qwen3-vl"


def test_env_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("IDP_VLM_BASE_URL", "https://env/v1")
    monkeypatch.setenv("IDP_VLM_API_KEY", "envkey")
    store = SettingsStore(Database(tmp_path / "db.sqlite"))
    s = store.load()
    assert s.base_url == "https://env/v1" and s.api_key == "envkey"
