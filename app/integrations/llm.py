"""
Gọi mô hình ngôn ngữ lớn (LLM) - dùng cho chatbot và gợi ý mô tả POI.

Hầu hết nhà cung cấp hiện nay đều có API "tương thích OpenAI" (cùng định dạng /chat/completions),
nên chỉ cần 1 client, đổi base_url + model là dùng được:

  gemini     : Google Gemini - CÓ GÓI MIỄN PHÍ, lấy key tại https://aistudio.google.com/apikey
  groq       : Groq (Llama) - có gói miễn phí, key tại https://console.groq.com/keys
  openrouter : OpenRouter - nhiều model, có model miễn phí (đuôi ":free")

LLM_PROVIDER=auto sẽ tự nhận ra nhà cung cấp theo dạng API key (AIza... / gsk_... / sk-or-...).
"""

import asyncio
import logging
import re
from typing import Protocol

import httpx

from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

PRESETS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.8-flash"),
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "openrouter": ("https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
}


class LLMClient(Protocol):
    async def complete(
        self, messages: list[dict[str, str]], *, temperature: float = 0.3, max_tokens: int | None = None
    ) -> str: ...


# Lỗi tạm thời phía nhà cung cấp (quá tải, bảo trì) -> nên thử lại
RETRYABLE_STATUS = {500, 502, 503, 504}


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 60.0,
        transport=None,
        retry_delays: tuple[float, ...] = (1.0, 3.0),
        max_backup_models: int = 2,
        extra_body: dict | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.transport = transport
        self.retry_delays = retry_delays  # số giây chờ giữa các lần thử lại khi AI quá tải
        self.max_backup_models = max_backup_models
        self.extra_body = extra_body or {}  # tham số riêng của nhà cung cấp (vd Gemini: giảm thời gian "suy nghĩ")
        self._model_checked = False  # chỉ tự dò model thay thế (khi 404) 1 lần
        self._model_ids: list[str] | None = None  # cache danh sách model của nhà cung cấp

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def complete(
        self, messages: list[dict[str, str]], *, temperature: float = 0.3, max_tokens: int | None = None
    ) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                model = self.model
                response = await self._post_with_retry(client, model, messages, temperature, max_tokens)

                # 400 khi có tham số riêng (vd reasoning_effort) -> model không hỗ trợ: bỏ tham số đó rồi gọi lại
                if response.status_code == 400 and self.extra_body:
                    logger.warning("Model %s không nhận tham số %s, gọi lại không kèm", model, list(self.extra_body))
                    self.extra_body = {}
                    response = await self._post_with_retry(client, model, messages, temperature, max_tokens)

                # 404 = model đã bị nhà cung cấp gỡ/đổi tên -> tự dò model khác còn dùng được, đổi hẳn
                if response.status_code == 404 and not self._model_checked:
                    self._model_checked = True
                    replacement = next(iter(await self.ranked_models(client, exclude=model)), None)
                    if replacement:
                        logger.warning("Model %s không còn dùng được, tự chuyển sang %s", model, replacement)
                        self.model = model = replacement
                        response = await self._post_with_retry(client, model, messages, temperature, max_tokens)

                # Vẫn quá tải sau khi thử lại -> TẠM dùng model dự phòng cho câu này (không đổi model chính)
                if response.status_code in RETRYABLE_STATUS:
                    backups = await self.ranked_models(client, exclude=self.model)
                    for backup in backups[: self.max_backup_models]:
                        logger.warning("Model %s đang quá tải, tạm dùng %s", self.model, backup)
                        model = backup
                        response = await self._post(client, backup, messages, temperature, max_tokens)
                        if response.status_code == 200:
                            break

                if response.status_code >= 400:
                    # In rõ mã lỗi + lời nhắn của nhà cung cấp để biết sai key, sai model hay hết lượt
                    logger.warning(
                        "Gọi AI lỗi HTTP %s (%s, model=%s): %s",
                        response.status_code,
                        self.base_url,
                        model,
                        response.text[:300],
                    )
                if response.status_code == 429:
                    raise ExternalServiceError("Dịch vụ AI đang hết lượt, thử lại sau", code="LLM_RATE_LIMITED")
                if response.status_code in RETRYABLE_STATUS:
                    raise ExternalServiceError("Dịch vụ AI đang quá tải, thử lại sau", code="LLM_BUSY")
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
        except ExternalServiceError:
            raise
        except httpx.TimeoutException as exc:
            logger.warning("AI (%s) trả lời quá %.0f giây, bỏ qua", self.model, self.timeout)
            raise ExternalServiceError("Dịch vụ AI phản hồi quá chậm", code="LLM_TIMEOUT") from exc
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            logger.warning("Gọi LLM (%s) lỗi: %s", self.model, exc)
            raise ExternalServiceError("Dịch vụ AI tạm thời không phản hồi", code="LLM_FAILED") from exc
        if not content or not content.strip():
            raise ExternalServiceError("Dịch vụ AI trả về câu rỗng", code="LLM_FAILED")
        return content.strip()

    async def _post(self, client, model, messages, temperature, max_tokens) -> httpx.Response:
        body = {"model": model, "messages": messages, "temperature": temperature, **self.extra_body}
        if max_tokens:
            body["max_tokens"] = max_tokens
        return await client.post(f"{self.base_url}/chat/completions", headers=self._headers, json=body)

    async def _post_with_retry(self, client, model, messages, temperature, max_tokens) -> httpx.Response:
        """Gọi AI; nếu nhà cung cấp quá tải (5xx) hoặc rớt mạng thì chờ một chút rồi thử lại."""
        for delay in (*self.retry_delays, None):
            try:
                response = await self._post(client, model, messages, temperature, max_tokens)
                if response.status_code not in RETRYABLE_STATUS or delay is None:
                    return response
                logger.info("AI quá tải (HTTP %s), thử lại sau %.0f giây...", response.status_code, delay)
            except httpx.TimeoutException:
                raise  # đã chờ đủ lâu -> không thử lại (tránh khách chờ vài phút)
            except httpx.TransportError:
                if delay is None:
                    raise
                logger.info("Mất kết nối tới AI, thử lại sau %.0f giây...", delay)
            await asyncio.sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover

    async def ranked_models(self, client: httpx.AsyncClient, *, exclude: str = "") -> list[str]:
        """Danh sách model dùng để chat của nhà cung cấp, xếp theo mức phù hợp (lấy 1 lần rồi cache)."""
        if self._model_ids is None:
            try:
                response = await client.get(f"{self.base_url}/models", headers=self._headers)
                response.raise_for_status()
                self._model_ids = [str(m["id"]).removeprefix("models/") for m in response.json().get("data", [])]
            except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
                logger.warning("Không lấy được danh sách model: %s", exc)
                return []
        return rank_models([m for m in self._model_ids if m != exclude], preferred=self.model)

    async def discover_model(self, client: httpx.AsyncClient) -> str | None:
        """Model thay thế phù hợp nhất (dùng trong lệnh kiểm tra check_llm)."""
        return next(iter(await self.ranked_models(client, exclude=self.model)), None)


# Model chuyên dụng (ảnh, giọng nói, embedding...) không dùng để chat
_SKIP_WORDS = ("embedding", "image", "tts", "audio", "live", "vision", "aqa", "imagen", "veo", "robotics", "computer")


def _version(model_id: str) -> tuple[float, ...]:
    """'gemini-3.8-flash' -> (3.8,) để so sánh model nào mới hơn."""
    return tuple(float(x) for x in re.findall(r"\d+(?:\.\d+)?", model_id)[:1]) or (0.0,)


def rank_models(ids: list[str], preferred: str = "") -> list[str]:
    """Xếp model: cùng "dòng" với model đang cấu hình (flash/pro...) -> bản ổn định -> phiên bản mới hơn."""
    chat_models = [m for m in ids if not any(w in m.lower() for w in _SKIP_WORDS)]
    family = next((f for f in ("flash-lite", "flash", "pro", "mini") if f in preferred.lower()), "flash")

    def score(m: str):
        name = m.lower()
        same_family = family in name and (family == "flash-lite" or "lite" not in name)
        unstable = any(w in name for w in ("preview", "exp", "latest"))
        return (same_family, not unstable, _version(name), -len(name))

    return sorted(chat_models, key=score, reverse=True)


def pick_best_model(ids: list[str], preferred: str = "") -> str | None:
    return next(iter(rank_models(ids, preferred)), None)


def detect_provider(api_key: str) -> str:
    """Đoán nhà cung cấp theo đầu key.

    Chỉ Groq (gsk_) và OpenRouter (sk-or-) có tiền tố cố định. Key Google có nhiều dạng
    (AIza..., AQ. ...) nên key không nhận ra được coi là Gemini - đúng với hướng dẫn trong README.
    Muốn chắc chắn thì đặt LLM_PROVIDER=gemini|groq|openrouter trong .env.
    """
    if api_key.startswith("gsk_"):
        return "groq"
    if api_key.startswith("sk-or-"):
        return "openrouter"
    if not api_key.startswith("AIza"):
        logger.info("Không nhận ra dạng key, mặc định dùng Gemini (đặt LLM_PROVIDER nếu sai)")
    return "gemini"


def resolve_llm_config(settings) -> tuple[str, str, str, str] | None:
    """Trả về (provider, api_key, base_url, model) hoặc None nếu chưa cấu hình."""
    if settings.LLM_PROVIDER == "none":
        return None
    # Bỏ khoảng trắng / dấu nháy hay bị dính khi copy key
    api_key = (settings.LLM_API_KEY or settings.OPENROUTER_API_KEY or "").strip().strip("\"'")
    if not api_key:
        return None
    provider_setting = (settings.LLM_PROVIDER or "auto").strip().lower()
    model_setting = (settings.LLM_MODEL or "").strip()
    if model_setting.lower() in PRESETS:
        # Lỗi hay gặp: ghi LLM_MODEL=gemini (tên nhà cung cấp) thay vì LLM_PROVIDER=gemini
        logger.warning("LLM_MODEL=%s là tên nhà cung cấp, hiểu thành LLM_PROVIDER=%s", model_setting, model_setting)
        if provider_setting not in PRESETS:
            provider_setting = model_setting.lower()
        model_setting = ""
    if provider_setting in PRESETS:
        provider = provider_setting
    elif settings.LLM_API_KEY:
        provider = detect_provider(api_key)
    else:
        provider = "openrouter"  # tương thích cấu hình cũ chỉ có OPENROUTER_API_KEY
    base_url, model = PRESETS[provider]
    if provider == "openrouter" and not settings.LLM_API_KEY:
        base_url, model = settings.OPENROUTER_BASE_URL, settings.OPENROUTER_MODEL
    return provider, api_key, settings.LLM_BASE_URL or base_url, model_setting or model


def build_llm(settings) -> LLMClient | None:
    config = resolve_llm_config(settings)
    if config is None:
        return None
    provider, api_key, base_url, model = config
    logger.info("Chatbot dùng AI tạo sinh: %s / %s", provider, model)
    return OpenAICompatibleClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        extra_body=provider_options(provider),
    )


def provider_options(provider: str) -> dict:
    """Gemini đời mới mặc định "suy nghĩ" khá lâu trước khi trả lời -> giảm xuống mức thấp cho chatbot nhanh hơn."""
    return {"reasoning_effort": "low"} if provider == "gemini" else {}