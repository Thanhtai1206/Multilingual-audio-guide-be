"""
Nghiệp vụ ĐA NGÔN NGỮ - trái tim của đề tài.

Pipeline cho mỗi POI x mỗi ngôn ngữ:
    Nội dung gốc (vi) -> dịch máy -> văn bản đích -> Edge-TTS -> file mp3 -> lưu poi_localizations

Quy tắc quan trọng:
- source_hash = MD5(tên + mô tả gốc). Bản dịch chỉ "còn hiệu lực" khi source_hash
  trùng với nội dung gốc hiện tại -> admin sửa mô tả thì bản dịch cũ tự động bị bỏ qua.
- Bản admin sửa tay (manual) không bị dịch máy ghi đè, trừ khi force=True.
- Lỗi 1 ngôn ngữ không làm hỏng các ngôn ngữ khác.
"""

import hashlib
import logging
from collections import defaultdict
from datetime import timedelta

from app.core.exceptions import BusinessRuleError, ExternalServiceError, NotFoundError
from app.core.security import utcnow
from app.models.domain import Language, LocalizationStatus, Poi, PoiLocalization, Tour, TranslatedBy
from app.models.views import LocalizationOverview
from app.services.poi_details import tips_hash

logger = logging.getLogger(__name__)

FAILED_RETRY_AFTER = timedelta(minutes=5)  # bản dịch lỗi: sau 5 phút khách chọn lại mới thử dịch lại
STALE_AFTER = timedelta(minutes=10)  # "đang dịch" quá 10 phút -> coi như kẹt (vd server tắt giữa chừng)
TOUR_REQUEST_INTERVAL = timedelta(minutes=2)  # cùng 1 tour + ngôn ngữ chỉ xếp hàng dịch 1 lần / 2 phút


def compute_source_hash(name: str, description: str) -> str:
    return hashlib.md5(f"{name}\n{description}".encode()).hexdigest()  # noqa: S324 - không dùng cho bảo mật


def is_fresh(loc: PoiLocalization | None, poi: Poi) -> bool:
    """Bản dịch dùng được: có đủ chữ và khớp nội dung gốc hiện tại."""
    return bool(
        loc is not None
        and loc.name
        and loc.description
        and loc.source_hash == compute_source_hash(poi.name, poi.description)
    )


def tips_fresh(loc: PoiLocalization | None, poi: Poi) -> bool:
    """Phần "lưu ý" có hash riêng: admin sửa lưu ý thì chỉ dịch lại lưu ý, không dịch lại mô tả + audio."""
    if not poi.tips:
        return True
    return bool(loc is not None and loc.tips and loc.tips_hash == tips_hash(poi.tips))


def is_complete(loc: PoiLocalization | None, poi: Poi) -> bool:
    return is_fresh(loc, poi) and tips_fresh(loc, poi)


class LocalizationService:
    def __init__(
        self,
        *,
        poi_repo,
        localization_repo,
        language_repo,
        tour_repo,
        translator,
        tts,
        storage,
        task_runner,
        source_lang: str = "vi",
    ):
        self.poi_repo = poi_repo
        self.localization_repo = localization_repo
        self.language_repo = language_repo
        self.tour_repo = tour_repo
        self.translator = translator
        self.tts = tts
        self.storage = storage
        self.task_runner = task_runner
        self.source_lang = source_lang

    # ------------------------------------------------------------------ helpers
    async def _get_poi(self, poi_id: str) -> Poi:
        poi = await self.poi_repo.get_by_id(poi_id)
        if poi is None:
            raise NotFoundError("Không tìm thấy POI", code="POI_NOT_FOUND")
        return poi

    async def _target_languages(self, langs: list[str] | None) -> list[Language]:
        active = await self.language_repo.list_all(active_only=True)
        if not langs:
            return active
        wanted = set(langs)
        unknown = wanted - {lang.code for lang in active}
        if unknown:
            raise BusinessRuleError(
                f"Ngôn ngữ không hỗ trợ hoặc đang tắt: {', '.join(sorted(unknown))}", code="LANGUAGE_NOT_SUPPORTED"
            )
        return [lang for lang in active if lang.code in wanted]

    async def _source_translator_code(self) -> str:
        source = await self.language_repo.get_by_code(self.source_lang)
        return source.translator_code if source else self.source_lang

    async def make_audio(self, text: str, voice: str) -> tuple[str | None, str | None]:
        """Tạo (hoặc dùng lại từ cache) file mp3. Trả về (url, lỗi)."""
        key = self.storage.audio_key(text, voice)
        if await self.storage.exists(key):
            return self.storage.url_for(key), None
        try:
            data = await self.tts.synthesize(text, voice=voice)
        except ExternalServiceError as exc:
            return None, exc.message
        return await self.storage.save(key, data), None

    # ------------------------------------------------------------------ pipeline
    async def localize_poi(self, poi_id: str, langs: list[str] | None = None, *, force: bool = False):
        """Dịch + tạo audio cho 1 POI (chạy đồng bộ). Trả về danh sách bản dịch sau xử lý."""
        poi = await self._get_poi(poi_id)
        languages = await self._target_languages(langs)
        source_code = await self._source_translator_code()
        results = []
        for language in languages:
            results.append(await self._localize_one(poi, language, source_code, force))
        return results

    async def _localize_one(self, poi: Poi, language: Language, source_code: str, force: bool) -> PoiLocalization:
        current_hash = compute_source_hash(poi.name, poi.description)
        existing = await self.localization_repo.get(poi.id, language.code)
        # Tên + mô tả đã dịch đúng nội dung hiện tại và đã có audio -> không cần dịch lại phần này.
        # (Không xét status: schedule_poi đặt "pending" trước khi chạy nhưng bản dịch cũ vẫn dùng tốt.)
        text_ready = not force and is_fresh(existing, poi) and bool(existing.audio_url)
        if text_ready:
            ready = {"status": LocalizationStatus.READY}
            # Đã đủ cả lưu ý -> bỏ qua (tiết kiệm thời gian & quota), chỉ trả trạng thái về "ready"
            if tips_fresh(existing, poi):
                if existing.status == LocalizationStatus.READY:
                    return existing
                return await self.localization_repo.upsert(poi.id, language.code, ready)
            # Chỉ thiếu phần lưu ý (vd admin vừa sửa lưu ý) -> dịch riêng phần đó, giữ nguyên mô tả + audio
            try:
                tips_fields = await self._translated_tips(poi, language, source_code)
            except ExternalServiceError as exc:
                logger.warning("Dịch lưu ý POI %s sang %s lỗi: %s", poi.code, language.code, exc.message)
                return await self.localization_repo.upsert(poi.id, language.code, ready)
            return await self.localization_repo.upsert(poi.id, language.code, {**ready, **tips_fields})

        await self.localization_repo.upsert(poi.id, language.code, {"status": LocalizationStatus.PROCESSING})

        # 1) Lấy văn bản theo ngôn ngữ đích
        keep_manual = (
            not force
            and existing is not None
            and existing.translated_by == TranslatedBy.MANUAL
            and is_fresh(existing, poi)
        )
        try:
            if language.code == self.source_lang:
                name, description, by = poi.name, poi.description, TranslatedBy.SOURCE
            elif keep_manual:
                name, description, by = existing.name, existing.description, TranslatedBy.MANUAL
            else:
                name = await self.translator.translate(poi.name, target=language.translator_code, source=source_code)
                description = await self.translator.translate(
                    poi.description, target=language.translator_code, source=source_code
                )
                by = TranslatedBy.MACHINE
            tips_fields = await self._translated_tips(poi, language, source_code)
        except ExternalServiceError as exc:
            # Giữ nguyên bản dịch cũ (nếu còn hợp lệ thì app vẫn dùng được), chỉ ghi nhận lỗi
            return await self.localization_repo.upsert(
                poi.id, language.code, {"status": LocalizationStatus.FAILED, "error": exc.message}
            )

        # 2) Tạo audio (lỗi audio không làm mất bản dịch chữ). Audio chỉ đọc tên + mô tả, không đọc lưu ý.
        audio_url, audio_error = await self.make_audio(f"{name}. {description}", language.tts_voice)
        return await self.localization_repo.upsert(
            poi.id,
            language.code,
            {
                "name": name,
                "description": description,
                "audio_url": audio_url,
                "status": LocalizationStatus.READY,
                "translated_by": by,
                "source_hash": current_hash,
                "error": audio_error,
                **tips_fields,
            },
        )

    async def _translated_tips(self, poi: Poi, language: Language, source_code: str) -> dict:
        """Bản dịch phần "lưu ý" + hash của bản gốc. POI không có lưu ý thì xóa bản dịch cũ."""
        if not poi.tips:
            return {"tips": None, "tips_hash": None}
        if language.code == self.source_lang:
            text = poi.tips
        else:
            text = await self.translator.translate(poi.tips, target=language.translator_code, source=source_code)
        return {"tips": text, "tips_hash": tips_hash(poi.tips)}

    # ------------------------------------------------------------------ chạy nền
    async def schedule_poi(self, poi_id: str, langs: list[str] | None = None, *, force: bool = False) -> int:
        """Xếp hàng dịch cho 1 POI. Trả về số ngôn ngữ được xếp hàng."""
        await self._get_poi(poi_id)
        languages = await self._target_languages(langs)
        for language in languages:
            await self.localization_repo.upsert(poi_id, language.code, {"status": LocalizationStatus.PENDING})
        codes = [lang.code for lang in languages]
        self.task_runner.submit(lambda: self.localize_poi(poi_id, codes, force=force), name=f"localize:{poi_id}")
        return len(codes)

    async def schedule_all(self, *, force: bool = False) -> int:
        pois = await self.poi_repo.list()
        for poi in pois:
            await self.schedule_poi(poi.id, force=force)
        tours = await self.tour_repo.list()
        for tour in tours:
            self.schedule_tour(tour.id)
        return len(pois)

    async def mark_outdated(self, poi_id: str) -> None:
        await self.localization_repo.mark_status_for_poi(poi_id, LocalizationStatus.OUTDATED)

    # ------------------------------------------------------------------ on-demand / thủ công
    async def ensure(self, poi_id: str, lang: str) -> PoiLocalization:
        """Tier 1.5 (theo presentation): khách cần ngay 1 ngôn ngữ chưa có -> dịch đồng bộ."""
        poi = await self._get_poi(poi_id)
        if not poi.is_active:
            raise NotFoundError("Không tìm thấy POI", code="POI_NOT_FOUND")
        existing = await self.localization_repo.get(poi_id, lang)
        if is_complete(existing, poi) and existing.audio_url:
            return existing
        results = await self.localize_poi(poi_id, [lang])
        return results[0]

    async def update_manual(
        self, poi_id: str, lang: str, *, name: str, description: str, regenerate_audio: bool = True
    ) -> PoiLocalization:
        poi = await self._get_poi(poi_id)
        language = (await self._target_languages([lang]))[0]
        if lang == self.source_lang:
            raise BusinessRuleError("Muốn sửa tiếng Việt hãy sửa trực tiếp nội dung POI", code="EDIT_SOURCE_VIA_POI")
        existing = await self.localization_repo.get(poi_id, lang)
        audio_url = existing.audio_url if existing else None
        error = None
        if regenerate_audio:
            audio_url, error = await self.make_audio(f"{name}. {description}", language.tts_voice)
        return await self.localization_repo.upsert(
            poi_id,
            lang,
            {
                "name": name,
                "description": description,
                "audio_url": audio_url,
                "status": LocalizationStatus.READY,
                "translated_by": TranslatedBy.MANUAL,
                "source_hash": compute_source_hash(poi.name, poi.description),
                "error": error,
            },
        )

    async def overview(self, poi_id: str) -> list[LocalizationOverview]:
        """Bảng trạng thái dịch của 1 POI cho mọi ngôn ngữ đang bật (cho admin)."""
        poi = await self._get_poi(poi_id)
        languages = await self.language_repo.list_all(active_only=True)
        by_lang = {loc.lang: loc for loc in await self.localization_repo.list_for_poi(poi_id)}
        rows = []
        for language in languages:
            loc = by_lang.get(language.code)
            rows.append(
                LocalizationOverview(
                    lang=language.code,
                    language_name=language.native_name,
                    status=loc.status if loc else "missing",
                    is_fresh=is_fresh(loc, poi),
                    translated_by=loc.translated_by if loc else None,
                    has_audio=bool(loc and loc.audio_url),
                    audio_url=loc.audio_url if loc else None,
                    name=loc.name if loc else None,
                    description=loc.description if loc else None,
                    error=loc.error if loc else None,
                )
            )
        return rows

    # ------------------------------------------------------------------ khách chọn ngôn ngữ
    async def request_language(self, lang: str) -> int:
        """
        Khách vừa chọn 1 ngôn ngữ: xếp hàng dịch NGAY (chạy nền) mọi POI/tour còn thiếu bản dịch
        của ngôn ngữ đó. Không bắt khách chờ - app hiển thị bản dự phòng rồi tự cập nhật.
        Trả về số POI đang chờ dịch (để app biết cần tải lại).
        """
        if lang == self.source_lang:
            return 0
        language = await self.language_repo.get_by_code(lang)
        if language is None or not language.is_active:
            return 0
        pois = await self.poi_repo.list_active()
        locs = {loc.poi_id: loc for loc in await self.localization_repo.list_for_langs([lang], [p.id for p in pois])}
        now = utcnow()
        retry_after = now - FAILED_RETRY_AFTER
        stale_before = now - STALE_AFTER
        pending = 0
        for poi in pois:
            loc = locs.get(poi.id)
            if is_complete(loc, poi):
                continue
            in_progress = loc and loc.status in (LocalizationStatus.PENDING, LocalizationStatus.PROCESSING)
            if in_progress and loc.updated_at > stale_before:
                pending += 1  # đang được dịch rồi, không xếp hàng lần nữa
                continue
            if loc and loc.status == LocalizationStatus.FAILED and loc.updated_at > retry_after:
                continue  # vừa lỗi xong (vd mất mạng) -> chờ một lúc rồi mới thử lại
            await self.localization_repo.upsert(poi.id, lang, {"status": LocalizationStatus.PENDING})
            self.task_runner.submit(
                lambda poi_id=poi.id: self.localize_poi(poi_id, [lang]), name=f"localize:{poi.id}:{lang}"
            )
            pending += 1
        for tour in await self.tour_repo.list_active():
            requested = tour.translation_requested_at.get(lang)
            # App tải lại vài lần trong lúc chờ -> chỉ xếp hàng dịch tour 1 lần / 2 phút (mốc lưu trong DB)
            if lang not in tour.translations and (requested is None or requested < now - TOUR_REQUEST_INTERVAL):
                await self.tour_repo.mark_translation_requested(tour.id, lang)
                self.schedule_tour(tour.id, [lang])
        return pending

    async def recover_unfinished(self) -> int:
        """
        Gọi lúc khởi động: server bị tắt khi đang dịch -> các bản dịch kẹt ở pending/processing.
        Xếp hàng chạy lại để không có bản dịch nào bị "treo" vĩnh viễn. Trả về số POI được khôi phục.
        """
        unfinished = await self.localization_repo.list_by_status(
            [LocalizationStatus.PENDING, LocalizationStatus.PROCESSING]
        )
        by_poi: dict[str, list[str]] = defaultdict(list)
        for loc in unfinished:
            by_poi[loc.poi_id].append(loc.lang)
        active_codes = {lang.code for lang in await self.language_repo.list_all(active_only=True)}
        recovered = 0
        for poi_id, langs in by_poi.items():
            langs = [code for code in langs if code in active_codes]
            if not langs or await self.poi_repo.get_by_id(poi_id) is None:
                continue
            self.task_runner.submit(
                lambda poi_id=poi_id, langs=langs: self.localize_poi(poi_id, langs), name=f"recover:{poi_id}"
            )
            recovered += 1
        if recovered:
            logger.info("Khôi phục %d POI có bản dịch đang dở sau khi khởi động lại", recovered)
        return recovered

    # ------------------------------------------------------------------ tour
    async def localize_tour(self, tour_id: str, langs: list[str] | None = None) -> Tour | None:
        tour = await self.tour_repo.get_by_id(tour_id)
        if tour is None:
            return None
        source_code = await self._source_translator_code()
        # Giữ các bản dịch đã có, chỉ thêm/ghi đè ngôn ngữ vừa dịch
        translations: dict[str, dict] = {code: tr.model_dump() for code, tr in tour.translations.items()}
        for language in await self.language_repo.list_all(active_only=True):
            if language.code == self.source_lang or (langs and language.code not in langs):
                continue
            try:
                name = await self.translator.translate(tour.name, target=language.translator_code, source=source_code)
                desc = (
                    await self.translator.translate(
                        tour.description, target=language.translator_code, source=source_code
                    )
                    if tour.description
                    else None
                )
                translations[language.code] = {"name": name, "description": desc}
            except ExternalServiceError:
                continue  # thiếu bản dịch -> app tự dùng fallback
        return await self.tour_repo.update(tour_id, {"translations": translations})

    def schedule_tour(self, tour_id: str, langs: list[str] | None = None) -> None:
        self.task_runner.submit(lambda: self.localize_tour(tour_id, langs), name=f"localize-tour:{tour_id}")
