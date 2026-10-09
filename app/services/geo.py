"""Hàm tính toán địa lý thuần (không I/O) -> dễ viết unit test."""

import math
from collections.abc import Sequence
from typing import TypeVar

EARTH_RADIUS_M = 6_371_000
WALKING_SPEED_M_PER_MIN = 60  # đi bộ tham quan chậm ~ 3.6 km/h (có bậc thang, dừng chụp ảnh)

T = TypeVar("T")


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Khoảng cách đường chim bay giữa 2 tọa độ (mét)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def walking_minutes(distance_m: float) -> float:
    return round(distance_m / WALKING_SPEED_M_PER_MIN, 1)


def nearest_neighbor_order(start: tuple[float, float], items: Sequence[T], coords) -> list[T]:
    """
    Sắp xếp lộ trình theo thuật toán "láng giềng gần nhất":
    từ vị trí hiện tại luôn đi tới điểm CHƯA thăm gần nhất.
    Không tối ưu tuyệt đối (bài toán TSP) nhưng đủ tốt với < 20 điểm và rất nhanh.
    `coords(item)` trả về (lat, lng) của phần tử.
    """
    remaining = list(items)
    route: list[T] = []
    current = start
    while remaining:
        nxt = min(remaining, key=lambda it: haversine_m(*current, *coords(it)))
        route.append(nxt)
        remaining.remove(nxt)
        current = coords(nxt)
    return route


def estimate_listen_minutes(text: str, words_per_minute: int = 150) -> float:
    return round(max(len(text.split()), 1) / words_per_minute, 1)
