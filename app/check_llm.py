"""
Kiểm tra nhanh cấu hình chatbot AI - gọi thử AI 1 lần (cùng cách server gọi) và in ra kết quả / lỗi thật.

Cách chạy (ở thư mục gốc project, đã bật .venv):
    python -m app.check_llm
"""

import asyncio
import logging

import httpx

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError
from app.integrations.llm import OpenAICompatibleClient, provider_options, resolve_llm_config

HINTS = {
    "400": "Key sai/không hợp lệ -> tạo key mới tại https://aistudio.google.com/apikey",
    "401": "Key không đúng nhà cung cấp -> đặt LLM_PROVIDER=gemini (key Google) trong .env",
    "403": "Key bị chặn hoặc chưa bật Gemini API cho project Google của key",
    "404": "Model không tồn tại -> để trống LLM_MODEL= trong .env",
    "LLM_RATE_LIMITED": "Hết lượt miễn phí -> đợi 1 phút (hoặc sang ngày mai) rồi thử lại",
    "LLM_TIMEOUT": "Google trả lời quá chậm (thường do quá tải) -> đợi vài phút rồi thử lại; "
    "mạng yếu thì tăng LLM_TIMEOUT_SECONDS=120 trong .env",
    "LLM_BUSY": "Máy chủ Google đang quá tải (lỗi tạm thời) -> đợi vài phút rồi thử lại. "
    "Trong lúc chờ, chatbot vẫn trả lời bằng chế độ trích đoạn tài liệu.",
}


async def main() -> None:
    # In các dòng log của client AI (thử lại, đổi model, mã lỗi...) ra màn hình
    logging.basicConfig(level=logging.INFO, format="  - %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    config = resolve_llm_config(get_settings())
    if config is None:
        print("[X] Chưa có LLM_API_KEY trong file .env (hoặc LLM_PROVIDER=none).")
        return

    provider, api_key, base_url, model = config
    print(f"Nhà cung cấp : {provider}")
    print(f"Model        : {model}")
    print(f"Địa chỉ      : {base_url}")
    print(f"Key          : {api_key[:4]}... (dài {len(api_key)} ký tự)")

    settings = get_settings()
    print(f"Chờ tối đa   : {settings.LLM_TIMEOUT_SECONDS:.0f} giây")
    print("Đang gọi thử AI...\n")
    client = OpenAICompatibleClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        extra_body=provider_options(provider),
    )
    try:
        text = await client.complete([{"role": "user", "content": "Chào bạn, trả lời 1 câu ngắn."}])
    except ExternalServiceError as exc:
        print(f"\n[X] Gọi AI thất bại ({exc.code}): {exc}")
        cause = exc.__cause__
        status = str(cause.response.status_code) if isinstance(cause, httpx.HTTPStatusError) else ""
        print("Gợi ý:", HINTS.get(exc.code) or HINTS.get(status, "Xem dòng log lỗi phía trên (KHÔNG gửi key)."))
        return

    print(f"\n[OK] AI trả lời: {text}")
    print(f"Chatbot AI đã sẵn sàng (model {client.model}). Nhớ tắt server (Ctrl+C) rồi chạy lại.")


if __name__ == "__main__":
    asyncio.run(main())