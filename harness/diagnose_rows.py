#!/usr/bin/env python3
"""Row-set failure diagnosis: turn "not_exact" into an aimable check class.

Framework motivation (runs sql05 + the GPT test evals): editors can only
aim edits at what receipts NAME. A flat `not_exact`/`order_wrong` hides
whether the miss was a scope filter, an ordering variant, a rounding
grain, or a systematic scale factor — so within-class rule variants were
invisible to the loop (coverage.py showed identical signatures for
different underlying mistakes). This module classifies a failed
result-set comparison deterministically; suite rubrics append its checks.

Diagnosis classes (all magnitudes collapse under coverage.py's digit
normalization, so each string below is one stable class):

  order_wrong_reversed      same multiset; candidate is the exact reverse
  order_wrong               same multiset, different sequence (other)
  rows_extra_only           expected is a strict sub-multiset (missing a
                            filter: scope/status/draft/dedup-existence)
  rows_missing_only         candidate is a strict sub-multiset
                            (over-filtering / lost rows)
  values_rounding_grain     keys align; every numeric drift has |d| <= 1
                            (rounding at the wrong level / grain)
  values_scaled             keys align; numeric ratios are consistent and
                            != 1 (double-count, missed discount/conversion)
  values_drift              keys align; numeric cells differ irregularly
  rows_differ               none of the above patterns fit

Purely stdlib and deterministic. hard/soft are the rubric's business —
this module only names the failure.
"""
from __future__ import annotations

Row = tuple


def _rows(rows) -> list[Row]:
    return [tuple(r) for r in rows]


def _multiset(rows: list[Row]) -> dict[Row, int]:
    out: dict[Row, int] = {}
    for r in rows:
        out[r] = out.get(r, 0) + 1
    return out


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _sub_multiset(a: dict, b: dict) -> bool:
    return all(b.get(k, 0) >= n for k, n in a.items())


def diagnose(got_rows, expected_rows, ordered: bool) -> list[str]:
    """Classify why got != expected. Empty list when they match."""
    got, exp = _rows(got_rows), _rows(expected_rows)
    gm, em = _multiset(got), _multiset(exp)

    if gm == em:
        if not ordered or got == exp:
            return []
        if got == exp[::-1]:
            return ["order_wrong_reversed"]
        return ["order_wrong"]

    if _sub_multiset(em, gm):
        return ["rows_extra_only"]
    if _sub_multiset(gm, em):
        return ["rows_missing_only"]

    drift = _value_drift(got, exp)
    if drift:
        return drift
    return ["rows_differ"]


def _value_drift(got: list[Row], exp: list[Row]) -> list[str]:
    """When rows align on their non-numeric key columns, classify how the
    numeric cells drifted. Returns [] when keys don't align."""
    if not exp or not got or len(got) != len(exp):
        return []
    width = len(exp[0])
    if any(len(r) != width for r in got + exp):
        return []
    num_cols = [i for i in range(width) if all(_is_num(r[i]) for r in exp)]
    key_cols = [i for i in range(width) if i not in num_cols]
    if not num_cols:
        return []

    def key(r: Row) -> Row:
        return tuple(r[i] for i in key_cols)

    def by_key(rows: list[Row]) -> dict[Row, list[Row]]:
        out: dict[Row, list[Row]] = {}
        for r in rows:
            out.setdefault(key(r), []).append(r)
        return out

    gk, ek = by_key(got), by_key(exp)
    if set(gk) != set(ek) or any(len(gk[k]) != len(ek[k]) for k in ek):
        return []

    diffs: list[float] = []
    ratios: list[float] = []
    for k in ek:
        for g_row, e_row in zip(sorted(gk[k]), sorted(ek[k])):
            for i in num_cols:
                g_val, e_val = float(g_row[i]), float(e_row[i])
                if g_val == e_val:
                    continue
                diffs.append(abs(g_val - e_val))
                if e_val != 0:
                    ratios.append(g_val / e_val)
    if not diffs:
        return []
    if all(d <= 1.0 for d in diffs):
        return ["values_rounding_grain"]
    if ratios and len(ratios) == len(diffs):
        spread = max(ratios) - min(ratios)
        mean = sum(ratios) / len(ratios)
        if mean != 0 and abs(spread) <= 0.02 * abs(mean):
            return [f"values_scaled_{mean:.2f}"]
    return ["values_drift"]
