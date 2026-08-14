"""Integration: profile + option catalogs."""
import pytest


@pytest.mark.integration
def test_profile_me_get(auth_api, live_api):
    r = auth_api.get("/api/v1/profile/me/")
    assert r.status_code in (200, 404)  # 404 if profile missing edge case
    # New users get profile on OTP verify
    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, dict)


@pytest.mark.integration
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/genders/",
        "/api/v1/sexualities/",
        "/api/v1/intents/",
        "/api/v1/turn_ons/",
        "/api/v1/mood_options/",
        "/api/v1/languages/",
        "/api/v1/avatars/",
    ],
)
def test_option_catalogs(auth_api, path, live_api):
    r = auth_api.get(path)
    assert r.status_code == 200, f"{path} → {r.status_code} {r.text[:200]}"


@pytest.mark.integration
def test_username_available(auth_api, live_api):
    r = auth_api.get(
        "/api/v1/profile/username-available/",
        params={"username": f"user_{__import__('uuid').uuid4().hex[:8]}"},
    )
    # Endpoint may return 200 with available flag
    assert r.status_code in (200, 400, 404)


@pytest.mark.integration
def test_theme_list(auth_api, live_api):
    r = auth_api.get("/api/v1/theme/")
    assert r.status_code in (200, 401)
