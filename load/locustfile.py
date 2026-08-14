"""
Locust load tests for SPYCE backend.

Assumes:
  DISABLE_RATE_LIMITING=True
  USE_TEST_OTP=True, MAGIC_OTP=123456
  REQUIRE_CAPTCHA=False
  FACE_VERIFICATION=False

Run:
  locust -f load/locustfile.py --host http://127.0.0.1:8000
  # headless:
  locust -f load/locustfile.py --host http://127.0.0.1:8000 \
    --users 20 --spawn-rate 5 --run-time 60s --headless
"""
from __future__ import annotations

import os
import uuid

from locust import HttpUser, between, events, task

MAGIC_OTP = os.getenv("MAGIC_OTP", "123456")


def _email() -> str:
    return f"load+{uuid.uuid4().hex[:10]}@example.com"


def _device() -> str:
    return f"load-device-{uuid.uuid4()}"


class SpyceUser(HttpUser):
    """Simulated dating app client: auth → onboarding → me → feed → interactions loop."""

    wait_time = between(0.5, 2.0)

    def on_start(self):
        self.email = _email()
        self.device_id = _device()
        self.access = None
        self.refresh = None
        self.user_id = None
        self.seen_candidates: list[str] = []
        self._authenticate()

    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Device-ID": self.device_id,
        }
        if self.access:
            h["Authorization"] = f"Bearer {self.access}"
        return h

    def _authenticate(self):
        # 1. Register (OTP request)
        with self.client.post(
            "/api/v1/auth/register/",
            json={
                "email": self.email,
                "device_id": self.device_id,
                "intent": "signup",
            },
            headers=self._headers(),
            name="auth:register",
            catch_response=True,
        ) as reg:
            if reg.status_code == 200:
                reg.success()
            elif reg.status_code == 429:
                reg.failure("rate limited on register")
                return
            else:
                reg.failure(f"register {reg.status_code}: {reg.text[:120]}")
                return

        # 2. Verify OTP
        with self.client.post(
            "/api/v1/auth/otp/verify/",
            json={
                "email": self.email,
                "otp": MAGIC_OTP,
                "device_id": self.device_id,
            },
            headers=self._headers(),
            name="auth:otp_verify",
            catch_response=True,
        ) as ver:
            if ver.status_code != 200:
                ver.failure(f"verify {ver.status_code}: {ver.text[:120]}")
                return
            data = ver.json()
            self.access = data.get("access")
            self.refresh = data.get("refresh")
            self.user_id = str(data.get("user_id") or "")
            if not self.access:
                ver.failure("no access token")
                return
            else:
                ver.success()

        # 3. Face mock verification (FACE_VERIFICATION=False)
        self.client.post(
            "/api/v1/verification/mock-complete/",
            json={},
            headers=self._headers(),
            name="verification:mock_complete",
        )

        # 4. Fetch option catalogs to find valid gender & sexuality IDs
        gender_id = 1
        sexuality_id = 1

        g_res = self.client.get(
            "/api/v1/genders/",
            headers=self._headers(),
            name="options:genders_onboarding",
        )
        if g_res.status_code == 200:
            try:
                g_list = g_res.json()
                if isinstance(g_list, list) and len(g_list) > 0:
                    gender_id = g_list[0].get("id", 1)
            except Exception:
                pass

        s_res = self.client.get(
            "/api/v1/sexualities/",
            headers=self._headers(),
            name="options:sexualities_onboarding",
        )
        if s_res.status_code == 200:
            try:
                s_list = s_res.json()
                if isinstance(s_list, list) and len(s_list) > 0:
                    sexuality_id = s_list[0].get("id", 1)
            except Exception:
                pass

        # 5. Populate profile onboarding details (sets is_discoverable = True)
        username = f"usr_{uuid.uuid4().hex[:12]}"
        onboarding_payload = {
            "username": username,
            "name": f"User {username[:6]}",
            "date_of_birth": "1998-05-15",
            "gender": gender_id,
            "sexuality": sexuality_id,
            "preferred_genders": [gender_id],
            "bio": "Load testing user profile with complete details for discovery feed testing.",
            "latitude": 12.9716,
            "longitude": 77.5946,
        }
        self.client.patch(
            "/api/v1/profile/me/",
            json=onboarding_payload,
            headers=self._headers(),
            name="profile:onboarding_patch",
        )

        # 6. Initialize presence & location in Redis
        self.client.post(
            "/api/v1/users/last-active/",
            json={"lat": 12.9716, "lon": 77.5946},
            headers=self._headers(),
            name="users:last_active_init",
        )

    @task(5)
    def health(self):
        self.client.get("/health/", name="health")

    @task(10)
    def users_me(self):
        if not self.access:
            return
        self.client.get("/api/v1/users/me/", headers=self._headers(), name="users:me")

    @task(8)
    def session(self):
        if not self.access:
            return
        self.client.get(
            "/api/v1/auth/session/",
            headers=self._headers(),
            name="auth:session",
        )

    @task(15)
    def feed(self):
        if not self.access:
            return
        res = self.client.get(
            "/api/v1/feed/",
            params={"count": 10},
            headers=self._headers(),
            name="feed:list",
        )
        if res.status_code == 200:
            try:
                data = res.json()
                results = data.get("results") or []
                for item in results:
                    cand_id = item.get("id") or item.get("user_id")
                    if cand_id and str(cand_id) not in self.seen_candidates:
                        self.seen_candidates.append(str(cand_id))
            except Exception:
                pass

    @task(5)
    def like_candidate(self):
        if not self.access or not self.seen_candidates:
            return
        target_id = self.seen_candidates.pop(0)
        self.client.post(
            "/api/v1/interaction/send/",
            json={"target_user_id": target_id},
            headers=self._headers(),
            name="interaction:like",
        )

    @task(3)
    def pass_candidate(self):
        if not self.access or not self.seen_candidates:
            return
        target_id = self.seen_candidates.pop(0)
        self.client.post(
            "/api/v1/interaction/pass/",
            json={"target_user_id": target_id},
            headers=self._headers(),
            name="interaction:pass",
        )

    @task(2)
    def received_likes(self):
        if not self.access:
            return
        self.client.get(
            "/api/v1/interaction/received/",
            headers=self._headers(),
            name="interaction:received",
        )

    @task(6)
    def last_active(self):
        if not self.access:
            return
        self.client.post(
            "/api/v1/users/last-active/",
            json={"lat": 12.9716, "lon": 77.5946},
            headers=self._headers(),
            name="users:last_active",
        )

    @task(4)
    def profile_me(self):
        if not self.access:
            return
        self.client.get(
            "/api/v1/profile/me/",
            headers=self._headers(),
            name="profile:me",
        )

    @task(3)
    def option_catalogs(self):
        if not self.access:
            return
        for path, name in (
            ("/api/v1/genders/", "options:genders"),
            ("/api/v1/intents/", "options:intents"),
            ("/api/v1/sexualities/", "options:sexualities"),
            ("/api/v1/turn_ons/", "options:turn_ons"),
            ("/api/v1/mood_options/", "options:mood_options"),
        ):
            self.client.get(path, headers=self._headers(), name=name)

    @task(2)
    def confessions(self):
        if not self.access:
            return
        self.client.get(
            "/api/v1/social/",
            headers=self._headers(),
            name="social:list",
        )

    @task(2)
    def verification_status(self):
        if not self.access:
            return
        self.client.get(
            "/api/v1/verification/status/",
            headers=self._headers(),
            name="verification:status",
        )

    @task(2)
    def subscription_status(self):
        if not self.access:
            return
        self.client.get(
            "/api/v1/subscriptions/status/",
            headers=self._headers(),
            name="subscriptions:status",
        )

    @task(1)
    def ws_ticket(self):
        if not self.access:
            return
        self.client.post(
            "/api/v1/auth/ws-ticket/",
            json={},
            headers=self._headers(),
            name="auth:ws_ticket",
        )


class AuthOnlyUser(HttpUser):
    """Hammer auth endpoints only (signup storm with magic OTP)."""

    wait_time = between(1.0, 3.0)
    weight = 1  # lower relative weight if mixed

    @task
    def signup_flow(self):
        email = _email()
        device = _device()
        headers = {"Content-Type": "application/json", "X-Device-ID": device}
        self.client.post(
            "/api/v1/auth/register/",
            json={"email": email, "device_id": device, "intent": "signup"},
            headers=headers,
            name="storm:register",
        )
        self.client.post(
            "/api/v1/auth/otp/verify/",
            json={"email": email, "otp": MAGIC_OTP, "device_id": device},
            headers=headers,
            name="storm:verify",
        )


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    print(
        f"[SPYCE load] MAGIC_OTP={MAGIC_OTP} | "
        "bot=off (no captcha) | face=mock | host="
        f"{getattr(environment, 'host', None)}"
    )

