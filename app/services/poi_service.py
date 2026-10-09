"""Nghiệp vụ quản trị POI (dành cho admin)."""

from typing import Any

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import utcnow
from app.models.domain import OpeningPeriod, Poi
from app.services.poi_details import AMENITIES, find_overlap, normalize_hours

CONTENT_FIELDS = {"name", "description"}  # đổi các trường này -> phải dịch lại (cả audio)


def clean_details(data: dict[str, Any]) -> dict[str, Any]:
    """Kiểm tra + chuẩn hóa phần thông tin chi tiết trước khi lưu (quy tắc nghiệp vụ, không phụ thuộc HTTP)."""
    data = dict(data)
    if data.get("opening_hours") is not None:
        hours = [p if isinstance(p, OpeningPeriod) else OpeningPeriod(**p) for p in data["opening_hours"]]
        problem = find_overlap(hours)
        if problem:
            raise BusinessRuleError(problem, code="OPENING_HOURS_OVERLAP")
        data["opening_hours"] = [p.model_dump() for p in normalize_hours(hours)]
    if data.get("amenities") is not None:
        unknown = sorted(set(data["amenities"]) - AMENITIES.keys())
        if unknown:
            raise BusinessRuleError(f"Tiện ích không hợp lệ: {', '.join(unknown)}", code="UNKNOWN_AMENITY")
        data["amenities"] = list(dict.fromkeys(data["amenities"]))  # bỏ trùng, giữ thứ tự
    if data.get("tips") is not None:
        data["tips"] = data["tips"].strip()
    return data


class PoiService:
    def __init__(self, *, poi_repo, localization_repo, tour_repo, localization_service):
        self.poi_repo = poi_repo
        self.localization_repo = localization_repo
        self.tour_repo = tour_repo
        self.localization_service = localization_service

    async def get(self, poi_id: str) -> Poi:
        poi = await self.poi_repo.get_by_id(poi_id)
        if poi is None:
            raise NotFoundError("Không tìm thấy POI", code="POI_NOT_FOUND")
        return poi

    async def search(self, *, keyword: str | None, is_active: bool | None, page: int, size: int):
        return await self.poi_repo.search(keyword=keyword, is_active=is_active, skip=(page - 1) * size, limit=size)

    async def create(self, data: dict[str, Any], *, auto_localize: bool = True) -> Poi:
        defaults = {
            "category": "landmark",
            "trigger_radius_m": 30,
            "priority": 0,
            "image_urls": [],
            "sort_order": 0,
            "is_active": True,
            "opening_hours": [],
            "entry_fee_vnd": 0,
            "visit_minutes": None,
            "amenities": [],
            "tips": "",
        }
        data = clean_details({**defaults, **data, "code": data["code"].strip().upper()})
        if await self.poi_repo.get_by_code(data["code"]):
            raise ConflictError(f"Mã POI '{data['code']}' đã tồn tại", code="POI_CODE_EXISTS")
        now = utcnow()
        poi = await self.poi_repo.insert({**data, "created_at": now, "updated_at": now})
        if auto_localize:
            await self.localization_service.schedule_poi(poi.id)
        return poi

    async def update(self, poi_id: str, data: dict[str, Any], *, auto_localize: bool = True) -> Poi:
        current = await self.get(poi_id)
        data = clean_details(data)
        if "code" in data and data["code"]:
            data["code"] = data["code"].strip().upper()
            other = await self.poi_repo.get_by_code(data["code"])
            if other and other.id != poi_id:
                raise ConflictError(f"Mã POI '{data['code']}' đã tồn tại", code="POI_CODE_EXISTS")
        content_changed = any(f in data and data[f] != getattr(current, f) for f in CONTENT_FIELDS)
        tips_changed = "tips" in data and data["tips"] != current.tips
        poi = await self.poi_repo.update(poi_id, {**data, "updated_at": utcnow()})
        if content_changed:
            # Nội dung gốc đổi -> bản dịch cũ hết hiệu lực, dịch lại toàn bộ
            await self.localization_service.mark_outdated(poi_id)
        if (content_changed or tips_changed) and auto_localize:
            # Chỉ đổi lưu ý -> pipeline tự nhận ra và chỉ dịch lại phần lưu ý (không tạo lại audio)
            await self.localization_service.schedule_poi(poi_id)
        return poi

    async def delete(self, poi_id: str) -> None:
        await self.get(poi_id)
        # Xóa dây chuyền: bản dịch + gỡ POI khỏi các tour
        await self.localization_repo.delete_for_poi(poi_id)
        await self.tour_repo.remove_poi_everywhere(poi_id)
        await self.poi_repo.delete(poi_id)
