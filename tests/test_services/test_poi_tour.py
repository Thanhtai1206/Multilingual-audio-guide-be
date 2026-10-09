"""Test nghiệp vụ POI và lộ trình."""

import pytest

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.services import geo
from tests.conftest import poi_data


class TestPoiService:
    async def test_create_normalizes_code_and_schedules(self, services, task_runner):
        poi = await services["poi"].create(poi_data("cong_tam_quan"))
        assert poi.code == "CONG_TAM_QUAN"
        assert task_runner.pending_count == 1

    async def test_duplicate_code_conflict(self, services):
        await services["poi"].create(poi_data("A"), auto_localize=False)
        with pytest.raises(ConflictError):
            await services["poi"].create(poi_data("a"), auto_localize=False)

    async def test_update_coords_does_not_relocalize(self, services, task_runner):
        poi = await services["poi"].create(poi_data("A"), auto_localize=False)
        await services["poi"].update(poi.id, {"latitude": 16.2})
        assert task_runner.pending_count == 0

    async def test_update_description_marks_outdated_and_relocalizes(self, services, task_runner, repos):
        poi = await services["poi"].create(poi_data("A"), auto_localize=False)
        await services["localization"].localize_poi(poi.id, ["en"])
        await services["poi"].update(poi.id, {"description": "Nội dung mới"})
        assert task_runner.pending_count == 1

    async def test_update_to_existing_code_conflict(self, services):
        await services["poi"].create(poi_data("A"), auto_localize=False)
        b = await services["poi"].create(poi_data("B"), auto_localize=False)
        with pytest.raises(ConflictError):
            await services["poi"].update(b.id, {"code": "A"})

    async def test_delete_cascades(self, services, repos):
        poi = await services["poi"].create(poi_data("A"), auto_localize=False)
        await services["localization"].localize_poi(poi.id, ["en"])
        tour = await services["tour"].create({"code": "T", "name": "Tour", "poi_ids": [poi.id]})
        await services["poi"].delete(poi.id)
        assert await repos["localization"].list_for_poi(poi.id) == []
        assert (await repos["tour"].get_by_id(tour.id)).poi_ids == []
        with pytest.raises(NotFoundError):
            await services["poi"].get(poi.id)


class TestTourService:
    @pytest.fixture
    async def three_pois(self, services):
        # Thẳng hàng theo vĩ độ: A (gần nhất) - B - C (xa nhất)
        a = await services["poi"].create(poi_data("A", latitude=16.1000, priority=1), auto_localize=False)
        b = await services["poi"].create(poi_data("B", latitude=16.1010, priority=9), auto_localize=False)
        c = await services["poi"].create(poi_data("C", latitude=16.1020, priority=5), auto_localize=False)
        return a, b, c

    async def test_create_rejects_unknown_poi(self, services):
        with pytest.raises(BusinessRuleError):
            await services["tour"].create({"code": "T", "name": "T", "poi_ids": ["64b000000000000000000000"]})

    async def test_create_rejects_duplicate_poi(self, services, three_pois):
        a, *_ = three_pois
        with pytest.raises(BusinessRuleError):
            await services["tour"].create({"code": "T", "name": "T", "poi_ids": [a.id, a.id]})

    async def test_recommend_orders_by_nearest_neighbor(self, services, three_pois):
        route = await services["tour"].recommend(latitude=16.0990, longitude=108.2779, lang="vi")
        assert [s.poi.code for s in route.stops] == ["A", "B", "C"]
        assert route.stops[0].walk_distance_m == pytest.approx(111, abs=2)
        assert route.total_distance_m > 0 and route.total_minutes > 0

    async def test_recommend_with_custom_selection(self, services, three_pois):
        a, _, c = three_pois
        route = await services["tour"].recommend(latitude=16.1030, longitude=108.2779, lang="vi", poi_ids=[a.id, c.id])
        assert [s.poi.code for s in route.stops] == ["C", "A"]

    async def test_recommend_max_stops_uses_priority(self, services, three_pois):
        route = await services["tour"].recommend(latitude=16.0990, longitude=108.2779, lang="vi", max_stops=2)
        assert {s.poi.code for s in route.stops} == {"B", "C"}

    async def test_recommend_from_tour(self, services, three_pois):
        a, b, _ = three_pois
        tour = await services["tour"].create({"code": "T", "name": "T", "poi_ids": [b.id, a.id]})
        route = await services["tour"].recommend(latitude=16.0990, longitude=108.2779, lang="vi", tour_id=tour.id)
        assert [s.poi.code for s in route.stops] == ["A", "B"]

    async def test_recommend_invalid_selection(self, services, three_pois):
        with pytest.raises(BusinessRuleError):
            await services["tour"].recommend(latitude=16.1, longitude=108.2, lang="vi", poi_ids=["nope"])

    async def test_tour_translation_and_fallback(self, services, task_runner):
        tour = await services["tour"].create({"code": "T", "name": "Lộ trình", "poi_ids": []})
        await task_runner.wait_all()
        (item,) = await services["content"].list_tours("fr")
        assert item.name == "[fr] Lộ trình" and item.served_lang == "fr"
        await services["tour"].update(tour.id, {"name": "Tên mới"})
        stored = await services["tour"].get(tour.id)
        assert stored.translations == {}


class TestGeo:
    def test_haversine_known_distance(self):
        # 0.001 độ vĩ ~ 111 m
        assert geo.haversine_m(16.1, 108.2, 16.101, 108.2) == pytest.approx(111.2, abs=0.5)

    def test_walking_and_listening(self):
        assert geo.walking_minutes(600) == 10
        assert geo.estimate_listen_minutes("từ " * 300) == 2
