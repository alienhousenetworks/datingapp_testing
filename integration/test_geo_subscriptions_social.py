"""Integration: geo, subscriptions status, confessions list."""
import pytest


@pytest.mark.integration
def test_geo_cities(auth_api, live_api):
    r = auth_api.get("/api/v1/geo/cities/", params={"q": "Bang"})
    assert r.status_code in (200, 400)


@pytest.mark.integration
def test_subscription_status(auth_api, live_api):
    r = auth_api.get("/api/v1/subscriptions/status/")
    assert r.status_code in (200, 401, 403, 404)


@pytest.mark.integration
def test_confessions_list(auth_api, live_api):
    r = auth_api.get("/api/v1/social/")
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, (list, dict))


@pytest.mark.integration
def test_matches_list(auth_api, live_api):
    r = auth_api.get("/api/v1/matches/")
    assert r.status_code in (200, 401)


@pytest.mark.integration
def test_conversations_list(auth_api, live_api):
    r = auth_api.get("/api/v1/conversations/")
    assert r.status_code in (200, 401)
