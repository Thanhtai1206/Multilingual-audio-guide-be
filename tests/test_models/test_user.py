"""Test cho model User."""
import pytest
from bson import ObjectId
from pydantic import ValidationError

from app.models.enums import Role
from app.models.user import User


def tao_user_hop_le(**ghi_de) -> User:
    du_lieu = {"username": "admin01", "email": "admin@example.com", "password_hash": "$2b$12$abcdef"}
    du_lieu.update(ghi_de)
    return User(**du_lieu)


def test_tao_user_hop_le_co_gia_tri_mac_dinh():
    user = tao_user_hop_le()
    assert user.id is None
    assert user.role == Role.EDITOR      # mặc định quyền thấp nhất
    assert user.is_active is True
    assert user.created_at.tzinfo is not None


def test_role_nhan_chuoi_va_doi_ra_enum():
    assert tao_user_hop_le(role="admin").role == Role.ADMIN


def test_doc_tu_mongo_objectid_duoc_ep_thanh_str():
    user = User.model_validate(
        {"_id": ObjectId(), "username": "abc", "email": "a@b.co", "password_hash": "x", "role": "admin"}
    )
    assert isinstance(user.id, str) and len(user.id) == 24


@pytest.mark.parametrize(
    "truong, gia_tri",
    [
        ("username", "ab"),            # quá ngắn
        ("username", "x" * 51),        # quá dài
        ("username", "co khoang trang"),
        ("username", "tên_có_dấu"),
        ("email", "khong-phai-email"),
        ("email", "a@"),
        ("password_hash", ""),         # rỗng
        ("role", "superuser"),         # không có trong Role
    ],
)
def test_du_lieu_sai_bi_tu_choi(truong, gia_tri):
    with pytest.raises(ValidationError):
        tao_user_hop_le(**{truong: gia_tri})


def test_dump_de_luu_mongo_role_la_chuoi_thuong():
    doc = tao_user_hop_le(role="admin").model_dump(by_alias=True, exclude={"id"}, mode="json")
    assert doc["role"] == "admin"
    assert "_id" not in doc
