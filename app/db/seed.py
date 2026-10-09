"""Khởi tạo dữ liệu ban đầu: ngôn ngữ, admin đầu tiên, dữ liệu mẫu (nếu DB còn trống)."""

import logging

from app.core.security import utcnow
from app.db.seed_data import LANGUAGES, SAMPLE_ARTICLES, SAMPLE_POI_DETAILS, SAMPLE_POIS, SAMPLE_TOURS
from app.repositories.repositories import (
    KnowledgeRepository,
    LanguageRepository,
    PoiRepository,
    TourRepository,
)

logger = logging.getLogger(__name__)


async def seed_languages(db) -> None:
    repo = LanguageRepository(db)
    for order, (code, name, native, translator_code, voice) in enumerate(LANGUAGES):
        await repo.upsert(
            {
                "code": code,
                "name": name,
                "native_name": native,
                "translator_code": translator_code,
                "tts_voice": voice,
                "sort_order": order,
                "is_active": True,
            }
        )


async def seed_sample_content(db) -> bool:
    """Chỉ chèn dữ liệu mẫu khi chưa có POI nào. Trả về True nếu đã chèn."""
    poi_repo = PoiRepository(db)
    if await poi_repo.count() > 0:
        return False
    now = utcnow()
    code_to_id = {}
    for data in SAMPLE_POIS:
        details = SAMPLE_POI_DETAILS.get(data["code"], {})
        poi = await poi_repo.insert(
            {**data, **details, "image_urls": [], "is_active": True, "created_at": now, "updated_at": now}
        )
        code_to_id[poi.code] = poi.id

    tour_repo = TourRepository(db)
    for data in SAMPLE_TOURS:
        tour = {k: v for k, v in data.items() if k != "poi_codes"}
        tour["poi_ids"] = [code_to_id[c] for c in data["poi_codes"]]
        await tour_repo.insert({**tour, "translations": {}, "is_active": True, "created_at": now, "updated_at": now})

    knowledge_repo = KnowledgeRepository(db)
    for data in SAMPLE_ARTICLES:
        await knowledge_repo.insert({**data, "is_active": True, "created_at": now, "updated_at": now})
    logger.info(
        "Đã chèn dữ liệu mẫu: %d POI, %d tour, %d bài viết", len(SAMPLE_POIS), len(SAMPLE_TOURS), len(SAMPLE_ARTICLES)
    )
    return True


async def backfill_sample_details(db) -> int:
    """
    DB tạo từ phiên bản cũ (chưa có giờ mở cửa, tiện ích...) -> bổ sung thông tin chi tiết mẫu
    cho các POI mẫu CHƯA có trường opening_hours. Không đụng tới POI admin đã nhập/sửa chi tiết.
    Trả về số POI được bổ sung.
    """
    collection = db[PoiRepository.collection_name]
    updated = 0
    for code, details in SAMPLE_POI_DETAILS.items():
        result = await collection.update_one(
            {"code": code, "opening_hours": {"$exists": False}},
            {"$set": {**details, "updated_at": utcnow()}},
        )
        updated += result.modified_count
    if updated:
        logger.info("Đã bổ sung thông tin chi tiết (giờ mở cửa, tiện ích...) cho %d điểm tham quan mẫu", updated)
    return updated
