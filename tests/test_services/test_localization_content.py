"""Test nghiệp vụ đa ngôn ngữ: pipeline dịch + audio, fallback 3 tầng, ETag version."""

import pytest

from app.core.exceptions import BusinessRuleError, NotFoundError
from tests.conftest import poi_data


@pytest.fixture
async def poi(services):
    return await services["poi"].create(poi_data("QUAN_AM"), auto_localize=False)


class TestLocalizationPipeline:
    async def test_localize_creates_text_and_audio(self, services, poi, translator, tts):
        results = await services["localization"].localize_poi(poi.id, ["vi", "en", "ja"])
        by_lang = {r.lang: r for r in results}
        assert by_lang["vi"].name == poi.name and by_lang["vi"].translated_by == "source"
        assert by_lang["en"].name == f"[en] {poi.name}"
        assert by_lang["ja"].translated_by == "machine"
        assert all(r.status == "ready" and r.audio_url.startswith("/media/audio/") for r in results)
        assert tts.calls == 3

    async def test_second_run_is_skipped(self, services, poi, translator, tts):
        await services["localization"].localize_poi(poi.id, ["en"])
        calls = len(translator.calls)
        await services["localization"].localize_poi(poi.id, ["en"])
        assert len(translator.calls) == calls  # không dịch lại khi nội dung không đổi
        assert tts.calls == 1

    async def test_audio_is_cached_by_content(self, services, poi, tts):
        await services["localization"].localize_poi(poi.id, ["en"])
        await services["localization"].localize_poi(poi.id, ["en"], force=True)
        assert tts.calls == 1  # cùng nội dung + giọng -> dùng lại file mp3

    async def test_translation_failure_isolated_per_language(self, services, poi, translator):
        translator.fail_langs = {"ja"}
        results = {r.lang: r for r in await services["localization"].localize_poi(poi.id, ["en", "ja"])}
        assert results["en"].status == "ready"
        assert results["ja"].status == "failed" and results["ja"].error

    async def test_tts_failure_keeps_text(self, services, poi, tts):
        tts.fail = True
        (loc,) = await services["localization"].localize_poi(poi.id, ["en"])
        assert loc.status == "ready" and loc.name and loc.audio_url is None and loc.error

    async def test_unknown_language_rejected(self, services, poi):
        with pytest.raises(BusinessRuleError):
            await services["localization"].localize_poi(poi.id, ["xx"])

    async def test_manual_translation_not_overwritten(self, services, poi):
        await services["localization"].update_manual(poi.id, "en", name="Guan Yin Statue", description="Manual.")
        (loc,) = await services["localization"].localize_poi(poi.id, ["en"])
        assert loc.name == "Guan Yin Statue" and loc.translated_by == "manual"

    async def test_cannot_manually_edit_source_language(self, services, poi):
        with pytest.raises(BusinessRuleError):
            await services["localization"].update_manual(poi.id, "vi", name="x", description="y")

    async def test_schedule_marks_pending_then_runs(self, services, poi, task_runner):
        queued = await services["localization"].schedule_poi(poi.id, ["en", "ja"])
        assert queued == 2
        overview = {r.lang: r for r in await services["localization"].overview(poi.id)}
        assert overview["en"].status == "pending"
        assert overview["ko"].status == "missing"
        await task_runner.wait_all()
        overview = {r.lang: r for r in await services["localization"].overview(poi.id)}
        assert overview["en"].status == "ready" and overview["en"].is_fresh

    async def test_ensure_on_demand(self, services, poi):
        loc = await services["localization"].ensure(poi.id, "ko")
        assert loc.lang == "ko" and loc.status == "ready"

    async def test_ensure_inactive_poi_not_found(self, services, poi):
        await services["poi"].update(poi.id, {"is_active": False})
        with pytest.raises(NotFoundError):
            await services["localization"].ensure(poi.id, "ko")


class TestContentFallback:
    async def test_fallback_to_vietnamese_when_nothing_translated(self, services, poi):
        (item,) = await services["content"].list_pois("ja")
        assert item.served_lang == "vi" and item.is_fallback and item.name == poi.name
        assert item.audio_url is None

    async def test_fallback_to_english(self, services, poi):
        await services["localization"].localize_poi(poi.id, ["en"])
        (item,) = await services["content"].list_pois("ja")
        assert item.served_lang == "en" and item.is_fallback
        assert item.name.startswith("[en]")

    async def test_exact_language(self, services, poi):
        await services["localization"].localize_poi(poi.id, ["ja"])
        (item,) = await services["content"].list_pois("ja")
        assert item.served_lang == "ja" and not item.is_fallback and item.audio_url

    async def test_stale_translation_ignored_after_source_change(self, services, poi, task_runner):
        await services["localization"].localize_poi(poi.id, ["ja"])
        await services["poi"].update(poi.id, {"description": "Mô tả mới hoàn toàn."}, auto_localize=False)
        (item,) = await services["content"].list_pois("ja")
        assert item.served_lang == "vi" and item.description == "Mô tả mới hoàn toàn."

    async def test_unsupported_language_falls_back_to_english(self, services, poi):
        (item,) = await services["content"].list_pois("xx")
        assert item.requested_lang == "en"

    async def test_nearby_sorted_and_filtered(self, services):
        await services["poi"].create(poi_data("NEAR", latitude=16.1003, longitude=108.2779), auto_localize=False)
        await services["poi"].create(poi_data("MID", latitude=16.1010, longitude=108.2779), auto_localize=False)
        await services["poi"].create(poi_data("FAR", latitude=16.2000, longitude=108.2779), auto_localize=False)
        result = await services["content"].nearby(16.1003, 108.2779, 300, "vi")
        assert [p.code for p in result] == ["NEAR", "MID"]
        assert result[0].distance_m < 1

    async def test_version_changes_when_content_changes(self, services, poi):
        v1 = await services["content"].compute_version("en")
        assert v1 == await services["content"].compute_version("en")
        await services["poi"].update(poi.id, {"name": "Tên khác"}, auto_localize=False)
        assert await services["content"].compute_version("en") != v1

    async def test_bundle_contains_everything(self, services, poi):
        bundle = await services["content"].build_bundle("en")
        assert bundle.lang == "en" and len(bundle.pois) == 1 and len(bundle.languages) == 16


class TestRequestLanguage:
    """Khách chọn ngôn ngữ chưa dịch -> hệ thống tự xếp hàng dịch (không cần admin)."""

    async def test_schedules_missing_translations(self, services, poi, task_runner):
        assert await services["localization"].request_language("ja") == 1
        (item,) = await services["content"].list_pois("ja")
        assert item.is_fallback  # chưa dịch xong -> vẫn hiển thị bản dự phòng
        await task_runner.wait_all()
        (item,) = await services["content"].list_pois("ja")
        assert item.served_lang == "ja" and item.audio_url
        assert await services["localization"].request_language("ja") == 0  # đã có -> không dịch lại

    async def test_no_duplicate_scheduling_while_pending(self, services, poi, task_runner):
        await services["localization"].request_language("ko")
        assert await services["localization"].request_language("ko") == 1
        assert task_runner.pending_count == 1

    async def test_source_and_unknown_language_skipped(self, services, poi, task_runner):
        assert await services["localization"].request_language("vi") == 0
        assert await services["localization"].request_language("xx") == 0
        assert task_runner.pending_count == 0

    async def test_recent_failure_not_retried_immediately(self, services, poi, task_runner, translator):
        translator.fail_langs = {"fr"}
        await services["localization"].request_language("fr")
        await task_runner.wait_all()
        assert await services["localization"].request_language("fr") == 0
        assert task_runner.pending_count == 0

    async def test_tour_translated_only_for_requested_language(self, services, poi, task_runner):
        tour = await services["tour"].create({"code": "TQ", "name": "Lộ trình", "poi_ids": [poi.id]})
        task_runner._queue.clear()  # bỏ tác vụ dịch toàn bộ lúc tạo tour
        await services["localization"].request_language("de")
        await task_runner.wait_all()
        stored = await services["tour"].get(tour.id)
        assert list(stored.translations) == ["de"]


class TestUiTextService:
    @pytest.fixture
    def ui(self, repos, translator):
        from app.repositories.repositories import UiTranslationRepository
        from app.services.ui_text_service import UiTextService

        return UiTextService(
            ui_repo=UiTranslationRepository(repos["poi"].db), language_repo=repos["language"], translator=translator
        )

    async def test_vi_en_builtin(self, ui, seeded_db, translator):
        assert (await ui.get_strings("vi"))[1]["tabMap"] == "Bản đồ"
        assert (await ui.get_strings("en"))[1]["tabMap"] == "Map"
        assert translator.calls == []

    async def test_translates_once_then_cached(self, ui, seeded_db, translator):
        lang, strings, fallback = await ui.get_strings("ja")
        assert lang == "ja" and not fallback and strings["tabMap"] == "[ja] Map"
        calls = len(translator.calls)
        await ui.get_strings("ja")
        assert len(translator.calls) == calls

    async def test_translation_failure_returns_english(self, ui, seeded_db, translator):
        translator.fail_langs = {"ko"}
        lang, strings, fallback = await ui.get_strings("ko")
        assert fallback and strings["tabMap"] == "Map"

    async def test_unknown_language(self, ui, seeded_db):
        assert (await ui.get_strings("xx"))[2] is True


class TestPersistence:
    """Những thứ trước đây nằm trong RAM nay lưu trong MongoDB."""

    async def test_recover_unfinished_after_restart(self, services, poi, task_runner, repos):
        await services["localization"].schedule_poi(poi.id, ["en", "ja"])
        task_runner._queue.clear()  # mô phỏng server tắt: tác vụ nền trong RAM mất
        assert await services["localization"].recover_unfinished() == 1
        await task_runner.wait_all()
        statuses = {loc.lang: loc.status for loc in await repos["localization"].list_for_poi(poi.id)}
        assert statuses == {"en": "ready", "ja": "ready"}

    async def test_stale_pending_is_rescheduled(self, services, poi, task_runner, repos):
        from datetime import timedelta

        await services["localization"].request_language("ko")
        task_runner._queue.clear()
        loc = await repos["localization"].get(poi.id, "ko")
        await repos["localization"].collection.update_one(
            {"_id": __import__("bson").ObjectId(loc.id)}, {"$set": {"updated_at": loc.updated_at - timedelta(hours=1)}}
        )
        assert await services["localization"].request_language("ko") == 1
        assert task_runner.pending_count == 1  # bị kẹt quá lâu -> xếp hàng lại

    async def test_tour_request_time_stored_in_db(self, services, poi, task_runner, repos):
        tour = await services["tour"].create({"code": "T1", "name": "Tour", "poi_ids": [poi.id]})
        task_runner._queue.clear()
        await services["localization"].request_language("fr")
        await services["localization"].request_language("fr")
        assert sum(1 for _ in task_runner._queue) == 2  # 1 POI + 1 tour (lần 2 không xếp thêm)
        stored = await repos["tour"].get_by_id(tour.id)
        assert "fr" in stored.translation_requested_at


class TestMongoMediaStorage:
    async def test_save_get_exists(self, db):
        from app.integrations.media_storage import MongoMediaStorage

        storage = MongoMediaStorage(db, "/media")
        key = storage.audio_key("Xin chào", "vi-VN-HoaiMyNeural")
        assert not await storage.exists(key)
        assert await storage.save(key, b"ID3abc") == f"/media/{key}"
        assert await storage.exists(key)
        assert await storage.get(key) == (b"ID3abc", "audio/mpeg")
        assert await storage.get("audio/khong-co.mp3") is None

    async def test_local_storage_blocks_path_traversal(self, tmp_path):
        from app.integrations.media_storage import LocalMediaStorage

        storage = LocalMediaStorage(str(tmp_path / "m"), "/media")
        assert await storage.get("../../etc/passwd") is None
        with pytest.raises(ValueError):
            await storage.save("../evil.mp3", b"x")
