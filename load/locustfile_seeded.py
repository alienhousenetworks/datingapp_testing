"""
Product load test against pre-seeded complete users.

This file does NOT sign up, mock-verify, or onboard. Those paths blocked
feed/like/confession/chat and saturated workers in the previous run.

Each virtual user:
  1. Claims one row from SEED_USERS_FILE (written by seed_load_users)
  2. Logs in with MAGIC OTP (intent=login)
  3. Loops real product actions with 4–9s think time

Prerequisites
  - Users seeded: seed_load_users / seed-load-users.sh on KVM-B
  - APP env: ALLOW_LOAD_TESTING=true USE_TEST_OTP=true MAGIC_OTP=123456
             DISABLE_RATE_LIMITING=true
  - SEED_USERS_FILE pointing at the JSONL (default testing/load/load_users.jsonl)

Run
  SEED_USERS_FILE=testing/load/load_users.jsonl \\
    locust -f testing/load/locustfile_seeded.py --host https://api01.spycenow.com \\
    --users 500 --spawn-rate 20 --run-time 10m
"""
from __future__ import annotations

import json
import os
import random
import threading
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from locust import HttpUser, between, events, task

MAGIC_OTP = os.getenv("MAGIC_OTP", "123456")
SEED_USERS_FILE = os.getenv(
    "SEED_USERS_FILE",
    str(Path(__file__).resolve().parent / "load_users.jsonl"),
)

_lock = threading.Lock()
_accounts: list[dict[str, Any]] = []
_claim_idx = 0
_feed_ids: deque[str] = deque(maxlen=4000)
_confession_ids: deque[str] = deque(maxlen=2000)

MOOD_TAGS = (
    "LONELY",
    "CURIOUS",
    "HAPPY",
    "ANXIOUS",
    "GRATEFUL",
    "FANTASY",
)


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
    for key in ("results", "users", "data", "items", "confessions"):
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
        card = item.get("profile_card") or item.get("profile") or {}
        if isinstance(card, dict):
            nested = card.get("user_id") or card.get("id")
            if nested:
                ids.append(str(nested))
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _load_accounts() -> None:
    path = Path(SEED_USERS_FILE)
    if not path.is_file():
        raise FileNotFoundError(
            f"SEED_USERS_FILE not found: {path}. "
            "Run seed-load-users.sh on KVM-B and copy load_users.jsonl here."
        )
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    if len(rows) < 2:
        raise RuntimeError(f"{path} has {len(rows)} users; need at least 2")
    random.shuffle(rows)
    _accounts.extend(rows)


def _claim_account() -> dict[str, Any]:
    global _claim_idx
    with _lock:
        if not _accounts:
            raise RuntimeError("No seeded accounts loaded")
        acc = _accounts[_claim_idx % len(_accounts)]
        _claim_idx += 1
        return acc


def _pool_add(pool: deque, value: Any) -> None:
    if not value:
        return
    with _lock:
        if value not in pool:
            pool.append(value)


def _pool_pick(pool: deque, exclude: str | None = None) -> Any | None:
    with _lock:
        choices = [x for x in pool if x and str(x) != exclude]
    return random.choice(choices) if choices else None


@events.init.add_listener
def _on_init(environment, **kwargs):
    _load_accounts()
    print(
        f"[SPYCE seeded load] accounts={len(_accounts)} file={SEED_USERS_FILE} "
        f"host={getattr(environment, 'host', None)} MAGIC_OTP={MAGIC_OTP}"
    )


class SeededProductUser(HttpUser):
    """Logged-in complete user exercising Discover, social, and chat."""

    wait_time = between(4.0, 9.0)
    weight = 10

    def on_start(self):
        self.account = _claim_account()
        self.email = self.account["email"]
        self.device_id = self.account.get("device_id") or f"seed-device-{uuid.uuid4().hex[:10]}"
        self.user_id = str(self.account.get("user_id") or "")
        self.lat = float(self.account.get("lat") or 12.9716)
        self.lon = float(self.account.get("lon") or 77.5946)
        self.partner_id = self.account.get("partner_user_id")
        self.conversation_id = self.account.get("conversation_id")
        self.access = None
        self.refresh = None
        self.feed_cursor = 0
        self.seen: deque[str] = deque(maxlen=80)
        self.confessions: deque[str] = deque(maxlen=40)
        self._login()

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
        expected: tuple[int, ...] = (200, 201, 204),
        also_ok: tuple[int, ...] = (400, 403, 404, 409, 429),
        **kwargs,
    ):
        kwargs.setdefault("headers", self._headers())
        with self.client.request(
            method, path, name=name, catch_response=True, **kwargs
        ) as res:
            if res.status_code in expected or res.status_code in also_ok:
                res.success()
            else:
                res.failure(f"{name} {res.status_code}: {(res.text or '')[:140]}")
        return res

    def _login(self) -> None:
        for _attempt in range(3):
            with self.client.post(
                "/api/v1/auth/register/",
                json={"email": self.email, "device_id": self.device_id, "intent": "login"},
                headers=self._headers(),
                name="auth:login_otp",
                catch_response=True,
            ) as reg:
                if reg.status_code in (200, 201, 429):
                    reg.success()
                else:
                    reg.failure(f"login otp {reg.status_code}: {(reg.text or '')[:120]}")
                    return

            with self.client.post(
                "/api/v1/auth/otp/verify/",
                json={"email": self.email, "otp": MAGIC_OTP, "device_id": self.device_id},
                headers=self._headers(),
                name="auth:login_verify",
                catch_response=True,
            ) as ver:
                if ver.status_code == 429:
                    ver.success()
                    continue
                if ver.status_code not in (200, 201):
                    ver.failure(f"verify {ver.status_code}: {(ver.text or '')[:120]}")
                    return
                data = _json(ver) or {}
                self.access = data.get("access")
                self.refresh = data.get("refresh")
                if data.get("user_id"):
                    self.user_id = str(data["user_id"])
                if not self.access:
                    ver.failure("no access token")
                    return
                ver.success()
                return

    def _ensure(self) -> bool:
        if self.access:
            return True
        self._login()
        return bool(self.access)

    def _remember_feed(self, res) -> None:
        if res.status_code != 200:
            return
        for uid in _extract_ids(_json(res), "id", "user_id"):
            if uid == self.user_id:
                continue
            if uid not in self.seen:
                self.seen.append(uid)
            _pool_add(_feed_ids, uid)

    def _remember_confessions(self, res) -> None:
        if res.status_code != 200:
            return
        for cid in _extract_ids(_json(res), "id"):
            if cid not in self.confessions:
                self.confessions.append(cid)
            _pool_add(_confession_ids, cid)

    def _pick_target(self) -> str | None:
        if self.seen:
            return self.seen.popleft()
        return _pool_pick(_feed_ids, self.user_id)

    def _pick_confession(self) -> str | None:
        if self.confessions:
            return self.confessions[0]
        return _pool_pick(_confession_ids)

    # ------------------------------------------------------------------ #
    # Discover
    # ------------------------------------------------------------------ #
    @task(20)
    def feed_scroll(self):
        if not self._ensure():
            return
        res = self._req(
            "GET",
            "/api/v2/feed/",
            "feed:v2_scroll",
            params={
                "count": 12,
                "cursor": self.feed_cursor,
                "lat": self.lat,
                "lon": self.lon,
            },
            also_ok=(400, 403, 404, 429),
        )
        self._remember_feed(res)
        if res.status_code == 200:
            self.feed_cursor += 12
            if self.feed_cursor > 80:
                self.feed_cursor = 0

    @task(14)
    def like_profile(self):
        if not self._ensure():
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
        if data.get("conversation_id"):
            self.conversation_id = str(data["conversation_id"])

    @task(5)
    def pass_profile(self):
        if not self._ensure():
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
    def view_profile(self):
        if not self._ensure():
            return
        target = self._pick_target() or self.partner_id
        if not target:
            return
        self._req("GET", f"/api/v1/profile/{target}/", "profile:other")

    @task(3)
    def received_likes(self):
        if not self._ensure():
            return
        res = self._req("GET", "/api/v1/interaction/received/", "interaction:received")
        self._remember_feed(res)

    # ------------------------------------------------------------------ #
    # Confessions
    # ------------------------------------------------------------------ #
    @task(10)
    def confession_list(self):
        if not self._ensure():
            return
        res = self._req("GET", "/api/v1/social/", "confession:list")
        self._remember_confessions(res)

    @task(10)
    def confession_feed(self):
        if not self._ensure():
            return
        res = self._req(
            "GET",
            "/api/v1/social/feed/",
            "confession:feed",
            params={"lat": self.lat, "lng": self.lon, "limit": 20},
        )
        self._remember_confessions(res)

    @task(2)
    def confession_create(self):
        if not self._ensure():
            return
        text = (
            f"Load confession {uuid.uuid4().hex[:8]} about missed trains, "
            f"late nights, and people we almost texted back."
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
            also_ok=(400, 403, 404, 409, 429),
        )
        data = _json(res) or {}
        cid = data.get("id")
        if cid:
            self.confessions.appendleft(str(cid))
            _pool_add(_confession_ids, str(cid))

    @task(8)
    def confession_relate(self):
        if not self._ensure():
            return
        cid = self._pick_confession()
        if not cid:
            return
        self._req("GET", f"/api/v1/social/{cid}/", "confession:detail")
        self._req("POST", f"/api/v1/social/{cid}/relate/", "confession:relate", json={})

    @task(4)
    def confession_repost(self):
        if not self._ensure():
            return
        cid = self._pick_confession()
        if not cid:
            return
        self._req("POST", f"/api/v1/social/{cid}/repost/", "confession:repost", json={})

    @task(4)
    def confession_comment(self):
        if not self._ensure():
            return
        cid = self._pick_confession()
        if not cid:
            return
        if random.random() < 0.5:
            self._req(
                "POST",
                f"/api/v1/social/{cid}/comments/",
                "confession:comment",
                json={"text": "Relatable. Seeded load comment.", "is_anonymous": True},
            )
        else:
            self._req("GET", f"/api/v1/social/{cid}/comments/", "confession:comments")

    # ------------------------------------------------------------------ #
    # Chat / matches
    # ------------------------------------------------------------------ #
    @task(8)
    def send_message(self):
        if not self._ensure() or not self.conversation_id:
            return
        self._req(
            "POST",
            "/api/v1/messages/",
            "messages:send",
            json={
                "conversation": self.conversation_id,
                "content": {"text": f"hey {uuid.uuid4().hex[:6]} — seeded chat load"},
                "message_type": "text",
            },
        )

    @task(6)
    def conversations(self):
        if not self._ensure():
            return
        res = self._req("GET", "/api/v1/conversations/", "conversations:list")
        if res.status_code != 200:
            return
        ids = _extract_ids(_json(res), "id")
        if ids and not self.conversation_id:
            self.conversation_id = ids[0]
        conv_id = self.conversation_id or (ids[0] if ids else None)
        if not conv_id:
            return
        self._req(
            "GET",
            "/api/v1/messages/",
            "messages:list",
            params={"conversation_id": conv_id},
        )

    @task(4)
    def matches(self):
        if not self._ensure():
            return
        self._req("GET", "/api/v1/matches/", "matches:list")

    # ------------------------------------------------------------------ #
    # Presence (same coords as seed — avoids full profile.save())
    # ------------------------------------------------------------------ #
    @task(3)
    def heartbeat(self):
        if not self._ensure():
            return
        self._req(
            "POST",
            "/api/v1/users/last-active/",
            "users:heartbeat",
            json={"lat": self.lat, "lon": self.lon},
        )

    @task(1)
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
            if data.get("refresh"):
                self.refresh = data["refresh"]
