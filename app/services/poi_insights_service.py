"""
Thông tin "sống" của 1 điểm tham quan: đang mở hay đóng cửa, giờ này có đông không.

Tách khỏi ContentService vì dữ liệu này đổi theo từng phút -> không đưa vào bundle (bundle được cache bằng ETag).
`clock` truyền từ ngoài vào để test được mọi thời điểm (8h sáng thứ Hai, nửa đêm Chủ nhật...).
"""

from collections.abc import Callable
from datetime import datetime, timedelta

from app.core.exceptions import NotFoundError
from app.core.security import utcnow
from app.models.views import PoiInsights
from app.services.poi_details import POPULAR_LOOKBACK_DAYS, opening_status, popular_times, site_timezone


class PoiInsightsService:
    def __init__(self, *, poi_repo, event_repo, utc_offset_hours: int = 7, clock: Callable[[], datetime] = utcnow):
        self.poi_repo = poi_repo
        self.event_repo = event_repo
        self.tz = site_timezone(utc_offset_hours)
        self.clock = clock

    def now_local(self) -> datetime:
        return self.clock().astimezone(self.tz)

    async def get(self, poi_id: str) -> PoiInsights:
        poi = await self.poi_repo.get_by_id(poi_id)
        if poi is None or not poi.is_active:
            raise NotFoundError("Không tìm thấy POI", code="POI_NOT_FOUND")
        now = self.now_local()
        since = self.clock() - timedelta(days=POPULAR_LOOKBACK_DAYS)
        popular = popular_times(await self.event_repo.times_for_poi(poi_id, since), self.tz)
        busy_now = popular["by_day"][now.weekday()][now.hour] if popular["by_day"] else None
        return PoiInsights(
            poi_id=poi_id,
            now_local=now.isoformat(timespec="minutes"),
            today=now.weekday(),
            open_status=opening_status(poi.opening_hours, now),
            popular_times=popular,
            busy_now=busy_now,
        )
