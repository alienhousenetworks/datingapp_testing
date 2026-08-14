"""
Root conftest for the external testing suite.

- Ensures testing/ is on sys.path
- Does NOT modify backend source
- Integration markers skip cleanly if API is down
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTING_ROOT = Path(__file__).resolve().parent
if str(TESTING_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTING_ROOT))

from suite_config.test_settings import test_config  # noqa: E402


def pytest_configure(config):
    # Always assert suite-level safety flags
    try:
        test_config.assert_test_mode_flags()
    except RuntimeError as exc:
        # Still allow collection; fail at runtime of tests that call assert
        config._spyce_config_error = str(exc)


@pytest.fixture(scope="session")
def cfg():
    test_config.assert_test_mode_flags()
    return test_config


@pytest.fixture(scope="session")
def base_url(cfg):
    return cfg.base_url


@pytest.fixture
def magic_otp(cfg):
    return cfg.magic_otp
