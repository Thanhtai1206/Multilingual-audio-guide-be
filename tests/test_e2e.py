"""
Test TÍCH HỢP đầu-cuối: chạy app thật (3 lớp đầy đủ), chỉ thay dịch máy/TTS bằng bản giả.
Mặc định dùng MongoDB giả lập; có biến TEST_MONGO_URI (CI) thì chạy trên MongoDB THẬT.
Mô phỏng đúng kịch bản trong PRD.
"""

import os
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.task_runner import InlineTaskRunner
from tests.fakes import FakeTranslator, FakeTTS


def start_app(settings):
    app = create_app(settings)
    return app, TestClient(app)


def use_fakes(app) -> InlineTaskRunner:
    runner = InlineTaskRunner()
    app.state.translator = FakeTranslator()
    app.state.tts = FakeTTS()
    app.state.task_runner = runner
    return runner


@pytest.fixture
def e2e_settings(settings):
    settings.SEED_SAMPLE_DATA = True
    real_uri = os.getenv("TEST_MONGO_URI")
    if real_uri:
        settings.MONGO_URI = real_uri
        settings.MONGO_DB_NAME = f"e2e_{uuid.uuid4().hex[:8]}"
    yield settings
    if real_uri:
        from pymongo import MongoClient

        with MongoClient(real_uri) as client:
            client.drop_database(settings.MONGO_DB_NAME)


@pytest.fixture
def e2e(e2e_settings):
    app, test_client = start_app(e2e_settings)
    with test_client as client:
        yield client, use_fakes(app)


def drain(client, runner) -> None:
    """Chạy hết tác vụ nền trên CHÍNH event loop của app (bắt buộc khi dùng MongoDB thật)."""
    client.portal.call(runner.wait_all)


def admin_headers(client) -> dict:
    token = client.post("/api/v1/admin/auth/login", json={"username": "admin", "password": "admin123"}).json()
    return {"Authorization": f"Bearer {token['data']['access_token']}"}


async def test_full_visitor_journey(e2e):
    client, runner = e2e
    admin = admin_headers(client)

    # 1. Admin dịch toàn bộ nội dung mẫu sang mọi ngôn ngữ
    queued = client.post("/api/v1/admin/localize-all", json={}, headers=admin).json()["data"]["queued"]
    assert queued == 6
    drain(client, runner)
    stats = client.get("/api/v1/admin/stats", headers=admin).json()["data"]
    assert stats["localization_coverage_percent"] == 100.0

    # 2. Khách thanh toán online qua cổng giả lập
    payment = client.post("/api/v1/access/online").json()["data"]
    redirect = client.post(
        f"/mock-gateway/{payment['payment_id']}/complete", data={"result": "success"}, follow_redirects=False
    )
    code = redirect.headers["location"].split("code=")[1]

    # 3. Đổi mã lấy token, tải toàn bộ dữ liệu tiếng Nhật
    token = client.post("/api/v1/access/token", json={"code": code}).json()["data"]["access_token"]
    visitor = {"Authorization": f"Bearer {token}"}
    bundle = client.get("/api/v1/content/bundle?lang=ja", headers=visitor)
    data = bundle.json()["data"]
    assert data["lang"] == "ja" and len(data["pois"]) == 6
    assert all(p["served_lang"] == "ja" and p["audio_url"] for p in data["pois"])
    assert data["tours"][0]["name"].startswith("[ja]")

    # 4. Lần mở app sau: dữ liệu không đổi -> 304
    again = client.get("/api/v1/content/bundle?lang=ja", headers={**visitor, "If-None-Match": bundle.headers["etag"]})
    assert again.status_code == 304

    # 5. File audio phục vụ được
    audio = client.get(data["pois"][0]["audio_url"])
    assert audio.status_code == 200 and audio.content.startswith(b"ID3")

    # 6. GPS: điểm gần + gợi ý lộ trình + ghi nhận sự kiện + hỏi chatbot
    nearby = client.get("/api/v1/pois/nearby?lat=16.1001&lng=108.27735&radius=50&lang=ja", headers=visitor)
    assert nearby.json()["data"][0]["code"] == "CONG_TAM_QUAN"
    route = client.post(
        "/api/v1/tours/recommend", json={"latitude": 16.1001, "longitude": 108.27735, "lang": "ja"}, headers=visitor
    ).json()["data"]
    assert route["stops"][0]["poi"]["code"] == "CONG_TAM_QUAN"
    poi_id = data["pois"][0]["id"]
    assert (
        client.post(
            "/api/v1/events", json={"poi_id": poi_id, "type": "audio_play", "lang": "ja"}, headers=visitor
        ).status_code
        == 201
    )
    chat = client.post("/api/v1/chat", json={"question": "Giờ mở cửa?", "lang": "ja"}, headers=visitor).json()
    assert chat["data"]["answer"].startswith("[ja]")

    # 7. Admin sửa mô tả -> bản dịch cũ hết hiệu lực, app tạm dùng tiếng Việt
    client.put(f"/api/v1/admin/pois/{poi_id}", json={"description": "Nội dung mới."}, headers=admin)
    poi = client.get(f"/api/v1/pois/{poi_id}?lang=ja", headers=visitor).json()["data"]
    assert poi["served_lang"] == "vi" and poi["is_fallback"] is True
    drain(client, runner)
    poi = client.get(f"/api/v1/pois/{poi_id}?lang=ja", headers=visitor).json()["data"]
    assert poi["served_lang"] == "ja" and poi["description"] == "[ja] Nội dung mới."

    # 8. Admin thu hồi -> token bị từ chối
    session_id = client.get("/api/v1/access/me", headers=visitor).json()["data"]["session_id"]
    client.post(f"/api/v1/admin/access-sessions/{session_id}/revoke", headers=admin)
    assert client.get("/api/v1/pois", headers=visitor).status_code == 401


async def test_cash_flow_and_admin_preview(e2e):
    client, _ = e2e
    admin = admin_headers(client)
    codes = client.post("/api/v1/admin/access-codes", json={"quantity": 2, "note": "Đoàn khách"}, headers=admin).json()[
        "data"
    ]
    assert len(codes) == 2 and codes[0]["status"] == "paid"
    token = client.post("/api/v1/access/token", json={"code": codes[0]["code"]}).json()["data"]["access_token"]
    assert client.get("/api/v1/pois", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    # Admin xem thử app bằng token admin
    me = client.get("/api/v1/access/me", headers=admin).json()["data"]
    assert me["is_admin_preview"] is True


async def test_switch_language_translates_automatically(e2e):
    """Không ai bấm dịch trước: khách chọn tiếng Hàn -> hệ thống tự dịch, lần tải sau đã là tiếng Hàn."""
    client, runner = e2e
    admin = admin_headers(client)
    code = client.post("/api/v1/admin/access-codes", json={"quantity": 1}, headers=admin).json()["data"][0]["code"]
    token = client.post("/api/v1/access/token", json={"code": code}).json()["data"]["access_token"]
    visitor = {"Authorization": f"Bearer {token}"}

    first = client.get("/api/v1/content/bundle?lang=ko", headers=visitor)
    assert first.headers["X-Translation-Pending"] == "6"
    assert all(p["is_fallback"] for p in first.json()["data"]["pois"])

    drain(client, runner)  # tác vụ nền dịch xong
    second = client.get("/api/v1/content/bundle?lang=ko", headers={**visitor, "If-None-Match": first.headers["etag"]})
    assert second.status_code == 200 and second.headers["X-Translation-Pending"] == "0"
    data = second.json()["data"]
    assert all(p["served_lang"] == "ko" for p in data["pois"])
    assert data["tours"][0]["name"].startswith("[ko]")

    ui = client.get("/api/v1/ui-strings/ko").json()["data"]
    assert ui["lang"] == "ko" and ui["strings"]["tabMap"] == "[ko] Map"


def test_data_survives_restart_and_unfinished_translations_resume(e2e_settings):
    """Dữ liệu nằm trong DB: tắt/mở lại server vẫn còn; bản dịch đang dở được chạy tiếp."""
    if e2e_settings.MONGO_URI.startswith("mongomock://"):
        pytest.skip("Cần MongoDB thật (TEST_MONGO_URI) để mô phỏng khởi động lại")
    app, test_client = start_app(e2e_settings)
    with test_client as client:
        use_fakes(app)
        admin = admin_headers(client)
        poi_id = client.get("/api/v1/admin/pois", headers=admin).json()["data"]["items"][0]["id"]
        client.post(f"/api/v1/admin/pois/{poi_id}/localize", json={"languages": ["ja"]}, headers=admin)
        # "Tắt server" khi bản dịch còn đang chờ (tác vụ nền chưa chạy)

    app2, test_client2 = start_app(e2e_settings)
    with test_client2 as client:
        admin = admin_headers(client)
        assert client.get("/api/v1/admin/pois", headers=admin).json()["data"]["total"] == 6  # dữ liệu còn nguyên
        # Lúc khởi động, bản dịch "ja" đang dở đã được tự động chạy lại (không còn kẹt ở pending).
        # Test tắt dịch máy nên kết quả là failed kèm lý do - quan trọng là nó ĐÃ được xử lý.
        for _ in range(50):
            rows = client.get(f"/api/v1/admin/pois/{poi_id}/localizations", headers=admin).json()["data"]
            ja = next(r for r in rows if r["lang"] == "ja")
            if ja["status"] not in ("pending", "processing"):
                break
            time.sleep(0.1)
        assert ja["status"] == "failed" and "tắt" in ja["error"]
