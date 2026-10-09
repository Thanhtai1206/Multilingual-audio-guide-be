"""
Kiểm tra frontend (JS thuần) và backend (Python) dùng CÙNG bộ mã/chuỗi.
Hai nơi được viết tay riêng nên dễ quên sửa một bên -> test này bắt lỗi đó.
"""

import json
import re
from pathlib import Path

from app.db.seed_data import SAMPLE_POI_DETAILS, SAMPLE_POIS
from app.db.ui_strings import UI_STRINGS_EN, UI_STRINGS_VI
from app.services.poi_details import AMENITIES

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


def js_object_keys(source: str, start_marker: str) -> set[str]:
    """Lấy các key `tên: ...` ở cấp 1 của object JS bắt đầu sau start_marker."""
    start = source.index(start_marker)
    end = source.index("\n  },", start)
    return set(re.findall(r"^\s{4}(\w+):", source[start:end], flags=re.MULTILINE))


def test_ui_strings_same_keys_in_js_and_python():
    source = (FRONTEND / "js" / "i18n.js").read_text(encoding="utf-8")
    assert js_object_keys(source, "  vi: {") == set(UI_STRINGS_VI)
    assert js_object_keys(source, "  en: {") == set(UI_STRINGS_EN) == set(UI_STRINGS_VI)


def test_ui_strings_have_no_newlines():
    # UiTextService ghép các chuỗi bằng "\n" để dịch 1 lần -> chuỗi không được chứa xuống dòng
    assert not [k for k, v in UI_STRINGS_EN.items() if "\n" in v]


def test_every_amenity_has_label_everywhere():
    for code in AMENITIES:
        assert f"amenity_{code}" in UI_STRINGS_EN and f"amenity_{code}" in UI_STRINGS_VI
    admin_js = (FRONTEND / "admin" / "admin.js").read_text(encoding="utf-8")
    block = admin_js[admin_js.index("const AMENITY_LABELS") : admin_js.index("};", admin_js.index("AMENITY_LABELS"))]
    assert set(re.findall(r"^\s+(\w+):", block, flags=re.MULTILINE)) == set(AMENITIES)


def test_sample_data_uses_known_codes():
    for poi in SAMPLE_POIS:
        assert f"cat_{poi['category']}" in UI_STRINGS_EN
        details = SAMPLE_POI_DETAILS[poi["code"]]
        assert set(details["amenities"]) <= set(AMENITIES)
        json.dumps(details)  # lưu được vào MongoDB
