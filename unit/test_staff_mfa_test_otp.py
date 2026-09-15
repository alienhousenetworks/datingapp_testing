"""Unit: Staff MFA supports MAGIC_OTP / test OTP for second factor verification."""
from unittest.mock import MagicMock, patch
import pytest
from django.test import override_settings


class DummyUser:
    def __init__(self, pk=1, email="admin@example.com", is_staff=True, is_active=True):
        self.pk = pk
        self.id = pk
        self.email = email
        self.is_staff = is_staff
        self.is_active = is_active
        self.is_authenticated = True
        self.is_anonymous = False
        self.otp_device = None


class DummyDevice:
    def __init__(self, user_id=1, persistent_id="email/1"):
        self.user_id = user_id
        self.persistent_id = persistent_id
        self.confirmed = True


@pytest.mark.unit
def test_staff_mfa_token_form_accepts_magic_otp(django_ready, force_test_flags):
    from core.common.auth.staff_mfa import StaffAuthenticationTokenForm, is_test_otp_active

    user = DummyUser(pk=42, email="admin_mfa@example.com")
    device = DummyDevice(user_id=42)

    with override_settings(
        USE_TEST_OTP=True,
        MAGIC_OTP="123456",
        DISABLE_RATE_LIMITING=True,
    ):
        assert is_test_otp_active() is True
        form = StaffAuthenticationTokenForm(user=user, initial_device=device)
        verified_device = form._verify_token(user, "123456", device=device)
        assert verified_device is device
        assert verified_device.user_id == 42


@pytest.mark.unit
def test_staff_mfa_backup_form_accepts_magic_otp(django_ready, force_test_flags):
    from core.common.auth.staff_mfa import StaffBackupTokenForm

    user = DummyUser(pk=42, email="admin_backup@example.com")
    device = DummyDevice(user_id=42)

    with override_settings(
        USE_TEST_OTP=True,
        MAGIC_OTP="123456",
        DISABLE_RATE_LIMITING=True,
    ):
        form = StaffBackupTokenForm(user=user, initial_device=device)
        verified_device = form._verify_token(user, "123456", device=device)
        assert verified_device is device
        assert verified_device.user_id == 42


@pytest.mark.unit
def test_staff_mfa_custom_magic_otp_value(django_ready, force_test_flags):
    from core.common.auth.staff_mfa import StaffAuthenticationTokenForm

    user = DummyUser(pk=42, email="admin_custom@example.com")
    device = DummyDevice(user_id=42)

    with override_settings(
        USE_TEST_OTP=True,
        MAGIC_OTP="987654",
        DISABLE_RATE_LIMITING=True,
    ):
        form = StaffAuthenticationTokenForm(user=user, initial_device=device)
        # Custom magic OTP matches
        verified_device = form._verify_token(user, "987654", device=device)
        assert verified_device is device


@pytest.mark.unit
def test_staff_mfa_resolves_fallback_device_when_none(django_ready, force_test_flags):
    from core.common.auth.staff_mfa import StaffAuthenticationTokenForm

    user = DummyUser(pk="a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11", email="admin_fallback@example.com")
    fallback_device = DummyDevice(user_id="a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11")

    with override_settings(
        USE_TEST_OTP=True,
        MAGIC_OTP="123456",
        DISABLE_RATE_LIMITING=True,
    ):
        with patch("two_factor.utils.default_device", return_value=fallback_device):
            form = StaffAuthenticationTokenForm(user=user, initial_device=None)
            verified_device = form._verify_token(user, "123456", device=None)
            assert verified_device is fallback_device


@pytest.mark.unit
def test_staff_mfa_disabled_when_use_test_otp_false(django_ready, force_test_flags):
    from core.common.auth.staff_mfa import (
        StaffAuthenticationTokenForm,
        is_test_otp_active,
    )

    user = DummyUser(pk=42, email="admin_disabled@example.com")
    device = DummyDevice(user_id=42)
    device.verify_token = MagicMock(return_value=False)

    with override_settings(
        USE_TEST_OTP=False,
        MAGIC_OTP="123456",
        DISABLE_RATE_LIMITING=True,
    ):
        assert is_test_otp_active() is False
        form = StaffAuthenticationTokenForm(user=user, initial_device=device)
        with pytest.raises(Exception):
            form._verify_token(user, "123456", device=device)
