"""Unit: suite + backend flag expectations for magic OTP / bot / face off."""
import pytest

from suite_config.test_settings import TestConfig, test_config


@pytest.mark.unit
def test_suite_defaults_magic_otp_bot_face():
    assert test_config.use_test_otp is True
    assert test_config.magic_otp
    assert test_config.require_captcha is False
    assert test_config.face_verification is False
    assert test_config.allow_mock_verification is True
    test_config.assert_test_mode_flags()


@pytest.mark.unit
def test_assert_fails_when_captcha_required():
    cfg = TestConfig(
        use_test_otp=True,
        magic_otp="123456",
        require_captcha=True,
        face_verification=False,
        allow_mock_verification=True,
    )
    with pytest.raises(RuntimeError, match="REQUIRE_CAPTCHA"):
        cfg.assert_test_mode_flags()


@pytest.mark.unit
def test_assert_fails_when_face_on():
    cfg = TestConfig(
        use_test_otp=True,
        magic_otp="123456",
        require_captcha=False,
        face_verification=True,
        allow_mock_verification=True,
    )
    with pytest.raises(RuntimeError, match="FACE_VERIFICATION"):
        cfg.assert_test_mode_flags()


@pytest.mark.unit
def test_assert_fails_when_test_otp_off():
    cfg = TestConfig(
        use_test_otp=False,
        magic_otp="123456",
        require_captcha=False,
        face_verification=False,
    )
    with pytest.raises(RuntimeError, match="USE_TEST_OTP"):
        cfg.assert_test_mode_flags()


@pytest.mark.unit
def test_api_v1_path(cfg):
    assert cfg.api_v1.endswith("/api/v1")
