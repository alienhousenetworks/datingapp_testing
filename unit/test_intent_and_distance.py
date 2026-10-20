"""Intent UUID ranking + missing GPS distance must not look 'perfect'."""
from core.apps.feed.engine.features import FeatureExtractionLayer
from core.apps.feed.engine.ranking import RankingEngine
from core.common.options_cache import IntentCatalogCache


def test_same_uuid_intents_score_one():
    uid = "11111111-1111-1111-1111-111111111111"
    assert FeatureExtractionLayer.compute_intent_match(uid, uid) == 1.0


def test_named_intents_use_matrix():
    score = FeatureExtractionLayer.compute_intent_match(
        "Long-term relationship", "Short-term fun"
    )
    assert score == 0.1


def test_intent_catalog_name_codes():
    assert IntentCatalogCache.code_for("New friends") == 3
    assert IntentCatalogCache.code_for(1) == 1
    assert IntentCatalogCache.code_for(None) == 0


def test_unknown_distance_is_neutral():
    assert FeatureExtractionLayer.compute_distance_score(None) == 0.5
    assert FeatureExtractionLayer.compute_distance_score(0.0) == 1.0


def test_gender_visibility_bucket_case_and_trans():
    assert RankingEngine.gender_visibility_bucket("Female") == "female"
    assert RankingEngine.gender_visibility_bucket("FEMALE") == "female"
    assert RankingEngine.gender_visibility_bucket("Transgender Female") == "female"
    assert RankingEngine.gender_visibility_bucket("Male") == "male"
    assert RankingEngine.gender_visibility_bucket("Non-binary") == "other"
