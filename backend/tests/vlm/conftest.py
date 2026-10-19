import json

import httpx
import pytest

from idp.vlm.settings import VlmSettings


class FakeGateway:
    """Minimal OpenAI-compatible gateway for tests. ``chat(body)`` returns the assistant message content."""

    def __init__(self, chat=None, models=("qwen2.5-vl",), status=None, reject_modes=()):
        self.chat = chat or (lambda body: "OK")
        self.models = list(models)
        self.status = status
        self.reject_modes = set(reject_modes)
        self.requests: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.status:
            return httpx.Response(self.status, json={"error": {"message": "denied"}})
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": m} for m in self.models]})
        body = json.loads(request.content)
        self.requests.append(body)
        if "json_schema" in self.reject_modes and "response_format" in body:
            return httpx.Response(400, json={"error": {"message": "response_format not supported"}})
        if "guided_json" in self.reject_modes and "guided_json" in body:
            return httpx.Response(400, json={"error": {"message": "guided_json not supported"}})
        content = self.chat(body)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


@pytest.fixture
def settings():
    return VlmSettings(enabled=True, base_url="https://gw.test/v1", api_key="sk-test", model="qwen2.5-vl", retries=2)


def transport(gw):
    return httpx.MockTransport(gw)
