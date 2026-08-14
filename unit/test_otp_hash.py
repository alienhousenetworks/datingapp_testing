"""Unit: OTP hashing uses HMAC-SHA256 with SECRET_KEY pepper."""
import hashlib
import hmac

import pytest


@pytest.mark.unit
def test_otp_hash_matches_auth_service(django_ready):
    from django.conf import settings
    from core.apps.auth.services import AuthService

    otp = "123456"
    expected = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        otp.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert AuthService._hash_otp(otp) == expected
    # Must not be plain SHA-256
    assert AuthService._hash_otp(otp) != hashlib.sha256(otp.encode()).hexdigest()


@pytest.mark.unit
def test_device_id_hash_stable(django_ready):
    from core.apps.auth.services import AuthService

    device = "test-device-abc"
    h1 = AuthService._hash_device_id(device)
    h2 = AuthService._hash_device_id(device)
    assert h1 == h2
    assert h1 == hashlib.sha256(device.encode()).hexdigest()


@pytest.mark.unit
def test_magic_otp_value_is_six_digits():
    from suite_config.test_settings import test_config

    assert test_config.magic_otp.isdigit()
    assert len(test_config.magic_otp) == 6
