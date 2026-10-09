"""Các bản GIẢ của dịch vụ bên ngoài để test chạy nhanh, không cần Internet."""

from app.core.exceptions import ExternalServiceError


class FakeTranslator:
    def __init__(self, fail_langs: set[str] | None = None):
        self.calls: list[tuple[str, str]] = []
        self.fail_langs = fail_langs or set()

    async def translate(self, text: str, *, target: str, source: str = "vi") -> str:
        self.calls.append((text, target))
        if target in self.fail_langs:
            raise ExternalServiceError("fake translate error", code="TRANSLATION_FAILED")
        if target == source:
            return text
        # Dịch từng dòng như dịch vụ thật (giữ nguyên số dòng)
        return "\n".join(f"[{target}] {line}" for line in text.split("\n"))


class FakeTTS:
    def __init__(self, fail: bool = False):
        self.calls = 0
        self.fail = fail

    async def synthesize(self, text: str, *, voice: str) -> bytes:
        self.calls += 1
        if self.fail:
            raise ExternalServiceError("fake tts error", code="TTS_FAILED")
        return b"ID3-fake-mp3-" + voice.encode()


class FakeLLM:
    def __init__(self, answer: str = "Câu trả lời từ AI", fail: bool = False):
        self.answer = answer
        self.fail = fail
        self.messages = None

    async def complete(self, messages, *, temperature: float = 0.3, max_tokens: int | None = None) -> str:
        self.messages = messages
        self.calls = getattr(self, "calls", 0) + 1
        if self.fail:
            raise ExternalServiceError("fake llm error", code="LLM_FAILED")
        return self.answer
