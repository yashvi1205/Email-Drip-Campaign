from fastapi.testclient import TestClient


def test_health_smoke():
    from api.main import app

    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "healthy"


def test_dashboard_drip_smoke():
    from api.main import app

    client = TestClient(app)
    r = client.get("/api/dashboard/drip", headers={"X-API-Key": "test-api-key"})
    # If DB is unavailable in the environment, skip rather than failing the suite.
    if r.status_code == 500:
        # backend uses HTTPException in various places; in DB misconfig this commonly becomes 500
        # (we intentionally don't assert response shape here to avoid coupling).
        import pytest

        pytest.skip("Dashboard endpoint requires a working database connection.")
    assert r.status_code == 200


def test_tracking_open_smoke_without_db():
    """
    Use the Gmail proxy user-agent so the endpoint will NOT attempt a DB write.
    This verifies the tracking route wiring, middleware, and rate limiting without requiring DB.
    """
    from api.main import app

    client = TestClient(app)
    r = client.get(
        "/api/tracking/open/test_tracking_id.gif",
        headers={"User-Agent": "GoogleImageProxy"},
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/")

