"""Test cho model POI. Mỗi model nên có một file test cùng tên theo mẫu này."""
import pytest
from bson import ObjectId
from pydantic import ValidationError

from app.models.poi import POI


def tao_poi_hop_le(**ghi_de) -> POI:
    du_lieu = {"name": "Chợ Bến Thành", "source_text": "Chợ được xây năm 1914.", "source_lang": "vi"}
    du_lieu.update(ghi_de)
    return POI(**du_lieu)


def test_tao_poi_hop_le_co_gia_tri_mac_dinh():
    poi = tao_poi_hop_le()
    assert poi.id is None                 # chưa lưu DB nên chưa có id
    assert poi.category_id is None
    assert poi.created_at.tzinfo is not None   # luôn có múi giờ (UTC)


def test_tu_dong_cat_khoang_trang():
    assert tao_poi_hop_le(name="  Chợ Bến Thành  ").name == "Chợ Bến Thành"


def test_doc_tu_mongo_objectid_duoc_ep_thanh_str():
    # Giả lập document đọc từ MongoDB: `_id` là ObjectId.
    poi = POI.model_validate({"_id": ObjectId(), "name": "A", "source_text": "B", "source_lang": "vi"})
    assert isinstance(poi.id, str) and len(poi.id) == 24


@pytest.mark.parametrize(
    "truong, gia_tri",
    [
        ("name", ""),                    # tên rỗng
        ("name", "x" * 201),             # tên quá dài
        ("source_text", ""),             # nội dung rỗng
        ("source_text", "x" * 5001),     # vượt giới hạn dịch/TTS
        ("source_lang", "Vietnamese"),   # sai định dạng mã ngôn ngữ
        ("source_lang", "VI"),           # phải là chữ thường
    ],
)
def test_du_lieu_sai_bi_tu_choi(truong, gia_tri):
    with pytest.raises(ValidationError):
        tao_poi_hop_le(**{truong: gia_tri})


def test_toa_do_hop_le():
    poi = tao_poi_hop_le(latitude=10.77, longitude=106.69)
    assert (poi.latitude, poi.longitude) == (10.77, 106.69)


@pytest.mark.parametrize("lat, lng", [(10.77, None), (None, 106.69)])
def test_chi_co_mot_trong_hai_toa_do_bi_tu_choi(lat, lng):
    with pytest.raises(ValidationError):
        tao_poi_hop_le(latitude=lat, longitude=lng)


def test_toa_do_ngoai_khoang_bi_tu_choi():
    with pytest.raises(ValidationError):
        tao_poi_hop_le(latitude=91, longitude=0)


def test_dump_de_luu_mongo_dung_alias_va_bo_id_rong():
    doc = tao_poi_hop_le().model_dump(by_alias=True, exclude={"id"})
    assert "_id" not in doc and "id" not in doc   # để MongoDB tự sinh _id
    assert doc["name"] == "Chợ Bến Thành"
