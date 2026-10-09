"""Tạo index cho các collection (chạy lúc khởi động, an toàn khi chạy lại nhiều lần)."""

import logging

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

logger = logging.getLogger(__name__)


async def ensure_indexes(db) -> None:
    await db.languages.create_index("code", unique=True)
    await db.pois.create_index("code", unique=True)
    await db.pois.create_index([("is_active", ASCENDING), ("sort_order", ASCENDING)])
    await db.poi_localizations.create_index([("poi_id", ASCENDING), ("lang", ASCENDING)], unique=True)
    await db.tours.create_index("code", unique=True)
    await db.admin_users.create_index("username", unique=True)
    await db.access_sessions.create_index("code", unique=True)
    await db.access_sessions.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    await db.payments.create_index("session_id")
    await db.chat_logs.create_index([("session_id", ASCENDING), ("created_at", DESCENDING)])
    await db.ui_translations.create_index("lang", unique=True)
    await db.chat_cache.create_index("key", unique=True)
    try:
        # TTL: MongoDB tự xóa cache khi hết hạn
        await db.chat_cache.create_index("expires_at", expireAfterSeconds=0)
    except OperationFailure as exc:
        # Vài hệ "tương thích MongoDB" (FerretDB, Cosmos...) chưa hỗ trợ TTL -> vẫn chạy được,
        # vì truy vấn cache đã tự bỏ qua bản hết hạn
        logger.warning("Không tạo được TTL index cho chat_cache: %s", exc)
    await db.media_files.create_index("key", unique=True)
    await db.visit_events.create_index([("poi_id", ASCENDING), ("created_at", DESCENDING)])
