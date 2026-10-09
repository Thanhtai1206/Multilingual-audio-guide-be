"""Nghiệp vụ ngôn ngữ: liệt kê, bật/tắt ngôn ngữ hỗ trợ."""

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.domain import Language
from app.repositories.repositories import LanguageRepository


class LanguageService:
    def __init__(self, language_repo: LanguageRepository, *, source_lang: str, fallback_lang: str):
        self.language_repo = language_repo
        self.source_lang = source_lang
        self.fallback_lang = fallback_lang

    async def list_languages(self, *, active_only: bool = True) -> list[Language]:
        return await self.language_repo.list_all(active_only=active_only)

    async def get_active(self, code: str) -> Language:
        """Lấy ngôn ngữ đang bật; ném lỗi nếu không hỗ trợ."""
        language = await self.language_repo.get_by_code(code)
        if language is None or not language.is_active:
            raise NotFoundError(f"Ngôn ngữ '{code}' không được hỗ trợ", code="LANGUAGE_NOT_SUPPORTED")
        return language

    async def resolve_code(self, code: str | None) -> str:
        """Ngôn ngữ không hợp lệ/không bật -> dùng ngôn ngữ dự phòng thay vì báo lỗi (thân thiện với app)."""
        if code:
            language = await self.language_repo.get_by_code(code)
            if language and language.is_active:
                return language.code
        return self.fallback_lang

    async def set_active(self, code: str, is_active: bool) -> Language:
        if not is_active and code in (self.source_lang, self.fallback_lang):
            raise BusinessRuleError("Không thể tắt ngôn ngữ gốc hoặc ngôn ngữ dự phòng", code="LANGUAGE_REQUIRED")
        language = await self.language_repo.set_active(code, is_active)
        if language is None:
            raise NotFoundError(f"Không tìm thấy ngôn ngữ '{code}'")
        return language
