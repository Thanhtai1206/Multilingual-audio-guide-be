"""Test bộ dịch: gọi HTTP được giả lập bằng httpx.MockTransport (không cần Internet)."""

import httpx
import pytest

from app.core.exceptions import ExternalServiceError
from app.integrations.translator import (
    RATE_LIMITED,
    FallbackTranslator,
    GoogleApiTranslator,
    MyMemoryTranslator,
    chunk_lines,
)


class Provider:
    def __init__(self, name, *, result=None, error_code=None):
        self.name = name
        self.result = result
        self.error_code = error_code
        self.calls = 0

    async def translate(self, text, *, target, source="vi"):
        self.calls += 1
        if self.error_code:
            raise ExternalServiceError("lỗi", code=self.error_code)
        return f"{self.result}:{text}"


async def test_fallback_switches_and_rests_blocked_provider():
    google = Provider("google", error_code=RATE_LIMITED)
    backup = Provider("backup", result="ok")
    translator = FallbackTranslator([google, backup], min_interval=0)
    assert await translator.translate("Xin chào", target="ja") == "ok:Xin chào"
    assert await translator.translate("Tạm biệt", target="ja") == "ok:Tạm biệt"
    assert google.calls == 1  # bị chặn -> lần sau bỏ qua, không gọi tiếp


async def test_fallback_all_fail():
    translator = FallbackTranslator([Provider("a", error_code="TRANSLATION_FAILED")], min_interval=0)
    with pytest.raises(ExternalServiceError) as exc:
        await translator.translate("x", target="ja")
    assert "a: lỗi" in exc.value.message


async def test_same_language_returns_text():
    translator = FallbackTranslator([Provider("a", error_code="X")], min_interval=0)
    assert await translator.translate("abc", target="vi", source="vi") == "abc"


def test_chunk_lines_keeps_line_count():
    text = "\n".join(f"dòng {i}" for i in range(100))
    groups = chunk_lines(text, 60)
    assert all(len(g) <= 60 for g in groups)
    assert "\n".join(groups) == text


async def test_google_api_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["tl"] == "ja"
        return httpx.Response(200, json=[[["こんにちは", "Xin chào", None, None]], None, "vi"])

    translator = GoogleApiTranslator(transport=httpx.MockTransport(handler))
    assert await translator.translate("Xin chào", target="ja") == "こんにちは"


async def test_google_api_429_is_rate_limited():
    translator = GoogleApiTranslator(transport=httpx.MockTransport(lambda r: httpx.Response(429)))
    with pytest.raises(ExternalServiceError) as exc:
        await translator.translate("Xin chào", target="ja")
    assert exc.value.code == RATE_LIMITED


async def test_mymemory_keeps_lines_and_email():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.params)
        q = request.url.params["q"]
        translated = "\n".join(f"T({line})" for line in q.split("\n"))
        return httpx.Response(200, json={"responseStatus": 200, "responseData": {"translatedText": translated}})

    translator = MyMemoryTranslator(email="a@b.c", transport=httpx.MockTransport(handler))
    text = "\n".join(["Map", "Places", "Route"] * 60)  # > 450 ký tự -> nhiều request
    result = await translator.translate(text, target="ja", source="en")
    assert result.split("\n")[:3] == ["T(Map)", "T(Places)", "T(Route)"]
    assert len(result.split("\n")) == 180
    assert len(seen) > 1 and seen[0]["de"] == "a@b.c" and seen[0]["langpair"] == "en|ja"


async def test_mymemory_quota():
    def handler(request):
        return httpx.Response(200, json={"responseStatus": 429, "quotaFinished": True, "responseData": {}})

    translator = MyMemoryTranslator(transport=httpx.MockTransport(handler))
    with pytest.raises(ExternalServiceError) as exc:
        await translator.translate("Xin chào", target="ja")
    assert exc.value.code == RATE_LIMITED
