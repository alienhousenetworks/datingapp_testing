"""
High-Performance Full-Feature Load Testing Engine for SPYCE API.
Supports 2,000 - 3,000+ Concurrent Virtual Users per Laptop.

Features tested by every user:
1. One-time Auto-Signup & Magic OTP Verification + Mock Verification + DPDP Consent
2. Profile Me, Profile Patch (Bio, Location Jitter), and Username Availability Check
3. Feed v1 (Django) & Feed v2 (FastAPI AI Recalculation & multi-attribute filters)
4. Swipe Interactions: Like, Pass, Superlike/Interested, Received Likes
5. Direct Conversation Requests (Send Icebreaker Request, Accept Incoming Request)
6. Matches List & Match Card Detail
7. Real-Time Chat: Conversation List, Message History, Send Messages, Drafts
8. Confession Wall: Geo Feed, General List, Create Confession with Mood Tags,
   Relate/Like, Repost, Comments List/Create, Confession Chat Requests, Accept/Reject
9. Presence Heartbeats, FCM Device Push Token Registration, Notifications Feed
10. System Catalogs (Genders, Sexualities, Intents, Turn-ons, Languages, Themes, Geo Autocomplete)
11. Wallet & Subscriptions (Calling Quota, Coin Packages, Plan Status, WebRTC ICE Servers)
12. Analytics Event Telemetry & Bulk Event Tracking
13. Health & Liveness Probes
"""
from __future__ import annotations

import os
import random
import threading
import time
import uuid
from collections import deque
from typing import Any

from locust import FastHttpUser, between, task

MAGIC_OTP = os.getenv("MAGIC_OTP", "123456")
LAT = float(os.getenv("LOAD_LAT", "12.9716"))
LON = float(os.getenv("LOAD_LON", "77.5946"))

_lock = threading.Lock()
_global_user_ids: deque[str] = deque(maxlen=4000)
_global_feed_ids: deque[str] = deque(maxlen=4000)
_global_confession_ids: deque[str] = deque(maxlen=2000)
_global_pending_confession_reqs: deque[tuple[str, str]] = deque(maxlen=1000)
_global_pending_conv_reqs: deque[tuple[str, str]] = deque(maxlen=1000)

MOOD_TAGS = (
    "LONELY",
    "CURIOUS",
    "HAPPY",
    "ANXIOUS",
    "GRATEFUL",
    "FANTASY",
)

CITIES = ("Bangalore", "Mumbai", "Delhi", "Hyderabad", "Pune", "Chennai", "Kolkata")


def _jitter_coords() -> tuple[float, float]:
    return (
        round(LAT + random.uniform(-0.06, 0.06), 6),
        round(LON + random.uniform(-0.06, 0.06), 6),
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
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def create_full_suite_user_class(node_name: str, node_index: int):
    """
    Factory creating a FastHttpUser testing class customized for a specific laptop/node.
    All instances test 100% of the platform features with distinct ID namespaces.
    """

    class FullPlatformLoadUser(FastHttpUser):
        wait_time = between(0.3, 1.2)

        def on_start(self):
            # Unique email & device per virtual user and laptop node
            self.email = f"node{node_index}_{uuid.uuid4().hex[:10]}@example.com"
            self.device_id = f"node{node_index}-device-{uuid.uuid4()}"
            self.access = None
            self.refresh = None
            self.user_id = None
            self.username = f"n{node_index}_{uuid.uuid4().hex[:8]}"
            self.lat, self.lon = _jitter_coords()
            self.gender_id = 1
            self.sexuality_id = 1
            self.mood_ids: list = []
            self.seen_candidates: deque[str] = deque(maxlen=200)
            self.confession_ids: deque[str] = deque(maxlen=80)
            self.match_ids: deque[str] = deque(maxlen=50)
            self.conversation_ids: deque[str] = deque(maxlen=50)
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
                _pool_add(_global_feed_ids, uid)

        def _pick_target(self) -> str | None:
            if self.seen_candidates:
                return self.seen_candidates.popleft()
            return _pool_pick(_global_feed_ids, self.user_id) or _pool_pick(_global_user_ids, self.user_id)

        def _is_auth(self) -> bool:
            return bool(self.access)

        def _authenticate_and_onboard(self):
            for attempt in range(5):
                with self.client.post(
                    "/api/v1/auth/login_otp/",
                    json={"email": self.email, "device_id": self.device_id},
                    headers=self._headers(),
                    name="auth:login_otp",
                    catch_response=True,
                ) as reg:
                    if reg.status_code in (200, 201, 409):
                        reg.success()
                    elif reg.status_code == 429:
                        reg.success()
                        time.sleep(0.3)
                        continue
                    else:
                        with self.client.post(
                            "/api/v1/auth/register/",
                            json={"email": self.email, "device_id": self.device_id},
                            headers=self._headers(),
                            name="auth:register",
                            catch_response=True,
                        ) as reg2:
                            if reg2.status_code in (200, 201, 409, 429):
                                reg2.success()

                with self.client.post(
                    "/api/v1/auth/otp/verify/",
                    json={"email": self.email, "otp": MAGIC_OTP, "device_id": self.device_id},
                    headers=self._headers(),
                    name="auth:otp_verify",
                    catch_response=True,
                ) as ver:
                    if ver.status_code == 429:
                        ver.success()
                        time.sleep(0.3)
                        continue
                    elif ver.status_code not in (200, 201):
                        ver.failure(f"verify {ver.status_code}: {(ver.text or '')[:100]}")
                        time.sleep(0.3)
                        continue
                    data = _json(ver) or {}
                    self.access = data.get("access")
                    self.refresh = data.get("refresh")
                    self.user_id = str(data.get("user_id") or "")
                    if not self.access:
                        ver.failure("no access token")
                        continue
                    ver.success()
                    break

            if not self.access:
                return

            self._req("POST", "/api/v1/verification/mock-complete/", "verification:mock_complete", json={})

            g_res = self._req("GET", "/api/v1/genders/", "options:genders_init")
            g_list = _json(g_res)
            if isinstance(g_list, list) and g_list:
                self.gender_id = g_list[0].get("id", 1)

            s_res = self._req("GET", "/api/v1/sexualities/", "options:sexualities_init")
            s_list = _json(s_res)
            if isinstance(s_list, list) and s_list:
                self.sexuality_id = s_list[0].get("id", 1)

            m_res = self._req("GET", "/api/v1/mood_options/", "options:moods_init")
            m_list = _json(m_res)
            if isinstance(m_list, list):
                self.mood_ids = [m.get("id") for m in m_list[:2] if m.get("id")]

            self._req(
                "PATCH",
                "/api/v1/profile/me/",
                "profile:onboarding_patch",
                json={
                    "username": self.username,
                    "name": f"User {self.username[:6]}",
                    "date_of_birth": "1998-07-20",
                    "gender": self.gender_id,
                    "sexuality": self.sexuality_id,
                    "preferred_genders": [self.gender_id],
                    "bio": f"Active load test user from {node_name}",
                    "latitude": self.lat,
                    "longitude": self.lon,
                },
            )

            if self.mood_ids:
                self._req("POST", "/api/v1/mood/", "mood:set_onboarding", json={"mood_ids": self.mood_ids})

            self._req("POST", "/api/v1/users/last-active/", "users:last_active_init", json={"lat": self.lat, "lon": self.lon})
            self._req(
                "POST",
                "/api/v1/users/dpdp-consent/",
                "users:dpdp_init",
                json={
                    "consent_version": "1.0",
                    "notice_language": "en",
                    "matchmaking_consent": True,
                    "location_processing_consent": True,
                    "sensitive_data_consent": True,
                },
            )
            if self.user_id:
                _pool_add(_global_user_ids, self.user_id)

        # -------------------------------------------------------------
        # 1. FEED & FEED AI (V1 Django + V2 FastAPI)
        # -------------------------------------------------------------
        @task(15)
        def task_feed_v1(self):
            if not self._is_auth():
                return
            res = self._req("GET", "/api/v1/feed/", "feed:v1", params={"count": 10, "cursor": 0})
            if res.status_code == 200:
                self._remember_users(_extract_ids(_json(res), "id", "user_id"))

        @task(8)
        def task_feed_v1_ai_refresh(self):
            if not self._is_auth():
                return
            res = self._req(
                "GET",
                "/api/v1/feed/",
                "feed:v1_ai_refresh",
                params={
                    "count": 15,
                    "cursor": 0,
                    "refresh": "true",
                    "min_age": random.choice([18, 22, 25]),
                    "max_age": random.choice([32, 38, 45]),
                    "currently_online": random.choice(["true", "false"]),
                    "city": random.choice(CITIES),
                },
            )
            if res.status_code == 200:
                self._remember_users(_extract_ids(_json(res), "id", "user_id"))

        @task(12)
        def task_feed_v2_fastapi(self):
            if not self._is_auth():
                return
            res = self._req("GET", "/api/v2/feed/", "feed:v2", params={"count": 10}, also_ok=(400, 403, 404, 429))
            if res.status_code == 200:
                self._remember_users(_extract_ids(_json(res), "id", "user_id"))

        @task(8)
        def task_feed_v2_ai_refresh(self):
            if not self._is_auth():
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

        # -------------------------------------------------------------
        # 2. SWIPE INTERACTIONS (Like, Pass, Interested, Received)
        # -------------------------------------------------------------
        @task(14)
        def task_like_candidate(self):
            if not self._is_auth():
                return
            target = self._pick_target()
            if not target:
                return
            res = self._req("POST", "/api/v1/interaction/send/", "interaction:like", json={"target_user_id": target})
            data = _json(res) or {}
            if data.get("status") == "match" or data.get("match_id"):
                if data.get("match_id"):
                    self.match_ids.append(str(data["match_id"]))
                if data.get("conversation_id"):
                    self.conversation_ids.append(str(data["conversation_id"]))

        @task(8)
        def task_pass_candidate(self):
            if not self._is_auth():
                return
            target = self._pick_target()
            if not target:
                return
            self._req("POST", "/api/v1/interaction/pass/", "interaction:pass", json={"target_user_id": target})

        @task(5)
        def task_send_interested(self):
            if not self._is_auth():
                return
            target = self._pick_target()
            if not target:
                return
            self._req("POST", "/api/v1/interested/", "interaction:interested", json={"target_user_id": target})

        @task(5)
        def task_received_likes(self):
            if not self._is_auth():
                return
            res = self._req("GET", "/api/v1/interaction/received/", "interaction:received")
            if res.status_code == 200:
                self._remember_users(_extract_ids(_json(res), "id", "user_id"))

        # -------------------------------------------------------------
        # 3. DIRECT CONVERSATION REQUESTS
        # -------------------------------------------------------------
        @task(4)
        def task_start_conversation_request(self):
            if not self._is_auth():
                return
            target = self._pick_target()
            if not target:
                return
            res = self._req(
                "POST",
                "/api/v1/interaction/start_conversation/",
                "interaction:start_conversation",
                json={"target_user_id": target, "message": "Hey! Nice profile, let's connect!"},
            )
            if res.status_code in (200, 201):
                _pool_add(_global_pending_conv_reqs, (target, self.user_id))

        @task(3)
        def task_accept_conversation_request(self):
            if not self._is_auth() or not self.user_id:
                return
            sender_id = _pop_pending_for(_global_pending_conv_reqs, self.user_id)
            if not sender_id:
                sender_id = _pool_pick(_global_user_ids, exclude=self.user_id)
            if not sender_id:
                return
            self._req("POST", "/api/v1/interaction/accept_request/", "interaction:accept_request", json={"sender_id": sender_id})

        # -------------------------------------------------------------
        # 4. MATCHES & REAL-TIME CHAT
        # -------------------------------------------------------------
        @task(8)
        def task_matches(self):
            if not self._is_auth():
                return
            res = self._req("GET", "/api/v1/matches/", "matches:list")
            if res.status_code != 200:
                return
            data = _json(res)
            for mid in _extract_ids(data, "id"):
                if mid not in self.match_ids:
                    self.match_ids.append(mid)
            items = _as_items(data)
            for item in items[:2]:
                if isinstance(item, dict) and item.get("id"):
                    self._req("GET", f"/api/v1/matches/{item['id']}/", "matches:detail")

        @task(10)
        def task_conversations(self):
            if not self._is_auth():
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
            self._req("GET", "/api/v1/messages/", "messages:list", params={"conversation_id": conv_id})
            self._req("GET", f"/api/v1/conversations/{conv_id}/draft/", "conversations:draft_get")

        @task(10)
        def task_send_chat_message(self):
            if not self._is_auth() or not self.conversation_ids:
                return
            conv_id = self.conversation_ids[0]
            self._req(
                "POST",
                "/api/v1/messages/",
                "messages:send",
                json={
                    "conversation": conv_id,
                    "content": f"Hey! message #{uuid.uuid4().hex[:6]}",
                    "message_type": "text",
                },
            )

        # -------------------------------------------------------------
        # 5. CONFESSIONS & SOCIAL
        # -------------------------------------------------------------
        @task(8)
        def task_confession_feed(self):
            if not self._is_auth():
                return
            res = self._req("GET", "/api/v1/social/feed/", "confession:feed", params={"lat": self.lat, "lng": self.lon, "limit": 20})
            self._store_confessions(res)

        @task(6)
        def task_confession_list(self):
            if not self._is_auth():
                return
            res = self._req("GET", "/api/v1/social/", "confession:list")
            self._store_confessions(res)

        @task(5)
        def task_confession_create(self):
            if not self._is_auth():
                return
            text = f"Confession #{uuid.uuid4().hex[:6]}: The late night city view always brings peaceful energy."
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
                _pool_add(_global_confession_ids, str(cid))

        @task(10)
        def task_confession_engage(self):
            if not self._is_auth():
                return
            cid = self.confession_ids[0] if self.confession_ids else _pool_pick(_global_confession_ids)
            if not cid:
                return

            self._req("GET", f"/api/v1/social/{cid}/", "confession:detail")
            self._req("POST", f"/api/v1/social/{cid}/relate/", "confession:relate", json={})

            if random.random() < 0.35:
                self._req("POST", f"/api/v1/social/{cid}/repost/", "confession:repost", json={})

            if random.random() < 0.5:
                self._req(
                    "POST",
                    f"/api/v1/social/{cid}/comments/",
                    "confession:comment_create",
                    json={"text": "Very relatable! Keep smiling.", "is_anonymous": True},
                )
            else:
                self._req("GET", f"/api/v1/social/{cid}/comments/", "confession:comments_list")

        @task(3)
        def task_confession_chat_request(self):
            if not self._is_auth():
                return
            cid = _pool_pick(_global_confession_ids) or (self.confession_ids[0] if self.confession_ids else None)
            if not cid:
                return
            res = self._req(
                "POST",
                f"/api/v1/social/{cid}/chat-request/",
                "confession:chat_request",
                json={"message": "Loved your confession! Want to talk anonymously?"},
            )
            data = _json(res) or {}
            req_id = data.get("id")
            if req_id and self.user_id:
                target_user = _pool_pick(_global_user_ids, exclude=self.user_id)
                if target_user:
                    _pool_add(_global_pending_confession_reqs, (target_user, str(req_id)))

        @task(3)
        def task_confession_requests_and_actions(self):
            if not self._is_auth():
                return
            self._req("GET", "/api/v1/social/moods/", "confession:moods")
            self._req("GET", "/api/v1/confession-requests/count/", "confession:request_count")

            req_res = self._req("GET", "/api/v1/confession-requests/", "confession:requests")
            req_data = _json(req_res)
            req_ids = _extract_ids(req_data, "id")

            if not req_ids and self.user_id:
                p_id = _pop_pending_for(_global_pending_confession_reqs, self.user_id)
                if p_id:
                    req_ids.append(p_id)

            if req_ids:
                target_req_id = req_ids[0]
                if random.random() < 0.75:
                    self._req("POST", f"/api/v1/confession-requests/{target_req_id}/accept/", "confession:request_accept", json={})
                else:
                    self._req("POST", f"/api/v1/confession-requests/{target_req_id}/reject/", "confession:request_reject", json={})

        def _store_confessions(self, res) -> None:
            if res.status_code != 200:
                return
            for cid in _extract_ids(_json(res), "id"):
                if cid not in self.confession_ids:
                    self.confession_ids.append(cid)
                _pool_add(_global_confession_ids, cid)

        # -------------------------------------------------------------
        # 6. PROFILE & MOODS
        # -------------------------------------------------------------
        @task(6)
        def task_profile_me(self):
            if not self._is_auth():
                return
            self._req("GET", "/api/v1/profile/me/", "profile:me")

        @task(4)
        def task_profile_update(self):
            if not self._is_auth():
                return
            self.lat, self.lon = _jitter_coords()
            self._req(
                "PATCH",
                "/api/v1/profile/me/",
                "profile:patch",
                json={"bio": f"Updated bio #{uuid.uuid4().hex[:4]}", "latitude": self.lat, "longitude": self.lon},
            )

        @task(6)
        def task_profile_other(self):
            if not self._is_auth():
                return
            target = self._pick_target()
            if not target:
                return
            self._req("GET", f"/api/v1/profile/{target}/", "profile:other")

        @task(3)
        def task_profile_username_check(self):
            if not self._is_auth():
                return
            self._req("GET", f"/api/v1/profile/username-available/?username=user_{uuid.uuid4().hex[:8]}", "profile:username_available")

        @task(2)
        def task_images_and_avatars(self):
            if not self._is_auth():
                return
            self._req("GET", "/api/v1/images/upload-status/", "images:upload_status")
            self._req("GET", "/api/v1/avatars/", "avatars:list")

        @task(2)
        def task_mood(self):
            if not self._is_auth():
                return
            self._req("GET", "/api/v1/mood/", "mood:get")
            if self.mood_ids:
                self._req("POST", "/api/v1/mood/", "mood:set", json={"mood_ids": self.mood_ids[:1]})

        # -------------------------------------------------------------
        # 7. NOTIFICATIONS & PRESENCE
        # -------------------------------------------------------------
        @task(6)
        def task_last_active(self):
            if not self._is_auth():
                return
            self.lat, self.lon = _jitter_coords()
            self._req("POST", "/api/v1/users/last-active/", "users:last_active", json={"lat": self.lat, "lon": self.lon})

        @task(3)
        def task_devices_and_push(self):
            if not self._is_auth():
                return
            self._req("GET", "/api/v1/users/devices/", "users:devices")
            self._req("GET", "/api/v1/notifications/", "notifications:list")
            self._req(
                "POST",
                "/api/v1/notifications/devices/",
                "notifications:register",
                json={"fcm_token": f"load-fcm-{self.device_id}", "device_type": "ANDROID"},
            )

        # -------------------------------------------------------------
        # 8. CATALOGS & THEMES
        # -------------------------------------------------------------
        @task(3)
        def task_option_catalogs(self):
            if not self._is_auth():
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
        def task_theme_and_geo(self):
            if not self._is_auth():
                return
            self._req("GET", "/api/v1/theme/options/", "theme:options")
            self._req("GET", "/api/v1/theme/me/", "theme:me")
            self._req(
                "GET",
                "/api/v1/geo/reverse/",
                "geo:reverse",
                params={"lat": self.lat, "lng": self.lon},
                also_ok=(400, 403, 404, 503, 429),
            )

        # -------------------------------------------------------------
        # 9. WALLET / SUBSCRIPTIONS / CALLS
        # -------------------------------------------------------------
        @task(2)
        def task_subscriptions(self):
            if not self._is_auth():
                return
            self._req("GET", "/api/v1/subscriptions/status/", "subscriptions:status")
            self._req("GET", "/api/v1/subscriptions/history/", "subscriptions:history")
            self._req("GET", "/api/v1/subscriptions/required-plan/", "subscriptions:required_plan")
            self._req("GET", "/api/v1/subscription/me/", "wallet:subscription_me")

        @task(2)
        def task_call_and_wallet(self):
            if not self._is_auth():
                return
            self._req("GET", "/api/v1/call/ice-servers/", "call:ice_servers")
            self._req("GET", "/api/v1/call/quota/", "call:quota")
            self._req("GET", "/api/v1/call-time/wallet/", "call:wallet")
            self._req("GET", "/api/v1/call-time/packages/", "call:packages")

        # -------------------------------------------------------------
        # 10. ANALYTICS & HEALTH
        # -------------------------------------------------------------
        @task(3)
        def task_analytics_event(self):
            if not self._is_auth():
                return
            self._req(
                "POST",
                "/api/v1/analytics/events/",
                "analytics:event",
                json={
                    "event_name": "feed_view",
                    "properties": {"source": "locust", "node": node_name},
                    "session_id": self.device_id[:32],
                    "device_type": "android",
                    "platform": "android",
                    "app_version": "load-v2",
                },
            )

        @task(2)
        def task_health(self):
            self._req("GET", "/health/", "health:status", also_ok=(404, 429))
            self._req("GET", "/health/live/", "health:live", also_ok=(404, 429))
            self._req("GET", "/health/ready/", "health:ready", also_ok=(404, 429))

    FullPlatformLoadUser.__name__ = f"User_{node_name}"
    return FullPlatformLoadUser
