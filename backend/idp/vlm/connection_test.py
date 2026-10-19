"""Six-step gateway connection test: network → auth/models → chat → vision → structured output → summary."""

from __future__ import annotations

import socket
import ssl
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, ValidationError
from rapidfuzz import fuzz

from idp.vlm.client import build_http_client, chat_body, encode_image, parse_json
from idp.vlm.settings import VlmSettings

VISION_TEXT = "Kiểm tra MB-OCR 2026: 15.250.000"
_FONTS = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]


class _Probe(BaseModel):
    answer: str
    number: int


def vision_probe_image() -> np.ndarray:
    img = Image.new("RGB", (900, 120), "white")
    draw = ImageDraw.Draw(img)
    font = None
    for path in _FONTS:
        if Path(path).exists():
            font = ImageFont.truetype(path, 44)
            break
    draw.text((20, 30), VISION_TEXT, fill="black", font=font or ImageFont.load_default())
    return np.array(img)


def _step(name: str, ok: bool, t0: float, detail: str = "", hint: str = "") -> dict:
    return {"name": name, "ok": ok, "latency_ms": int((time.perf_counter() - t0) * 1000), "detail": detail, "hint": hint}


def _http_hint(status: int) -> str:
    return {
        401: "Sai hoặc thiếu API key — kiểm tra ô API key / header xác thực.",
        403: "Key không có quyền dùng gateway/model này — liên hệ quản trị LLM Gateway.",
        404: "Sai đường dẫn — base_url thường kết thúc bằng /v1.",
        429: "Bị giới hạn tần suất — giảm số request đồng thời.",
    }.get(status, "Gateway trả lỗi — xem chi tiết.")


def _network(settings: VlmSettings) -> dict:
    t0 = time.perf_counter()
    url = urlparse(settings.base_url)
    if not url.scheme or not url.hostname:
        return _step("network", False, t0, f"base_url không hợp lệ: {settings.base_url!r}", "Ví dụ: https://llm-gateway.mb.local/v1")
    port = url.port or (443 if url.scheme == "https" else 80)
    try:
        socket.getaddrinfo(url.hostname, port)
    except OSError as exc:
        return _step("network", False, t0, f"DNS lỗi: {exc}", "Kiểm tra tên miền / DNS nội bộ / proxy.")
    try:
        with socket.create_connection((url.hostname, port), timeout=min(10, settings.timeout_s)) as sock:
            if url.scheme == "https":
                ctx = ssl.create_default_context(cafile=settings.ca_bundle or None)
                if not settings.verify_ssl:
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                with ctx.wrap_socket(sock, server_hostname=url.hostname) as tls:
                    detail = f"TLS {tls.version()} tới {url.hostname}:{port}"
            else:
                detail = f"TCP tới {url.hostname}:{port}"
    except ssl.SSLCertVerificationError as exc:
        return _step("network", False, t0, f"Lỗi chứng chỉ: {exc}", "Gateway dùng CA nội bộ? Khai báo đường dẫn file CA bundle.")
    except OSError as exc:
        return _step("network", False, t0, f"Không kết nối được: {exc}", "Kiểm tra firewall / proxy / cổng.")
    return _step("network", True, t0, detail)


def run_connection_test(settings: VlmSettings, transport: httpx.BaseTransport | None = None) -> dict:
    steps: list[dict] = []
    if transport is not None:
        t0 = time.perf_counter()
        steps.append(_step("network", True, t0, "bỏ qua (transport giả lập)"))
    else:
        steps.append(_network(settings))
    client = build_http_client(settings, transport)

    # 2) auth + model list
    t0 = time.perf_counter()
    try:
        r = client.get("/models")
        if r.status_code != 200:
            steps.append(_step("models", False, t0, f"HTTP {r.status_code}: {r.text[:200]}", _http_hint(r.status_code)))
        else:
            ids = [m.get("id") for m in r.json().get("data", [])]
            if settings.model and ids and settings.model not in ids:
                steps.append(_step("models", False, t0, f"Model {settings.model!r} không có trong danh sách: {ids[:20]}", "Chọn model từ danh sách."))
            else:
                steps.append(_step("models", True, t0, f"{len(ids)} model: {ids[:20]}"))
    except httpx.HTTPError as exc:
        steps.append(_step("models", False, t0, f"{type(exc).__name__}: {exc}", "Không gọi được /models."))

    def chat(prompt: str, image=None, schema=None, mode=None):
        body = chat_body(settings, prompt, encode_image(image, settings.max_image_side) if image is not None else None, schema, mode, "probe")
        return client.post("/chat/completions", json=body)

    # 3) plain chat
    t0 = time.perf_counter()
    try:
        r = chat("Trả lời đúng một từ: OK")
        if r.status_code == 200 and r.json()["choices"][0]["message"]["content"]:
            steps.append(_step("chat", True, t0, r.json()["choices"][0]["message"]["content"][:80]))
        else:
            steps.append(_step("chat", False, t0, f"HTTP {r.status_code}: {r.text[:200]}", _http_hint(r.status_code)))
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        steps.append(_step("chat", False, t0, f"{type(exc).__name__}: {exc}"))

    # 4) vision: the model must read a known Vietnamese line from an image
    t0 = time.perf_counter()
    try:
        r = chat("Chép lại chính xác dòng chữ trong ảnh, chỉ trả về dòng chữ đó.", image=vision_probe_image())
        if r.status_code != 200:
            steps.append(_step("vision", False, t0, f"HTTP {r.status_code}: {r.text[:200]}", "Model có hỗ trợ ảnh (VLM) không?"))
        else:
            got = r.json()["choices"][0]["message"]["content"].strip()
            score = fuzz.ratio(got, VISION_TEXT)
            ok = "15.250.000" in got and score >= 80
            steps.append(
                _step("vision", ok, t0, f"Đọc được: {got[:120]!r} (giống {score:.0f}%)", "" if ok else "Model không đọc đúng ảnh / mất dấu tiếng Việt.")
            )
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        steps.append(_step("vision", False, t0, f"{type(exc).__name__}: {exc}"))

    # 5) structured output
    t0 = time.perf_counter()
    schema = _Probe.model_json_schema()
    candidates = ["json_schema", "guided_json", "prompt_only"] if settings.structured_output == "auto" else [settings.structured_output]
    detected, tried = None, []
    for mode in candidates:
        try:
            r = chat('Trả về answer="OK" và number=42.', schema=schema, mode=mode)
            if r.status_code == 200:
                _Probe.model_validate(parse_json(r.json()["choices"][0]["message"]["content"]))
                detected = mode
                break
            tried.append(f"{mode}: HTTP {r.status_code}")
        except (httpx.HTTPError, KeyError, IndexError, ValueError, ValidationError) as exc:
            tried.append(f"{mode}: {type(exc).__name__}")
    steps.append(
        _step(
            "structured",
            detected is not None,
            t0,
            f"Chế độ hỗ trợ: {detected}" + (f" (đã thử: {', '.join(tried)})" if tried else ""),
            "" if detected else "Gateway không trả JSON đúng schema ở mọi chế độ.",
        )
    )

    # 6) summary
    t0 = time.perf_counter()
    ok_steps = [s for s in steps if s["ok"] and s["name"] in ("chat", "vision", "structured")]
    avg_ms = sum(s["latency_ms"] for s in ok_steps) / len(ok_steps) if ok_steps else 0
    recommended = max(1, min(8, int(round(8000 / max(avg_ms, 500))))) if ok_steps else 1
    ok = all(s["ok"] for s in steps)
    steps.append(_step("summary", ok, t0, f"Độ trễ trung bình {avg_ms:.0f} ms; đề xuất {recommended} request đồng thời"))
    return {"ok": ok, "steps": steps, "detected_mode": detected, "recommended_concurrency": recommended}
