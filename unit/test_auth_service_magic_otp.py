"""Unit: AuthService uses MAGIC_OTP when USE_TEST_OTP is on."""
import pytest


@pytest.mark.unit
def test_send_otp_stores_magic_otp_hash(django_ready, force_test_flags):
    from django.core.cache import cache
    from django.test import override_settings
    from core.apps.auth.services import AuthService
    from core.common.redis.keys import RedisKeys

    email = "magic-otp-unit@example.com"

    with override_settings(
        USE_TEST_OTP=True,
        MAGIC_OTP="123456",
        REQUIRE_CAPTCHA=False,
        DISABLE_RATE_LIMITING=True,
    ):
        cache.clear()
        ok, msg = AuthService.send_otp(
            email, ip_address="127.0.0.1", captcha_token=None
        )
        assert ok is True, msg
        assert "test mode" in msg.lower() or "otp sent" in msg.lower()

        otp_key = RedisKeys.get_otp_key(email)
        stored = cache.get(otp_key)
        expected = AuthService._hash_otp("123456")
        assert stored == expected


@pytest.mark.unit
def test_verify_magic_otp_creates_user(django_ready, force_test_flags):
    from django.core.cache import cache
    from django.contrib.auth import get_user_model
    from django.test import override_settings
    from core.apps.auth.services import AuthService
    from core.common.redis.keys import RedisKeys

    User = get_user_model()
    email = "verify-magic@example.com"

    with override_settings(
        USE_TEST_OTP=True,
        MAGIC_OTP="123456",
        DISABLE_RATE_LIMITING=True,
        REQUIRE_CAPTCHA=False,
    ):
        cache.clear()
        otp_key = RedisKeys.get_otp_key(email)
        cache.set(otp_key, AuthService._hash_otp("123456"), timeout=300)

        success, payload, err = AuthService.verify_otp(
            email=email,
            otp="123456",
            device_id="unit-device-1",
            ip_address="127.0.0.1",
            user_agent="pytest",
        )
        assert success is True, err
        assert payload.get("access")
        assert payload.get("refresh")
        user = User.objects.get(email=email)
        assert user.is_otp_verified is True
        assert user.is_email_verified is True
        # Identity is NOT granted by OTP alone
        assert user.is_identity_verified is False


@pytest.mark.unit
def test_verify_wrong_otp_fails(django_ready, force_test_flags):
    from django.core.cache import cache
    from django.test import override_settings
    from core.apps.auth.services import AuthService
    from core.common.redis.keys import RedisKeys

    email = "wrong-otp@example.com"

    with override_settings(DISABLE_RATE_LIMITING=True):
        cache.clear()
        cache.set(
            RedisKeys.get_otp_key(email),
            AuthService._hash_otp("123456"),
            timeout=300,
        )

        success, _payload, err = AuthService.verify_otp(
            email=email,
            otp="000000",
            device_id="unit-device-2",
            ip_address="127.0.0.1",
            user_agent="pytest",
        )
        assert success is False
        assert "invalid" in err.lower() or "expired" in err.lower()
