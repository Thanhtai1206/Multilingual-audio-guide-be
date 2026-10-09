"""Nghiệp vụ lộ trình: quản trị tour cố định + gợi ý lộ trình theo vị trí GPS."""

from typing import Any

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import utcnow
from app.models.domain import Tour
from app.models.views import RecommendedRoute, RouteStop
from app.services.geo import estimate_listen_minutes, haversine_m, nearest_neighbor_order, walking_minutes

DEFAULT_MAX_STOPS = 6


class TourService:
    def __init__(self, *, tour_repo, poi_repo, content_service, localization_service):
        self.tour_repo = tour_repo
        self.poi_repo = poi_repo
        self.content_service = content_service
        self.localization_service = localization_service

    # ------------------------------------------------------------------ quản trị
    async def get(self, tour_id: str) -> Tour:
        tour = await self.tour_repo.get_by_id(tour_id)
        if tour is None:
            raise NotFoundError("Không tìm thấy lộ trình", code="TOUR_NOT_FOUND")
        return tour

    async def list_all(self) -> list[Tour]:
        return await self.tour_repo.list(sort=[("name", 1)])

    async def _validate_pois(self, poi_ids: list[str]) -> None:
        if len(set(poi_ids)) != len(poi_ids):
            raise BusinessRuleError("Một POI không được lặp lại trong lộ trình", code="DUPLICATE_POI_IN_TOUR")
        missing = await self.poi_repo.ids_exist(poi_ids)
        if missing:
            raise BusinessRuleError(f"POI không tồn tại: {', '.join(missing)}", code="POI_NOT_FOUND")

    async def create(self, data: dict[str, Any]) -> Tour:
        defaults = {"description": None, "poi_ids": [], "estimated_minutes": 30, "is_active": True}
        data = {**defaults, **data, "code": data["code"].strip().upper()}
        if await self.tour_repo.get_by_code(data["code"]):
            raise ConflictError(f"Mã lộ trình '{data['code']}' đã tồn tại", code="TOUR_CODE_EXISTS")
        await self._validate_pois(data.get("poi_ids", []))
        now = utcnow()
        tour = await self.tour_repo.insert({**data, "translations": {}, "created_at": now, "updated_at": now})
        self.localization_service.schedule_tour(tour.id)
        return tour

    async def update(self, tour_id: str, data: dict[str, Any]) -> Tour:
        current = await self.get(tour_id)
        if "poi_ids" in data and data["poi_ids"] is not None:
            await self._validate_pois(data["poi_ids"])
        if data.get("code"):
            data["code"] = data["code"].strip().upper()
            other = await self.tour_repo.get_by_code(data["code"])
            if other and other.id != tour_id:
                raise ConflictError(f"Mã lộ trình '{data['code']}' đã tồn tại", code="TOUR_CODE_EXISTS")
        text_changed = any(k in data and data[k] != getattr(current, k) for k in ("name", "description"))
        if text_changed:
            data["translations"] = {}
        tour = await self.tour_repo.update(tour_id, {**data, "updated_at": utcnow()})
        if text_changed:
            self.localization_service.schedule_tour(tour_id)
        return tour

    async def delete(self, tour_id: str) -> None:
        await self.get(tour_id)
        await self.tour_repo.delete(tour_id)

    # ------------------------------------------------------------------ gợi ý lộ trình
    async def recommend(
        self,
        *,
        latitude: float,
        longitude: float,
        lang: str,
        poi_ids: list[str] | None = None,
        tour_id: str | None = None,
        max_stops: int | None = None,
    ) -> RecommendedRoute:
        """
        Gợi ý thứ tự tham quan bắt đầu từ vị trí hiện tại.
        - Có tour_id: dùng các POI của tour đó.
        - Có poi_ids: dùng các POI khách tự chọn (PRD: "customizable").
        - Không có gì: lấy các POI ưu tiên cao nhất.
        """
        pois = await self.content_service.list_pois(lang)
        if tour_id:
            tour = await self.get(tour_id)
            poi_ids = tour.poi_ids
        if poi_ids:
            wanted = set(poi_ids)
            pois = [p for p in pois if p.id in wanted]
            if not pois:
                raise BusinessRuleError("Không có POI hợp lệ nào để tạo lộ trình", code="EMPTY_ROUTE")
        else:
            pois = sorted(pois, key=lambda p: -p.priority)[: max_stops or DEFAULT_MAX_STOPS]
        if max_stops:
            pois = pois[:max_stops]

        ordered = nearest_neighbor_order((latitude, longitude), pois, lambda p: (p.latitude, p.longitude))
        stops, total_distance, total_minutes = [], 0.0, 0.0
        prev = (latitude, longitude)
        for index, poi in enumerate(ordered, start=1):
            dist = round(haversine_m(*prev, poi.latitude, poi.longitude), 1)
            walk = walking_minutes(dist)
            listen = estimate_listen_minutes(poi.description)
            stops.append(
                RouteStop(order=index, poi=poi, walk_distance_m=dist, walk_minutes=walk, listen_minutes=listen)
            )
            total_distance += dist
            total_minutes += walk + listen
            prev = (poi.latitude, poi.longitude)
        return RecommendedRoute(
            start_latitude=latitude,
            start_longitude=longitude,
            stops=stops,
            total_distance_m=round(total_distance, 1),
            total_minutes=round(total_minutes, 1),
        )
