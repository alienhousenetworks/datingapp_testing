"""Unit: like persist flush must drop integer ids and not storm Celery."""
from unittest.mock import MagicMock, patch

import pytest

UUID_A = "11111111-1111-1111-1111-111111111111"
UUID_B = "22222222-2222-2222-2222-222222222222"


@pytest.mark.unit
def test_is_user_uuid_rejects_integers():
    from core.apps.interaction.persist_buffer import is_user_uuid

    assert is_user_uuid(UUID_A) is True
    assert is_user_uuid("46") is False
    assert is_user_uuid(46) is False
    assert is_user_uuid("") is False
    assert is_user_uuid(None) is False


@pytest.mark.unit
def test_enqueue_like_drops_non_uuid(django_ready):
    from core.apps.interaction.persist_buffer import PersistBuffer

    with patch.object(PersistBuffer, "_push") as mock_push:
        PersistBuffer.enqueue_like("46", "156")
        mock_push.assert_not_called()
        PersistBuffer.enqueue_like(UUID_A, UUID_B)
        mock_push.assert_called_once()


@pytest.mark.unit
def test_push_schedules_flush_only_on_batch_threshold(django_ready):
    from core.apps.interaction.persist_buffer import PersistBuffer
    from core.common.redis.keys import RedisKeys

    redis = MagicMock()
    with (
        patch.object(PersistBuffer, "_redis", return_value=redis),
        patch.object(PersistBuffer, "_schedule_flush") as mock_flush,
    ):
        redis.rpush.return_value = RedisKeys.PERSIST_BATCH_SIZE - 1
        PersistBuffer._push("likes", {"sender_id": UUID_A, "receiver_id": UUID_B})
        mock_flush.assert_not_called()

        redis.rpush.return_value = RedisKeys.PERSIST_BATCH_SIZE
        PersistBuffer._push("likes", {"sender_id": UUID_A, "receiver_id": UUID_B})
        mock_flush.assert_called_once_with("likes")

        mock_flush.reset_mock()
        redis.rpush.return_value = RedisKeys.PERSIST_BATCH_SIZE + 50
        PersistBuffer._push("likes", {"sender_id": UUID_A, "receiver_id": UUID_B})
        mock_flush.assert_not_called()


@pytest.mark.unit
def test_flush_likes_drops_integer_ids_and_does_not_requeue_them(django_ready):
    from core.apps.interaction.tasks import flush_likes_persist_queue

    poison = {"sender_id": "46", "receiver_id": "156"}
    with (
        patch(
            "core.apps.interaction.persist_buffer.PersistBuffer.pop_batch",
            return_value=[poison],
        ),
        patch("core.apps.interaction.models.Like.objects.bulk_create") as mock_create,
        patch(
            "core.apps.interaction.persist_buffer.PersistBuffer.requeue_batch"
        ) as mock_requeue,
        patch(
            "core.apps.interaction.persist_buffer.PersistBuffer.enqueue_like"
        ) as mock_enqueue,
    ):
        result = flush_likes_persist_queue()
        assert result == 0
        mock_create.assert_not_called()
        mock_requeue.assert_not_called()
        mock_enqueue.assert_not_called()
