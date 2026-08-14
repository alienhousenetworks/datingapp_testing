"""Auth helpers using MAGIC_OTP (USE_TEST_OTP path). Captcha omitted (bot off)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from suite_config.test_settings import test_config
from helpers.api_client import APIClient


def unique_email(prefix: str = "pytest") -> str:
    return f"{prefix}+{uuid.uuid4().hex[:12]}@example.com"


def unique_device_id(prefix: str = "test-device") -> str:
    return f"{prefix}-{uuid.uuid4()}"


@dataclass
class AuthSession:
    email: str
    device_id: str
    access: str
    refresh: str
    user_id: str
    is_new_user: bool
    raw: dict


class AuthHelper:
    """
    Full OTP register → magic OTP verify flow.

    Backend paths (see core/apps/auth/views.py + services.py):
      POST /api/v1/auth/register/     {email, device_id, intent?}
      POST /api/v1/auth/otp/verify/   {email, otp, device_id}
    """

    def __init__(self, client: Optional[APIClient] = None):
        self.client = client or APIClient()
        test_config.assert_test_mode_flags()

    def request_otp(
        self,
        email: str,
        device_id: str,
        intent: Optional[str] = "signup",
    ) -> dict:
        body = {
            "email": email,
            "device_id": device_id,
        }
        # Bot off: no captcha_token
        if intent:
            body["intent"] = intent
        resp = self.client.post(
            "/api/v1/auth/register/",
            json=body,
            auth=False,
        )
        return {"status_code": resp.status_code, "data": _safe_json(resp), "response": resp}

    def verify_otp(
        self,
        email: str,
        device_id: str,
        otp: Optional[str] = None,
    ) -> dict:
        body = {
            "email": email,
            "otp": otp or test_config.magic_otp,
            "device_id": device_id,
        }
        resp = self.client.post(
            "/api/v1/auth/otp/verify/",
            json=body,
            auth=False,
        )
        return {"status_code": resp.status_code, "data": _safe_json(resp), "response": resp}

    def login_with_magic_otp(
        self,
        email: Optional[str] = None,
        device_id: Optional[str] = None,
        intent: str = "signup",
    ) -> AuthSession:
        email = email or unique_email()
        device_id = device_id or unique_device_id()

        reg = self.request_otp(email, device_id, intent=intent)
        if reg["status_code"] not in (200, 201):
            raise AssertionError(
                f"OTP request failed ({reg['status_code']}): {reg['data']}"
            )

        ver = self.verify_otp(email, device_id)
        if ver["status_code"] != 200:
            raise AssertionError(
                f"OTP verify failed ({ver['status_code']}): {ver['data']}"
            )

        data = ver["data"] or {}
        access = data.get("access")
        refresh = data.get("refresh")
        user_id = str(data.get("user_id") or "")
        if not access or not refresh:
            raise AssertionError(f"Missing tokens in verify response: {data}")

        self.client.set_token(access)
        self.client.device_id = device_id

        return AuthSession(
            email=email,
            device_id=device_id,
            access=access,
            refresh=refresh,
            user_id=user_id,
            is_new_user=bool(data.get("is_new_user", data.get("is_new", False))),
            raw=data,
        )


def _safe_json(resp) -> dict:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"_raw": data}
    except Exception:
        return {"_text": getattr(resp, "text", "")[:500]}
