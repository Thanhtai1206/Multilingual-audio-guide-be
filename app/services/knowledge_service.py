"""Quản lý bài viết kiến thức (nguồn dữ liệu cho chatbot)."""

from typing import Any

from app.core.exceptions import NotFoundError
from app.core.security import utcnow
from app.models.domain import KnowledgeArticle


class KnowledgeService:
    def __init__(self, *, knowledge_repo):
        self.knowledge_repo = knowledge_repo

    async def list_all(self) -> list[KnowledgeArticle]:
        return await self.knowledge_repo.list(sort=[("title", 1)])

    async def get(self, article_id: str) -> KnowledgeArticle:
        article = await self.knowledge_repo.get_by_id(article_id)
        if article is None:
            raise NotFoundError("Không tìm thấy bài viết", code="ARTICLE_NOT_FOUND")
        return article

    async def create(self, data: dict[str, Any]) -> KnowledgeArticle:
        now = utcnow()
        return await self.knowledge_repo.insert({**data, "created_at": now, "updated_at": now})

    async def update(self, article_id: str, data: dict[str, Any]) -> KnowledgeArticle:
        await self.get(article_id)
        return await self.knowledge_repo.update(article_id, {**data, "updated_at": utcnow()})

    async def delete(self, article_id: str) -> None:
        await self.get(article_id)
        await self.knowledge_repo.delete(article_id)
