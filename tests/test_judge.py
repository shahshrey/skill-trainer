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


def make_suite(tmp_path, config=None):
    suite = tmp_path / "suite"
    suite.mkdir(exist_ok=True)
    cfg = {"default_mode": "checklist", **(config or {})}
    (suite / "scoring.md").write_text(
        "# Scoring\n\n```json\n" + json.dumps(cfg) + "\n```\n", encoding="utf-8")
    return suite


def verdict(criteria, notes=""):
    return "```json\n" + json.dumps({"criteria": criteria, "notes": notes}) + "\n```\n"


def make_judged_ws(tmp_path, name, output="some output\n", judge_outputs=None,
                   scoring=None):
    ws = tmp_path / "batch" / name
    ws.mkdir(parents=True)
    task = {"id": name, "suite": "primary",
            "scoring": scoring or {"mode": "checklist", "required": ["some"],
                                   "soft_source": "judge",
                                   "judge": {"criteria": CRIT}}}
    if judge_outputs is not None:
        task["mock"] = {"judge_outputs": judge_outputs}
    (ws / "task.json").write_text(json.dumps(task), encoding="utf-8")
    (ws / "output.txt").write_text(output, encoding="utf-8")
    return ws


def test_judge_workspace_mock_majority_and_json(tmp_path):
    from judge import judge_workspace
    suite = make_suite(tmp_path)
    outs = [verdict({"tone": True, "complete": True}),
            verdict({"tone": True, "complete": False}),
            verdict({"tone": False, "complete": False})]
    ws = make_judged_ws(tmp_path, "t1", judge_outputs=outs)
    r = judge_workspace(suite, ws, "mock", None, False, 120)
    assert r["status"] == "judged"
    j = json.loads((ws / "judge.json").read_text(encoding="utf-8"))
    assert j["criteria"] == {"tone": 1, "complete": 0}
    assert j["soft"] == 0.5
    assert len(j["samples"]) == 3
    assert j["backend"] == "mock"


def test_judge_workspace_skips_undeclared_and_empty(tmp_path):
    from judge import judge_workspace
    suite = make_suite(tmp_path)
    plain = make_judged_ws(tmp_path, "t2",
                           scoring={"mode": "checklist", "required": ["x"]})
    assert judge_workspace(suite, plain, "mock", None, False, 120)["status"] == "skipped"
    empty = make_judged_ws(tmp_path, "t3", output="   \n",
                           judge_outputs=[verdict({"tone": True, "complete": True})])
    assert judge_workspace(suite, empty, "mock", None, False, 120)["status"] == "empty"
    assert not (empty / "judge.json").exists()


def test_judge_workspace_cache_and_force(tmp_path):
    from judge import judge_workspace
    suite = make_suite(tmp_path)
    outs = [verdict({"tone": True, "complete": True})]
    ws = make_judged_ws(tmp_path, "t4", judge_outputs=outs)
    assert judge_workspace(suite, ws, "mock", 1, False, 120)["status"] == "judged"
    assert judge_workspace(suite, ws, "mock", 1, False, 120)["status"] == "cached"
    # output changed -> stale cache is re-judged
    (ws / "output.txt").write_text("different output\n", encoding="utf-8")
    assert judge_workspace(suite, ws, "mock", 1, False, 120)["status"] == "judged"
    assert judge_workspace(suite, ws, "mock", 1, True, 120)["status"] == "judged"


def test_judge_workspace_unparseable_sample_dropped_with_flag(tmp_path):
    from judge import judge_workspace
    suite = make_suite(tmp_path)
    outs = [verdict({"tone": True, "complete": True}), "garbage, no json",
            verdict({"tone": True, "complete": True})]
    ws = make_judged_ws(tmp_path, "t5", judge_outputs=outs)
    judge_workspace(suite, ws, "mock", 3, False, 120)
    j = json.loads((ws / "judge.json").read_text(encoding="utf-8"))
    assert j["flags"] == ["sample_1_unparseable"]
    assert len(j["samples"]) == 2
    assert j["criteria"] == {"tone": 1, "complete": 1}


def test_judge_workspace_all_samples_failed_raises(tmp_path):
    from judge import JudgeError, judge_workspace
    suite = make_suite(tmp_path)
    ws = make_judged_ws(tmp_path, "t6", judge_outputs=["nope"])
    with pytest.raises(JudgeError):
        judge_workspace(suite, ws, "mock", 2, False, 120)


def test_judge_cli_batch_mock(tmp_path):
    suite = make_suite(tmp_path, {"soft_source": "judge", "judge_samples": 1})
    good = verdict({"tone": True, "complete": True})
    make_judged_ws(tmp_path, "a", judge_outputs=[good],
                   scoring={"mode": "checklist", "required": ["some"],
                            "judge": {"criteria": CRIT}})
    make_judged_ws(tmp_path, "b",
                   scoring={"mode": "checklist", "required": ["some"],
                            "soft_source": "self"})
    proc = subprocess.run(
        [sys.executable, str(HARNESS / "judge.py"), "--suite", str(suite),
         "--batch", str(tmp_path / "batch"), "--backend", "mock"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout)
    assert summary["judged"] == ["a"]
    assert summary["skipped"] == ["b"]
    assert (tmp_path / "batch" / "a" / "judge.json").exists()
    assert not (tmp_path / "batch" / "b" / "judge.json").exists()


def test_judge_cli_error_exit_2(tmp_path):
    suite = make_suite(tmp_path)
    make_judged_ws(tmp_path, "bad", judge_outputs=["garbage"])
    proc = subprocess.run(
        [sys.executable, str(HARNESS / "judge.py"), "--suite", str(suite),
         "--batch", str(tmp_path / "batch"), "--backend", "mock"],
        capture_output=True, text=True)
    assert proc.returncode == 2
    assert "bad" in json.loads(proc.stderr)["errors"]
