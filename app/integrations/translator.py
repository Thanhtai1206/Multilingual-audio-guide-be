"""
Dịch máy - thuộc lớp Data Access (nguồn dữ liệu bên ngoài).

Service chỉ biết tới "giao diện" Translator (có hàm translate). Muốn đổi sang
DeepL/Azure chỉ cần viết thêm 1 class, không phải sửa Service. Trong test dùng bản giả.

Các dịch vụ MIỄN PHÍ đều giới hạn số lần gọi; gọi dồn dập sẽ bị chặn tạm thời
(lỗi 429 "Too Many Requests"). Vì vậy dùng FallbackTranslator:
  - Giãn nhịp: mỗi dịch vụ chỉ nhận 1 yêu cầu mỗi ~0.6 giây.
  - Dịch vụ báo bị chặn -> "nghỉ" dịch vụ đó 10 phút, tự chuyển sang dịch vụ kế tiếp.
  - Thứ tự: Google (deep-translator) -> Google API (translate.googleapis.com) -> MyMemory.
"""

import asyncio
import logging
import time
from typing import Protocol

import httpx

from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

MAX_CHARS_PER_REQUEST = 4500  # Google giới hạn ~5000 ký tự / lần
RATE_LIMITED = "TRANSLATION_RATE_LIMITED"


class Translator(Protocol):
    async def translate(self, text: str, *, target: str, source: str = "vi") -> str: ...


def split_text(text: str, limit: int = MAX_CHARS_PER_REQUEST) -> list[str]:
    """Cắt văn bản dài theo đoạn/câu để không vượt giới hạn của dịch vụ dịch."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for part in text.replace("\n", "\n<SPLIT>").split("<SPLIT>"):
        sentences = part.split(". ") if len(part) > limit else [part]
        for i, sentence in enumerate(sentences):
            piece = sentence + (". " if i < len(sentences) - 1 else "")
            if len(current) + len(piece) > limit and current:
                chunks.append(current)
                current = ""
            current += piece
    if current:
        chunks.append(current)
    return chunks


def chunk_lines(text: str, limit: int) -> list[str]:
    """Gom các dòng thành nhóm <= limit ký tự (giữ nguyên ranh giới dòng để ghép lại đúng)."""
    groups: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.split("\n"):
        if current and size + len(line) + 1 > limit:
            groups.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        groups.append("\n".join(current))
    return groups


async def translate_in_groups(text: str, limit: int, translate_one) -> str:
    """Dịch từng nhóm dòng; dòng quá dài thì cắt theo câu. Kết quả giữ đúng số dòng."""
    out = []
    for group in chunk_lines(text, limit):
        if len(group) <= limit:
            out.append(await translate_one(group))
        else:  # 1 dòng rất dài
            out.append(" ".join([(await translate_one(piece)).strip() for piece in split_text(group, limit)]))
    return "\n".join(out)


# ---------------------------------------------------------------- dịch vụ 1: thư viện deep-translator
class GoogleTranslatorClient:
    """Google Translate bản miễn phí qua thư viện deep-translator."""

    name = "google"

    async def translate(self, text: str, *, target: str, source: str = "vi") -> str:
        if not text.strip() or target == source:
            return text
        from deep_translator import GoogleTranslator
        from deep_translator.exceptions import TooManyRequests

        def _run() -> str:
            translator = GoogleTranslator(source=source, target=target)
            return "".join(translator.translate(chunk) or "" for chunk in split_text(text))

        try:
            return await asyncio.to_thread(_run)
        except TooManyRequests as exc:
            raise ExternalServiceError("Google tạm chặn vì gọi quá nhiều", code=RATE_LIMITED) from exc
        except Exception as exc:  # noqa: BLE001 - thư viện ném nhiều loại lỗi khác nhau
            raise ExternalServiceError(f"Dịch máy lỗi: {exc}", code="TRANSLATION_FAILED") from exc


# ---------------------------------------------------------------- dịch vụ 2: Google API công khai
class GoogleApiTranslator:
    """Gọi thẳng translate.googleapis.com (endpoint khác với bản web, thường không bị chặn cùng lúc)."""

    name = "google-api"
    URL = "https://translate.googleapis.com/translate_a/single"

    def __init__(self, timeout: float = 20.0, transport: httpx.AsyncBaseTransport | None = None):
        self.timeout = timeout
        self.transport = transport

    async def translate(self, text: str, *, target: str, source: str = "vi") -> str:
        if not text.strip() or target == source:
            return text
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:

            async def one(chunk: str) -> str:
                params = {"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": chunk}
                try:
                    response = await client.get(self.URL, params=params)
                except httpx.HTTPError as exc:
                    raise ExternalServiceError(f"Google API lỗi mạng: {exc}", code="TRANSLATION_FAILED") from exc
                if response.status_code == 429:
                    raise ExternalServiceError("Google API tạm chặn vì gọi quá nhiều", code=RATE_LIMITED)
                if response.status_code != 200:
                    raise ExternalServiceError(f"Google API lỗi HTTP {response.status_code}", code="TRANSLATION_FAILED")
                try:
                    return "".join(seg[0] for seg in response.json()[0] if seg and seg[0])
                except (ValueError, TypeError, IndexError) as exc:
                    raise ExternalServiceError("Google API trả dữ liệu lạ", code="TRANSLATION_FAILED") from exc

            return await translate_in_groups(text, 1500, one)


# ---------------------------------------------------------------- dịch vụ 3: MyMemory
class MyMemoryTranslator:
    """
    MyMemory (mymemory.translated.net) - miễn phí, không cần tài khoản.
    Giới hạn ~5.000 ký tự/ngày; khai báo email (MYMEMORY_EMAIL) được ~50.000 ký tự/ngày.
    """

    name = "mymemory"
    URL = "https://api.mymemory.translated.net/get"

    def __init__(
        self, email: str | None = None, timeout: float = 20.0, transport: httpx.AsyncBaseTransport | None = None
    ):
        self.email = email
        self.timeout = timeout
        self.transport = transport

    async def translate(self, text: str, *, target: str, source: str = "vi") -> str:
        if not text.strip() or target == source:
            return text
        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:

            async def one(chunk: str) -> str:
                params = {"q": chunk, "langpair": f"{source}|{target}"}
                if self.email:
                    params["de"] = self.email
                try:
                    response = await client.get(self.URL, params=params)
                    data = response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    raise ExternalServiceError(f"MyMemory lỗi: {exc}", code="TRANSLATION_FAILED") from exc
                status = int(data.get("responseStatus") or response.status_code)
                if status == 429 or data.get("quotaFinished"):
                    raise ExternalServiceError("MyMemory hết lượt dịch hôm nay", code=RATE_LIMITED)
                if status != 200:
                    raise ExternalServiceError(
                        f"MyMemory lỗi: {data.get('responseDetails')}", code="TRANSLATION_FAILED"
                    )
                return data["responseData"]["translatedText"]

            return await translate_in_groups(text, 450, one)  # MyMemory giới hạn ~500 byte/lần


# ---------------------------------------------------------------- bộ điều phối
class FallbackTranslator:
    """Thử lần lượt các dịch vụ; giãn nhịp gọi và tạm nghỉ dịch vụ bị chặn."""

    def __init__(self, providers: list, *, min_interval: float = 0.6, cooldown: float = 600):
        self.providers = providers
        self.min_interval = min_interval
        self.cooldown = cooldown
        self._blocked_until: dict[str, float] = {}
        self._last_call: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def _throttle(self, name: str) -> None:
        lock = self._locks.setdefault(name, asyncio.Lock())
        async with lock:
            wait = self._last_call.get(name, 0) + self.min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call[name] = time.monotonic()

    async def translate(self, text: str, *, target: str, source: str = "vi") -> str:
        if not text.strip() or target == source:
            return text
        errors = []
        for provider in self.providers:
            if self._blocked_until.get(provider.name, 0) > time.monotonic():
                errors.append(f"{provider.name}: đang tạm nghỉ do bị chặn")
                continue
            await self._throttle(provider.name)
            try:
                return await provider.translate(text, target=target, source=source)
            except ExternalServiceError as exc:
                if exc.code == RATE_LIMITED:
                    self._blocked_until[provider.name] = time.monotonic() + self.cooldown
                    logger.warning(
                        "%s bị chặn (quá nhiều yêu cầu) -> nghỉ %ds, chuyển dịch vụ khác", provider.name, self.cooldown
                    )
                else:
                    logger.warning("%s dịch %s->%s lỗi: %s", provider.name, source, target, exc.message)
                errors.append(f"{provider.name}: {exc.message}")
        raise ExternalServiceError("Tất cả dịch vụ dịch đều lỗi - " + "; ".join(errors), code="TRANSLATION_FAILED")


class DisabledTranslator:
    """Khi tắt dịch máy (TRANSLATOR_PROVIDER=none): luôn báo lỗi để hệ thống dùng fallback."""

    async def translate(self, text: str, *, target: str, source: str = "vi") -> str:
        if target == source:
            return text
        raise ExternalServiceError("Dịch máy đang tắt", code="TRANSLATION_DISABLED")


def build_translator(provider: str, *, mymemory_email: str | None = None) -> Translator:
    """
    google (mặc định) : Google -> Google API -> MyMemory (tự chuyển khi bị chặn)
    mymemory          : chỉ dùng MyMemory
    none              : tắt dịch máy
    """
    if provider in ("google", "auto"):
        return FallbackTranslator([GoogleTranslatorClient(), GoogleApiTranslator(), MyMemoryTranslator(mymemory_email)])
    if provider == "mymemory":
        return FallbackTranslator([MyMemoryTranslator(mymemory_email)])
    return DisabledTranslator()
