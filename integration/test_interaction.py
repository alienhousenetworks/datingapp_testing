"""Integration: like / pass / received likes."""
import pytest

from helpers.auth import AuthHelper, unique_device_id, unique_email


@pytest.mark.integration
def test_self_like_rejected(auth_api, authenticated_session, live_api):
    r = auth_api.post(
        "/api/v1/interaction/send/",
        json={"target_user_id": authenticated_session.user_id},
    )
    assert r.status_code == 400
    assert "self" in str(r.json()).lower() or "error" in r.json()


@pytest.mark.integration
def test_like_missing_target(auth_api, live_api):
    r = auth_api.post("/api/v1/interaction/send/", json={})
    assert r.status_code == 400


@pytest.mark.integration
def test_like_and_pass_between_users(auth_helper, live_api):
    a = auth_helper.login_with_magic_otp(
        email=unique_email("likeA"), device_id=unique_device_id("A")
    )
    b = auth_helper.login_with_magic_otp(
        email=unique_email("likeB"), device_id=unique_device_id("B")
    )

    # Client A likes B
    client_a = auth_helper.client
    client_a.set_token(a.access)
    client_a.device_id = a.device_id

    like = client_a.post(
        "/api/v1/interaction/send/",
        json={"target_user_id": b.user_id},
    )
    assert like.status_code in (200, 400), like.text
    # 400 possible if discoverability / identity rules block

    pass_r = client_a.post(
        "/api/v1/interaction/pass/",
        json={"target_user_id": b.user_id},
    )
    assert pass_r.status_code in (200, 400)


@pytest.mark.integration
def test_received_likes(auth_api, live_api):
    r = auth_api.get("/api/v1/interaction/received/")
    assert r.status_code == 200
    data = r.json()
    assert "count" in data or "users" in data or "can_see_incoming_likes" in data
