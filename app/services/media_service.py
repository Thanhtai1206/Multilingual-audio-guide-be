"""Phục vụ file media (audio) cho app - lớp API không gọi thẳng nơi lưu file."""

from app.core.exceptions import NotFoundError


class MediaService:
    def __init__(self, *, storage):
        self.storage = storage

    async def get(self, key: str) -> tuple[bytes, str]:
        found = await self.storage.get(key)
        if found is None:
            raise NotFoundError("Không tìm thấy file", code="MEDIA_NOT_FOUND")
        return found
