"""
Nghiệp vụ "thông tin chi tiết" của điểm tham quan - giống thẻ địa điểm trên Google Maps:
giờ mở cửa từng ngày, đang mở/đóng cửa, vé, thời gian tham quan, tiện ích, khung giờ đông khách.

Toàn bộ là HÀM THUẦN (không gọi DB, không đọc đồng hồ hệ thống) -> test được với mọi thời điểm.
Lớp Service truyền vào giờ hiện tại và dữ liệu đã đọc từ Repository.
"""

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta, timezone

from app.models.domain import OpeningPeriod

# Mã tiện ích -> nhãn tiếng Việt (nhãn các ngôn ngữ khác nằm trong chuỗi giao diện "amenity_<mã>")
AMENITIES: dict[str, str] = {
    "wheelchair": "Lối đi cho xe lăn",
    "stairs": "Nhiều bậc thang",
    "parking": "Bãi gửi xe",
    "restroom": "Nhà vệ sinh",
    "drinking_water": "Nước uống",
    "shade": "Có bóng mát, ghế nghỉ",
    "photo_ok": "Được chụp ảnh",
    "no_photo_ceremony": "Không chụp ảnh khi hành lễ",
    "shoes_off": "Bỏ giày dép trước khi vào",
    "quiet_zone": "Giữ yên lặng",
    "dress_code": "Trang phục kín đáo",
}

DAY_NAMES_VI = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"]

CLOSING_SOON_MINUTES = 60  # còn <= 60 phút là "Sắp đóng cửa" (giống Google Maps)
OPENING_SOON_MINUTES = 60
POPULAR_MIN_EVENTS = 20  # ít hơn số lượt này thì chưa đủ dữ liệu để vẽ "khung giờ đông khách"
POPULAR_LOOKBACK_DAYS = 56  # chỉ tính 8 tuần gần nhất


def site_timezone(utc_offset_hours: int) -> timezone:
    return timezone(timedelta(hours=utc_offset_hours))


def to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def fmt_minutes(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


def tips_hash(tips: str) -> str:
    return hashlib.md5(tips.encode()).hexdigest()  # noqa: S324 - chỉ để so sánh nội dung


def periods_for_day(hours: Iterable[OpeningPeriod], day: int) -> list[tuple[int, int]]:
    """Các khung giờ (phút bắt đầu, phút kết thúc) của 1 ngày, đã sắp xếp."""
    return sorted((to_minutes(p.open), to_minutes(p.close)) for p in hours if p.day == day)


def normalize_hours(hours: Iterable[OpeningPeriod]) -> list[OpeningPeriod]:
    """Sắp xếp theo ngày + giờ mở; dùng trước khi lưu DB để dữ liệu luôn gọn."""
    return sorted(hours, key=lambda p: (p.day, to_minutes(p.open)))


def find_overlap(hours: Iterable[OpeningPeriod]) -> str | None:
    """Trả về mô tả lỗi nếu có 2 khung giờ chồng nhau trong cùng ngày, không lỗi thì None."""
    for day in range(7):
        periods = periods_for_day(hours, day)
        for (_, end), (start, _) in zip(periods, periods[1:], strict=False):
            if start < end:
                return f"{DAY_NAMES_VI[day]} có 2 khung giờ chồng nhau"
    return None


# ------------------------------------------------------------------ đang mở / đóng cửa
def opening_status(hours: list[OpeningPeriod], now_local: datetime) -> dict:
    """
    Trạng thái mở cửa tại thời điểm `now_local` (giờ địa phương của chùa).

    state: open | closing_soon | closed | opening_soon | unknown (chưa nhập giờ)
    - Đang mở: kèm `closes_at` ("21:00").
    - Đang đóng: kèm `opens_at` + `opens_day` (0-6) của lần mở cửa kế tiếp; `opens_in_days` = 0 là hôm nay.
    """
    if not hours:
        return {"state": "unknown"}
    today = now_local.weekday()
    minute = now_local.hour * 60 + now_local.minute

    for start, end in periods_for_day(hours, today):
        if start <= minute < end:
            left = end - minute
            return {
                "state": "closing_soon" if left <= CLOSING_SOON_MINUTES else "open",
                "closes_at": fmt_minutes(end),
                "minutes_left": left,
            }

    # Đang đóng cửa -> tìm lần mở kế tiếp (hôm nay sau giờ hiện tại, rồi các ngày sau)
    for offset in range(8):
        day = (today + offset) % 7
        for start, _ in periods_for_day(hours, day):
            if offset == 0 and start <= minute:
                continue
            wait = offset * 24 * 60 + start - minute
            return {
                "state": "opening_soon" if wait <= OPENING_SOON_MINUTES else "closed",
                "opens_at": fmt_minutes(start),
                "opens_day": day,
                "opens_in_days": offset,
            }
    return {"state": "unknown"}


# ------------------------------------------------------------------ khung giờ đông khách
def popular_times(event_times: Iterable[datetime], tz: timezone) -> dict:
    """
    "Khung giờ đông khách" từ dữ liệu THẬT: các lượt xem/nghe/đi qua POI (visit_events).

    Trả về {"sample_size", "by_day": {0..6: [24 số 0-100]}} - 100 = giờ đông nhất trong tuần.
    Chưa đủ POPULAR_MIN_EVENTS lượt thì by_day = None (giao diện báo "chưa đủ dữ liệu").
    """
    counts = [[0] * 24 for _ in range(7)]
    total = 0
    for moment in event_times:
        if moment.tzinfo is None:  # MongoDB trả datetime UTC không kèm múi giờ
            moment = moment.replace(tzinfo=UTC)
        local = moment.astimezone(tz)
        counts[local.weekday()][local.hour] += 1
        total += 1
    if total < POPULAR_MIN_EVENTS:
        return {"sample_size": total, "by_day": None}
    peak = max(max(row) for row in counts)
    return {
        "sample_size": total,
        "by_day": {day: [round(c * 100 / peak) for c in row] for day, row in enumerate(counts)},
    }


# ------------------------------------------------------------------ văn bản cho chatbot
def describe_hours_vi(hours: list[OpeningPeriod]) -> str:
    """'Thứ Hai - Chủ nhật: 06:00-11:30, 13:30-21:00' - gộp các ngày liền nhau có cùng giờ."""
    if not hours:
        return "chưa có thông tin"
    by_day = [", ".join(f"{fmt_minutes(a)}-{fmt_minutes(b)}" for a, b in periods_for_day(hours, d)) for d in range(7)]
    groups: list[tuple[int, int, str]] = []
    for day, text in enumerate(by_day):
        if groups and groups[-1][2] == text:
            groups[-1] = (groups[-1][0], day, text)
        else:
            groups.append((day, day, text))
    parts = []
    for first, last, text in groups:
        days = DAY_NAMES_VI[first] if first == last else f"{DAY_NAMES_VI[first]} - {DAY_NAMES_VI[last]}"
        parts.append(f"{days}: {text or 'đóng cửa'}")
    return "; ".join(parts)


def describe_details_vi(poi) -> str:
    """Thông tin chi tiết dạng văn bản tiếng Việt để đưa vào tài liệu cho chatbot."""
    lines = [f"Giờ mở cửa: {describe_hours_vi(poi.opening_hours)}."]
    fee = "miễn phí" if poi.entry_fee_vnd == 0 else f"{poi.entry_fee_vnd:,} đồng".replace(",", ".")
    lines.append(f"Vé vào cửa: {fee}.")
    if poi.visit_minutes:
        lines.append(f"Thời gian tham quan gợi ý: khoảng {poi.visit_minutes} phút.")
    if poi.amenities:
        lines.append("Tiện ích / quy định: " + ", ".join(AMENITIES.get(a, a) for a in poi.amenities) + ".")
    if poi.tips:
        lines.append(f"Lưu ý: {poi.tips}")
    return " ".join(lines)
