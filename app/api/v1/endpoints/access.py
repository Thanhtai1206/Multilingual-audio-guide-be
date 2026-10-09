"""
API công khai: ngôn ngữ, mua quyền truy cập, webhook thanh toán.

Quy tắc của lớp API: chỉ nhận request -> validate (Pydantic tự làm) -> gọi Service -> trả response.
KHÔNG có logic nghiệp vụ, KHÔNG truy cập DB trực tiếp.
"""

from fastapi import APIRouter, Depends, Header

from app.api.deps import (
    VisitorContext,
    get_access_service,
    get_language_service,
    get_payment_service,
    get_settings_dep,
    get_ui_text_service,
    get_visitor,
)
from app.api.schemas.common import COMMON_ERRORS, ApiResponse, ok
from app.api.schemas.content import (
    AccessInfoOut,
    AccessTokenOut,
    LanguageOut,
    OnlinePaymentOut,
    RedeemRequest,
    UiStringsOut,
    VisitorSessionOut,
    WebhookRequest,
)

router = APIRouter()


@router.get(
    "/languages",
    response_model=ApiResponse[list[LanguageOut]],
    tags=["Public"],
    summary="Danh sách ngôn ngữ đang hỗ trợ",
)
async def list_languages(service=Depends(get_language_service)):
    languages = await service.list_languages(active_only=True)
    return ok([LanguageOut.model_validate(lang.model_dump()) for lang in languages])


@router.get(
    "/ui-strings/{lang}",
    response_model=ApiResponse[UiStringsOut],
    tags=["Public"],
    summary="Chuỗi giao diện app theo ngôn ngữ (tự dịch lần đầu, sau đó lưu lại)",
)
async def ui_strings(lang: str, service=Depends(get_ui_text_service)):
    served, strings, is_fallback = await service.get_strings(lang)
    return ok(UiStringsOut(lang=served, strings=strings, is_fallback=is_fallback))


@router.get(
    "/access/info",
    response_model=ApiResponse[AccessInfoOut],
    tags=["Access"],
    summary="Giá và phương thức mua quyền truy cập",
)
async def access_info(settings=Depends(get_settings_dep)):
    return ok(
        AccessInfoOut(
            price_vnd=settings.ACCESS_PRICE_VND,
            access_hours=settings.VISITOR_TOKEN_HOURS,
            methods=["online", "cash"],
            access_required=settings.ACCESS_REQUIRED,
        )
    )


@router.post(
    "/access/online",
    response_model=ApiResponse[OnlinePaymentOut],
    status_code=201,
    tags=["Access"],
    summary="Bắt đầu thanh toán online -> nhận URL cổng thanh toán",
)
async def start_online_payment(service=Depends(get_payment_service)):
    _, payment, url = await service.start_online_payment()
    return ok(
        OnlinePaymentOut(payment_id=payment.id, payment_url=url, amount=payment.amount, currency=payment.currency)
    )


@router.post(
    "/access/token",
    response_model=ApiResponse[AccessTokenOut],
    tags=["Access"],
    summary="Đổi mã truy cập (online hoặc tiền mặt) lấy access token",
    responses={**COMMON_ERRORS, 409: {"description": "PAYMENT_PENDING - thanh toán chưa xong, thử lại sau"}},
)
async def redeem_code(body: RedeemRequest, service=Depends(get_access_service)):
    token, session = await service.redeem(body.code)
    return ok(AccessTokenOut(access_token=token, expires_at=session.access_expires_at))


@router.get(
    "/access/me",
    response_model=ApiResponse[VisitorSessionOut],
    tags=["Access"],
    summary="Thông tin quyền truy cập hiện tại",
    responses=COMMON_ERRORS,
)
async def my_access(visitor: VisitorContext = Depends(get_visitor)):
    return ok(
        VisitorSessionOut(
            session_id=visitor.session_id,
            status=visitor.status,
            access_expires_at=visitor.access_expires_at,
            is_admin_preview=visitor.is_admin_preview,
        )
    )


@router.post(
    "/payments/webhook",
    response_model=ApiResponse[dict],
    tags=["Access"],
    summary="Cổng thanh toán gọi để báo kết quả (có chữ ký HMAC)",
)
async def payment_webhook(
    body: WebhookRequest, x_signature: str = Header(..., alias="X-Signature"), service=Depends(get_payment_service)
):
    payment = await service.handle_webhook(body.model_dump(), x_signature)
    return ok({"payment_id": payment.id, "status": payment.status})
