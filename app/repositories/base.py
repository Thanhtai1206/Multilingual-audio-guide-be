"""
Lớp 3 - DATA ACCESS LAYER (Repository).

Repository là nơi DUY NHẤT được phép nói chuyện với MongoDB.
Nó nhận/trả về domain model (app/models/domain.py), giấu chi tiết như `_id`, ObjectId.
Lớp Service gọi Repository; lớp API KHÔNG BAO GIỜ gọi thẳng Repository.

BaseRepository gom các thao tác CRUD chung để các repository con khỏi viết lại.
"""

from typing import Any, Generic, TypeVar

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import ConflictError
from app.core.security import utcnow
from app.models.domain import DomainModel

ModelT = TypeVar("ModelT", bound=DomainModel)


def to_object_id(value: str | None) -> ObjectId | None:
    """Chuyển chuỗi id thành ObjectId; id sai định dạng trả về None (coi như không tồn tại)."""
    if not value:
        return None
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


class BaseRepository(Generic[ModelT]):
    collection_name: str = ""
    model: type[ModelT]

    def __init__(self, db):
        self.db = db
        self.collection = db[self.collection_name]

    # ---------- chuyển đổi document <-> model ----------
    def _to_model(self, doc: dict[str, Any] | None) -> ModelT | None:
        if doc is None:
            return None
        data = dict(doc)
        data["id"] = str(data.pop("_id"))
        return self.model.model_validate(data)

    # ---------- CRUD chung ----------
    async def get_by_id(self, item_id: str) -> ModelT | None:
        oid = to_object_id(item_id)
        if oid is None:
            return None
        return self._to_model(await self.collection.find_one({"_id": oid}))

    async def find_one(self, filters: dict[str, Any]) -> ModelT | None:
        return self._to_model(await self.collection.find_one(filters))

    async def list(
        self,
        filters: dict[str, Any] | None = None,
        *,
        sort: list[tuple[str, int]] | None = None,
        skip: int = 0,
        limit: int = 0,
    ) -> list[ModelT]:
        cursor = self.collection.find(filters or {})
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return [self._to_model(doc) async for doc in cursor]

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        return await self.collection.count_documents(filters or {})

    async def insert(self, data: dict[str, Any]) -> ModelT:
        doc = dict(data)
        try:
            result = await self.collection.insert_one(doc)
        except DuplicateKeyError as exc:
            raise ConflictError("Dữ liệu bị trùng (vi phạm khóa duy nhất)", code="DUPLICATE") from exc
        doc["_id"] = result.inserted_id
        return self._to_model(doc)

    async def update(self, item_id: str, data: dict[str, Any]) -> ModelT | None:
        oid = to_object_id(item_id)
        if oid is None:
            return None
        try:
            doc = await self.collection.find_one_and_update(
                {"_id": oid}, {"$set": data}, return_document=ReturnDocument.AFTER
            )
        except DuplicateKeyError as exc:
            raise ConflictError("Dữ liệu bị trùng (vi phạm khóa duy nhất)", code="DUPLICATE") from exc
        return self._to_model(doc)

    async def delete(self, item_id: str) -> bool:
        oid = to_object_id(item_id)
        if oid is None:
            return False
        result = await self.collection.delete_one({"_id": oid})
        return result.deleted_count == 1

    @staticmethod
    def now():
        return utcnow()
