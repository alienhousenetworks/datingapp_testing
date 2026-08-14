"""
Integration end-to-end happy path (magic OTP, bot off, face mock):

1. Signup + magic OTP
2. Session + me
3. Verification status + mock complete
4. Feed read
5. Heartbeat
6. Logout
"""
import pytest

from helpers.auth import AuthHelper, unique_device_id, unique_email
from helpers.api_client import APIClient


@pytest.mark.integration
@pytest.mark.slow
def test_full_user_journey(live_api, cfg, magic_otp):
    client = APIClient(base_url=live_api)
    auth = AuthHelper(client)

    email = unique_email("journey")
    device = unique_device_id("journey")

    # 1. Auth
    session = auth.login_with_magic_otp(email=email, device_id=device, intent="signup")
    assert session.access
    client.set_token(session.access)
    client.device_id = device

    # 2. Me + session
    me = client.get("/api/v1/users/me/")
    assert me.status_code == 200

    sess = client.get("/api/v1/auth/session/")
    assert sess.status_code == 200

    # 3. Face off → mock verification
    status = client.get("/api/v1/verification/status/")
    assert status.status_code == 200

    start = client.post("/api/v1/verification/start/", json={})
    assert start.status_code in (400, 403)  # real face disabled

    mock = client.post("/api/v1/verification/mock-complete/", json={})
    assert mock.status_code in (200, 201, 400)

    # 4. Feed (may be empty / incomplete profile)
    feed = client.get("/api/v1/feed/", params={"count": 10})
    assert feed.status_code == 200

    # 5. Heartbeat
    hb = client.post(
        "/api/v1/users/last-active/",
        json={"lat": 28.6139, "lon": 77.2090},
    )
    assert hb.status_code == 200

    # 6. Options catalogs (public-ish with auth)
    genders = client.get("/api/v1/genders/")
    assert genders.status_code == 200

    # 7. Logout
    out = client.post("/api/v1/auth/logout/", json={"refresh": session.refresh})
    assert out.status_code == 200
