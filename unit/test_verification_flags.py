"""Unit: face verification off → mock allowed; start path blocked at service helpers."""
import pytest


@pytest.mark.unit
def test_face_verification_disabled(django_ready, force_test_flags):
    from core.apps.verification.services import (
        is_face_verification_enabled,
        is_mock_verification_allowed,
    )

    assert is_face_verification_enabled() is False
    assert is_mock_verification_allowed() is True


@pytest.mark.unit
def test_face_on_disables_mock(django_ready):
    from django.test import override_settings
    from core.apps.verification import services as vs

    with override_settings(FACE_VERIFICATION=True, ALLOW_MOCK_VERIFICATION=True):
        assert vs.is_face_verification_enabled() is True
        assert vs.is_mock_verification_allowed() is False


@pytest.mark.unit
def test_max_retries_default(django_ready, force_test_flags):
    from core.apps.verification.services import get_max_retries

    assert get_max_retries() >= 1
