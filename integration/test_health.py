"""Integration: health endpoints."""
import pytest


@pytest.mark.integration
def test_health_legacy(api, live_api):
    r = api.get("/health/", auth=False)
    assert r.status_code == 200


@pytest.mark.integration
def test_health_live(api, live_api):
    r = api.get("/health/live/", auth=False)
    assert r.status_code == 200


@pytest.mark.integration
def test_health_ready(api, live_api):
    r = api.get("/health/ready/", auth=False)
    # ready may be 200 or 503 depending on redis/db — must not be 404
    assert r.status_code in (200, 503)
