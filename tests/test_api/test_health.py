from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_tra_ve_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}