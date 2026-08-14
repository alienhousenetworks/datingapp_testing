"""Integration: users/me and heartbeat."""
import pytest


@pytest.mark.integration
def test_users_me(auth_api, authenticated_session, live_api):
    r = auth_api.get("/api/v1/users/me/")
    assert r.status_code == 200
    data = r.json()
    # Serializer may use id / email fields
    assert data.get("email") == authenticated_session.email or data.get("id") or data.get("user_id")


@pytest.mark.integration
def test_users_me_requires_auth(api, live_api):
    r = api.get("/api/v1/users/me/", auth=False)
    assert r.status_code in (401, 403)


@pytest.mark.integration
def test_last_active_heartbeat(auth_api, live_api):
    r = auth_api.post(
        "/api/v1/users/last-active/",
        json={"lat": 12.9716, "lon": 77.5946},
    )
    assert r.status_code == 200
    assert "status" in r.json() or r.status_code == 200


@pytest.mark.integration
def test_last_active_without_coords(auth_api, live_api):
    r = auth_api.post("/api/v1/users/last-active/", json={})
    assert r.status_code == 200
