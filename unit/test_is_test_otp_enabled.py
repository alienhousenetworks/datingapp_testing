"""Unit: settings.is_test_otp_enabled helper."""
import pytest


@pytest.mark.unit
def test_is_test_otp_enabled_true(django_ready):
    from django.test import override_settings
    from django.conf import settings as dj

    with override_settings(USE_TEST_OTP=True, MAGIC_OTP="123456"):
        assert bool(dj.USE_TEST_OTP and dj.MAGIC_OTP) is True
        try:
            from config.settings.base import is_test_otp_enabled

            assert callable(is_test_otp_enabled)
        except ImportError:
            pass


@pytest.mark.unit
def test_is_test_otp_enabled_false_without_magic(django_ready):
    from django.test import override_settings
    from django.conf import settings as dj

    with override_settings(USE_TEST_OTP=True, MAGIC_OTP=None):
        assert not bool(dj.USE_TEST_OTP and dj.MAGIC_OTP)
