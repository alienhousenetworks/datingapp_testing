"""
Product load test against pre-seeded complete users.

Auth is NOT part of the load mix.
Each virtual user logs in once on start (only if the seed row has no
token). After that the loop hits real product APIs only:

  Feed load, send like, pass, interested, received likes,
  send request / accept request,
  chat list + send,
  confession feed / create / like / repost / comment / chat-request,
  profile me / other, matches.

This file does NOT sign up, mock-verify, onboard, refresh tokens,
or call session / ws-ticket / OTP again.

Prerequisites
  - Users seeded: seed_load_users / seed-load-users.sh on KVM-B
  - APP env: ALLOW_LOAD_TESTING=true USE_TEST_OTP=true MAGIC_OTP=123456
             DISABLE_RATE_LIMITING=true
  - SEED_USERS_FILE pointing at the JSONL (default testing/load/load_users.jsonl)

Optional seed columns (skip login entirely if present):
  access | access_token | token
  refresh | refresh_token

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

REQUEST_NOTES = (
    "Hey! Saw your profile on Discover — let's connect!",
    "Your profile stood out. Want to chat?",
    "Hi, would love to talk if you're open to it.",
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


def _seed_token(account: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        val = account.get(key)
        if val:
            return str(val)
    return None


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


def _pop_pending_for(pool: deque[tuple[str, str]], target_receiver_id: str) -> str | None:
    with _lock:
        for item in list(pool):
            receiver_id, payload_id = item
            if receiver_id == target_receiver_id:
                pool.remove(item)
                return payload_id
    return None


@events.init.add_listener
def _on_init(environment, **kwargs):
    _load_accounts()
    with_tokens = sum(
        1
        for row in _accounts
        if _seed_token(row, "access", "access_token", "token")
    )
    print(
        f"[SPYCE seeded load] accounts={len(_accounts)} "
        f"preissued_tokens={with_tokens} file={SEED_USERS_FILE} "
        f"host={getattr(environment, 'host', None)} "
        "auth=one-time-login-if-needed (no auth APIs in loop)"
    )


class SeededProductUser(HttpUser):
    """One login (if needed), then Discover / social / chat / profile only."""

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
        self.access = _seed_token(self.account, "access", "access_token", "token")
        self.refresh = _seed_token(self.account, "refresh", "refresh_token")
        self.feed_cursor = 0
        self.seen: deque[str] = deque(maxlen=80)
        self.confessions: deque[str] = deque(maxlen=40)
        if self.partner_id:
            self.seen.append(str(self.partner_id))
            _pool_add(_feed_ids, str(self.partner_id))
        if not self.access:
            self._login_once()
        if not self.access:
            # Do not burn the run on unauthenticated 401s.
            self.stop(force=True)

    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Device-ID": self.device_id,
        }
        if self.access:
            h["Authorization"] = f"Bearer {self.access}"
        return h

    def _ready(self) -> bool:
        return bool(self.access)

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

    def _login_once(self) -> None:
        """Single login per VU. Never called from feature tasks."""
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
            return random.choice(list(self.confessions))
        return _pool_pick(_confession_ids)

    # ------------------------------------------------------------------ #
    # Discover — feed load
    # ------------------------------------------------------------------ #
    @task(20)
    def feed_v2_load(self):
        if not self._ready():
            return
        res = self._req(
            "GET",
            "/api/v2/feed/",
            "feed:v2_load",
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

    @task(8)
    def feed_v1_load(self):
        if not self._ready():
            return
        res = self._req(
            "GET",
            "/api/v1/feed/",
            "feed:v1_load",
            params={"count": 10, "cursor": 0, "lat": self.lat, "lon": self.lon},
        )
        self._remember_feed(res)

    # ------------------------------------------------------------------ #
    # Likes / pass / interested / incoming likes
    # ------------------------------------------------------------------ #
    @task(14)
    def send_like(self):
        if not self._ready():
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
        if not self._ready():
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

    @task(5)
    def send_interested(self):
        if not self._ready():
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

    @task(4)
    def received_likes(self):
        if not self._ready():
            return
        res = self._req("GET", "/api/v1/interaction/received/", "interaction:received")
        self._remember_feed(res)

    # ------------------------------------------------------------------ #
    # Send request / accept request
    # ------------------------------------------------------------------ #
    @task(5)
    def send_conversation_request(self):
        if not self._ready():
            return
        target = self._pick_target()
        if not target:
            return
        res = self._req(
            "POST",
            "/api/v1/interaction/start_conversation/",
            "interaction:send_request",
            json={
                "target_user_id": target,
                "message": random.choice(REQUEST_NOTES),
            },
        )
        if res.status_code in (200, 201) and self.user_id:
            _pool_add(_pending_conversation_reqs, (target, self.user_id))

    @task(3)
    def accept_conversation_request(self):
        if not self._ready() or not self.user_id:
            return
        sender_id = _pop_pending_for(_pending_conversation_reqs, self.user_id)
        if not sender_id:
            sender_id = self.partner_id or _pool_pick(_feed_ids, self.user_id)
        if not sender_id:
            return
        res = self._req(
            "POST",
            "/api/v1/interaction/accept_request/",
            "interaction:accept_request",
            json={"sender_id": sender_id},
        )
        data = _json(res) or {}
        if data.get("conversation_id"):
            self.conversation_id = str(data["conversation_id"])

    # ------------------------------------------------------------------ #
    # Profile
    # ------------------------------------------------------------------ #
    @task(6)
    def profile_me(self):
        if not self._ready():
            return
        self._req("GET", "/api/v1/profile/me/", "profile:me")
        self._req("GET", "/api/v1/users/me/", "users:me")

    @task(5)
    def profile_other(self):
        if not self._ready():
            return
        target = self._pick_target() or self.partner_id
        if not target:
            return
        self._req("GET", f"/api/v1/profile/{target}/", "profile:other")

    # ------------------------------------------------------------------ #
    # Confessions — load, create, like, repost, comment, chat request
    # ------------------------------------------------------------------ #
    @task(10)
    def confession_list_load(self):
        if not self._ready():
            return
        res = self._req("GET", "/api/v1/social/", "confession:list")
        self._remember_confessions(res)

    @task(10)
    def confession_feed_load(self):
        if not self._ready():
            return
        res = self._req(
            "GET",
            "/api/v1/social/feed/",
            "confession:feed",
            params={"lat": self.lat, "lng": self.lon, "limit": 20},
        )
        self._remember_confessions(res)

    @task(3)
    def confession_create(self):
        if not self._ready():
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
    def confession_like(self):
        if not self._ready():
            return
        cid = self._pick_confession()
        if not cid:
            return
        self._req("GET", f"/api/v1/social/{cid}/", "confession:detail")
        self._req("POST", f"/api/v1/social/{cid}/relate/", "confession:like", json={})

    @task(4)
    def confession_repost(self):
        if not self._ready():
            return
        cid = self._pick_confession()
        if not cid:
            return
        self._req("POST", f"/api/v1/social/{cid}/repost/", "confession:repost", json={})

    @task(4)
    def confession_comment(self):
        if not self._ready():
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

    @task(3)
    def confession_chat_request(self):
        if not self._ready():
            return
        cid = self._pick_confession()
        if not cid:
            return
        self._req(
            "POST",
            f"/api/v1/social/{cid}/chat-request/",
            "confession:chat_request",
            json={"message": "Hey, your confession hit hard. Want to talk about it?"},
        )

    # ------------------------------------------------------------------ #
    # Chat / matches
    # ------------------------------------------------------------------ #
    @task(8)
    def send_chat(self):
        if not self._ready() or not self.conversation_id:
            return
        self._req(
            "POST",
            "/api/v1/messages/",
            "chat:send",
            json={
                "conversation": self.conversation_id,
                "content": {"text": f"hey {uuid.uuid4().hex[:6]} — seeded chat load"},
                "message_type": "text",
            },
        )

    @task(6)
    def chat_load(self):
        if not self._ready():
            return
        res = self._req("GET", "/api/v1/conversations/", "chat:conversations")
        if res.status_code != 200:
            return
        ids = _extract_ids(_json(res), "id")
        if ids and not self.conversation_id:
            self.conversation_id = ids[0]
        conv_id = self.conversation_id or (ids[0] if ids else None)
        if not conv_id:
            return
        self._req("GET", f"/api/v1/conversations/{conv_id}/", "chat:conversation_detail")
        self._req(
            "GET",
            "/api/v1/messages/",
            "chat:messages",
            params={"conversation_id": conv_id},
        )

    @task(4)
    def matches_load(self):
        if not self._ready():
            return
        self._req("GET", "/api/v1/matches/", "matches:list")
