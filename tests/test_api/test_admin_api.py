"""Test API quản trị với Service giả: phân quyền + validate + định dạng response."""

from datetime import UTC, datetime

from app.api import deps
from app.core.exceptions import ConflictError
from app.models.domain import Poi
from tests.test_api.conftest import async_mock_service, make_admin, override

NOW = datetime(2026, 10, 1, tzinfo=UTC)

VALID_POI = {
    "code": "CONG_TAM_QUAN",
    "name": "Cổng Tam Quan",
    "description": "Mô tả",
    "latitude": 16.1,
    "longitude": 108.27,
}


def poi_model(**kw) -> Poi:
    return Poi(id="p1", created_at=NOW, updated_at=NOW, **{**VALID_POI, **kw})


class TestAdminAuth:
    def test_login_hides_password_hash(self, app, client):
        service = override(app, deps.get_auth_service, async_mock_service("login"))
        service.login.return_value = ("tok", make_admin())
        body = client.post("/api/v1/admin/auth/login", json={"username": "admin", "password": "admin123"}).json()
        assert body["data"]["access_token"] == "tok"
        assert "password_hash" not in body["data"]["user"]

    def test_admin_routes_require_login(self, app, client):
        override(app, deps.get_auth_service, async_mock_service("get_user_from_token"))
        response = client.get("/api/v1/admin/pois")
        assert response.status_code == 401 and response.json()["error"]["code"] == "NOT_AUTHENTICATED"


class TestAdminPoi:
    def test_create_poi(self, app, client, as_admin):
        service = override(app, deps.get_poi_service, async_mock_service("create"))
        service.create.return_value = poi_model()
        response = client.post("/api/v1/admin/pois", json=VALID_POI)
        assert response.status_code == 201
        assert service.create.await_args.args[0]["trigger_radius_m"] == 30  # giá trị mặc định đã điền

    def test_staff_cannot_create_poi(self, app, client, as_staff):
        service = override(app, deps.get_poi_service, async_mock_service("create"))
        response = client.post("/api/v1/admin/pois", json=VALID_POI)
        assert response.status_code == 403 and response.json()["error"]["code"] == "ADMIN_ONLY"
        service.create.assert_not_called()

    def test_staff_can_read_pois(self, app, client, as_staff):
        service = override(app, deps.get_poi_service, async_mock_service("search"))
        service.search.return_value = ([poi_model()], 1)
        body = client.get("/api/v1/admin/pois?page=1&size=10&q=cong").json()
        assert body["data"]["total"] == 1 and body["data"]["items"][0]["code"] == "CONG_TAM_QUAN"

    def test_create_poi_validation(self, client, as_admin):
        bad = {**VALID_POI, "latitude": 200, "code": "có dấu cách"}
        body = client.post("/api/v1/admin/pois", json=bad).json()
        fields = {d["field"] for d in body["error"]["details"]}
        assert {"latitude", "code"} <= fields

    def test_opening_hours_validation(self, client, as_admin):
        bad_hours = [
            {"day": 7, "open": "06:00", "close": "21:00"},  # chỉ có 0-6
            {"day": 0, "open": "6h", "close": "21:00"},  # sai định dạng
            {"day": 1, "open": "21:00", "close": "06:00"},  # đóng trước khi mở
        ]
        for period in bad_hours:
            response = client.post("/api/v1/admin/pois", json={**VALID_POI, "opening_hours": [period]})
            assert response.status_code == 422, period

    def test_create_poi_with_details(self, app, client, as_admin):
        service = override(app, deps.get_poi_service, async_mock_service("create"))
        service.create.return_value = poi_model()
        details = {
            "opening_hours": [{"day": 0, "open": "06:00", "close": "24:00"}],
            "entry_fee_vnd": 0,
            "visit_minutes": 20,
            "amenities": ["parking"],
            "tips": "Mang nón",
        }
        assert client.post("/api/v1/admin/pois", json={**VALID_POI, **details}).status_code == 201
        sent = service.create.await_args.args[0]
        assert sent["opening_hours"] == details["opening_hours"] and sent["tips"] == "Mang nón"

    def test_duplicate_code_409(self, app, client, as_admin):
        service = override(app, deps.get_poi_service, async_mock_service("create"))
        service.create.side_effect = ConflictError("trùng", code="POI_CODE_EXISTS")
        assert client.post("/api/v1/admin/pois", json=VALID_POI).status_code == 409

    def test_partial_update_only_sends_given_fields(self, app, client, as_admin):
        service = override(app, deps.get_poi_service, async_mock_service("update"))
        service.update.return_value = poi_model(name="Mới")
        client.put("/api/v1/admin/pois/p1", json={"name": "Mới"})
        assert service.update.await_args.args == ("p1", {"name": "Mới"})


class TestAdminOther:
    def test_localize_returns_202(self, app, client, as_admin):
        service = override(app, deps.get_localization_service, async_mock_service("schedule_poi"))
        service.schedule_poi.return_value = 16
        response = client.post("/api/v1/admin/pois/p1/localize", json={"force": True})
        assert response.status_code == 202 and response.json()["data"]["queued"] == 16
        service.schedule_poi.assert_awaited_once_with("p1", None, force=True)

    def test_staff_creates_cash_codes(self, app, client, as_staff):
        service = override(app, deps.get_access_service, async_mock_service("create_cash_codes"))
        service.create_cash_codes.return_value = []
        assert client.post("/api/v1/admin/access-codes", json={"quantity": 2}).status_code == 201
        assert service.create_cash_codes.await_args.kwargs == {"staff_id": "u1", "quantity": 2, "note": None}

    def test_cash_code_quantity_limit(self, client, as_staff):
        assert client.post("/api/v1/admin/access-codes", json={"quantity": 500}).status_code == 422

    def test_session_status_filter_validated(self, client, as_admin):
        assert client.get("/api/v1/admin/access-sessions?status=hacked").status_code == 422

    def test_users_admin_only(self, client, as_staff):
        assert client.get("/api/v1/admin/users").status_code == 403
