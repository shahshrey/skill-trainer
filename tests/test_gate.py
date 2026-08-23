"""Gate correctness: scripted score sequences -> right decisions."""
import pytest

from gate import decide, min_delta_from_baseline, mixed_score


def test_mixed_score_default_weights():
    assert mixed_score(1.0, 0.5) == 0.75
    assert mixed_score(0.0, 0.8, soft_weight=1.0) == 0.8
    assert mixed_score(0.6, 0.0, soft_weight=0.0) == 0.6


def test_reject_when_not_beating_min_delta():
    r = decide(candidate=0.66, current=0.65, best=0.70, min_delta=0.02)
    assert r["action"] == "reject"
    assert r["new_current"] == 0.65
    assert r["new_best"] == 0.70


def test_reject_on_exact_tie():
    r = decide(candidate=0.65, current=0.65, best=0.65, min_delta=0.0)
    assert r["action"] == "reject"


def test_accept_between_current_and_best():
    r = decide(candidate=0.68, current=0.65, best=0.70, min_delta=0.02)
    assert r["action"] == "accept"
    assert r["new_current"] == 0.68
    assert r["new_best"] == 0.70


def test_accept_new_best():
    r = decide(candidate=0.73, current=0.65, best=0.70, min_delta=0.02)
    assert r["action"] == "accept_new_best"
    assert r["new_current"] == 0.73
    assert r["new_best"] == 0.73


def test_non_authoritative_mode_never_moves_best():
    r = decide(candidate=0.73, current=0.65, best=0.70, min_delta=0.02,
               best_eligible=False)
    assert r["action"] == "accept"
    assert r["new_best"] == 0.70


def test_two_suite_rule_blocks_secondary_regression():
    r = decide(candidate=0.80, current=0.65, best=0.70, min_delta=0.02,
               cand_secondary=0.40, current_secondary=0.55)
    assert r["action"] == "reject"
    assert "secondary regression" in r["reason"]


def test_two_suite_rule_allows_small_secondary_dip():
    r = decide(candidate=0.80, current=0.65, best=0.70, min_delta=0.02,
               cand_secondary=0.54, current_secondary=0.55)
    assert r["action"] == "accept_new_best"
    assert r["new_current_secondary"] == 0.54


def test_secondary_must_come_in_pairs():
    with pytest.raises(ValueError):
        decide(candidate=0.8, current=0.6, best=0.7, min_delta=0.01,
               cand_secondary=0.5)


def test_min_delta_from_baseline_spread():
    assert min_delta_from_baseline([0.60, 0.65, 0.62]) == pytest.approx(0.05)
    assert min_delta_from_baseline([0.60, 0.601, 0.60]) == 0.01  # floor
