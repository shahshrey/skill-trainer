"""Scoring: per-mode correctness and batch aggregates."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from score import aggregate, score_task

HARNESS = Path(__file__).resolve().parent.parent / "harness"


def make_ws(tmp_path, name, task, output):
    ws = tmp_path / name
    ws.mkdir(parents=True)
    (ws / "task.json").write_text(json.dumps(task), encoding="utf-8")
    (ws / "output.txt").write_text(output, encoding="utf-8")
    return ws


def test_exact_mode(tmp_path):
    task = {"id": "t1", "scoring": {"mode": "exact", "expected": r"RESULT: solved"}}
    ws = make_ws(tmp_path, "t1", task, "blah\nRESULT: solved\n")
    assert score_task(task, ws, "cheap", {}, None)["hard"] == 1
    ws2 = make_ws(tmp_path, "t1b", task, "RESULT: unsolved\n")
    assert score_task(task, ws2, "cheap", {}, None)["hard"] == 0


def test_checklist_partial_credit(tmp_path):
    task = {"id": "t2", "scoring": {"mode": "checklist", "required": ["PASS:a", "PASS:b", "PASS:c"]}}
    ws = make_ws(tmp_path, "t2", task, "PASS:a\nPASS:c\n")
    r = score_task(task, ws, "cheap", {}, None)
    assert r["hard"] == 0
    assert r["soft"] == 0.6667
    assert "missing:PASS:b" in r["checks"]


def test_empty_output_scores_zero(tmp_path):
    task = {"id": "t3", "scoring": {"mode": "checklist", "required": ["x"]}}
    ws = make_ws(tmp_path, "t3", task, "   \n")
    r = score_task(task, ws, "cheap", {}, None)
    assert (r["hard"], r["soft"]) == (0, 0.0)
    assert "output_empty" in r["checks"]


def test_command_mode(tmp_path):
    task = {"id": "t4", "scoring": {"mode": "command", "command": "grep -q solved \"$TASK_OUTPUT\""}}
    ws = make_ws(tmp_path, "t4", task, "solved\n")
    assert score_task(task, ws, "cheap", {}, None)["hard"] == 1


def test_aggregate_by_suite():
    results = {"a": {"hard": 1, "soft": 1.0}, "b": {"hard": 0, "soft": 0.5},
               "c": {"hard": 1, "soft": 0.8}}
    suites = {"a": "clone", "b": "clone", "c": "workflow-A"}
    agg = aggregate(results, suites, weight=0.5)
    assert agg["overall"]["n"] == 3
    assert agg["by_suite"]["clone"]["hard"] == 0.5
    assert agg["by_suite"]["clone"]["mixed"] == 0.625
    assert agg["by_suite"]["workflow-A"]["soft"] == 0.8


def test_batch_cli_with_suite_default_and_rubric(tmp_path):
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "scoring.md").write_text(
        "# Scoring\n\n```json\n"
        '{"default_mode": "rubric", "mixed_weight": 0.5}\n'
        "```\n", encoding="utf-8")
    (suite / "rubric.py").write_text(
        "def score(task, workdir, mode):\n"
        "    text = (workdir / 'output.txt').read_text()\n"
        "    ok = 'good' in text\n"
        "    return {'hard': int(ok), 'soft': 1.0 if ok else 0.25, 'checks': ['rubric_ran']}\n",
        encoding="utf-8")
    batch = tmp_path / "batch"
    make_ws(batch, "x1", {"id": "x1", "suite": "clone"}, "good output")
    make_ws(batch, "x2", {"id": "x2", "suite": "clone"}, "bad output")
    proc = subprocess.run(
        [sys.executable, str(HARNESS / "score.py"), "--suite", str(suite),
         "--batch", str(batch), "--mode", "cheap"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["tasks"]["x1"]["hard"] == 1
    assert report["tasks"]["x2"]["soft"] == 0.25
    assert report["aggregate"]["overall"]["mixed"] == 0.5625


def test_batch_keeps_k_rollouts_as_separate_samples(tmp_path):
    """K seed-workspaces of one task must all count (gate = mean over K x |val|)."""
    suite = tmp_path / "suite"
    suite.mkdir()
    task = {"id": "t1", "scoring": {"mode": "exact", "expected": "good"}}
    batch = tmp_path / "batch"
    make_ws(batch, "t1_s0", task, "good output")
    make_ws(batch, "t1_s1", task, "bad output")
    proc = subprocess.run(
        [sys.executable, str(HARNESS / "score.py"), "--suite", str(suite),
         "--batch", str(batch)],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["aggregate"]["overall"]["n"] == 2
    assert report["aggregate"]["overall"]["hard"] == 0.5
    assert report["tasks"]["t1_s0"]["task"] == "t1"


def test_scoring_error_exits_2_not_zero_score(tmp_path):
    suite = tmp_path / "suite"
    suite.mkdir()
    batch = tmp_path / "batch"
    make_ws(batch, "x1", {"id": "x1", "scoring": {"mode": "no-such-mode"}}, "text")
    proc = subprocess.run(
        [sys.executable, str(HARNESS / "score.py"), "--suite", str(suite),
         "--batch", str(batch)],
        capture_output=True, text=True)
    assert proc.returncode == 2
    assert "error" in proc.stderr


def make_judged_ws(tmp_path, name, output, judge_payload):
    task = {"id": name, "scoring": {"mode": "checklist", "required": ["PASS"],
                                    "soft_source": "judge",
                                    "judge": {"criteria": [
                                        {"id": "tone", "desc": "d"},
                                        {"id": "complete", "desc": "d"}]}}}
    ws = make_ws(tmp_path, name, task, output)
    if judge_payload is not None:
        payload = {"output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
                   "backend": "mock", "model": None, "samples": [],
                   "flags": [], **judge_payload}
        (ws / "judge.json").write_text(json.dumps(payload), encoding="utf-8")
    return task, ws


def test_soft_source_judge_reads_judge_json(tmp_path):
    task, ws = make_judged_ws(tmp_path, "j1", "PASS output\n",
                              {"criteria": {"tone": 1, "complete": 0}, "soft": 0.5})
    r = score_task(task, ws, "cheap", {}, None)
    assert r["hard"] == 1              # deterministic checklist floor
    assert r["soft"] == 0.5            # judge-owned
    assert r["soft_source"] == "judge"
    assert "judge:tone:1" in r["checks"] and "judge:complete:0" in r["checks"]


def test_soft_source_judge_missing_judge_json_raises(tmp_path):
    task, ws = make_judged_ws(tmp_path, "j2", "PASS output\n", None)
    with pytest.raises(FileNotFoundError):
        score_task(task, ws, "cheap", {}, None)


def test_soft_source_judge_stale_sha_raises(tmp_path):
    task, ws = make_judged_ws(tmp_path, "j3", "PASS output\n",
                              {"criteria": {"tone": 1, "complete": 1}, "soft": 1.0})
    (ws / "output.txt").write_text("PASS but edited\n", encoding="utf-8")
    with pytest.raises(ValueError):
        score_task(task, ws, "cheap", {}, None)


def test_soft_source_judge_empty_output_short_circuits(tmp_path):
    task, ws = make_judged_ws(tmp_path, "j4", "   \n", None)
    r = score_task(task, ws, "cheap", {}, None)      # no judge.json needed
    assert (r["hard"], r["soft"]) == (0, 0.0)
    assert "output_empty" in r["checks"]


def test_suite_level_soft_source_judge(tmp_path):
    task = {"id": "j5", "scoring": {"mode": "checklist", "required": ["PASS"],
                                    "judge": {"criteria": [{"id": "tone", "desc": "d"}]}}}
    output = "PASS output\n"
    ws = make_ws(tmp_path, "j5", task, output)
    (ws / "judge.json").write_text(json.dumps(
        {"output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
         "criteria": {"tone": 1}, "soft": 1.0}), encoding="utf-8")
    r = score_task(task, ws, "cheap", {"soft_source": "judge"}, None)
    assert r["soft"] == 1.0 and r["soft_source"] == "judge"
