"""Integration: discovery feed."""
import pytest


@pytest.mark.integration
def test_feed_list_authenticated(auth_api, live_api):
    r = auth_api.get("/api/v1/feed/", params={"count": 5})
    assert r.status_code == 200
    data = r.json()
    # Incomplete profile returns profile_incomplete flag
    assert "results" in data or "profile_incomplete" in data or isinstance(data, list)


@pytest.mark.integration
def test_feed_requires_auth(api, live_api):
    r = api.get("/api/v1/feed/", auth=False)
    assert r.status_code in (401, 403)
