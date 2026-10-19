import json

import numpy as np
import pytest
from pydantic import BaseModel

from idp.vlm.client import VlmClient, VlmError, VlmUnavailable
from tests.vlm.conftest import FakeGateway, transport


class Answer(BaseModel):
    text: str
    confidence: float


IMG = np.full((40, 120, 3), 255, np.uint8)


def test_json_schema_mode_sends_response_format_and_image(settings):
    gw = FakeGateway(chat=lambda b: json.dumps({"text": "Hà Nội", "confidence": 0.9}))
    settings.structured_output = "json_schema"
    client = VlmClient(settings, transport=transport(gw))
    out = client.ask("Đọc chữ", Answer, image=IMG)
    assert out == Answer(text="Hà Nội", confidence=0.9)
    body = gw.requests[0]
    assert body["response_format"]["type"] == "json_schema"
    content = body["messages"][-1]["content"]
    assert any(p["type"] == "image_url" and p["image_url"]["url"].startswith("data:image/png;base64,") for p in content)


def test_auto_mode_falls_back_to_guided_json_then_remembers(settings):
    gw = FakeGateway(chat=lambda b: json.dumps({"text": "x", "confidence": 1}), reject_modes={"json_schema"})
    client = VlmClient(settings, transport=transport(gw))
    client.ask("p", Answer)
    assert client.mode == "guided_json"
    client.ask("p", Answer)
    assert "response_format" not in gw.requests[-1] and "guided_json" in gw.requests[-1]


def test_prompt_only_parses_fenced_json(settings):
    settings.structured_output = "prompt_only"
    gw = FakeGateway(chat=lambda b: 'Kết quả:\n```json\n{"text": "OK", "confidence": 0.7}\n```')
    out = VlmClient(settings, transport=transport(gw)).ask("p", Answer)
    assert out.text == "OK"
    assert "JSON" in gw.requests[0]["messages"][0]["content"]


def test_invalid_output_retries_then_raises(settings):
    settings.structured_output = "json_schema"
    gw = FakeGateway(chat=lambda b: "not json")
    client = VlmClient(settings, transport=transport(gw))
    with pytest.raises(VlmError):
        client.ask("p", Answer)
    assert len(gw.requests) == 3  # 1 + 2 retries


def test_cache_hit_skips_gateway(settings, tmp_path):
    from idp.jobs.db import Database

    settings.structured_output = "json_schema"
    gw = FakeGateway(chat=lambda b: json.dumps({"text": "x", "confidence": 1}))
    client = VlmClient(settings, transport=transport(gw), db=Database(tmp_path / "c.sqlite"))
    client.ask("p", Answer, image=IMG)
    client.ask("p", Answer, image=IMG)
    assert len(gw.requests) == 1
    assert client.calls == 1 and client.cache_hits == 1


def test_circuit_breaker_opens_after_failures(settings):
    settings.structured_output = "json_schema"
    settings.retries = 0
    gw = FakeGateway(status=503)
    client = VlmClient(settings, transport=transport(gw), breaker_threshold=2)
    for _ in range(2):
        with pytest.raises(VlmUnavailable):
            client.ask("p", Answer)
    with pytest.raises(VlmUnavailable):
        client.ask("p", Answer)
    assert client.breaker_open
