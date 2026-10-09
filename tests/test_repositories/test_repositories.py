"""Test lớp Data Access: kiểm tra câu truy vấn MongoDB đúng (không test nghiệp vụ ở đây)."""

from datetime import timedelta

import pytest

from app.core.exceptions import ConflictError
from app.core.security import utcnow
from tests.conftest import poi_data


async def make_poi(repos, code="P1", **kw):
    now = utcnow()
    return await repos["poi"].insert({**poi_data(code, **kw), "created_at": now, "updated_at": now})


class TestBaseRepository:
    async def test_insert_and_get_by_id(self, repos):
        poi = await make_poi(repos)
        assert poi.id
        found = await repos["poi"].get_by_id(poi.id)
        assert found.code == "P1"

    async def test_get_by_invalid_id_returns_none(self, repos):
        assert await repos["poi"].get_by_id("khong-phai-objectid") is None
        assert await repos["poi"].get_by_id("") is None

    async def test_update_returns_new_document(self, repos):
        poi = await make_poi(repos)
        updated = await repos["poi"].update(poi.id, {"name": "Tên mới"})
        assert updated.name == "Tên mới"

    async def test_update_missing_returns_none(self, repos):
        assert await repos["poi"].update("64b000000000000000000000", {"name": "x"}) is None

    async def test_delete(self, repos):
        poi = await make_poi(repos)
        assert await repos["poi"].delete(poi.id) is True
        assert await repos["poi"].delete(poi.id) is False

    async def test_unique_index_raises_conflict(self, repos):
        await make_poi(repos, "DUP")
        with pytest.raises(ConflictError):
            await make_poi(repos, "DUP")


class TestPoiRepository:
    async def test_list_active_sorted(self, repos):
        await make_poi(repos, "B", sort_order=2)
        await make_poi(repos, "A", sort_order=1)
        await make_poi(repos, "C", is_active=False)
        result = await repos["poi"].list_active()
        assert [p.code for p in result] == ["A", "B"]

    async def test_search_keyword_and_paging(self, repos):
        for i in range(5):
            await make_poi(repos, f"CODE{i}", name=f"Điểm {i}")
        items, total = await repos["poi"].search(keyword="CODE", is_active=None, skip=2, limit=2)
        assert total == 5
        assert len(items) == 2

    async def test_ids_exist_returns_missing(self, repos):
        poi = await make_poi(repos)
        missing = await repos["poi"].ids_exist([poi.id, "64b000000000000000000000", "sai"])
        assert missing == ["64b000000000000000000000", "sai"]


class TestLocalizationRepository:
    async def test_upsert_creates_then_updates(self, repos):
        loc = await repos["localization"].upsert("p1", "en", {"name": "A", "status": "pending"})
        assert loc.name == "A" and loc.lang == "en"
        loc2 = await repos["localization"].upsert("p1", "en", {"status": "ready"})
        assert loc2.id == loc.id
        assert loc2.name == "A" and loc2.status == "ready"

    async def test_list_for_langs_filters(self, repos):
        await repos["localization"].upsert("p1", "en", {"status": "ready"})
        await repos["localization"].upsert("p1", "ja", {"status": "ready"})
        await repos["localization"].upsert("p2", "en", {"status": "ready"})
        result = await repos["localization"].list_for_langs(["en"], ["p1"])
        assert [(r.poi_id, r.lang) for r in result] == [("p1", "en")]

    async def test_count_by_status_and_delete_for_poi(self, repos):
        await repos["localization"].upsert("p1", "en", {"status": "ready"})
        await repos["localization"].upsert("p1", "ja", {"status": "failed"})
        assert await repos["localization"].count_by_status() == {"ready": 1, "failed": 1}
        assert await repos["localization"].delete_for_poi("p1") == 2


class TestTourRepository:
    async def test_remove_poi_everywhere(self, repos):
        now = utcnow()
        tour = await repos["tour"].insert(
            {
                "code": "T",
                "name": "T",
                "poi_ids": ["a", "b"],
                "estimated_minutes": 10,
                "translations": {},
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
        )
        assert await repos["tour"].remove_poi_everywhere("a") == 1
        assert (await repos["tour"].get_by_id(tour.id)).poi_ids == ["b"]


class TestAccessSessionRepository:
    async def _session(self, repos, code, status, amount=50000):
        now = utcnow()
        return await repos["session"].insert(
            {
                "code": code,
                "method": "cash",
                "status": status,
                "amount": amount,
                "created_at": now,
                "code_expires_at": now + timedelta(hours=1),
            }
        )

    async def test_get_by_code_and_exists(self, repos):
        await self._session(repos, "ABC123", "paid")
        assert (await repos["session"].get_by_code("ABC123")).status == "paid"
        assert await repos["session"].code_exists("ABC123") is True
        assert await repos["session"].code_exists("ZZZ999") is False

    async def test_revenue_counts_only_paid_states(self, repos):
        await self._session(repos, "A1", "paid")
        await self._session(repos, "A2", "active")
        await self._session(repos, "A3", "pending")
        await self._session(repos, "A4", "cancelled")
        assert await repos["session"].total_revenue() == 100000


class TestEventRepository:
    async def test_top_pois(self, repos):
        now = utcnow()
        for poi_id, n in (("x", 3), ("y", 1)):
            for _ in range(n):
                await repos["event"].insert({"poi_id": poi_id, "lang": "en", "type": "view", "created_at": now})
        top = await repos["event"].top_pois(5)
        assert top[0] == {"poi_id": "x", "count": 3}
        assert await repos["event"].count_by_lang() == {"en": 4}


class TestLanguageRepository:
    async def test_upsert_keeps_admin_toggle(self, seeded_db, repos):
        await repos["language"].set_active("ja", False)
        await repos["language"].upsert(
            {
                "code": "ja",
                "name": "Japanese",
                "native_name": "日本語",
                "translator_code": "ja",
                "tts_voice": "v",
                "is_active": True,
            }
        )
        assert (await repos["language"].get_by_code("ja")).is_active is False
        assert len(await repos["language"].list_all(active_only=True)) == 15
