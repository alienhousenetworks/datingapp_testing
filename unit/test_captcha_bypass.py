"""Unit: CAPTCHA_VERIFICATION_ACTIVE flag controls CaptchaService."""
import pytest


@pytest.mark.unit
def test_captcha_bypassed_when_inactive(django_ready, force_test_flags):
    from django.test import override_settings
    from core.common.utils.captcha import CaptchaService

    with override_settings(
        CAPTCHA_VERIFICATION_ACTIVE=False,
        REQUIRE_CAPTCHA=False,
    ):
        ok, msg = CaptchaService.verify_token(token=None, ip_address="127.0.0.1")
        assert ok is True
        assert "bypass" in msg.lower() or "inactive" in msg.lower() or ok


@pytest.mark.unit
def test_captcha_bypassed_with_empty_token_when_inactive(django_ready):
    from django.test import override_settings
    from core.common.utils.captcha import CaptchaService

    with override_settings(CAPTCHA_VERIFICATION_ACTIVE=False, REQUIRE_CAPTCHA=False):
        ok, _msg = CaptchaService.verify_token(token="", ip_address="127.0.0.1")
        assert ok is True


@pytest.mark.unit
def test_captcha_required_blocks_without_token(django_ready):
    from django.test import override_settings
    from core.common.utils.captcha import CaptchaService

    with override_settings(
        CAPTCHA_VERIFICATION_ACTIVE=True,
        REQUIRE_CAPTCHA=True,
        CAPTCHA_PROVIDER="recaptcha_enterprise",
        RECAPTCHA_ENTERPRISE_PROJECT_ID="demo",
        RECAPTCHA_ENTERPRISE_API_KEY="x",
        RECAPTCHA_ANDROID_SITE_KEY="site",
        RECAPTCHA_SECRET_KEY="",
        TURNSTILE_SECRET_KEY="",
    ):
        ok, msg = CaptchaService.verify_token(token=None, ip_address="127.0.0.1")
        assert ok is False
        assert "required" in msg.lower() or "captcha" in msg.lower()


@pytest.mark.unit
def test_captcha_required_blocks_without_credentials(django_ready):
    from django.test import override_settings
    from core.common.utils.captcha import CaptchaService

    with override_settings(
        CAPTCHA_VERIFICATION_ACTIVE=True,
        REQUIRE_CAPTCHA=True,
        CAPTCHA_PROVIDER="auto",
        RECAPTCHA_ENTERPRISE_PROJECT_ID="",
        RECAPTCHA_ENTERPRISE_API_KEY="",
        RECAPTCHA_SECRET_KEY="",
        TURNSTILE_SECRET_KEY="",
    ):
        ok, msg = CaptchaService.verify_token(token="fake-token", ip_address="127.0.0.1")
        assert ok is False
        assert (
            "unavailable" in msg.lower()
            or "not configured" in msg.lower()
            or "CAPTCHA" in msg
        )


@pytest.mark.unit
def test_public_config_shape(django_ready):
    from django.test import override_settings
    from core.common.utils.captcha import CaptchaService

    with override_settings(
        CAPTCHA_VERIFICATION_ACTIVE=True,
        CAPTCHA_PROVIDER="recaptcha_enterprise",
        RECAPTCHA_ANDROID_SITE_KEY="and-key",
        RECAPTCHA_IOS_SITE_KEY="ios-key",
    ):
        cfg = CaptchaService.public_config()
        assert cfg["captcha_verification_active"] is True
        assert cfg["android_site_key"] == "and-key"
        assert cfg["ios_site_key"] == "ios-key"
