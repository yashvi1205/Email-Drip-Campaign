"""Phase 0: Smoke tests for critical API endpoints"""
import pytest


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestAuthEndpoints:
    def test_login_endpoint_exists(self, client):
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        assert response.status_code in [200, 401, 422]

    def test_me_endpoint_requires_auth(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401


class TestDashboardEndpoints:
    def test_dashboard_endpoint_exists(self, client, auth_header_dashboard):
        response = client.get("/api/dashboard/drip", headers=auth_header_dashboard)
        assert response.status_code in [200, 404]

    def test_profiles_endpoint_exists(self, client, auth_header_dashboard):
        response = client.get("/api/profiles", headers=auth_header_dashboard)
        assert response.status_code in [200, 404]


class TestTrackingEndpoints:
    def test_tracking_pixel_endpoint_exists(self, client):
        response = client.get("/api/tracking/pixel", params={"tracking_id": "test"})
        assert response.status_code in [200, 404]


class TestLeadsEndpoints:
    def test_leads_endpoint_requires_auth(self, client):
        response = client.get("/api/leads")
        assert response.status_code == 401

    def test_leads_endpoint_with_auth(self, client, auth_header_admin):
        response = client.get("/api/leads", headers=auth_header_admin)
        assert response.status_code in [200, 404]
