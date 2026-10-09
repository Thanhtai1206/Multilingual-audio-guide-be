"""
Tạo lượt tham quan GIẢ LẬP để demo biểu đồ "Khung giờ đông khách" khi chưa có du khách thật.

    python -m app.db.demo_events            # tạo ~4 tuần dữ liệu cho mọi điểm đang hoạt động
    python -m app.db.demo_events --clear    # xóa toàn bộ dữ liệu giả lập (dữ liệu thật giữ nguyên)

Mọi sự kiện giả lập có session_id = "demo-simulated" -> dễ phân biệt và xóa sạch, không lẫn với dữ liệu thật.
Mô phỏng: sáng sớm và chiều mát đông, trưa vắng, cuối tuần đông hơn ngày thường.
"""

import argparse
import asyncio
import random
from datetime import UTC, timedelta

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings
from app.core.security import utcnow
from app.services.poi_details import site_timezone

DEMO_SESSION = "demo-simulated"
# Mức đông tương đối theo giờ (giờ địa phương) - 0 là không có khách
HOURLY_WEIGHT = {
    5: 2, 6: 6, 7: 9, 8: 10, 9: 8, 10: 6, 11: 4, 12: 2, 13: 2,
    14: 3, 15: 6, 16: 9, 17: 10, 18: 7, 19: 4, 20: 2,
}  # fmt: skip


async def generate(db, *, weeks: int = 4, seed: int = 7) -> int:
    rng = random.Random(seed)  # noqa: S311 - chỉ để giả lập dữ liệu, không dùng cho bảo mật
    tz = site_timezone(get_settings().SITE_UTC_OFFSET_HOURS)
    pois = [p async for p in db.pois.find({"is_active": True}, {"_id": 1, "priority": 1})]
    today = utcnow().astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    events = []
    for poi in pois:
        popularity = 0.5 + (poi.get("priority") or 0) / 10  # điểm ưu tiên cao thì đông hơn
        for day_offset in range(1, weeks * 7 + 1):
            day = today - timedelta(days=day_offset)
            weekend = 1.6 if day.weekday() >= 5 else 1.0
            for hour, weight in HOURLY_WEIGHT.items():
                visits = rng.randint(0, round(weight * popularity * weekend))
                for _ in range(visits):
                    moment = day + timedelta(hours=hour, minutes=rng.randint(0, 59))
                    events.append(
                        {
                            "poi_id": str(poi["_id"]),
                            "session_id": DEMO_SESSION,
                            "lang": rng.choice(["vi", "vi", "en", "ko", "zh", "ja"]),
                            "type": rng.choice(["view", "audio_play", "geofence_enter"]),
                            "created_at": moment.astimezone(UTC),
                        }
                    )
    if events:
        await db.visit_events.insert_many(events)
    return len(events)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clear", action="store_true", help="Xóa dữ liệu giả lập")
    parser.add_argument("--weeks", type=int, default=4)
    args = parser.parse_args()

    settings = get_settings()
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB_NAME]
    removed = (await db.visit_events.delete_many({"session_id": DEMO_SESSION})).deleted_count
    if args.clear:
        print(f"Đã xóa {removed} lượt tham quan giả lập.")
    else:
        created = await generate(db, weeks=args.weeks)
        print(f"Đã tạo {created} lượt tham quan giả lập ({args.weeks} tuần).")
        print("Xóa bằng: python -m app.db.demo_events --clear")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
