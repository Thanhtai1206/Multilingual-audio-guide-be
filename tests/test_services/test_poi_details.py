"""Test thông tin chi tiết POI: giờ mở cửa, đang mở/đóng, khung giờ đông khách, lưu ý đa ngôn ngữ."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.db.seed import backfill_sample_details
from app.db.seed_data import SAMPLE_POI_DETAILS
from app.models.domain import OpeningPeriod
from app.services.poi_details import (
    POPULAR_MIN_EVENTS,
    describe_details_vi,
    describe_hours_vi,
    find_overlap,
    opening_status,
    popular_times,
    site_timezone,
)
from app.services.poi_insights_service import PoiInsightsService
from tests.conftest import poi_data

VN = site_timezone(7)


def every_day(*periods):
    return [OpeningPeriod(day=d, open=o, close=c) for d in range(7) for o, c in periods]


def at(day: int, hhmm: str) -> datetime:
    """Thời điểm giờ Việt Nam; 2026-10-05 là Thứ Hai -> day 0."""
    hours, minutes = map(int, hhmm.split(":"))
    return datetime(2026, 10, 5 + day, hours, minutes, tzinfo=VN)


LUNCH_BREAK = every_day(("06:00", "11:30"), ("13:30", "21:00"))


class TestOpeningStatus:
    def test_open(self):
        assert opening_status(LUNCH_BREAK, at(0, "09:00")) == {
            "state": "open",
            "closes_at": "11:30",
            "minutes_left": 150,
        }

    def test_closing_soon_within_one_hour(self):
        status = opening_status(LUNCH_BREAK, at(0, "20:15"))
        assert status["state"] == "closing_soon" and status["closes_at"] == "21:00" and status["minutes_left"] == 45

    def test_lunch_break_reopens_today(self):
        assert opening_status(LUNCH_BREAK, at(2, "12:00"))["state"] == "closed"  # còn 90 phút mới mở
        status = opening_status(LUNCH_BREAK, at(2, "12:45"))
        assert status == {"state": "opening_soon", "opens_at": "13:30", "opens_day": 2, "opens_in_days": 0}

    def test_after_closing_opens_next_morning(self):
        status = opening_status(LUNCH_BREAK, at(6, "22:00"))  # tối Chủ nhật -> sáng Thứ Hai
        assert status == {"state": "closed", "opens_at": "06:00", "opens_day": 0, "opens_in_days": 1}

    def test_closed_on_monday_opens_tuesday(self):
        hours = [p for p in every_day(("08:00", "17:00")) if p.day != 0]
        status = opening_status(hours, at(0, "10:00"))
        assert status["state"] == "closed" and status["opens_day"] == 1 and status["opens_in_days"] == 1

    def test_boundaries_open_inclusive_close_exclusive(self):
        assert opening_status(LUNCH_BREAK, at(0, "06:00"))["state"] == "open"  # đúng 06:00 là đã mở
        assert opening_status(LUNCH_BREAK, at(0, "11:30"))["state"] == "closed"  # 11:30 đã đóng

    def test_open_until_midnight(self):
        status = opening_status(every_day(("18:00", "24:00")), at(4, "23:50"))
        assert status["state"] == "closing_soon" and status["closes_at"] == "24:00"

    def test_no_hours_is_unknown(self):
        assert opening_status([], at(0, "10:00")) == {"state": "unknown"}


class TestPopularTimes:
    def test_not_enough_data(self):
        events = [at(0, "09:10").astimezone(UTC)] * (POPULAR_MIN_EVENTS - 1)
        assert popular_times(events, VN) == {"sample_size": POPULAR_MIN_EVENTS - 1, "by_day": None}

    def test_normalized_to_peak_and_converted_to_local_time(self):
        # 02:30 UTC = 09:30 giờ Việt Nam; datetime không kèm múi giờ (như Mongo trả về) được hiểu là UTC
        busy = [datetime(2026, 10, 5, 2, 30)] * 30
        quiet = [at(0, "15:00").astimezone(UTC)] * 15
        result = popular_times(busy + quiet, VN)
        assert result["sample_size"] == 45
        assert result["by_day"][0][9] == 100 and result["by_day"][0][15] == 50 and result["by_day"][1][9] == 0


class TestDescriptions:
    def test_groups_days_with_same_hours(self):
        hours = [p for p in every_day(("06:00", "21:00")) if p.day < 5] + [
            OpeningPeriod(day=5, open="05:00", close="22:00")
        ]
        assert describe_hours_vi(hours) == ("Thứ Hai - Thứ Sáu: 06:00-21:00; Thứ Bảy: 05:00-22:00; Chủ nhật: đóng cửa")

    def test_details_text_for_chatbot(self):
        class P:
            opening_hours = every_day(("06:00", "21:00"))
            entry_fee_vnd = 20000
            visit_minutes = 15
            amenities = ["parking", "shoes_off"]
            tips = "Mang nón."

        text = describe_details_vi(P())
        assert "Thứ Hai - Chủ nhật: 06:00-21:00" in text and "20.000 đồng" in text
        assert "Bãi gửi xe" in text and "Bỏ giày dép" in text and "Lưu ý: Mang nón." in text

    def test_overlap_detected(self):
        bad = [OpeningPeriod(day=1, open="06:00", close="12:00"), OpeningPeriod(day=1, open="11:00", close="15:00")]
        assert find_overlap(bad) == "Thứ Ba có 2 khung giờ chồng nhau"
        assert find_overlap(LUNCH_BREAK) is None


DETAILS = {
    "opening_hours": [
        {"day": 1, "open": "13:30", "close": "21:00"},
        {"day": 1, "open": "06:00", "close": "11:30"},
    ],
    "entry_fee_vnd": 0,
    "visit_minutes": 15,
    "amenities": ["shoes_off", "parking", "shoes_off"],
    "tips": "  Nghỉ trưa từ 11:30.  ",
}


class TestPoiServiceDetails:
    async def test_create_normalizes_details(self, services):
        poi = await services["poi"].create(poi_data("CHI_TIET", **DETAILS), auto_localize=False)
        assert [(p.open, p.close) for p in poi.opening_hours] == [("06:00", "11:30"), ("13:30", "21:00")]
        assert poi.amenities == ["shoes_off", "parking"] and poi.tips == "Nghỉ trưa từ 11:30."

    async def test_overlapping_hours_rejected(self, services):
        bad = [{"day": 0, "open": "06:00", "close": "12:00"}, {"day": 0, "open": "10:00", "close": "14:00"}]
        with pytest.raises(BusinessRuleError) as exc:
            await services["poi"].create(poi_data("X1", opening_hours=bad), auto_localize=False)
        assert exc.value.code == "OPENING_HOURS_OVERLAP"

    async def test_unknown_amenity_rejected(self, services):
        with pytest.raises(BusinessRuleError) as exc:
            await services["poi"].create(poi_data("X2", amenities=["helipad"]), auto_localize=False)
        assert exc.value.code == "UNKNOWN_AMENITY"

    async def test_changing_hours_does_not_invalidate_translation(self, services, repos):
        poi = await services["poi"].create(poi_data("GIO"), auto_localize=False)
        await services["localization"].localize_poi(poi.id, ["en"])
        await services["poi"].update(poi.id, {"opening_hours": [{"day": 0, "open": "07:00", "close": "17:00"}]})
        assert (await repos["localization"].get(poi.id, "en")).status == "ready"


class TestTipsTranslation:
    async def test_tips_translated_with_content_and_served_in_bundle(self, services):
        poi = await services["poi"].create(poi_data("TIPS", **DETAILS), auto_localize=False)
        await services["localization"].localize_poi(poi.id, ["en"])
        localized = await services["content"].get_poi(poi.id, "en")
        assert localized.tips == "[en] Nghỉ trưa từ 11:30." and localized.tips_lang == "en"
        assert localized.visit_minutes == 15 and localized.amenities == ["shoes_off", "parking"]
        assert localized.opening_hours[0] == {"day": 1, "open": "06:00", "close": "11:30"}

    async def test_only_tips_retranslated_when_tips_change(self, services, translator, tts, task_runner, repos):
        poi = await services["poi"].create(poi_data("TIPS2", **DETAILS), auto_localize=False)
        await services["localization"].localize_poi(poi.id, ["en"])
        translator.calls.clear()
        # sửa lưu ý -> chỉ dịch lại lưu ý, KHÔNG dịch lại tên/mô tả, KHÔNG tạo lại audio
        await services["poi"].update(poi.id, {"tips": "Mang theo nước."})
        await task_runner.wait_all()
        en_calls = [c for c in translator.calls if c[1] == "en"]
        assert en_calls == [("Mang theo nước.", "en")]
        assert (await repos["localization"].get(poi.id, "en")).status == "ready"
        assert (await services["content"].get_poi(poi.id, "en")).tips == "[en] Mang theo nước."
        en_loc = await repos["localization"].get(poi.id, "en")
        assert en_loc.audio_url and en_loc.description.startswith("[en]")  # audio + mô tả giữ nguyên

    async def test_stale_tips_fall_back_to_vietnamese(self, services, repos):
        poi = await services["poi"].create(poi_data("TIPS3", **DETAILS), auto_localize=False)
        await services["localization"].localize_poi(poi.id, ["en"])
        await repos["poi"].update(poi.id, {"tips": "Lưu ý mới chưa dịch"})  # sửa thẳng DB, chưa dịch
        localized = await services["content"].get_poi(poi.id, "en")
        assert localized.tips == "Lưu ý mới chưa dịch" and localized.tips_lang == "vi"
        assert not localized.is_fallback  # tên + mô tả vẫn là bản tiếng Anh

    async def test_request_language_queues_missing_tips(self, services, repos):
        poi = await services["poi"].create(poi_data("TIPS4"), auto_localize=False)
        await services["localization"].localize_poi(poi.id, ["en"])
        assert await services["localization"].request_language("en") == 0
        await repos["poi"].update(poi.id, {"tips": "Có lưu ý mới"})
        assert await services["localization"].request_language("en") == 1  # thiếu bản dịch lưu ý


class TestInsightsService:
    @pytest.fixture
    def insights(self, repos):
        # Thứ Tư 12:00 giờ Việt Nam
        return PoiInsightsService(
            poi_repo=repos["poi"], event_repo=repos["event"], clock=lambda: at(2, "12:00").astimezone(UTC)
        )

    async def test_status_and_popular_times(self, services, repos, insights):
        poi = await services["poi"].create(poi_data("INS", **DETAILS | {"opening_hours": []}), auto_localize=False)
        await services["poi"].update(poi.id, {"opening_hours": [{"day": 2, "open": "13:30", "close": "21:00"}]})
        noon = at(2, "12:20").astimezone(UTC) - timedelta(days=7)
        for _ in range(POPULAR_MIN_EVENTS):
            await repos["event"].insert(
                {"poi_id": poi.id, "lang": "vi", "type": "view", "session_id": None, "created_at": noon}
            )
        result = await insights.get(poi.id)
        assert result.today == 2 and result.now_local.startswith("2026-10-07T12:00")
        assert result.open_status["state"] == "closed" and result.open_status["opens_at"] == "13:30"
        assert result.busy_now == 100 and result.popular_times["sample_size"] == POPULAR_MIN_EVENTS

    async def test_old_events_ignored_and_missing_poi(self, services, repos, insights):
        poi = await services["poi"].create(poi_data("INS2"), auto_localize=False)
        old = datetime(2025, 1, 1, tzinfo=UTC)
        await repos["event"].insert({"poi_id": poi.id, "lang": "vi", "type": "view", "created_at": old})
        result = await insights.get(poi.id)
        assert result.popular_times == {"sample_size": 0, "by_day": None} and result.busy_now is None
        assert result.open_status == {"state": "unknown"}
        with pytest.raises(NotFoundError):
            await insights.get("000000000000000000000000")


class TestBackfill:
    async def test_adds_details_only_to_sample_pois_without_them(self, services, repos, seeded_db):
        old = await repos["poi"].insert(
            poi_data("CHANH_DIEN") | {"created_at": at(0, "08:00"), "updated_at": at(0, "08:00")}
        )
        await seeded_db["pois"].update_one({"code": "CHANH_DIEN"}, {"$unset": {"opening_hours": ""}})
        custom = await services["poi"].create(
            poi_data("CONG_TAM_QUAN", opening_hours=[{"day": 0, "open": "07:00", "close": "08:00"}]),
            auto_localize=False,
        )
        assert await backfill_sample_details(seeded_db) == 1
        refreshed = await repos["poi"].get_by_id(old.id)
        assert refreshed.amenities == SAMPLE_POI_DETAILS["CHANH_DIEN"]["amenities"]
        assert len((await repos["poi"].get_by_id(custom.id)).opening_hours) == 1  # admin đã nhập -> giữ nguyên
        assert await backfill_sample_details(seeded_db) == 0  # chạy lại không làm gì
