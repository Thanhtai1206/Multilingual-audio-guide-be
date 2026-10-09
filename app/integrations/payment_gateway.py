"""
Cổng thanh toán.

PRD dùng Payoo, nhưng sinh viên không có tài khoản merchant nên ta làm
MockPaymentGateway mô phỏng đúng quy trình thật:
  1. Backend tạo URL thanh toán -> 2. Khách thanh toán trên trang cổng
  3. Cổng gọi webhook (có chữ ký HMAC) báo kết quả -> 4. Cổng redirect khách về app.
Khi có Payoo/VNPay thật chỉ cần viết class mới cùng các hàm này.
"""

import json
from typing import Protocol

from app.core.security import sign_payload, verify_signature


class PaymentGateway(Protocol):
    name: str

    def create_payment_url(self, payment_id: str, amount: int) -> str: ...

    def verify_webhook(self, payload: dict, signature: str) -> bool: ...


def canonical_json(payload: dict) -> str:
    """Chuỗi JSON chuẩn hóa (sắp xếp key) để 2 bên ký cùng 1 nội dung."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class MockPaymentGateway:
    name = "mock"

    def __init__(self, base_url: str, secret: str):
        self.base_url = base_url.rstrip("/")
        self.secret = secret

    def create_payment_url(self, payment_id: str, amount: int) -> str:
        return f"{self.base_url}/mock-gateway/{payment_id}"

    def sign(self, payload: dict) -> str:
        return sign_payload(canonical_json(payload), self.secret)

    def verify_webhook(self, payload: dict, signature: str) -> bool:
        return verify_signature(canonical_json(payload), signature, self.secret)
