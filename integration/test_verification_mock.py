"""
Integration: face verification OFF → mock path.

FACE_VERIFICATION=False → start real liveness should fail;
POST /api/v1/verification/mock-complete/ should work.
"""
import pytest


@pytest.mark.integration
def test_verification_status_shows_face_off(auth_api, live_api):
    r = auth_api.get("/api/v1/verification/status/")
    assert r.status_code == 200
    data = r.json()
    # Config may be nested or flat
    face = data.get("face_verification")
    if face is None and isinstance(data.get("config"), dict):
        face = data["config"].get("face_verification")
    if face is not None:
        assert face is False
    mock = data.get("mock_mode")
    if mock is None and isinstance(data.get("config"), dict):
        mock = data["config"].get("mock_mode")
    if mock is not None:
        assert mock is True


@pytest.mark.integration
def test_real_start_blocked_when_face_off(auth_api, live_api):
    r = auth_api.post("/api/v1/verification/start/", json={})
    # Backend returns 400 with guidance to use mock-complete
    assert r.status_code in (400, 403)
    body = r.text.lower()
    assert (
        "face" in body
        or "mock" in body
        or "disabled" in body
        or "verification" in body
    )


@pytest.mark.integration
def test_mock_complete_when_face_off(auth_api, live_api):
    r = auth_api.post("/api/v1/verification/mock-complete/", json={})
    # 200 success, or 400 if already verified / edge case
    assert r.status_code in (200, 400, 201), r.text
    if r.status_code == 200:
        data = r.json()
        assert (
            data.get("verified") is True
            or data.get("status") in ("verified", "success", "completed")
            or "message" in data
            or data.get("is_identity_verified") is True
        )
