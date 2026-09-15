"""Unit: is_liked follows like TTL even when likes:out membership is missing."""
from __future__ import annotations

import pytest


class _FakePipe:
    def __init__(self, redis):
        self.redis = redis
        self.cmds = []

    def sismember(self, key, member):
        self.cmds.append(("sismember", key, member))
        return self

    def exists(self, key):
        self.cmds.append(("exists", key))
        return self

    def execute(self):
        out = []
        for cmd in self.cmds:
            if cmd[0] == "sismember":
                out.append(self.redis.sismember(cmd[1], cmd[2]))
            elif cmd[0] == "exists":
                out.append(self.redis.exists(cmd[1]))
        self.cmds = []
        return out


class _FakeRedis:
    def __init__(self):
        self.sets = {}
        self.kv = {}

    def pipeline(self, transaction=False):
        return _FakePipe(self)

    def smismember(self, key, *ids):
        members = self.sets.get(key, set())
        return [1 if i in members else 0 for i in ids]

    def sismember(self, key, member):
        return 1 if member in self.sets.get(key, set()) else 0

    def exists(self, key):
        return 1 if key in self.kv else 0

    def sadd(self, key, member):
        self.sets.setdefault(key, set()).add(member)

    def setex(self, key, ttl, val):
        self.kv[key] = val


@pytest.mark.unit
def test_is_liked_true_from_like_ts_when_out_set_empty():
    from core.apps.interaction.like_state import (
        overlay_feed_is_liked,
        viewer_has_liked,
        viewer_liked_ids,
    )
    from core.common.redis.keys import RedisKeys

    redis = _FakeRedis()
    viewer = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    target = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    redis.setex(RedisKeys.get_like_ts_key(viewer, target), 129600, "1")

    assert target in viewer_liked_ids(redis, viewer, [target])
    # Compact UUID form must still resolve to the same like:ts key
    compact = target.replace("-", "")
    assert target in viewer_liked_ids(redis, viewer.replace("-", ""), [compact])
    assert viewer_has_liked(viewer, target, redis_conn=redis)

    stale = [
        {
            "id": target,
            "is_liked": False,
            "profile_card": {"id": target, "is_liked": False},
        }
    ]
    overlay_feed_is_liked(stale, viewer, redis)
    assert stale[0]["is_liked"] is True
    assert stale[0]["profile_card"]["is_liked"] is True


@pytest.mark.unit
def test_is_liked_false_when_only_likes_out_set():
    """Stale likes:out membership after TTL must not keep the heart filled."""
    from core.apps.interaction.like_state import viewer_liked_ids
    from core.common.redis.keys import RedisKeys

    redis = _FakeRedis()
    viewer = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    target = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    redis.sadd(RedisKeys.get_likes_out_key(viewer), target)

    assert target not in viewer_liked_ids(redis, viewer, [target])


@pytest.mark.unit
def test_overlay_not_liked_when_only_out_set():
    from core.apps.interaction.like_state import overlay_feed_is_liked

    redis = _FakeRedis()
    viewer = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    target = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    redis.sadd("likes:out:" + viewer, target)
    rows = [{"id": target, "is_liked": True, "profile_card": {"id": target, "is_liked": True}}]
    overlay_feed_is_liked(rows, viewer, redis)
    assert rows[0]["is_liked"] is False
    assert rows[0]["profile_card"]["is_liked"] is False


@pytest.mark.unit
def test_is_liked_false_when_ttl_and_set_absent():
    from core.apps.interaction.like_state import viewer_has_liked, viewer_liked_ids

    redis = _FakeRedis()
    viewer = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    target = "dddddddd-dddd-dddd-dddd-dddddddddddd"

    assert target not in viewer_liked_ids(redis, viewer, [target])
    assert viewer_has_liked(viewer, target, redis_conn=redis) is False
