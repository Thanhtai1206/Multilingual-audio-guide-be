"""
Dịch chuỗi giao diện (UI) của app sang ngôn ngữ khách chọn.

Lần đầu có khách dùng 1 ngôn ngữ: dịch toàn bộ chuỗi tiếng Anh 1 lần (gộp thành 1 request
cho nhanh) rồi lưu DB. Các lần sau trả ngay từ DB. Khi chuỗi gốc đổi (source_hash khác) -> dịch lại.
Dịch lỗi -> trả tiếng Anh, lần sau thử lại.
"""

import asyncio
import hashlib
import json

from app.core.exceptions import ExternalServiceError
from app.db.ui_strings import UI_STRINGS_EN, UI_STRINGS_VI

_LOCKS: dict[str, asyncio.Lock] = {}  # tránh 2 request cùng dịch 1 ngôn ngữ một lúc


def ui_source_hash() -> str:
    return hashlib.md5(json.dumps(UI_STRINGS_EN, sort_keys=True).encode()).hexdigest()  # noqa: S324


class UiTextService:
    def __init__(self, *, ui_repo, language_repo, translator):
        self.ui_repo = ui_repo
        self.language_repo = language_repo
        self.translator = translator

    async def _translate_all(self, translator_code: str) -> dict[str, str]:
        keys = list(UI_STRINGS_EN)
        # Gộp tất cả chuỗi thành 1 đoạn, mỗi dòng 1 chuỗi -> chỉ 1 lần gọi dịch
        joined = "\n".join(UI_STRINGS_EN[k] for k in keys)
        lines = [
            line.strip()
            for line in (await self.translator.translate(joined, target=translator_code, source="en")).split("\n")
        ]
        lines = [line for line in lines if line]
        if len(lines) == len(keys):
            return dict(zip(keys, lines, strict=True))
        # Dịch máy làm lệch số dòng -> dịch từng chuỗi (chậm hơn nhưng chắc chắn)
        result = {}
        for key in keys:
            result[key] = await self.translator.translate(UI_STRINGS_EN[key], target=translator_code, source="en")
        return result

    async def get_strings(self, lang: str) -> tuple[str, dict[str, str], bool]:
        """Trả về (ngôn ngữ, bộ chuỗi, is_fallback)."""
        if lang == "en":
            return "en", UI_STRINGS_EN, False
        if lang == "vi":
            return "vi", UI_STRINGS_VI, False
        language = await self.language_repo.get_by_code(lang)
        if language is None or not language.is_active:
            return "en", UI_STRINGS_EN, True

        source_hash = ui_source_hash()
        cached = await self.ui_repo.get(lang)
        if cached and cached.get("source_hash") == source_hash:
            return lang, {**UI_STRINGS_EN, **cached["strings"]}, False

        lock = _LOCKS.setdefault(lang, asyncio.Lock())
        async with lock:
            cached = await self.ui_repo.get(lang)  # request khác có thể vừa dịch xong
            if cached and cached.get("source_hash") == source_hash:
                return lang, {**UI_STRINGS_EN, **cached["strings"]}, False
            try:
                strings = await self._translate_all(language.translator_code)
            except ExternalServiceError:
                return lang, UI_STRINGS_EN, True
            await self.ui_repo.save(lang, strings, source_hash)
            return lang, strings, False
