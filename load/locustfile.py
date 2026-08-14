"""
Locust load tests for the SPYCE dating API.

Each virtual user signs up (magic OTP), completes onboarding, then loops
across the real client surfaces:
- Feed & Feed AI (Django v1 + FastAPI v2 with filters & cache refresh)
- Like / Pass / Interested / Received Likes / Matches
- Send Request & Accept Request (Direct Conversation Requests)
- Confession Social (Create, Detail, Relate/Like, Repost, Comments, Chat Request, Request List/Count/Accept/Reject, Moods)
- Profile (Me, Patch, Other, Username Available, Mood get/set, Avatars, Upload Status)
- Catalogs, Theme, Geo, Presence, Notifications, Subscriptions, Wallet, Call, Verification, Moderation, Analytics, Health.

Assumes the target backend has:
  DISABLE_RATE_LIMITING=True
  USE_TEST_OTP=True, MAGIC_OTP=123456
  REQUIRE_CAPTCHA=False
  FACE_VERIFICATION=False

Run:
  locust -f load/locustfile.py --host http://127.0.0.1:8000
  locust -f load/locustfile.py --host https://api01.spycenow.com \
    --users 50 --spawn-rate 5 --run-time 3m --headless
"""
from __future__ import annotations

import os
import random
import threading
import time
import uuid
from collections import deque
from typing import Any

from locust import HttpUser, between, events, task

MAGIC_OTP = os.getenv("MAGIC_OTP", "123456")
LAT = float(os.getenv("LOAD_LAT", "12.9716"))
LON = float(os.getenv("LOAD_LON", "77.5946"))

# Shared across VUs so likes/requests can land on other load-test users and create matches.
_lock = threading.Lock()
_user_ids: deque[str] = deque(maxlen=1000)
_feed_ids: deque[str] = deque(maxlen=1000)
_confession_ids: deque[str] = deque(maxlen=500)

# (receiver_user_id, request_id)
_pending_confession_reqs: deque[tuple[str, str]] = deque(maxlen=500)
# (receiver_user_id, sender_user_id)
_pending_conversation_reqs: deque[tuple[str, str]] = deque(maxlen=500)

MOOD_TAGS = (
    "LONELY",
    "CURIOUS",
    "HAPPY",
    "ANXIOUS",
    "GRATEFUL",
    "FANTASY",
)

CITIES = ("Bangalore", "Mumbai", "Delhi", "Hyderabad", "Pune")


def _email() -> str:
    return f"load+{uuid.uuid4().hex[:10]}@example.com"


def _device() -> str:
    return f"load-device-{uuid.uuid4()}"


def _jitter_coords() -> tuple[float, float]:
    return (
        round(LAT + random.uniform(-0.04, 0.04), 6),
        round(LON + random.uniform(-0.04, 0.04), 6),
    )


def _pool_add(pool: deque, value: Any) -> None:
    if not value:
        return
    with _lock:
        if value not in pool:
            pool.append(value)


def _pool_pick(pool: deque, exclude: str | None = None) -> Any | None:
    with _lock:
        if not pool:
            return None
        choices = [x for x in pool if x and (isinstance(x, tuple) or str(x) != exclude)]
    return random.choice(choices) if choices else None


def _pop_pending_for(pool: deque[tuple[str, str]], target_receiver_id: str) -> str | None:
    with _lock:
        for item in list(pool):
            receiver_id, payload_id = item
            if receiver_id == target_receiver_id:
                pool.remove(item)
                return payload_id
    return None


def _json(res):
    try:
        return res.json()
    except Exception:
        return None


def _as_items(data) -> list:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("results", "users", "data", "items"):
        val = data.get(key)
        if isinstance(val, list):
            return val
    return []


def _extract_ids(data, *keys: str) -> list[str]:
    ids: list[str] = []
    for item in _as_items(data):
        if not isinstance(item, dict):
            continue
        for key in keys:
            val = item.get(key)
            if isinstance(val, dict):
                val = val.get("id") or val.get("user_id")
            if val:
                ids.append(str(val))
                break
        profile = item.get("profile") or item.get("profile_card") or {}
        if isinstance(profile, dict):
            nested = profile.get("user_id") or profile.get("id")
            if nested:
                ids.append(str(nested))
    # preserve order, drop dups
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


class SpyceUser(HttpUser):
    """Full app session: onboard once, then hit every client API surface."""

    wait_time = between(0.3, 1.2)
    weight = 10

    def on_start(self):
        self.email = _email()
        self.device_id = _device()
        self.access = None
        self.refresh = None
        self.user_id = None
        self.username = f"usr_{uuid.uuid4().hex[:12]}"
        self.lat, self.lon = _jitter_coords()
        self.gender_id = 1
        self.sexuality_id = 1
        self.mood_ids: list = []
        self.seen_candidates: deque[str] = deque(maxlen=100)
        self.confession_ids: deque[str] = deque(maxlen=50)
        self.match_ids: deque[str] = deque(maxlen=30)
        self.conversation_ids: deque[str] = deque(maxlen=30)
        self._authenticate_and_onboard()

    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Device-ID": self.device_id,
        }
        if self.access:
            h["Authorization"] = f"Bearer {self.access}"
        return h

    def _req(
        self,
        method: str,
        path: str,
        name: str,
        expected: tuple[int, ...] = (200, 201, 204, 304),
        also_ok: tuple[int, ...] = (400, 403, 404, 409, 429),
        **kwargs,
    ):
        kwargs.setdefault("headers", self._headers())
        with self.client.request(
            method,
            path,
            name=name,
            catch_response=True,
            **kwargs,
        ) as res:
            if res.status_code in expected or res.status_code in also_ok:
                res.success()
            else:
                body = (res.text or "")[:120]
                res.failure(f"{name} {res.status_code}: {body}")
        return res

    def _remember_users(self, ids: list[str]) -> None:
        for uid in ids:
            if uid == self.user_id:
                continue
            if uid not in self.seen_candidates:
                self.seen_candidates.append(uid)
            _pool_add(_feed_ids, uid)

    def _pick_target(self) -> str | None:
        if self.seen_candidates:
            return self.seen_candidates.popleft()
        return _pool_pick(_feed_ids, self.user_id) or _pool_pick(_user_ids, self.user_id)

    def _ensure_auth(self) -> bool:
        if self.access:
            return True
        self._authenticate_and_onboard()
        return self.access is not None

    def _authenticate_and_onboard(self):
        # Retry authentication if rate-limited during high-concurrency spawn
        for attempt in range(3):
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
                if reg.status_code in (200, 201):
                    reg.success()
                elif reg.status_code == 429:
                    reg.success()
                    time.sleep(0.5)
                    continue
                else:
                    reg.failure(f"register {reg.status_code}: {(reg.text or '')[:120]}")
                    return

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
                if ver.status_code == 429:
                    ver.success()
                    time.sleep(0.5)
                    continue
                elif ver.status_code not in (200, 201):
                    ver.failure(f"verify {ver.status_code}: {(ver.text or '')[:120]}")
                    return
                data = _json(ver) or {}
                self.access = data.get("access")
                self.refresh = data.get("refresh")
                self.user_id = str(data.get("user_id") or "")
                if not self.access:
                    ver.failure("no access token")
                    return
                ver.success()
                break

        if not self.access:
            return

        self._req(
            "POST",
            "/api/v1/verification/mock-complete/",
            "verification:mock_complete",
            json={},
        )

        g_res = self._req("GET", "/api/v1/genders/", "options:genders_onboarding")
        g_list = _json(g_res)
        if isinstance(g_list, list) and g_list:
            self.gender_id = g_list[0].get("id", 1)

        s_res = self._req("GET", "/api/v1/sexualities/", "options:sexualities_onboarding")
        s_list = _json(s_res)
        if isinstance(s_list, list) and s_list:
            self.sexuality_id = s_list[0].get("id", 1)

        m_res = self._req("GET", "/api/v1/mood_options/", "options:moods_onboarding")
        m_list = _json(m_res)
        if isinstance(m_list, list):
            self.mood_ids = [m.get("id") for m in m_list[:2] if m.get("id")]

        self._req(
            "GET",
            f"/api/v1/profile/username-available/?username={self.username}",
            "profile:username_available",
        )

        self._req(
            "PATCH",
            "/api/v1/profile/me/",
            "profile:onboarding_patch",
            json={
                "username": self.username,
                "name": f"User {self.username[:6]}",
                "date_of_birth": "1998-05-15",
                "gender": self.gender_id,
                "sexuality": self.sexuality_id,
                "preferred_genders": [self.gender_id],
                "bio": "Load testing user. Complete profile so Discover and likes work.",
                "latitude": self.lat,
                "longitude": self.lon,
            },
        )

        if self.mood_ids:
            self._req(
                "POST",
                "/api/v1/mood/",
                "mood:set_onboarding",
                json={"mood_ids": self.mood_ids},
            )

        self._req(
            "POST",
            "/api/v1/users/last-active/",
            "users:last_active_init",
            json={"lat": self.lat, "lon": self.lon},
        )
        self._req("GET", "/api/v1/users/dpdp-consent/", "users:dpdp_get")
        self._req(
            "POST",
            "/api/v1/users/dpdp-consent/",
            "users:dpdp_post",
            json={
                "consent_version": "1.0",
                "notice_language": "en",
                "matchmaking_consent": True,
                "location_processing_consent": True,
                "sensitive_data_consent": True,
                "marketing_consent": False,
            },
        )
        if self.user_id:
            _pool_add(_user_ids, self.user_id)

    # ------------------------------------------------------------------ #
    # Health / session / token
    # ------------------------------------------------------------------ #
    @task(4)
    def health(self):
        self._req("GET", "/health/", "health", also_ok=(404, 429))
        self._req("GET", "/health/live/", "health:live", also_ok=(404, 429))
        self._req("GET", "/health/ready/", "health:ready", also_ok=(404, 429))

    @task(8)
    def session_and_me(self):
        if not self._ensure_auth():
            return
        self._req("GET", "/api/v1/users/me/", "users:me")
        self._req("GET", "/api/v1/auth/session/", "auth:session")

    @task(2)
    def token_refresh(self):
        if not self.refresh:
            return
        res = self._req(
            "POST",
            "/api/v1/token/refresh/",
            "auth:token_refresh",
            json={"refresh": self.refresh},
            also_ok=(400, 401, 429),
        )
        data = _json(res) or {}
        if res.status_code == 200 and data.get("access"):
            self.access = data["access"]
        if self.access:
            self._req(
                "POST",
                "/api/v1/token/verify/",
                "auth:token_verify",
                json={"token": self.access},
                also_ok=(400, 401, 429),
            )

    @task(1)
    def ws_ticket(self):
        if not self._ensure_auth():
            return
        self._req("POST", "/api/v1/auth/ws-ticket/", "auth:ws_ticket", json={})

    # ------------------------------------------------------------------ #
    # Feed & Feed AI (Django v1 + FastAPI v2 + AI recalculation & filters)
    # ------------------------------------------------------------------ #
    @task(16)
    def feed_v1(self):
        if not self._ensure_auth():
            return
        res = self._req(
            "GET",
            "/api/v1/feed/",
            "feed:v1",
            params={"count": 10, "cursor": 0},
        )
        if res.status_code == 200:
            self._remember_users(_extract_ids(_json(res), "id", "user_id"))

    @task(6)
    def feed_v1_ai_refresh(self):
        """Feed AI cache refresh + multi-attribute filtering."""
        if not self._ensure_auth():
            return
        res = self._req(
            "GET",
            "/api/v1/feed/",
            "feed:v1_ai_refresh",
            params={
                "count": 15,
                "cursor": 0,
                "refresh": "true",
                "min_age": 18,
                "max_age": 35,
                "currently_online": "true",
                "city": random.choice(CITIES),
            },
        )
        if res.status_code == 200:
            self._remember_users(_extract_ids(_json(res), "id", "user_id"))

    @task(12)
    def feed_v2(self):
        """FastAPI v2 Feed."""
        if not self._ensure_auth():
            return
        res = self._req(
            "GET",
            "/api/v2/feed/",
            "feed:v2",
            params={"count": 10},
            also_ok=(400, 403, 404, 429),
        )
        if res.status_code == 200:
            self._remember_users(_extract_ids(_json(res), "id", "user_id"))

    @task(6)
    def feed_v2_ai_refresh(self):
        """FastAPI v2 Feed with AI refresh and location mode filters."""
        if not self._ensure_auth():
            return
        res = self._req(
            "GET",
            "/api/v2/feed/",
            "feed:v2_ai_refresh",
            params={
                "count": 15,
                "refresh": "true",
                "location_mode": "nearby",
                "currently_online": "1",
                "lat": self.lat,
                "lon": self.lon,
            },
            also_ok=(400, 403, 404, 429),
        )
        if res.status_code == 200:
            self._remember_users(_extract_ids(_json(res), "id", "user_id"))

    # ------------------------------------------------------------------ #
    # Likes / Pass / Interested / Requests
    # ------------------------------------------------------------------ #
    @task(12)
    def like_candidate(self):
        if not self._ensure_auth():
            return
        target = self._pick_target()
        if not target:
            return
        res = self._req(
            "POST",
            "/api/v1/interaction/send/",
            "interaction:like",
            json={"target_user_id": target},
        )
        data = _json(res) or {}
        if data.get("status") == "match" or data.get("match_id"):
            if data.get("match_id"):
                self.match_ids.append(str(data["match_id"]))
            if data.get("conversation_id"):
                self.conversation_ids.append(str(data["conversation_id"]))

    @task(6)
    def interested(self):
        if not self._ensure_auth():
            return
        target = self._pick_target()
        if not target:
            return
        self._req(
            "POST",
            "/api/v1/interested/",
            "interaction:interested",
            json={"target_user_id": target},
        )

    @task(5)
    def pass_candidate(self):
        if not self._ensure_auth():
            return
        target = self._pick_target()
        if not target:
            return
        self._req(
            "POST",
            "/api/v1/interaction/pass/",
            "interaction:pass",
            json={"target_user_id": target},
        )

    @task(4)
    def received_likes(self):
        if not self._ensure_auth():
            return
        res = self._req("GET", "/api/v1/interaction/received/", "interaction:received")
        if res.status_code == 200:
            self._remember_users(_extract_ids(_json(res), "id", "user_id"))

    @task(3)
    def start_conversation_request(self):
        """Send a direct connection/chat request to a candidate."""
        if not self._ensure_auth():
            return
        target = self._pick_target()
        if not target:
            return
        res = self._req(
            "POST",
            "/api/v1/interaction/start_conversation/",
            "interaction:start_conversation",
            json={
                "target_user_id": target,
                "message": "Hey! Saw your profile on Discover — let's connect!",
            },
        )
        if res.status_code in (200, 201):
            _pool_add(_pending_conversation_reqs, (target, self.user_id))

    @task(2)
    def accept_conversation_request(self):
        """Accept an incoming connection/chat request."""
        if not self._ensure_auth() or not self.user_id:
            return
        sender_id = _pop_pending_for(_pending_conversation_reqs, self.user_id)
        if not sender_id:
            sender_id = _pool_pick(_user_ids, exclude=self.user_id)
        if not sender_id:
            return
        self._req(
            "POST",
            "/api/v1/interaction/accept_request/",
            "interaction:accept_request",
            json={"sender_id": sender_id},
        )

    # ------------------------------------------------------------------ #
    # Matches + Chat
    # ------------------------------------------------------------------ #
    @task(6)
    def matches(self):
        if not self._ensure_auth():
            return
        res = self._req("GET", "/api/v1/matches/", "matches:list")
        if res.status_code != 200:
            return
        data = _json(res)
        for mid in _extract_ids(data, "id"):
            if mid not in self.match_ids:
                self.match_ids.append(mid)
        items = _as_items(data)
        for item in items[:3]:
            if not isinstance(item, dict):
                continue
            pk = item.get("id")
            if pk:
                self._req("GET", f"/api/v1/matches/{pk}/", "matches:detail")

    @task(6)
    def conversations(self):
        if not self._ensure_auth():
            return
        res = self._req("GET", "/api/v1/conversations/", "conversations:list")
        if res.status_code != 200:
            return
        data = _json(res)
        ids = _extract_ids(data, "id")
        for cid in ids:
            if cid not in self.conversation_ids:
                self.conversation_ids.append(cid)
        if not ids:
            return
        conv_id = ids[0]
        self._req("GET", f"/api/v1/conversations/{conv_id}/", "conversations:detail")
        self._req(
            "GET",
            "/api/v1/messages/",
            "messages:list",
            params={"conversation_id": conv_id},
        )
        self._req(
            "GET",
            f"/api/v1/conversations/{conv_id}/draft/",
            "conversations:draft_get",
        )

    @task(4)
    def send_chat_message(self):
        if not self._ensure_auth() or not self.conversation_ids:
            return
        conv_id = self.conversation_ids[0]
        self._req(
            "POST",
            "/api/v1/messages/",
            "messages:send",
            json={
                "conversation": conv_id,
                "content": f"load msg {uuid.uuid4().hex[:8]}",
                "message_type": "text",
            },
        )

    # ------------------------------------------------------------------ #
    # Confession Social (Create, Feed, Detail, Relate/Like, Repost, Comments, Chat Request, Accept/Reject)
    # ------------------------------------------------------------------ #
    @task(8)
    def confession_list(self):
        if not self._ensure_auth():
            return
        res = self._req("GET", "/api/v1/social/", "confession:list")
        self._store_confessions(res)

    @task(8)
    def confession_feed(self):
        if not self._ensure_auth():
            return
        res = self._req(
            "GET",
            "/api/v1/social/feed/",
            "confession:feed",
            params={"lat": self.lat, "lng": self.lon, "limit": 20},
        )
        self._store_confessions(res)

    @task(4)
    def confession_create(self):
        if not self._ensure_auth():
            return
        text = (
            f"Load-test confession {uuid.uuid4().hex[:8]} about late-night "
            f"thoughts and city lights. This must be at least thirty chars."
        )
        res = self._req(
            "POST",
            "/api/v1/social/",
            "confession:create",
            json={
                "text": text,
                "mood_tag": random.choice(MOOD_TAGS),
                "language": "en",
                "latitude": self.lat,
                "longitude": self.lon,
            },
        )
        data = _json(res) or {}
        cid = data.get("id")
        if cid:
            self.confession_ids.appendleft(str(cid))
            _pool_add(_confession_ids, str(cid))

    @task(8)
    def confession_engage(self):
        """Full confession interaction: Detail, Relate (Like), Repost, Comment, Report."""
        if not self._ensure_auth():
            return
        cid = None
        if self.confession_ids:
            cid = self.confession_ids[0]
        else:
            cid = _pool_pick(_confession_ids)
        if not cid:
            return

        self._req("GET", f"/api/v1/social/{cid}/", "confession:detail")
        self._req("POST", f"/api/v1/social/{cid}/relate/", "confession:relate", json={})

        if random.random() < 0.4:
            self._req("POST", f"/api/v1/social/{cid}/repost/", "confession:repost", json={})

        if random.random() < 0.5:
            self._req(
                "POST",
                f"/api/v1/social/{cid}/comments/",
                "confession:comment_create",
                json={"text": "Relatable load-test comment.", "is_anonymous": True},
            )
        else:
            self._req("GET", f"/api/v1/social/{cid}/comments/", "confession:comments_list")

        if random.random() < 0.1:
            self._req(
                "POST",
                f"/api/v1/social/{cid}/report/",
                "confession:report",
                json={"reason": "OTHER", "description": "Load test report check"},
            )

    @task(3)
    def confession_chat_request(self):
        """Send anonymous chat request on a confession."""
        if not self._ensure_auth():
            return
        cid = _pool_pick(_confession_ids) or (
            self.confession_ids[0] if self.confession_ids else None
        )
        if not cid:
            return
        res = self._req(
            "POST",
            f"/api/v1/social/{cid}/chat-request/",
            "confession:chat_request",
            json={"message": "Hey, your confession hit hard. Want to talk about it?"},
        )
        data = _json(res) or {}
        req_id = data.get("id")
        if req_id and self.user_id:
            target_user = _pool_pick(_user_ids, exclude=self.user_id)
            if target_user:
                _pool_add(_pending_confession_reqs, (target_user, str(req_id)))

    @task(3)
    def confession_requests_and_actions(self):
        """List incoming confession requests, check badge count, accept/reject."""
        if not self._ensure_auth():
            return
        self._req("GET", "/api/v1/social/moods/", "confession:moods")
        self._req("GET", "/api/v1/confession-requests/count/", "confession:request_count")

        req_res = self._req("GET", "/api/v1/confession-requests/", "confession:requests")
        req_data = _json(req_res)
        req_ids = _extract_ids(req_data, "id")

        if not req_ids and self.user_id:
            p_id = _pop_pending_for(_pending_confession_reqs, self.user_id)
            if p_id:
                req_ids.append(p_id)

        if req_ids:
            target_req_id = req_ids[0]
            if random.random() < 0.7:
                self._req(
                    "POST",
                    f"/api/v1/confession-requests/{target_req_id}/accept/",
                    "confession:request_accept",
                    json={},
                )
            else:
                self._req(
                    "POST",
                    f"/api/v1/confession-requests/{target_req_id}/reject/",
                    "confession:request_reject",
                    json={},
                )

    def _store_confessions(self, res) -> None:
        if res.status_code != 200:
            return
        for cid in _extract_ids(_json(res), "id"):
            if cid not in self.confession_ids:
                self.confession_ids.append(cid)
            _pool_add(_confession_ids, cid)

    # ------------------------------------------------------------------ #
    # Profile & Moods
    # ------------------------------------------------------------------ #
    @task(8)
    def profile_me(self):
        if not self._ensure_auth():
            return
        self._req("GET", "/api/v1/profile/me/", "profile:me")

    @task(3)
    def profile_update(self):
        if not self._ensure_auth():
            return
        self.lat, self.lon = _jitter_coords()
        self._req(
            "PATCH",
            "/api/v1/profile/me/",
            "profile:patch",
            json={
                "bio": f"Updated bio {uuid.uuid4().hex[:6]} for load testing.",
                "latitude": self.lat,
                "longitude": self.lon,
            },
        )

    @task(4)
    def profile_other(self):
        if not self._ensure_auth():
            return
        target = self._pick_target()
        if not target:
            return
        self._req("GET", f"/api/v1/profile/{target}/", "profile:other")

    @task(2)
    def profile_username_check(self):
        if not self._ensure_auth():
            return
        self._req(
            "GET",
            f"/api/v1/profile/username-available/?username=load_{uuid.uuid4().hex[:8]}",
            "profile:username_available",
        )

    @task(2)
    def images_and_avatars(self):
        if not self._ensure_auth():
            return
        self._req("GET", "/api/v1/images/upload-status/", "images:upload_status")
        self._req("GET", "/api/v1/avatars/", "avatars:list")

    @task(2)
    def mood(self):
        if not self._ensure_auth():
            return
        self._req("GET", "/api/v1/mood/", "mood:get")
        if self.mood_ids:
            self._req(
                "POST",
                "/api/v1/mood/",
                "mood:set",
                json={"mood_ids": self.mood_ids[:1]},
            )

    # ------------------------------------------------------------------ #
    # Catalogs / Theme / Geo
    # ------------------------------------------------------------------ #
    @task(3)
    def option_catalogs(self):
        if not self._ensure_auth():
            return
        for path, name in (
            ("/api/v1/genders/", "options:genders"),
            ("/api/v1/intents/", "options:intents"),
            ("/api/v1/sexualities/", "options:sexualities"),
            ("/api/v1/turn_ons/", "options:turn_ons"),
            ("/api/v1/mood_options/", "options:mood_options"),
            ("/api/v1/languages/", "options:languages"),
        ):
            self._req("GET", path, name)

    @task(2)
    def theme(self):
        if not self._ensure_auth():
            return
        self._req("GET", "/api/v1/theme/options/", "theme:options")
        self._req("GET", "/api/v1/theme/me/", "theme:me")

    @task(2)
    def geo(self):
        if not self._ensure_auth():
            return
        self._req(
            "GET",
            "/api/v1/geo/reverse/",
            "geo:reverse",
            params={"lat": self.lat, "lng": self.lon},
            also_ok=(400, 403, 404, 503, 429),
        )
        q = random.choice(("Ban", "Mum", "Del", "Hyd", "Pun"))
        self._req("GET", "/api/v1/geo/cities/", "geo:cities", params={"q": q})
        self._req("GET", "/api/v1/geo/autocomplete/", "geo:autocomplete", params={"q": q})

    # ------------------------------------------------------------------ #
    # Presence / Devices / Notifications
    # ------------------------------------------------------------------ #
    @task(6)
    def last_active(self):
        if not self._ensure_auth():
            return
        self.lat, self.lon = _jitter_coords()
        self._req(
            "POST",
            "/api/v1/users/last-active/",
            "users:last_active",
            json={"lat": self.lat, "lon": self.lon},
        )

    @task(2)
    def devices_and_push(self):
        if not self._ensure_auth():
            return
        self._req("GET", "/api/v1/users/devices/", "users:devices")
        self._req("GET", "/api/v1/notifications/", "notifications:list")
        self._req(
            "POST",
            "/api/v1/notifications/devices/",
            "notifications:register",
            json={
                "fcm_token": f"load-fcm-{self.device_id}",
                "device_type": "ANDROID",
            },
        )

    # ------------------------------------------------------------------ #
    # Wallet / Subscriptions / Calls
    # ------------------------------------------------------------------ #
    @task(2)
    def subscriptions(self):
        if not self._ensure_auth():
            return
        self._req("GET", "/api/v1/subscriptions/status/", "subscriptions:status")
        self._req("GET", "/api/v1/subscriptions/history/", "subscriptions:history")
        self._req("GET", "/api/v1/subscriptions/required-plan/", "subscriptions:required_plan")
        self._req("GET", "/api/v1/subscription/me/", "wallet:subscription_me")

    @task(2)
    def call_and_wallet(self):
        if not self._ensure_auth():
            return
        self._req("GET", "/api/v1/call/ice-servers/", "call:ice_servers")
        self._req("GET", "/api/v1/call/quota/", "call:quota")
        self._req("GET", "/api/v1/call-time/wallet/", "call:wallet")
        self._req("GET", "/api/v1/call-time/packages/", "call:packages")

    # ------------------------------------------------------------------ #
    # Analytics / Verification / Moderation
    # ------------------------------------------------------------------ #
    @task(2)
    def analytics_event(self):
        if not self._ensure_auth():
            return
        self._req(
            "POST",
            "/api/v1/analytics/events/",
            "analytics:event",
            json={
                "event_name": "feed_view",
                "properties": {"source": "locust"},
                "session_id": self.device_id[:32],
                "device_type": "android",
                "platform": "android",
                "app_version": "load-1",
            },
        )
        self._req(
            "POST",
            "/api/v1/events/bulk/",
            "analytics:bulk",
            json={
                "events": [
                    {
                        "type": "heartbeat",
                        "data": {"lat": self.lat, "lon": self.lon},
                    }
                ]
            },
        )

    @task(1)
    def verification_and_blocks(self):
        if not self._ensure_auth():
            return
        self._req("GET", "/api/v1/verification/status/", "verification:status")
        self._req("GET", "/api/v1/moderation/blocks/", "moderation:blocks")


class AuthOnlyUser(HttpUser):
    """Signup storm only (register + magic OTP)."""

    wait_time = between(2.0, 5.0)
    weight = 1

    @task
    def signup_flow(self):
        email = _email()
        device = _device()
        headers = {"Content-Type": "application/json", "X-Device-ID": device}
        with self.client.post(
            "/api/v1/auth/register/",
            json={"email": email, "device_id": device, "intent": "signup"},
            headers=headers,
            name="storm:register",
            catch_response=True,
        ) as res:
            if res.status_code in (200, 201, 429):
                res.success()
            else:
                res.failure(f"storm:register {res.status_code}: {(res.text or '')[:100]}")

        with self.client.post(
            "/api/v1/auth/otp/verify/",
            json={"email": email, "otp": MAGIC_OTP, "device_id": device},
            headers=headers,
            name="storm:verify",
            catch_response=True,
        ) as res:
            if res.status_code in (200, 201, 429):
                res.success()
            else:
                res.failure(f"storm:verify {res.status_code}: {(res.text or '')[:100]}")


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    print(
        f"[SPYCE load] MAGIC_OTP={MAGIC_OTP} | "
        "full API (feed/feed AI/like/pass/requests/confessions/profile/etc) | "
        f"host={getattr(environment, 'host', None)}"
    )
