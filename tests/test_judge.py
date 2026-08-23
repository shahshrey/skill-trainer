"""Judge phase: verdict parsing, majority vote, cache, mock backend, CLI."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from judge import majority, parse_verdict, resolve_judge

HARNESS = Path(__file__).resolve().parent.parent / "harness"

CRIT = [{"id": "tone", "desc": "matches requested tone"},
        {"id": "complete", "desc": "all steps addressed"}]


def test_resolve_judge_task_level():
    task = {"id": "t1", "scoring": {"mode": "checklist", "soft_source": "judge",
                                    "judge": {"criteria": CRIT}}}
    spec = resolve_judge(task, {})
    assert spec == {"criteria": CRIT, "samples": 3, "backend": None}


def test_resolve_judge_suite_default_and_overrides():
    config = {"soft_source": "judge", "judge_samples": 5, "judge_backend": "claude"}
    task = {"id": "t1", "scoring": {"mode": "checklist", "judge": {"criteria": CRIT}}}
    spec = resolve_judge(task, config)
    assert (spec["samples"], spec["backend"]) == (5, "claude")
    # task-level opt-out beats a judged suite default
    opted_out = {"id": "t2", "scoring": {"mode": "checklist", "soft_source": "self"}}
    assert resolve_judge(opted_out, config) is None


def test_resolve_judge_absent_means_none():
    assert resolve_judge({"id": "t1", "scoring": {"mode": "exact"}}, {}) is None
    assert resolve_judge({"id": "t1"}, {}) is None


def test_resolve_judge_missing_criteria_raises():
    task = {"id": "t1", "scoring": {"soft_source": "judge"}}
    with pytest.raises(ValueError):
        resolve_judge(task, {})
    bad = {"id": "t1", "scoring": {"soft_source": "judge",
                                   "judge": {"criteria": [{"id": "x"}]}}}  # no desc
    with pytest.raises(ValueError):
        resolve_judge(bad, {})


def test_parse_verdict_last_fenced_block_wins():
    out = ('preamble\n```json\n{"criteria": {"tone": false, "complete": false}}\n```\n'
           'wait, correcting:\n```json\n{"criteria": {"tone": true, "complete": false}, '
           '"notes": "missed step 2"}\n```\n')
    v = parse_verdict(out, ["tone", "complete"])
    assert v == {"criteria": {"tone": True, "complete": False}, "notes": "missed step 2"}


def test_parse_verdict_bare_json_and_plain_fence():
    assert parse_verdict('{"criteria": {"tone": true}}', ["tone"])["criteria"] == {"tone": True}
    assert parse_verdict('```\n{"criteria": {"tone": true}}\n```', ["tone"]) is not None


def test_parse_verdict_rejects_incomplete_or_nonbool():
    assert parse_verdict('{"criteria": {"tone": true}}', ["tone", "complete"]) is None
    assert parse_verdict('{"criteria": {"tone": 7, "complete": true}}', ["tone", "complete"]) is None
    assert parse_verdict("no json here", ["tone"]) is None


def test_parse_verdict_ignores_extra_criteria():
    v = parse_verdict('{"criteria": {"tone": true, "invented": true}}', ["tone"])
    assert v["criteria"] == {"tone": True}


def test_majority_strict_and_tie_fails():
    s = [{"criteria": {"a": True, "b": True}}, {"criteria": {"a": True, "b": False}},
         {"criteria": {"a": False, "b": False}}]
    criteria, soft = majority(s, ["a", "b"])
    assert criteria == {"a": 1, "b": 0}
    assert soft == 0.5
    # 1-1 tie on an even number of valid samples fails the criterion
    criteria, soft = majority(s[:2], ["a", "b"])
    assert criteria == {"a": 1, "b": 0}
    assert soft == 0.5
