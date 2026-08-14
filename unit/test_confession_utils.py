"""Unit: confession content filters (pure functions)."""
import pytest


@pytest.mark.unit
def test_contains_phone_number(django_ready):
    from core.apps.confession.utils import contains_phone_number

    assert contains_phone_number("Call me at +91 98765 43210") is True
    assert contains_phone_number("hello world") is False
    assert contains_phone_number("123") is False


@pytest.mark.unit
def test_contains_links(django_ready):
    from core.apps.confession.utils import contains_links

    assert contains_links("check https://example.com now") is True
    assert contains_links("see www.spam.com") is True
    assert contains_links("no links here") is False


@pytest.mark.unit
def test_content_hash_stable(django_ready):
    from core.apps.confession.utils import get_content_hash

    h1 = get_content_hash("  Hello World  ")
    h2 = get_content_hash("hello world")
    assert h1 == h2
    assert len(h1) == 32  # md5 hex
