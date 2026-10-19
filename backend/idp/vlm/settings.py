"""Runtime-editable VLM gateway settings (SQLite-backed, env overrides, API key never leaves in clear)."""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field

StructuredMode = Literal["auto", "json_schema", "guided_json", "prompt_only"]


class VlmSettings(BaseModel):
    enabled: bool = False
    base_url: str = ""  # e.g. https://llm-gateway.mb.local/v1
    api_key: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    verify_ssl: bool = True
    ca_bundle: str = ""
    proxy: str = ""
    model: str = ""
    temperature: float = 0.0
    max_tokens: int = 2048
    structured_output: StructuredMode = "auto"
    detected_mode: str | None = None
    timeout_s: float = 60.0
    max_concurrency: int = 4
    retries: int = 2
    max_image_side: int = 1600
    vlm_threshold: float = 0.85  # VietOCR probabilities cluster at 0.85-0.91 for correct lines
    ui_threshold: float = 0.80
    always_types: list[str] = Field(default_factory=lambda: ["handwritten_note", "form_field", "signature", "stamp", "figure"])
    max_calls_per_page: int = 20


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) < 8:
        return "****"
    return f"{key[:3]}****{key[-4:]}"


_ENV = {
    "IDP_VLM_BASE_URL": "base_url",
    "IDP_VLM_API_KEY": "api_key",
    "IDP_VLM_MODEL": "model",
}


class SettingsStore:
    KEY = "vlm"

    def __init__(self, db):
        self.db = db

    def load(self) -> VlmSettings:
        data = self.db.get_setting(self.KEY, {}) or {}
        for env, field in _ENV.items():
            if os.environ.get(env):
                data[field] = os.environ[env]
        if os.environ.get("IDP_VLM_ENABLED"):
            data["enabled"] = os.environ["IDP_VLM_ENABLED"].lower() in {"1", "true", "yes"}
        return VlmSettings(**data)

    def save(self, settings: VlmSettings) -> None:
        self.db.set_setting(self.KEY, settings.model_dump())

    def public(self, settings: VlmSettings | None = None) -> dict:
        s = settings or self.load()
        data = s.model_dump()
        data["api_key"] = mask_key(s.api_key)
        data["api_key_set"] = bool(s.api_key)
        return data

    def merge(self, incoming: dict) -> VlmSettings:
        """Apply a (possibly partial) update from the UI; a masked/blank key keeps the stored one."""
        current = self.load()
        data = {k: v for k, v in incoming.items() if k in VlmSettings.model_fields}
        key = data.get("api_key")
        if key is None or key == mask_key(current.api_key) or (key == "" and incoming.get("keep_api_key", True)):
            data["api_key"] = current.api_key
        return VlmSettings(**{**current.model_dump(), **data})
