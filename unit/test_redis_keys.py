"""Unit: Redis key templates used by auth/feed/interaction."""
import pytest


@pytest.mark.unit
def test_otp_key_format(django_ready):
    from core.common.redis.keys import RedisKeys

    email = "user@example.com"
    key = RedisKeys.get_otp_key(email) if hasattr(RedisKeys, "get_otp_key") else RedisKeys.OTP_KEY.format(email=email)
    assert "otp" in key.lower() or email in key
    assert email in key or "user" in key


@pytest.mark.unit
def test_redis_key_constants(django_ready):
    from core.common.redis.keys import RedisKeys

    assert RedisKeys.OTP_TTL == 300
    assert RedisKeys.OTP_COOLDOWN_TTL == 60
    assert RedisKeys.OTP_MAX_REQUESTS == 5
    assert "likes:out" in RedisKeys.LIKES_OUT
    assert "likes:in" in RedisKeys.LIKES_IN
    assert "feed:" in RedisKeys.FEED_KEY
