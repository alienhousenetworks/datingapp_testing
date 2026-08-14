"""
Django bootstrap for unit tests that import backend modules.

PYTHONPATH:
  - backend/datingapp        → package `core`
  - backend/datingapp/core   → package `config`
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

TESTING_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = TESTING_ROOT.parent / "backend" / "datingapp"
BACKEND_CORE = BACKEND_ROOT / "core"

for p in (str(BACKEND_ROOT), str(BACKEND_CORE), str(TESTING_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Prefer backend core env files if present (read-only)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
os.environ.setdefault("ENV", "development")
os.environ.setdefault("DEBUG", "True")

# Force test-mode flags (override any ambient production-ish env)
os.environ["USE_TEST_OTP"] = "True"
os.environ["MAGIC_OTP"] = os.environ.get("MAGIC_OTP", "123456")
os.environ["REQUIRE_CAPTCHA"] = "False"
os.environ["FACE_VERIFICATION"] = "False"
os.environ["ALLOW_MOCK_VERIFICATION"] = "True"
# Avoid hard rate-limit flakiness in unit tests when Redis is shared
os.environ.setdefault("DISABLE_RATE_LIMITING", "True")


def pytest_configure(config):
    """Configure Django once for unit package."""
    try:
        import django
        from django.conf import settings

        if not settings.configured:
            django.setup()
        else:
            # Ensure critical flags even if already configured
            settings.USE_TEST_OTP = True
            settings.MAGIC_OTP = os.environ.get("MAGIC_OTP", "123456")
            settings.REQUIRE_CAPTCHA = False
            settings.CAPTCHA_VERIFICATION_ACTIVE = False
            settings.FACE_VERIFICATION = False
            settings.ALLOW_MOCK_VERIFICATION = True
            settings.DISABLE_RATE_LIMITING = True
    except Exception as exc:
        # Pure unit tests (no Django) can still run; Django-dependent ones skip
        config._django_setup_error = str(exc)


@pytest.fixture(scope="session")
def django_ready():
    """Skip if Django cannot start (missing DB libs, etc.)."""
    try:
        import django
        from django.conf import settings

        if not settings.configured:
            django.setup()
        return True
    except Exception as exc:
        pytest.skip(f"Django not available for unit tests: {exc}")


@pytest.fixture
def force_test_flags(django_ready):
    """Override Django settings for test-mode flags (no backend file writes)."""
    from django.conf import settings
    from django.test import override_settings

    cm = override_settings(
        USE_TEST_OTP=True,
        MAGIC_OTP="123456",
        REQUIRE_CAPTCHA=False,
        CAPTCHA_VERIFICATION_ACTIVE=False,
        FACE_VERIFICATION=False,
        ALLOW_MOCK_VERIFICATION=True,
        DISABLE_RATE_LIMITING=True,
        ENV="development",
    )
    cm.enable()
    try:
        yield settings
    finally:
        cm.disable()
