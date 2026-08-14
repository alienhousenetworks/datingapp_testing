"""
Central test configuration.

Mirrors backend QA flags without writing into the backend tree:
  - USE_TEST_OTP=True  → MAGIC_OTP path (no real email)
  - REQUIRE_CAPTCHA=False → bot/Turnstile off
  - FACE_VERIFICATION=False → mock face verification
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

TESTING_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = TESTING_ROOT.parent
BACKEND_ROOT = WORKSPACE_ROOT / "backend" / "datingapp"
BACKEND_CORE = BACKEND_ROOT / "core"

# Load testing/.env if present (optional dependency)
try:
    from dotenv import load_dotenv

    load_dotenv(TESTING_ROOT / ".env", override=False)
except ImportError:
    pass


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class TestConfig:
    __test__ = False  # not a pytest test class
    # API
    base_url: str = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    http_timeout: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))

    # Magic OTP (backend AuthService when USE_TEST_OTP + MAGIC_OTP)
    use_test_otp: bool = True
    magic_otp: str = "123456"

    # Bot protection off
    require_captcha: bool = False

    # Face verification off → mock path
    face_verification: bool = False
    allow_mock_verification: bool = True

    # Paths (for unit tests that import backend)
    testing_root: Path = TESTING_ROOT
    workspace_root: Path = WORKSPACE_ROOT
    backend_root: Path = BACKEND_ROOT
    backend_core: Path = BACKEND_CORE

    # Django settings module for unit tests
    django_settings_module: str = "config.settings.dev"

    @staticmethod
    def from_env() -> "TestConfig":
        return TestConfig(
            base_url=os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
            http_timeout=float(os.getenv("HTTP_TIMEOUT_SECONDS", "30")),
            use_test_otp=_bool("USE_TEST_OTP", True),
            magic_otp=(os.getenv("MAGIC_OTP", "123456").strip() or "123456"),
            require_captcha=_bool("REQUIRE_CAPTCHA", False),
            face_verification=_bool("FACE_VERIFICATION", False),
            allow_mock_verification=_bool("ALLOW_MOCK_VERIFICATION", True),
            testing_root=TESTING_ROOT,
            workspace_root=WORKSPACE_ROOT,
            backend_root=BACKEND_ROOT,
            backend_core=BACKEND_CORE,
            django_settings_module=os.getenv(
                "DJANGO_SETTINGS_MODULE", "config.settings.dev"
            ),
        )

    @property
    def api_v1(self) -> str:
        return f"{self.base_url}/api/v1"

    def assert_test_mode_flags(self) -> None:
        """Fail fast if someone tries to run suite with production-unsafe intent."""
        if not self.use_test_otp:
            raise RuntimeError(
                "USE_TEST_OTP must be True for this suite (magic OTP)."
            )
        if not self.magic_otp:
            raise RuntimeError("MAGIC_OTP must be set (e.g. 123456).")
        if self.require_captcha:
            raise RuntimeError(
                "REQUIRE_CAPTCHA must be False for this suite (bot off)."
            )
        if self.face_verification:
            raise RuntimeError(
                "FACE_VERIFICATION must be False for this suite (mock face)."
            )


test_config = TestConfig.from_env()
