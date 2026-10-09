"""Chuyển văn bản thành giọng nói (Text-to-Speech) bằng Microsoft Edge-TTS (miễn phí)."""

import logging
import re
from typing import Protocol

from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class TTSProvider(Protocol):
    async def synthesize(self, text: str, *, voice: str) -> bytes: ...


def clean_for_speech(text: str) -> str:
    """Bỏ ký hiệu Markdown để máy đọc không đọc ra dấu # hay *."""
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"[*_`>]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


class EdgeTTSClient:
    async def synthesize(self, text: str, *, voice: str) -> bytes:
        import edge_tts

        try:
            communicate = edge_tts.Communicate(clean_for_speech(text), voice)
            audio = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio.extend(chunk["data"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Edge-TTS lỗi (voice=%s): %s", voice, exc)
            raise ExternalServiceError(f"Tạo audio lỗi: {exc}", code="TTS_FAILED") from exc
        if not audio:
            raise ExternalServiceError("Edge-TTS trả về audio rỗng", code="TTS_FAILED")
        return bytes(audio)


class DisabledTTS:
    async def synthesize(self, text: str, *, voice: str) -> bytes:
        raise ExternalServiceError("TTS đang tắt", code="TTS_DISABLED")


def build_tts(provider: str) -> TTSProvider:
    if provider == "edge":
        return EdgeTTSClient()
    return DisabledTTS()
