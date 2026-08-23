"""Row-diagnosis classes (harness/diagnose_rows.py)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))
from diagnose_rows import diagnose  # noqa: E402

EXP = [("Books", 300), ("Toys", 200), ("Home", 100)]


def test_match_returns_empty():
    assert diagnose(EXP, EXP, ordered=True) == []
    assert diagnose(list(reversed(EXP)), EXP, ordered=False) == []


def test_order_reversed_vs_generic():
    assert diagnose(list(reversed(EXP)), EXP, ordered=True) == \
        ["order_wrong_reversed"]
    shuffled = [EXP[1], EXP[0], EXP[2]]
    assert diagnose(shuffled, EXP, ordered=True) == ["order_wrong"]


def test_under_filtering_is_rows_extra_only():
    got = EXP + [("Garden", 50)]           # forgot a scope filter
    assert diagnose(got, EXP, ordered=True) == ["rows_extra_only"]


def test_over_filtering_is_rows_missing_only():
    assert diagnose(EXP[:2], EXP, ordered=True) == ["rows_missing_only"]


def test_rounding_grain():
    got = [("Books", 300.4), ("Toys", 199.6), ("Home", 100)]
    assert diagnose(got, EXP, ordered=True) == ["values_rounding_grain"]


def test_consistent_scale_factor():
    got = [(k, v * 2) for k, v in EXP]      # double-count (missed dedup)
    out = diagnose(got, EXP, ordered=True)
    assert len(out) == 1 and out[0].startswith("values_scaled_2.0")


def test_irregular_drift():
    got = [("Books", 305), ("Toys", 150), ("Home", 100)]
    assert diagnose(got, EXP, ordered=True) == ["values_drift"]


def test_disjoint_falls_back():
    got = [("Alpha", 1), ("Beta", 2), ("Gamma", 3)]
    assert diagnose(got, EXP, ordered=True) == ["rows_differ"]


def test_all_numeric_rows_use_set_relations():
    exp = [(1,), (2,), (3,)]
    assert diagnose([(1,), (2,), (3,), (9,)], exp, True) == ["rows_extra_only"]
    assert diagnose([(1,), (2,)], exp, True) == ["rows_missing_only"]


def test_duplicate_keys_align_in_order():
    exp = [("A", 10), ("A", 20)]
    got = [("A", 10.3), ("A", 20.3)]
    assert diagnose(got, exp, ordered=True) == ["values_rounding_grain"]
