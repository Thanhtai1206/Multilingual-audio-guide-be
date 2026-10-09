"""Thống kê cho dashboard giám sát + ghi nhận sự kiện sử dụng của du khách."""

from app.core.exceptions import NotFoundError
from app.core.security import utcnow
from app.models.domain import EventType, LocalizationStatus
from app.models.views import StatsOverview


class StatsService:
    def __init__(self, *, poi_repo, localization_repo, language_repo, session_repo, chat_repo, event_repo):
        self.poi_repo = poi_repo
        self.localization_repo = localization_repo
        self.language_repo = language_repo
        self.session_repo = session_repo
        self.chat_repo = chat_repo
        self.event_repo = event_repo

    async def record_event(self, *, poi_id: str, event_type: EventType, lang: str, session_id: str | None) -> None:
        poi = await self.poi_repo.get_by_id(poi_id)
        if poi is None:
            raise NotFoundError("Không tìm thấy POI", code="POI_NOT_FOUND")
        await self.event_repo.insert(
            {"poi_id": poi_id, "type": event_type, "lang": lang, "session_id": session_id, "created_at": utcnow()}
        )

    async def recent_chats(self, limit: int = 20):
        return await self.chat_repo.recent(limit)

    async def overview(self) -> StatsOverview:
        total_pois = await self.poi_repo.count()
        active_pois = await self.poi_repo.count({"is_active": True})
        active_languages = await self.language_repo.count({"is_active": True})
        loc_status = await self.localization_repo.count_by_status()
        expected = total_pois * active_languages
        ready = loc_status.get(LocalizationStatus.READY, 0)
        coverage = round(100 * ready / expected, 1) if expected else 0.0

        top = await self.event_repo.top_pois(5)
        for row in top:
            poi = await self.poi_repo.get_by_id(row["poi_id"])
            row["name"] = poi.name if poi else "(đã xóa)"

        return StatsOverview(
            total_pois=total_pois,
            active_pois=active_pois,
            active_languages=active_languages,
            localization_status=loc_status,
            localization_coverage_percent=min(coverage, 100.0),
            access_sessions=await self.session_repo.count_by_status(),
            revenue_vnd=await self.session_repo.total_revenue(),
            total_chats=await self.chat_repo.count(),
            total_events=await self.event_repo.count(),
            top_pois=top,
            events_by_lang=await self.event_repo.count_by_lang(),
        )
