import json

from idp.vlm.connection_test import run_connection_test
from tests.vlm.conftest import FakeGateway, transport


def _smart_chat(body):
    if "response_format" in body or "guided_json" in body:
        return json.dumps({"answer": "OK", "number": 42})
    content = body["messages"][-1]["content"]
    if isinstance(content, list):
        return "Kiểm tra MB-OCR 2026: 15.250.000"
    return "OK"


def test_all_steps_pass_and_mode_detected(settings):
    settings.structured_output = "auto"
    result = run_connection_test(settings, transport=transport(FakeGateway(chat=_smart_chat)))
    names = [s["name"] for s in result["steps"]]
    assert names == ["network", "models", "chat", "vision", "structured", "summary"]
    assert result["ok"], result
    assert result["detected_mode"] == "json_schema"
    assert result["recommended_concurrency"] >= 1


def test_auth_failure_is_reported_with_hint(settings):
    result = run_connection_test(settings, transport=transport(FakeGateway(status=401)))
    models = next(s for s in result["steps"] if s["name"] == "models")
    assert not result["ok"] and not models["ok"]
    assert "401" in models["detail"] and models["hint"]


def test_missing_model_and_bad_vision_fail(settings):
    gw = FakeGateway(chat=lambda b: "tôi không thấy ảnh", models=["other-model"])
    result = run_connection_test(settings, transport=transport(gw))
    steps = {s["name"]: s for s in result["steps"]}
    assert not steps["models"]["ok"] and "qwen2.5-vl" in steps["models"]["detail"]
    assert not steps["vision"]["ok"]


def test_guided_json_detected_when_json_schema_rejected(settings):
    gw = FakeGateway(chat=_smart_chat, reject_modes={"json_schema"})
    result = run_connection_test(settings, transport=transport(gw))
    assert result["detected_mode"] == "guided_json"
