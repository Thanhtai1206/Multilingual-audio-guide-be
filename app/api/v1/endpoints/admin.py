"""
API quản trị (Admin dashboard).

Phân quyền:
- staff: đọc dữ liệu, tạo mã truy cập tiền mặt, xem thống kê.
- admin: toàn quyền (thêm/sửa/xóa POI, tour, ngôn ngữ, tài khoản...).
"""

from fastapi import APIRouter, Depends, Query

from app.api.deps import (
    get_access_service,
    get_ai_assistant_service,
    get_auth_service,
    get_current_admin,
    get_knowledge_service,
    get_language_service,
    get_localization_service,
    get_poi_service,
    get_state,
    get_stats_service,
    get_tour_service,
    require_admin_role,
)
from app.api.schemas.admin import (
    AccessSessionOut,
    AdminUserOut,
    ArticleCreate,
    ArticleOut,
    ArticleUpdate,
    CashCodeRequest,
    ChangePasswordRequest,
    ChatLogOut,
    EnhanceOut,
    EnhanceRequest,
    LanguageAdminOut,
    LanguageToggle,
    LocalizationOverviewOut,
    LocalizeAllRequest,
    LocalizeQueuedOut,
    LocalizeRequest,
    LoginOut,
    LoginRequest,
    ManualLocalizationRequest,
    PoiCreate,
    PoiOut,
    PoiUpdate,
    StatsOut,
    TourCreate,
    TourOut,
    TourUpdate,
    UserCreate,
    UserUpdate,
)
from app.api.schemas.common import COMMON_ERRORS, ApiResponse, Page, ok
from app.models.domain import AdminUser, Tour

# Router đăng nhập không cần token; các router còn lại đều yêu cầu đăng nhập
auth_router = APIRouter(prefix="/admin/auth", tags=["Admin - Auth"])
router = APIRouter(prefix="/admin", dependencies=[Depends(get_current_admin)], responses=COMMON_ERRORS)


def user_out(user: AdminUser) -> dict:
    return AdminUserOut.model_validate(user.model_dump()).model_dump()


def tour_out(tour: Tour) -> dict:
    return TourOut(
        **tour.model_dump(exclude={"translations"}), translated_languages=sorted(tour.translations.keys())
    ).model_dump()


# ================================================================== AUTH
@auth_router.post(
    "/login",
    response_model=ApiResponse[LoginOut],
    summary="Đăng nhập dashboard",
    responses={401: {"description": "Sai tài khoản hoặc mật khẩu"}},
)
async def login(body: LoginRequest, service=Depends(get_auth_service)):
    token, user = await service.login(body.username, body.password)
    return ok({"access_token": token, "token_type": "bearer", "user": user_out(user)})


@auth_router.get("/me", response_model=ApiResponse[AdminUserOut], summary="Thông tin tài khoản đang đăng nhập")
async def me(user: AdminUser = Depends(get_current_admin)):
    return ok(user_out(user))


@auth_router.post("/change-password", response_model=ApiResponse[None], summary="Đổi mật khẩu")
async def change_password(
    body: ChangePasswordRequest, user: AdminUser = Depends(get_current_admin), service=Depends(get_auth_service)
):
    await service.change_password(user, body.old_password, body.new_password)
    return ok(None, "Đã đổi mật khẩu")


# ================================================================== USERS (admin)
@router.get(
    "/users",
    response_model=ApiResponse[list[AdminUserOut]],
    tags=["Admin - Users"],
    dependencies=[Depends(require_admin_role)],
)
async def list_users(service=Depends(get_auth_service)):
    return ok([user_out(u) for u in await service.list_users()])


@router.post(
    "/users",
    response_model=ApiResponse[AdminUserOut],
    status_code=201,
    tags=["Admin - Users"],
    dependencies=[Depends(require_admin_role)],
)
async def create_user(body: UserCreate, service=Depends(get_auth_service)):
    return ok(user_out(await service.create_user(**body.model_dump())))


@router.patch("/users/{user_id}", response_model=ApiResponse[AdminUserOut], tags=["Admin - Users"])
async def update_user(
    user_id: str, body: UserUpdate, actor: AdminUser = Depends(require_admin_role), service=Depends(get_auth_service)
):
    return ok(user_out(await service.update_user(user_id, body.model_dump(exclude_unset=True), actor=actor)))


# ================================================================== POI
@router.get("/pois", response_model=ApiResponse[Page[PoiOut]], tags=["Admin - POI"], summary="Tìm/lọc POI")
async def search_pois(
    q: str | None = Query(None, max_length=100, description="Tìm theo tên hoặc mã"),
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    service=Depends(get_poi_service),
):
    items, total = await service.search(keyword=q, is_active=is_active, page=page, size=size)
    return ok({"items": [i.model_dump() for i in items], "total": total, "page": page, "size": size})


@router.post(
    "/pois",
    response_model=ApiResponse[PoiOut],
    status_code=201,
    tags=["Admin - POI"],
    summary="Tạo POI (tự động xếp hàng dịch + tạo audio)",
    dependencies=[Depends(require_admin_role)],
)
async def create_poi(body: PoiCreate, service=Depends(get_poi_service)):
    return ok((await service.create(body.model_dump())).model_dump(), "Đã tạo POI, đang dịch đa ngôn ngữ")


@router.get("/pois/{poi_id}", response_model=ApiResponse[PoiOut], tags=["Admin - POI"])
async def get_poi(poi_id: str, service=Depends(get_poi_service)):
    return ok((await service.get(poi_id)).model_dump())


@router.put(
    "/pois/{poi_id}",
    response_model=ApiResponse[PoiOut],
    tags=["Admin - POI"],
    summary="Sửa POI (đổi tên/mô tả -> tự dịch lại)",
    dependencies=[Depends(require_admin_role)],
)
async def update_poi(poi_id: str, body: PoiUpdate, service=Depends(get_poi_service)):
    return ok((await service.update(poi_id, body.model_dump(exclude_unset=True))).model_dump())


@router.delete(
    "/pois/{poi_id}",
    response_model=ApiResponse[None],
    tags=["Admin - POI"],
    summary="Xóa POI (xóa kèm bản dịch, gỡ khỏi tour)",
    dependencies=[Depends(require_admin_role)],
)
async def delete_poi(poi_id: str, service=Depends(get_poi_service)):
    await service.delete(poi_id)
    return ok(None, "Đã xóa POI")


# ================================================================== LOCALIZATION
@router.get(
    "/pois/{poi_id}/localizations",
    response_model=ApiResponse[list[LocalizationOverviewOut]],
    tags=["Admin - Localization"],
    summary="Trạng thái dịch/audio của POI theo từng ngôn ngữ",
)
async def localization_overview(poi_id: str, service=Depends(get_localization_service)):
    return ok([row.model_dump() for row in await service.overview(poi_id)])


@router.post(
    "/pois/{poi_id}/localize",
    response_model=ApiResponse[LocalizeQueuedOut],
    status_code=202,
    tags=["Admin - Localization"],
    summary="Xếp hàng dịch + tạo audio (chạy nền)",
    dependencies=[Depends(require_admin_role)],
)
async def localize_poi(poi_id: str, body: LocalizeRequest, service=Depends(get_localization_service)):
    queued = await service.schedule_poi(poi_id, body.languages, force=body.force)
    return ok({"queued": queued}, "Đã xếp hàng xử lý")


@router.put(
    "/pois/{poi_id}/localizations/{lang}",
    response_model=ApiResponse[LocalizationOverviewOut],
    tags=["Admin - Localization"],
    summary="Sửa tay bản dịch (không bị dịch máy ghi đè)",
    dependencies=[Depends(require_admin_role)],
)
async def update_localization(
    poi_id: str, lang: str, body: ManualLocalizationRequest, service=Depends(get_localization_service)
):
    await service.update_manual(
        poi_id, lang, name=body.name, description=body.description, regenerate_audio=body.regenerate_audio
    )
    rows = await service.overview(poi_id)
    return ok(next(r.model_dump() for r in rows if r.lang == lang))


@router.post(
    "/localize-all",
    response_model=ApiResponse[LocalizeQueuedOut],
    status_code=202,
    tags=["Admin - Localization"],
    summary="Dịch lại toàn bộ POI + tour",
    dependencies=[Depends(require_admin_role)],
)
async def localize_all(body: LocalizeAllRequest, service=Depends(get_localization_service)):
    return ok({"queued": await service.schedule_all(force=body.force)}, "Đã xếp hàng xử lý")


# ================================================================== TOURS
@router.get("/tours", response_model=ApiResponse[list[TourOut]], tags=["Admin - Tours"])
async def list_tours(service=Depends(get_tour_service)):
    return ok([tour_out(t) for t in await service.list_all()])


@router.post(
    "/tours",
    response_model=ApiResponse[TourOut],
    status_code=201,
    tags=["Admin - Tours"],
    dependencies=[Depends(require_admin_role)],
)
async def create_tour(body: TourCreate, service=Depends(get_tour_service)):
    return ok(tour_out(await service.create(body.model_dump())))


@router.put(
    "/tours/{tour_id}",
    response_model=ApiResponse[TourOut],
    tags=["Admin - Tours"],
    dependencies=[Depends(require_admin_role)],
)
async def update_tour(tour_id: str, body: TourUpdate, service=Depends(get_tour_service)):
    return ok(tour_out(await service.update(tour_id, body.model_dump(exclude_unset=True))))


@router.delete(
    "/tours/{tour_id}",
    response_model=ApiResponse[None],
    tags=["Admin - Tours"],
    dependencies=[Depends(require_admin_role)],
)
async def delete_tour(tour_id: str, service=Depends(get_tour_service)):
    await service.delete(tour_id)
    return ok(None, "Đã xóa lộ trình")


# ================================================================== LANGUAGES
@router.get("/languages", response_model=ApiResponse[list[LanguageAdminOut]], tags=["Admin - Languages"])
async def list_all_languages(service=Depends(get_language_service)):
    return ok([lang.model_dump() for lang in await service.list_languages(active_only=False)])


@router.patch(
    "/languages/{code}",
    response_model=ApiResponse[LanguageAdminOut],
    tags=["Admin - Languages"],
    summary="Bật/tắt ngôn ngữ",
    dependencies=[Depends(require_admin_role)],
)
async def toggle_language(code: str, body: LanguageToggle, service=Depends(get_language_service)):
    return ok((await service.set_active(code, body.is_active)).model_dump())


# ================================================================== ACCESS CODES
@router.post(
    "/access-codes",
    response_model=ApiResponse[list[AccessSessionOut]],
    status_code=201,
    tags=["Admin - Access"],
    summary="Nhân viên thu tiền mặt -> tạo mã truy cập cho khách",
)
async def create_cash_codes(
    body: CashCodeRequest, user: AdminUser = Depends(get_current_admin), service=Depends(get_access_service)
):
    sessions = await service.create_cash_codes(staff_id=user.id, quantity=body.quantity, note=body.note)
    return ok([s.model_dump() for s in sessions])


@router.get("/access-sessions", response_model=ApiResponse[Page[AccessSessionOut]], tags=["Admin - Access"])
async def list_sessions(
    status: str | None = Query(None, pattern="^(pending|paid|active|expired|cancelled)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    service=Depends(get_access_service),
):
    items, total = await service.search(status=status, page=page, size=size)
    return ok({"items": [i.model_dump() for i in items], "total": total, "page": page, "size": size})


@router.post(
    "/access-sessions/{session_id}/revoke",
    response_model=ApiResponse[AccessSessionOut],
    tags=["Admin - Access"],
    summary="Thu hồi quyền truy cập",
    dependencies=[Depends(require_admin_role)],
)
async def revoke_session(session_id: str, service=Depends(get_access_service)):
    return ok((await service.revoke(session_id)).model_dump())


# ================================================================== KNOWLEDGE BASE
@router.get("/knowledge", response_model=ApiResponse[list[ArticleOut]], tags=["Admin - Knowledge"])
async def list_articles(service=Depends(get_knowledge_service)):
    return ok([a.model_dump() for a in await service.list_all()])


@router.post(
    "/knowledge",
    response_model=ApiResponse[ArticleOut],
    status_code=201,
    tags=["Admin - Knowledge"],
    dependencies=[Depends(require_admin_role)],
)
async def create_article(body: ArticleCreate, service=Depends(get_knowledge_service)):
    return ok((await service.create(body.model_dump())).model_dump())


@router.put(
    "/knowledge/{article_id}",
    response_model=ApiResponse[ArticleOut],
    tags=["Admin - Knowledge"],
    dependencies=[Depends(require_admin_role)],
)
async def update_article(article_id: str, body: ArticleUpdate, service=Depends(get_knowledge_service)):
    return ok((await service.update(article_id, body.model_dump(exclude_unset=True))).model_dump())


@router.delete(
    "/knowledge/{article_id}",
    response_model=ApiResponse[None],
    tags=["Admin - Knowledge"],
    dependencies=[Depends(require_admin_role)],
)
async def delete_article(article_id: str, service=Depends(get_knowledge_service)):
    await service.delete(article_id)
    return ok(None, "Đã xóa bài viết")


# ================================================================== STATS / MONITORING / AI
@router.get(
    "/stats",
    response_model=ApiResponse[StatsOut],
    tags=["Admin - Monitoring"],
    summary="Số liệu tổng quan cho dashboard giám sát",
)
async def stats(service=Depends(get_stats_service), state=Depends(get_state)):
    overview = (await service.overview()).model_dump()
    return ok({**overview, "background_tasks": state.task_runner.pending_count})


@router.get(
    "/chat-logs",
    response_model=ApiResponse[list[ChatLogOut]],
    tags=["Admin - Monitoring"],
    summary="Các câu hỏi gần đây của du khách",
)
async def chat_logs(limit: int = Query(20, ge=1, le=100), service=Depends(get_stats_service)):
    return ok([log.model_dump() for log in await service.recent_chats(limit)])


@router.post(
    "/ai/enhance-description",
    response_model=ApiResponse[EnhanceOut],
    tags=["Admin - AI"],
    summary="AI gợi ý viết lại mô tả POI",
    dependencies=[Depends(require_admin_role)],
)
async def enhance_description(body: EnhanceRequest, service=Depends(get_ai_assistant_service)):
    return ok({"description": await service.enhance_description(body.name, body.description)})
