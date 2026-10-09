"""
Trang CỔNG THANH TOÁN GIẢ LẬP (thay Payoo khi demo).

Trang này đóng vai "bên thứ 3": khi khách bấm Thanh toán, nó tự ký payload rồi gọi
PaymentService.handle_webhook - đúng như cổng thật gọi webhook về backend -
sau đó chuyển khách về app kèm mã truy cập.
Chỉ bật khi PAYMENT_PROVIDER=mock và ẩn khỏi Swagger.
"""

import html
import uuid

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api.deps import get_payment_service, get_state
from app.core.exceptions import AppError

router = APIRouter(prefix="/mock-gateway", include_in_schema=False)

PAGE = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Cổng thanh toán (giả lập)</title>
<style>body{{font-family:Arial,sans-serif;margin:0;padding:16px;color:#222}}
.box{{max-width:360px;margin:20px auto;border:1px solid #aaa;padding:14px 16px}}
.warn{{background:#fff3c4;border:1px solid #d8bd55;padding:4px 6px;font-size:12px}}
.amount{{font-size:26px;font-weight:bold;margin:12px 0}}
button{{display:block;width:100%;padding:9px;margin-top:8px;font-size:15px;border:1px solid #888;cursor:pointer}}
.pay{{background:#2e7d32;color:#fff;border-color:#1b5e20}}</style></head><body><div class="box">
<div class="warn">Môi trường giả lập - không trừ tiền thật</div>
<h3>Thanh toán vé thuyết minh</h3><div style="font-size:12px;color:#666">Mã giao dịch: {payment_id}</div>
<div class="amount">{amount} đ</div>{body}</div></body></html>"""


@router.get("/{payment_id}", response_class=HTMLResponse)
async def payment_page(payment_id: str, service=Depends(get_payment_service)):
    try:
        payment, _ = await service.get_payment(payment_id)
    except AppError as exc:
        return HTMLResponse(
            PAGE.format(payment_id=html.escape(payment_id), amount="—", body=f"<p>{html.escape(exc.message)}</p>"),
            status_code=404,
        )
    if payment.status != "pending":
        body = f"<p>Giao dịch đã xử lý: <b>{payment.status}</b></p><a href='/'>Về ứng dụng</a>"
    else:
        body = (
            f"<form method='post' action='/mock-gateway/{payment.id}/complete'>"
            "<button class='pay' name='result' value='success'>Thanh toán thành công</button>"
            "<button class='cancel' name='result' value='failed'>Hủy / thất bại</button></form>"
        )
    return HTMLResponse(PAGE.format(payment_id=payment.id, amount=f"{payment.amount:,}".replace(",", "."), body=body))


@router.post("/{payment_id}/complete")
async def complete_payment(
    payment_id: str, result: str = Form(...), service=Depends(get_payment_service), state=Depends(get_state)
):
    payload = {
        "payment_id": payment_id,
        "status": "success" if result == "success" else "failed",
        "provider_ref": f"MOCK-{uuid.uuid4().hex[:10].upper()}",
    }
    signature = state.payment_gateway.sign(payload)  # cổng thật sẽ tự ký bằng secret chung
    payment = await service.handle_webhook(payload, signature)
    _, session = await service.get_payment(payment.id)
    if payment.status == "success":
        return RedirectResponse(f"/?payment=success&code={session.code}", status_code=303)
    return RedirectResponse("/?payment=failed", status_code=303)
