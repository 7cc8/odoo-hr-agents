"""The similarity thresholds live in one module and the callers use them."""
import matching_thresholds as mt
import musleh_service
from agents.muwaffaq_agent import MuwaffaqAgent


def test_values_unchanged_by_centralisation():
    assert mt.AUTO_REPAIR_MIN_CONFIDENCE == 0.90
    assert mt.PROPOSE_PATCH_MIN_CONFIDENCE == 0.80
    assert mt.FUZZY_CANDIDATE_CUTOFF == 0.5
    assert mt.CLOSEST_MATCH_SUGGESTION_CUTOFF == 0.6
    assert (mt.MUWAFFAQ_HIGH_CONFIDENCE, mt.MUWAFFAQ_MEDIUM_CONFIDENCE, mt.MUWAFFAQ_LOW_CONFIDENCE) == (0.90, 0.70, 0.50)


def test_musleh_keeps_its_public_constant():
    assert musleh_service.CONFIDENCE_THRESHOLD_AUTO_REPAIR == mt.AUTO_REPAIR_MIN_CONFIDENCE


def test_muwaffaq_agent_uses_shared_thresholds():
    agent = MuwaffaqAgent()
    assert agent.confidence_thresholds == {
        "high": mt.MUWAFFAQ_HIGH_CONFIDENCE,
        "medium": mt.MUWAFFAQ_MEDIUM_CONFIDENCE,
        "low": mt.MUWAFFAQ_LOW_CONFIDENCE,
    }
