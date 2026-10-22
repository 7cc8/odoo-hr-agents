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


def test_new_named_constants_keep_their_values():
    assert mt.PROPOSE_MISSING_ENTITY_BELOW_CONFIDENCE == 0.60
    assert mt.MISSING_ENTITY_PROPOSAL_CONFIDENCE == 0.95
    assert mt.STATIC_CONSULTATION_REPORT_CONFIDENCE == 0.85
    assert mt.MUWAFFAQ_MIN_CANDIDATE_SIMILARITY == 0.60
    assert mt.MUWAFFAQ_SAME_DEPARTMENT_BOOST == 0.15
    assert mt.ESCALATION_DECISION_CONFIDENCE == 0.50


def test_no_threshold_literals_left_in_matching_code():
    """Thresholds must live in matching_thresholds.py (0.0 and 1.0 are plain bounds)."""
    import ast
    import os

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in ("musleh_service.py", "validator.py", os.path.join("agents", "muwaffaq_agent.py")):
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        found = sorted({(n.lineno, n.value) for n in ast.walk(tree)
                        if isinstance(n, ast.Constant) and isinstance(n.value, float) and n.value not in (0.0, 1.0)})
        assert not found, f"{rel} has hardcoded thresholds: {found}"
