"""Trợ lý AI cho admin: gợi ý viết lại mô tả POI hay hơn (tính năng AI Advisor trong presentation)."""

from app.core.exceptions import ExternalServiceError


class AiAssistantService:
    def __init__(self, *, llm):
        self.llm = llm

    async def enhance_description(self, name: str, description: str) -> str:
        if self.llm is None:
            raise ExternalServiceError("Chưa cấu hình AI (thiếu OPENROUTER_API_KEY)", code="LLM_NOT_CONFIGURED")
        messages = [
            {
                "role": "system",
                "content": (
                    "Bạn là biên tập viên nội dung thuyết minh du lịch tâm linh. Viết lại mô tả tiếng Việt "
                    "cho giọng đọc thuyết minh: tự nhiên, trang nghiêm, 120-200 từ. TUYỆT ĐỐI không thêm "
                    "số liệu hay sự kiện không có trong bản gốc. Chỉ trả về đoạn văn, không tiêu đề, không Markdown."
                ),
            },
            {"role": "user", "content": f"Điểm tham quan: {name}\nMô tả gốc: {description}"},
        ]
        return await self.llm.complete(messages, temperature=0.5)
