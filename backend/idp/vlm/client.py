"""OpenAI-compatible VLM client for the MB LLM Gateway.

Structured output: ``json_schema`` (response_format) → ``guided_json`` (vLLM) → ``prompt_only`` (+ validation),
auto-detected and remembered. Exact SHA-256 cache, retries on invalid output, circuit breaker on outages.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time

import cv2
import httpx
import numpy as np
from pydantic import BaseModel, ValidationError

from idp.vlm.settings import VlmSettings

PROMPT_VERSION = "v1"
SYSTEM_PROMPT = (
    "Bạn là chuyên gia đọc hồ sơ ngân hàng Việt Nam (báo cáo tài chính, hợp đồng, biểu mẫu). "
    "Đọc chính xác từng ký tự, giữ nguyên dấu tiếng Việt, số liệu và định dạng số kiểu Việt Nam (15.250.000; (1.290)). "
    "Không bịa nội dung không có trong ảnh. Chỉ trả về JSON hợp lệ theo schema, không giải thích."
)


class VlmError(Exception):
    """The gateway answered but the output could not be used."""


class VlmUnavailable(VlmError):
    """The gateway could not be reached / refused the request."""


class _ModeRejected(Exception):
    pass


def encode_image(img: np.ndarray, max_side: int) -> str:
    h, w = img.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR) if img.ndim == 3 else img
    ok, buf = cv2.imencode(".png", bgr)
    if not ok:
        raise VlmError("cannot encode image")
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode()


def parse_json(content: str):
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in output")
    return json.loads(text[start : end + 1])


def build_http_client(settings: VlmSettings, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    headers = {"Content-Type": "application/json", **settings.headers}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"
    verify: bool | str = settings.ca_bundle if (settings.verify_ssl and settings.ca_bundle) else settings.verify_ssl
    kwargs = dict(base_url=settings.base_url.rstrip("/"), headers=headers, timeout=settings.timeout_s, verify=verify)
    if transport is not None:
        kwargs["transport"] = transport
    elif settings.proxy:
        kwargs["proxy"] = settings.proxy
    return httpx.Client(**kwargs)


def chat_body(settings: VlmSettings, prompt: str, image_url: str | None, schema: dict | None, mode: str | None, name: str = "result") -> dict:
    system = SYSTEM_PROMPT
    if schema is not None and mode == "prompt_only":
        system += "\nTrả về DUY NHẤT một đối tượng JSON đúng schema sau:\n" + json.dumps(schema, ensure_ascii=False)
    user = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_url}}] if image_url else prompt
    body: dict = {
        "model": settings.model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
    }
    if schema is not None and mode == "json_schema":
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": False}}
    elif schema is not None and mode == "guided_json":
        body["guided_json"] = schema
    return body


class VlmClient:
    def __init__(self, settings: VlmSettings, transport: httpx.BaseTransport | None = None, db=None, breaker_threshold: int = 3):
        self.settings = settings
        self.db = db
        self.breaker_threshold = breaker_threshold
        self._http = build_http_client(settings, transport)
        if settings.structured_output != "auto":
            self.mode: str | None = settings.structured_output
        else:
            self.mode = settings.detected_mode
        self.calls = 0
        self.cache_hits = 0
        self._consecutive_failures = 0
        self.breaker_open = False

    @property
    def model(self) -> str:
        return self.settings.model

    def _cache_key(self, prompt: str, schema: type[BaseModel], image_url: str | None) -> str:
        h = hashlib.sha256()
        for part in (PROMPT_VERSION, self.settings.model, schema.__name__, prompt, image_url or ""):
            h.update(part.encode("utf-8"))
            h.update(b"\x00")
        return h.hexdigest()

    def _unavailable(self, msg: str) -> VlmUnavailable:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.breaker_threshold:
            self.breaker_open = True
        return VlmUnavailable(msg)

    def ask(self, prompt: str, schema: type[BaseModel], image: np.ndarray | None = None) -> BaseModel:
        if self.breaker_open:
            raise VlmUnavailable("circuit breaker open: gateway failed repeatedly")
        image_url = encode_image(image, self.settings.max_image_side) if image is not None else None
        key = self._cache_key(prompt, schema, image_url)
        if self.db is not None:
            cached = self.db.cache_get(key)
            if cached is not None:
                self.cache_hits += 1
                return schema.model_validate(cached)
        modes = [self.mode] if self.mode else ["json_schema", "guided_json", "prompt_only"]
        for mode in modes:
            try:
                result = self._ask_mode(mode, prompt, schema, image_url)
            except _ModeRejected:
                continue
            self.mode = mode
            if self.db is not None:
                self.db.cache_put(key, result.model_dump(mode="json"))
            return result
        raise VlmError("gateway rejected every structured-output mode")

    def _ask_mode(self, mode: str, prompt: str, schema: type[BaseModel], image_url: str | None) -> BaseModel:
        schema_json = schema.model_json_schema()
        last_error = ""
        for attempt in range(1 + self.settings.retries):
            body = chat_body(self.settings, prompt, image_url, schema_json, mode, schema.__name__)
            try:
                self.calls += 1
                resp = self._http.post("/chat/completions", json=body)
            except httpx.HTTPError as exc:
                if attempt == self.settings.retries:
                    raise self._unavailable(f"{type(exc).__name__}: {exc}") from exc
                time.sleep(min(2.0, 0.2 * 2**attempt))
                continue
            if resp.status_code in (400, 422) and mode in ("json_schema", "guided_json") and self.settings.structured_output == "auto":
                raise _ModeRejected(resp.text[:200])
            if resp.status_code in (401, 403, 404):
                raise self._unavailable(f"HTTP {resp.status_code}: {resp.text[:200]}")
            if resp.status_code >= 400:
                if attempt == self.settings.retries:
                    raise self._unavailable(f"HTTP {resp.status_code}: {resp.text[:200]}")
                time.sleep(min(2.0, 0.2 * 2**attempt))
                continue
            self._consecutive_failures = 0
            try:
                content = resp.json()["choices"][0]["message"]["content"] or ""
                return schema.model_validate(parse_json(content))
            except (ValueError, KeyError, IndexError, ValidationError) as exc:
                last_error = str(exc)[:200]
                prompt = prompt + "\n\nLƯU Ý: lần trước kết quả không đúng schema JSON. Chỉ trả về JSON hợp lệ."
        raise VlmError(f"invalid output after {1 + self.settings.retries} attempts: {last_error}")
