"""Test tiện ích lõi: cấu hình production, JWT, chữ ký HMAC, cắt văn bản dịch, truy hồi BM25."""

from datetime import timedelta

import pytest

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    ACCESS_CODE_ALPHABET,
    create_token,
    decode_token,
    generate_access_code,
    sign_payload,
    verify_signature,
)
from app.integrations.translator import split_text
from app.services.retrieval import BM25Index, Document, normalize


def test_production_rejects_default_secrets():
    with pytest.raises(RuntimeError) as exc:
        Settings(_env_file=None, APP_ENV="production", MONGO_URI="mongomock://x").validate_for_production()
    assert "JWT_SECRET" in str(exc.value) and "MONGO_URI" in str(exc.value)


def test_production_ok_with_real_config():
    Settings(
        _env_file=None,
        APP_ENV="production",
        JWT_SECRET="x" * 40,
        FIRST_ADMIN_PASSWORD="StrongPass!2026",
        PAYMENT_WEBHOOK_SECRET="another-secret",
        MONGO_URI="mongodb://db:27017",
    ).validate_for_production()


def test_jwt_roundtrip_and_type_check():
    token, _ = create_token(subject="s1", token_type="visitor", expires_delta=timedelta(minutes=5), secret="k" * 32)
    assert decode_token(token, secret="k" * 32, expected_type="visitor")["sub"] == "s1"
    with pytest.raises(UnauthorizedError):
        decode_token(token, secret="k" * 32, expected_type="admin")
    with pytest.raises(UnauthorizedError):
        decode_token(token, secret="sai" * 11, expected_type="visitor")


def test_expired_token():
    token, _ = create_token(subject="s", token_type="visitor", expires_delta=timedelta(seconds=-1), secret="k" * 32)
    with pytest.raises(UnauthorizedError) as exc:
        decode_token(token, secret="k" * 32, expected_type="visitor")
    assert exc.value.code == "TOKEN_EXPIRED"


def test_access_code_alphabet_has_no_ambiguous_chars():
    code = generate_access_code()
    assert len(code) == 6 and set(code) <= set(ACCESS_CODE_ALPHABET)
    assert not set("01OIL") & set(ACCESS_CODE_ALPHABET)


def test_hmac_signature():
    sig = sign_payload("hello", "secret")
    assert verify_signature("hello", sig, "secret")
    assert not verify_signature("hello!", sig, "secret")


def test_split_text_respects_limit():
    text = ". ".join([f"Câu số {i} dài dài" for i in range(500)])
    chunks = split_text(text, limit=200)
    assert all(len(c) <= 200 for c in chunks)
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_normalize_and_bm25_ranking():
    assert normalize("Đà Nẵng Quan Thế Âm") == "da nang quan the am"
    index = BM25Index(
        [
            Document("1", "poi", "Tượng Quan Âm", "Tượng cao 67 mét hướng ra biển"),
            Document("2", "article", "Giờ mở cửa", "Mở cửa từ 6 giờ sáng"),
        ]
    )
    assert index.search("tuong cao bao nhieu")[0].document.id == "1"
    assert index.search("mấy giờ mở cửa")[0].document.id == "2"
    assert index.search("xyz") == []
