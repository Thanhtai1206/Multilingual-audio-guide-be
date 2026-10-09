"""Test client AI: cấu hình theo nhà cung cấp + gọi API (giả lập HTTP)."""

import json

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import ExternalServiceError
from app.integrations.llm import OpenAICompatibleClient, build_llm, resolve_llm_config


def make(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


@pytest.mark.parametrize(
    ("key", "provider", "model"),
    [
        ("AIzaSyFAKE", "gemini", "gemini-3.8-flash"),
        ("gsk_FAKE", "groq", "llama-3.3-70b-versatile"),
        ("sk-or-FAKE", "openrouter", "openai/gpt-4o-mini"),
        ("AQ.Ab8FAKE", "gemini", "gemini-3.8-flash"),  # key Google dạng mới
        ("unknown-format", "gemini", "gemini-3.8-flash"),
    ],
)
def test_auto_detect_provider_from_key(key, provider, model):
    assert resolve_llm_config(make(LLM_API_KEY=key))[0::3] == (provider, model)


def test_explicit_provider_and_key_cleanup():
    cfg = resolve_llm_config(make(LLM_API_KEY='  "AQ.xyz" ', LLM_PROVIDER="gemini"))
    assert cfg[:2] == ("gemini", "AQ.xyz")
    assert resolve_llm_config(make(LLM_API_KEY="whatever", LLM_PROVIDER="groq"))[0] == "groq"


def test_provider_name_written_in_llm_model_is_understood():
    """Ghi nhầm LLM_MODEL=gemini -> vẫn dùng Gemini với model mặc định (không gửi nhầm sang OpenRouter)."""
    cfg = resolve_llm_config(make(LLM_API_KEY="AQ.xyz", LLM_MODEL="gemini"))
    assert cfg[0] == "gemini" and cfg[3] == "gemini-3.8-flash"
    assert cfg[2].startswith("https://generativelanguage.googleapis.com")


def test_overrides_and_disabled():
    cfg = resolve_llm_config(make(LLM_API_KEY="AIzaX", LLM_MODEL="gemini-2.0-flash", LLM_BASE_URL="http://x/v1"))
    assert cfg == ("gemini", "AIzaX", "http://x/v1", "gemini-2.0-flash")
    assert resolve_llm_config(make()) is None
    assert resolve_llm_config(make(LLM_API_KEY="AIzaX", LLM_PROVIDER="none")) is None
    assert build_llm(make()) is None


def test_legacy_openrouter_settings_still_work():
    cfg = resolve_llm_config(make(OPENROUTER_API_KEY="old-key", OPENROUTER_MODEL="meta/llama:free"))
    assert cfg == ("openrouter", "old-key", "https://openrouter.ai/api/v1", "meta/llama:free")


async def test_client_sends_openai_format():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "  Xin chào!  "}}]})

    client = OpenAICompatibleClient(
        api_key="k", base_url="https://ai.test/v1/", model="m", transport=httpx.MockTransport(handler)
    )
    assert await client.complete([{"role": "user", "content": "hi"}], max_tokens=50) == "Xin chào!"
    assert seen["url"] == "https://ai.test/v1/chat/completions" and seen["auth"] == "Bearer k"
    assert seen["body"]["model"] == "m" and seen["body"]["max_tokens"] == 50


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(429), "LLM_RATE_LIMITED"),
        (httpx.Response(503), "LLM_BUSY"),
        (httpx.Response(200, json={"choices": [{"message": {"content": ""}}]}), "LLM_FAILED"),
        (httpx.Response(200, json={"error": "x"}), "LLM_FAILED"),
    ],
)
async def test_client_errors(response, code):
    client = OpenAICompatibleClient(
        api_key="k",
        base_url="https://ai.test/v1",
        model="m",
        transport=httpx.MockTransport(lambda r: response),
        retry_delays=(0, 0),
    )
    with pytest.raises(ExternalServiceError) as exc:
        await client.complete([{"role": "user", "content": "hi"}])
    assert exc.value.code == code


def test_pick_best_model_prefers_newest_stable_flash():
    from app.integrations.llm import pick_best_model

    ids = [
        "gemini-2.5-flash",
        "gemini-3.8-flash",
        "gemini-3.8-flash-preview-05",
        "gemini-3.8-flash-lite",
        "gemini-3.8-pro",
        "gemini-embedding-001",
        "gemini-3.8-flash-image",
    ]
    assert pick_best_model(ids, preferred="gemini-2.5-flash") == "gemini-3.8-flash"
    assert pick_best_model(ids, preferred="gemini-2.5-pro") == "gemini-3.8-pro"
    assert pick_best_model(["text-embedding-004"]) is None


async def test_model_removed_404_auto_switches_to_available_model():
    """Google gỡ model cũ (404) -> client tự lấy danh sách model, chuyển sang model mới và gọi lại."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            models = [{"id": "models/gemini-3.8-flash"}, {"id": "models/gemini-3.8-pro"}]
            return httpx.Response(200, json={"data": models})
        model = json.loads(request.content)["model"]
        seen.append(model)
        if model == "gemini-2.5-flash":
            return httpx.Response(404, json=[{"error": {"code": 404, "message": "no longer available"}}])
        return httpx.Response(200, json={"choices": [{"message": {"content": "Xin chào!"}}]})

    client = OpenAICompatibleClient(
        api_key="k", base_url="http://ai/v1", model="gemini-2.5-flash", transport=httpx.MockTransport(handler)
    )
    assert await client.complete([{"role": "user", "content": "hi"}]) == "Xin chào!"
    assert seen == ["gemini-2.5-flash", "gemini-3.8-flash"] and client.model == "gemini-3.8-flash"
    # các lần gọi sau dùng luôn model mới, không dò lại
    await client.complete([{"role": "user", "content": "hi"}])
    assert seen[-1] == "gemini-3.8-flash"


def _overloaded_server(busy_models: set[str], calls: list[str]):
    """Giả lập Google: các model trong busy_models luôn trả 503 (quá tải)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            ids = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.8-flash-lite", "gemini-embedding-001"]
            return httpx.Response(200, json={"data": [{"id": f"models/{m}"} for m in ids]})
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model in busy_models:
            return httpx.Response(503, json=[{"error": {"code": 503, "status": "UNAVAILABLE"}}])
        return httpx.Response(200, json={"choices": [{"message": {"content": f"trả lời bởi {model}"}}]})

    return httpx.MockTransport(handler)


async def test_overloaded_model_is_retried_then_backup_model_used():
    calls: list[str] = []
    client = OpenAICompatibleClient(
        api_key="k",
        base_url="http://ai/v1",
        model="gemini-3.8-flash",
        transport=_overloaded_server({"gemini-3.8-flash"}, calls),
        retry_delays=(0, 0),
    )
    assert await client.complete([{"role": "user", "content": "hi"}]) == "trả lời bởi gemini-3.5-flash"
    # thử model chính 3 lần (1 + 2 lần thử lại) rồi mới dùng model dự phòng cùng dòng "flash"
    assert calls == ["gemini-3.8-flash"] * 3 + ["gemini-3.5-flash"]
    assert client.model == "gemini-3.8-flash"  # model chính giữ nguyên, lần sau vẫn ưu tiên


async def test_temporary_overload_recovers_on_retry():
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = OpenAICompatibleClient(
        api_key="k", base_url="http://ai/v1", model="m", transport=httpx.MockTransport(handler), retry_delays=(0, 0)
    )
    assert await client.complete([{"role": "user", "content": "hi"}]) == "ok" and state["n"] == 2


async def test_all_models_overloaded_raises_busy():
    calls: list[str] = []
    busy = {"gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.8-flash-lite"}
    client = OpenAICompatibleClient(
        api_key="k",
        base_url="http://ai/v1",
        model="gemini-3.8-flash",
        transport=_overloaded_server(busy, calls),
        retry_delays=(0,),
    )
    with pytest.raises(ExternalServiceError) as exc:
        await client.complete([{"role": "user", "content": "hi"}])
    assert exc.value.code == "LLM_BUSY"
    assert len(calls) == 2 + 2  # 2 lần model chính + tối đa 2 model dự phòng


async def test_gemini_gets_low_reasoning_and_unsupported_option_is_dropped():
    from app.integrations.llm import provider_options

    assert provider_options("gemini") == {"reasoning_effort": "low"} and provider_options("groq") == {}
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if "reasoning_effort" in body:
            return httpx.Response(400, json={"error": {"message": "Unknown name reasoning_effort"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = OpenAICompatibleClient(
        api_key="k",
        base_url="http://ai/v1",
        model="m",
        transport=httpx.MockTransport(handler),
        extra_body={"reasoning_effort": "low"},
    )
    assert await client.complete([{"role": "user", "content": "hi"}]) == "ok"
    assert bodies[0]["reasoning_effort"] == "low" and "reasoning_effort" not in bodies[1]
    await client.complete([{"role": "user", "content": "hi"}])
    assert len(bodies) == 3  # lần sau không gửi tham số đó nữa


async def test_timeout_is_not_retried_and_reported():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=request)

    client = OpenAICompatibleClient(
        api_key="k", base_url="http://ai/v1", model="m", transport=httpx.MockTransport(handler), retry_delays=(0, 0)
    )
    with pytest.raises(ExternalServiceError) as exc:
        await client.complete([{"role": "user", "content": "hi"}])
    assert exc.value.code == "LLM_TIMEOUT" and len(calls) == 1