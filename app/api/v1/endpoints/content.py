"""API nội dung cho du khách (cần access token)."""

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api.deps import (
    VisitorContext,
    get_chat_service,
    get_content_service,
    get_language_service,
    get_localization_service,
    get_poi_insights_service,
    get_stats_service,
    get_tour_service,
    get_visitor,
)
from app.api.schemas.common import COMMON_ERRORS, ApiResponse, ok
from app.api.schemas.content import (
    ChatAnswerOut,
    ChatRequest,
    ContentBundleOut,
    EventRequest,
    LocalizedPoiOut,
    LocalizedTourOut,
    PoiInsightsOut,
    RecommendedRouteOut,
    RecommendRequest,
)

router = APIRouter(dependencies=[Depends(get_visitor)], responses=COMMON_ERRORS)

LangQuery = Query("vi", min_length=2, max_length=10, description="Mã ngôn ngữ, vd: vi, en, ja")


@router.get(
    "/content/bundle",
    response_model=ApiResponse[ContentBundleOut],
    tags=["Content"],
    summary="Tải TOÀN BỘ dữ liệu 1 lần (PRD Key Logic 1), hỗ trợ ETag/304",
    responses={304: {"description": "Dữ liệu không đổi so với phiên bản client đang có"}},
)
async def get_bundle(
    response: Response,
    lang: str = LangQuery,
    if_none_match: str | None = Header(None, alias="If-None-Match"),
    content_service=Depends(get_content_service),
    language_service=Depends(get_language_service),
    localization_service=Depends(get_localization_service),
):
    resolved = await language_service.resolve_code(lang)
    # Khách chọn ngôn ngữ chưa dịch -> xếp hàng dịch ngay ở nền; app tải lại khi số này về 0
    pending = await localization_service.request_language(resolved)
    version = await content_service.compute_version(resolved)
    etag = f'W/"{version}"'
    headers = {"ETag": etag, "X-Translation-Pending": str(pending), "Cache-Control": "no-cache"}
    if if_none_match == etag:
        return Response(status_code=304, headers=headers)
    bundle = await content_service.build_bundle(resolved)
    response.headers.update(headers)
    return ok({**bundle.model_dump(), "pending_translations": pending})


@router.get(
    "/pois", response_model=ApiResponse[list[LocalizedPoiOut]], tags=["Content"], summary="Danh sách POI theo ngôn ngữ"
)
async def list_pois(lang: str = LangQuery, service=Depends(get_content_service)):
    return ok([p.model_dump() for p in await service.list_pois(lang)])


@router.get(
    "/pois/nearby",
    response_model=ApiResponse[list[LocalizedPoiOut]],
    tags=["Content"],
    summary="POI gần vị trí GPS, sắp xếp gần -> xa",
)
async def nearby_pois(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius: float = Query(300, ge=10, le=5000, description="Bán kính tìm (mét)"),
    lang: str = LangQuery,
    service=Depends(get_content_service),
):
    return ok([p.model_dump() for p in await service.nearby(lat, lng, radius, lang)])


@router.get("/pois/{poi_id}", response_model=ApiResponse[LocalizedPoiOut], tags=["Content"], summary="Chi tiết 1 POI")
async def get_poi(poi_id: str, lang: str = LangQuery, service=Depends(get_content_service)):
    return ok((await service.get_poi(poi_id, lang)).model_dump())


@router.get(
    "/pois/{poi_id}/insights",
    response_model=ApiResponse[PoiInsightsOut],
    tags=["Content"],
    summary="Đang mở/đóng cửa + khung giờ đông khách (tính theo giờ hiện tại, không cache)",
)
async def poi_insights(poi_id: str, response: Response, service=Depends(get_poi_insights_service)):
    response.headers["Cache-Control"] = "no-store"
    return ok((await service.get(poi_id)).model_dump())


@router.post(
    "/pois/{poi_id}/localizations/{lang}/ensure",
    response_model=ApiResponse[LocalizedPoiOut],
    tags=["Content"],
    summary="Dịch + tạo audio NGAY cho 1 ngôn ngữ chưa có (on-demand)",
)
async def ensure_localization(
    poi_id: str,
    lang: str,
    localization_service=Depends(get_localization_service),
    content_service=Depends(get_content_service),
    language_service=Depends(get_language_service),
):
    await language_service.get_active(lang)
    await localization_service.ensure(poi_id, lang)
    return ok((await content_service.get_poi(poi_id, lang)).model_dump())


@router.get("/tours", response_model=ApiResponse[list[LocalizedTourOut]], tags=["Tours"], summary="Các lộ trình có sẵn")
async def list_tours(lang: str = LangQuery, service=Depends(get_content_service)):
    return ok([t.model_dump() for t in await service.list_tours(lang)])


@router.post(
    "/tours/recommend",
    response_model=ApiResponse[RecommendedRouteOut],
    tags=["Tours"],
    summary="Gợi ý thứ tự tham quan từ vị trí hiện tại",
)
async def recommend_route(body: RecommendRequest, service=Depends(get_tour_service)):
    route = await service.recommend(
        latitude=body.latitude,
        longitude=body.longitude,
        lang=body.lang,
        poi_ids=body.poi_ids,
        tour_id=body.tour_id,
        max_stops=body.max_stops,
    )
    return ok(route.model_dump())


@router.post(
    "/chat",
    response_model=ApiResponse[ChatAnswerOut],
    tags=["Chatbot"],
    summary="Hỏi chatbot (RAG) bằng ngôn ngữ tự nhiên",
    responses={429: {"description": "Vượt giới hạn câu hỏi trong ngày"}},
)
async def chat(body: ChatRequest, visitor: VisitorContext = Depends(get_visitor), service=Depends(get_chat_service)):
    answer = await service.ask(question=body.question, lang=body.lang, session_id=visitor.session_id)
    return ok(answer.model_dump())


@router.post(
    "/events",
    response_model=ApiResponse[None],
    status_code=201,
    tags=["Analytics"],
    summary="Ghi nhận hành vi (xem POI, nghe audio, vào vùng geofence)",
)
async def record_event(
    body: EventRequest, visitor: VisitorContext = Depends(get_visitor), service=Depends(get_stats_service)
):
    await service.record_event(poi_id=body.poi_id, event_type=body.type, lang=body.lang, session_id=visitor.session_id)
    return ok(None, "Đã ghi nhận")
