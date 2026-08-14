"""Integration fixtures: live HTTP against BASE_URL (magic OTP, bot/face off)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import requests

TESTING_ROOT = Path(__file__).resolve().parent.parent
if str(TESTING_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTING_ROOT))

from suite_config.test_settings import test_config
from helpers.api_client import APIClient
from helpers.auth import AuthHelper, unique_device_id, unique_email


def _api_up() -> bool:
    try:
        r = requests.get(
            f"{test_config.base_url}/health/",
            timeout=3,
        )
        return r.status_code < 500
    except Exception:
        return False


@pytest.fixture(scope="session")
def live_api():
    if not _api_up():
        pytest.skip(
            f"Backend not reachable at {test_config.base_url}. "
            "Start the API (runserver/docker) then re-run integration tests."
        )
    test_config.assert_test_mode_flags()
    return test_config.base_url


@pytest.fixture
def api(live_api):
    return APIClient(base_url=live_api)


@pytest.fixture
def auth_helper(api):
    return AuthHelper(api)


@pytest.fixture
def authenticated_session(auth_helper):
    """Fresh user via magic OTP signup."""
    return auth_helper.login_with_magic_otp(
        email=unique_email("int"),
        device_id=unique_device_id("int"),
        intent="signup",
    )


@pytest.fixture
def auth_api(api, authenticated_session):
    api.set_token(authenticated_session.access)
    api.device_id = authenticated_session.device_id
    return api
