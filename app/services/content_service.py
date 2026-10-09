"""
Nghiệp vụ phục vụ NỘI DUNG cho du khách.

Chuỗi fallback 3 tầng: ngôn ngữ yêu cầu -> tiếng Anh -> tiếng Việt gốc.
Khách luôn thấy nội dung, không bao giờ màn hình trống; cờ `is_fallback`
cho frontend biết đang hiển thị ngôn ngữ thay thế.

Theo PRD (Key Logic 1): sau khi xác thực, frontend tải TOÀN BỘ dữ liệu 1 lần qua
`build_bundle`; kèm `version` để lần sau dùng ETag, dữ liệu không đổi thì trả 304.
"""

import hashlib

from app.core.exceptions import NotFoundError
from app.models.domain import Poi, PoiLocalization, Tour
from app.models.views import ContentBundle, LocalizedPoi, LocalizedTour
from app.services.geo import haversine_m
from app.services.localization_service import is_fresh, tips_fresh


class ContentService:
    def __init__(self, *, poi_repo, localization_repo, tour_repo, language_service):
        self.poi_repo = poi_repo
        self.localization_repo = localization_repo
        self.tour_repo = tour_repo
        self.language_service = language_service

    def _chain(self, lang: str) -> list[str]:
        chain = [lang, self.language_service.fallback_lang, self.language_service.source_lang]
        return list(dict.fromkeys(chain))  # bỏ trùng, giữ thứ tự

    def localize(self, poi: Poi, locs: dict[str, PoiLocalization], lang: str) -> LocalizedPoi:
        """Chọn bản dịch tốt nhất cho POI theo chuỗi fallback (hàm thuần, dễ test)."""
        source = self.language_service.source_lang
        name, description, audio_url, served = poi.name, poi.description, None, source
        for code in self._chain(lang):
            loc = locs.get(code)
            if is_fresh(loc, poi):
                name, description, audio_url, served = loc.name, loc.description, loc.audio_url, code
                break
            if code == source:
                # Tầng cuối: nội dung gốc; audio chỉ dùng nếu khớp nội dung hiện tại
                break
        tips, tips_lang = self._pick_tips(poi, locs, lang)
        return LocalizedPoi(
            **poi.model_dump(
                include={
                    "id",
                    "code",
                    "category",
                    "latitude",
                    "longitude",
                    "trigger_radius_m",
                    "priority",
                    "thumbnail_url",
                    "image_urls",
                    "opening_hours",
                    "entry_fee_vnd",
                    "visit_minutes",
                    "amenities",
                }
            ),
            tips=tips,
            tips_lang=tips_lang,
            name=name,
            description=description,
            audio_url=audio_url,
            requested_lang=lang,
            served_lang=served,
            is_fallback=served != lang,
        )

    def _pick_tips(self, poi: Poi, locs: dict[str, PoiLocalization], lang: str) -> tuple[str, str | None]:
        """Phần "lưu ý" dịch riêng (có hash riêng) nên chọn theo chuỗi fallback riêng."""
        if not poi.tips:
            return "", None
        for code in self._chain(lang):
            if code == self.language_service.source_lang:
                break
            loc = locs.get(code)
            if tips_fresh(loc, poi):
                return loc.tips, code
        return poi.tips, self.language_service.source_lang

    async def _localize_many(self, pois: list[Poi], lang: str) -> list[LocalizedPoi]:
        locs = await self.localization_repo.list_for_langs(self._chain(lang), [p.id for p in pois])
        grouped: dict[str, dict[str, PoiLocalization]] = {}
        for loc in locs:
            grouped.setdefault(loc.poi_id, {})[loc.lang] = loc
        return [self.localize(p, grouped.get(p.id, {}), lang) for p in pois]

    def localize_tour(self, tour: Tour, lang: str) -> LocalizedTour:
        name, description, served = tour.name, tour.description, self.language_service.source_lang
        for code in self._chain(lang):
            if code in tour.translations:
                tr = tour.translations[code]
                name, description, served = tr.name, tr.description or tour.description, code
                break
            if code == self.language_service.source_lang:
                break
        return LocalizedTour(
            id=tour.id,
            code=tour.code,
            name=name,
            description=description,
            poi_ids=tour.poi_ids,
            estimated_minutes=tour.estimated_minutes,
            served_lang=served,
        )

    # ------------------------------------------------------------------ public API
    async def list_pois(self, lang: str) -> list[LocalizedPoi]:
        lang = await self.language_service.resolve_code(lang)
        return await self._localize_many(await self.poi_repo.list_active(), lang)

    async def get_poi(self, poi_id: str, lang: str) -> LocalizedPoi:
        lang = await self.language_service.resolve_code(lang)
        poi = await self.poi_repo.get_by_id(poi_id)
        if poi is None or not poi.is_active:
            raise NotFoundError("Không tìm thấy POI", code="POI_NOT_FOUND")
        return (await self._localize_many([poi], lang))[0]

    async def nearby(self, lat: float, lng: float, radius_m: float, lang: str) -> list[LocalizedPoi]:
        """POI trong bán kính, sắp xếp gần -> xa. Tính Haversine trong bộ nhớ (số POI 1 chùa rất ít)."""
        lang = await self.language_service.resolve_code(lang)
        result = []
        for item in await self._localize_many(await self.poi_repo.list_active(), lang):
            item.distance_m = round(haversine_m(lat, lng, item.latitude, item.longitude), 1)
            if item.distance_m <= radius_m:
                result.append(item)
        return sorted(result, key=lambda p: p.distance_m)

    async def list_tours(self, lang: str) -> list[LocalizedTour]:
        lang = await self.language_service.resolve_code(lang)
        return [self.localize_tour(t, lang) for t in await self.tour_repo.list_active()]

    async def compute_version(self, lang: str) -> str:
        """Phiên bản dữ liệu = hash các mốc cập nhật mới nhất. Dữ liệu đổi -> version đổi."""
        parts = [
            lang,
            str(await self.poi_repo.latest_update()),
            str(await self.poi_repo.count()),
            str(await self.localization_repo.latest_update()),
            str(await self.tour_repo.latest_update()),
            ",".join(lang.code for lang in await self.language_service.list_languages()),
        ]
        return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]  # noqa: S324

    async def build_bundle(self, lang: str) -> ContentBundle:
        lang = await self.language_service.resolve_code(lang)
        languages = await self.language_service.list_languages()
        return ContentBundle(
            lang=lang,
            version=await self.compute_version(lang),
            languages=[{"code": lg.code, "name": lg.name, "native_name": lg.native_name} for lg in languages],
            pois=await self.list_pois(lang),
            tours=await self.list_tours(lang),
        )
