"""
Các repository cụ thể - mỗi class ứng với 1 collection.

Chỉ chứa câu truy vấn dữ liệu, KHÔNG chứa quy tắc nghiệp vụ
(vd: "mã hết hạn thì không cho đổi" là việc của Service, không phải ở đây).
"""

from datetime import datetime, timedelta
from typing import Any

from pymongo import ASCENDING, DESCENDING, ReturnDocument

from app.models.domain import (
    AccessSession,
    AdminUser,
    ChatLog,
    KnowledgeArticle,
    Language,
    Payment,
    Poi,
    PoiLocalization,
    Tour,
    VisitEvent,
)
from app.repositories.base import BaseRepository, to_object_id


class LanguageRepository(BaseRepository[Language]):
    collection_name = "languages"
    model = Language

    async def get_by_code(self, code: str) -> Language | None:
        return await self.find_one({"code": code})

    async def list_all(self, *, active_only: bool = False) -> list[Language]:
        filters = {"is_active": True} if active_only else {}
        return await self.list(filters, sort=[("sort_order", ASCENDING)])

    async def set_active(self, code: str, is_active: bool) -> Language | None:
        doc = await self.collection.find_one_and_update(
            {"code": code}, {"$set": {"is_active": is_active}}, return_document=ReturnDocument.AFTER
        )
        return self._to_model(doc)

    async def upsert(self, data: dict[str, Any]) -> None:
        """Dùng khi seed: thêm nếu chưa có, không ghi đè trạng thái is_active admin đã chỉnh."""
        on_insert = {"is_active": data.get("is_active", True)}
        fields = {k: v for k, v in data.items() if k != "is_active"}
        await self.collection.update_one(
            {"code": data["code"]}, {"$set": fields, "$setOnInsert": on_insert}, upsert=True
        )


class PoiRepository(BaseRepository[Poi]):
    collection_name = "pois"
    model = Poi

    async def get_by_code(self, code: str) -> Poi | None:
        return await self.find_one({"code": code})

    async def list_active(self) -> list[Poi]:
        return await self.list({"is_active": True}, sort=[("sort_order", ASCENDING), ("name", ASCENDING)])

    async def search(self, *, keyword: str | None, is_active: bool | None, skip: int, limit: int):
        filters: dict[str, Any] = {}
        if keyword:
            filters["$or"] = [
                {"name": {"$regex": keyword, "$options": "i"}},
                {"code": {"$regex": keyword, "$options": "i"}},
            ]
        if is_active is not None:
            filters["is_active"] = is_active
        items = await self.list(filters, sort=[("sort_order", ASCENDING)], skip=skip, limit=limit)
        return items, await self.count(filters)

    async def ids_exist(self, ids: list[str]) -> list[str]:
        """Trả về các id KHÔNG tồn tại trong danh sách."""
        oids = [to_object_id(i) for i in ids]
        valid = [o for o in oids if o is not None]
        found = {str(d["_id"]) async for d in self.collection.find({"_id": {"$in": valid}}, {"_id": 1})}
        return [i for i in ids if i not in found]

    async def latest_update(self) -> datetime | None:
        docs = await self.collection.find({}, {"updated_at": 1}).sort("updated_at", DESCENDING).limit(1).to_list(1)
        return docs[0]["updated_at"] if docs else None


class PoiLocalizationRepository(BaseRepository[PoiLocalization]):
    collection_name = "poi_localizations"
    model = PoiLocalization

    async def get(self, poi_id: str, lang: str) -> PoiLocalization | None:
        return await self.find_one({"poi_id": poi_id, "lang": lang})

    async def list_for_poi(self, poi_id: str) -> list[PoiLocalization]:
        return await self.list({"poi_id": poi_id})

    async def list_for_langs(self, langs: list[str], poi_ids: list[str] | None = None) -> list[PoiLocalization]:
        filters: dict[str, Any] = {"lang": {"$in": langs}}
        if poi_ids is not None:
            filters["poi_id"] = {"$in": poi_ids}
        return await self.list(filters)

    async def upsert(self, poi_id: str, lang: str, data: dict[str, Any]) -> PoiLocalization:
        fields = {**data, "updated_at": self.now()}
        doc = await self.collection.find_one_and_update(
            {"poi_id": poi_id, "lang": lang},
            {"$set": fields, "$setOnInsert": {"poi_id": poi_id, "lang": lang}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return self._to_model(doc)

    async def mark_status_for_poi(self, poi_id: str, status: str, *, langs: list[str] | None = None) -> int:
        filters: dict[str, Any] = {"poi_id": poi_id}
        if langs is not None:
            filters["lang"] = {"$in": langs}
        result = await self.collection.update_many(filters, {"$set": {"status": status, "updated_at": self.now()}})
        return result.modified_count

    async def list_by_status(self, statuses: list[str]) -> list[PoiLocalization]:
        return await self.list({"status": {"$in": statuses}})

    async def delete_for_poi(self, poi_id: str) -> int:
        result = await self.collection.delete_many({"poi_id": poi_id})
        return result.deleted_count

    async def count_by_status(self) -> dict[str, int]:
        result: dict[str, int] = {}
        async for row in self.collection.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
            result[row["_id"]] = row["n"]
        return result

    async def latest_update(self) -> datetime | None:
        docs = await self.collection.find({}, {"updated_at": 1}).sort("updated_at", DESCENDING).limit(1).to_list(1)
        return docs[0]["updated_at"] if docs else None


class TourRepository(BaseRepository[Tour]):
    collection_name = "tours"
    model = Tour

    async def get_by_code(self, code: str) -> Tour | None:
        return await self.find_one({"code": code})

    async def list_active(self) -> list[Tour]:
        return await self.list({"is_active": True}, sort=[("name", ASCENDING)])

    async def mark_translation_requested(self, tour_id: str, lang: str) -> None:
        oid = to_object_id(tour_id)
        if oid is not None:
            await self.collection.update_one({"_id": oid}, {"$set": {f"translation_requested_at.{lang}": self.now()}})

    async def remove_poi_everywhere(self, poi_id: str) -> int:
        result = await self.collection.update_many(
            {"poi_ids": poi_id}, {"$pull": {"poi_ids": poi_id}, "$set": {"updated_at": self.now()}}
        )
        return result.modified_count

    async def latest_update(self) -> datetime | None:
        docs = await self.collection.find({}, {"updated_at": 1}).sort("updated_at", DESCENDING).limit(1).to_list(1)
        return docs[0]["updated_at"] if docs else None


class AdminUserRepository(BaseRepository[AdminUser]):
    collection_name = "admin_users"
    model = AdminUser

    async def get_by_username(self, username: str) -> AdminUser | None:
        return await self.find_one({"username": username})


class AccessSessionRepository(BaseRepository[AccessSession]):
    collection_name = "access_sessions"
    model = AccessSession

    async def get_by_code(self, code: str) -> AccessSession | None:
        return await self.find_one({"code": code})

    async def code_exists(self, code: str) -> bool:
        return await self.collection.count_documents({"code": code}, limit=1) > 0

    async def search(self, *, status: str | None, skip: int, limit: int):
        filters = {"status": status} if status else {}
        items = await self.list(filters, sort=[("created_at", DESCENDING)], skip=skip, limit=limit)
        return items, await self.count(filters)

    async def count_by_status(self) -> dict[str, int]:
        result: dict[str, int] = {}
        async for row in self.collection.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
            result[row["_id"]] = row["n"]
        return result

    async def total_revenue(self) -> int:
        pipeline = [
            {"$match": {"status": {"$in": ["paid", "active", "expired"]}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
        ]
        async for row in self.collection.aggregate(pipeline):
            return int(row["total"])
        return 0


class PaymentRepository(BaseRepository[Payment]):
    collection_name = "payments"
    model = Payment


class KnowledgeRepository(BaseRepository[KnowledgeArticle]):
    collection_name = "knowledge_articles"
    model = KnowledgeArticle

    async def list_active(self) -> list[KnowledgeArticle]:
        return await self.list({"is_active": True})


class ChatLogRepository(BaseRepository[ChatLog]):
    collection_name = "chat_logs"
    model = ChatLog

    async def count_since(self, session_id: str, since: datetime) -> int:
        return await self.count({"session_id": session_id, "created_at": {"$gte": since}})

    async def recent_for_session(self, session_id: str, limit: int) -> list[ChatLog]:
        """Các lượt hỏi-đáp gần nhất của 1 phiên, xếp từ cũ đến mới."""
        items = await self.list({"session_id": session_id}, sort=[("created_at", DESCENDING)], limit=limit)
        return list(reversed(items))

    async def recent(self, limit: int = 20) -> list[ChatLog]:
        return await self.list({}, sort=[("created_at", DESCENDING)], limit=limit)


class VisitEventRepository(BaseRepository[VisitEvent]):
    collection_name = "visit_events"
    model = VisitEvent

    async def top_pois(self, limit: int = 5) -> list[dict[str, Any]]:
        pipeline = [
            {"$group": {"_id": "$poi_id", "n": {"$sum": 1}}},
            {"$sort": {"n": -1}},
            {"$limit": limit},
        ]
        return [{"poi_id": r["_id"], "count": r["n"]} async for r in self.collection.aggregate(pipeline)]

    async def times_for_poi(self, poi_id: str, since: datetime) -> list[datetime]:
        """Thời điểm các lượt xem/nghe/đi qua 1 POI (chỉ lấy trường created_at cho nhẹ)."""
        cursor = self.collection.find({"poi_id": poi_id, "created_at": {"$gte": since}}, {"created_at": 1, "_id": 0})
        return [doc["created_at"] async for doc in cursor]

    async def count_by_lang(self) -> dict[str, int]:
        result: dict[str, int] = {}
        async for row in self.collection.aggregate([{"$group": {"_id": "$lang", "n": {"$sum": 1}}}]):
            result[row["_id"]] = row["n"]
        return result


class UiTranslationRepository:
    """Bản dịch chuỗi giao diện theo ngôn ngữ: {lang, strings: {key: text}, source_hash, updated_at}."""

    collection_name = "ui_translations"

    def __init__(self, db):
        self.collection = db[self.collection_name]

    async def get(self, lang: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"lang": lang}, {"_id": 0})

    async def save(self, lang: str, strings: dict[str, str], source_hash: str) -> None:
        await self.collection.update_one(
            {"lang": lang},
            {"$set": {"strings": strings, "source_hash": source_hash, "updated_at": BaseRepository.now()}},
            upsert=True,
        )


class ChatCacheRepository:
    """
    Cache câu trả lời chatbot: {key, answer, expires_at}.
    MongoDB tự xóa document khi quá expires_at (TTL index) -> không phình to, khởi động lại vẫn còn.
    """

    collection_name = "chat_cache"

    def __init__(self, db):
        self.collection = db[self.collection_name]

    async def get(self, key: str) -> dict[str, Any] | None:
        # TTL index của MongoDB chạy định kỳ ~60s, nên vẫn lọc expires_at cho chắc
        doc = await self.collection.find_one({"key": key, "expires_at": {"$gt": BaseRepository.now()}})
        return doc["answer"] if doc else None

    async def set(self, key: str, answer: dict[str, Any], ttl_seconds: int) -> None:
        expires_at = BaseRepository.now() + timedelta(seconds=ttl_seconds)
        await self.collection.update_one(
            {"key": key}, {"$set": {"answer": answer, "expires_at": expires_at}}, upsert=True
        )
