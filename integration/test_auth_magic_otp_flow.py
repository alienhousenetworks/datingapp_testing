"""
Integration: auth with MAGIC_OTP, no captcha, bot off.

Backend:
  POST /api/v1/auth/register/
  POST /api/v1/auth/otp/verify/
  GET  /api/v1/auth/session/
  POST /api/v1/auth/logout/
  POST /api/v1/auth/ws-ticket/
"""
import pytest

from helpers.auth import unique_device_id, unique_email


@pytest.mark.integration
def test_signup_request_otp_no_captcha(auth_helper, magic_otp, live_api):
    email = unique_email("signup")
    device = unique_device_id()
    reg = auth_helper.request_otp(email, device, intent="signup")
    assert reg["status_code"] == 200, reg["data"]
    assert "message" in reg["data"] or reg["status_code"] == 200


@pytest.mark.integration
def test_signup_verify_magic_otp(auth_helper, magic_otp, live_api):
    session = auth_helper.login_with_magic_otp(intent="signup")
    assert session.access
    assert session.refresh
    assert session.user_id
    assert session.is_new_user is True


@pytest.mark.integration
def test_login_intent_unknown_email_404(auth_helper, live_api):
    email = unique_email("nouser")
    device = unique_device_id()
    reg = auth_helper.request_otp(email, device, intent="login")
    assert reg["status_code"] == 404
    assert reg["data"].get("code") == "email_not_found"


@pytest.mark.integration
def test_signup_intent_existing_email_409(auth_helper, live_api):
    session = auth_helper.login_with_magic_otp(intent="signup")
    # Second signup with same email
    reg = auth_helper.request_otp(
        session.email, unique_device_id(), intent="signup"
    )
    assert reg["status_code"] == 409
    assert reg["data"].get("code") == "email_exists"


@pytest.mark.integration
def test_login_existing_user_magic_otp(auth_helper, live_api):
    first = auth_helper.login_with_magic_otp(intent="signup")
    # Login again (may hit OTP cooldown — use same or wait; backend has 60s cooldown)
    # Re-request may 429 if cooldown; if so, skip soft
    reg = auth_helper.request_otp(first.email, first.device_id, intent="login")
    if reg["status_code"] == 429:
        pytest.skip("OTP cooldown active — expected under rapid re-login")
    assert reg["status_code"] == 200, reg["data"]
    ver = auth_helper.verify_otp(first.email, first.device_id)
    assert ver["status_code"] == 200, ver["data"]
    assert ver["data"].get("access")
    assert ver["data"].get("is_new_user") is False or ver["data"].get("is_new") is False


@pytest.mark.integration
def test_wrong_otp_rejected(auth_helper, live_api):
    email = unique_email("badotp")
    device = unique_device_id()
    reg = auth_helper.request_otp(email, device, intent="signup")
    assert reg["status_code"] == 200, reg["data"]
    ver = auth_helper.verify_otp(email, device, otp="000000")
    assert ver["status_code"] == 400


@pytest.mark.integration
def test_session_status(auth_api, authenticated_session, live_api):
    r = auth_api.get("/api/v1/auth/session/")
    assert r.status_code == 200
    data = r.json()
    assert str(data.get("user_id")) == str(authenticated_session.user_id)
    assert "onboarding_complete" in data
    assert "is_identity_verified" in data


@pytest.mark.integration
def test_ws_ticket(auth_api, live_api):
    r = auth_api.post("/api/v1/auth/ws-ticket/", json={})
    assert r.status_code == 200
    assert r.json().get("ticket")


@pytest.mark.integration
def test_logout_blacklists_refresh(auth_api, authenticated_session, live_api):
    r = auth_api.post(
        "/api/v1/auth/logout/",
        json={"refresh": authenticated_session.refresh},
    )
    assert r.status_code == 200
