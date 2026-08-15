"""Feed cache-key filters must ignore device GPS unless city search is on."""
from core.apps.feed.filter_utils import canonical_feed_cache_filters, normalize_feed_filters


def test_drops_gps_when_not_city_search():
    filters = normalize_feed_filters(
        {"city_lat": 22.5726, "city_lon": 88.3639, "distance": 0}
    )
    cache = canonical_feed_cache_filters(filters)
    assert "city_lat" not in cache
    assert "city_lon" not in cache
    assert cache.get("distance") == 0


def test_keeps_gps_when_city_search():
    cache = canonical_feed_cache_filters(
        {"city": "Kolkata", "city_lat": 22.5726, "city_lon": 88.3639}
    )
    assert cache["city"] == "Kolkata"
    assert cache["city_lat"] == 22.5726
    assert cache["city_lon"] == 88.3639


def test_strips_internal_pagination_hints():
    cache = canonical_feed_cache_filters(
        {"distance": 50, "_max_stream_len": 40, "city_lat": 1.0}
    )
    assert "_max_stream_len" not in cache
    assert "city_lat" not in cache
    assert cache["distance"] == 50
