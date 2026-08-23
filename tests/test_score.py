"""Scoring: per-mode correctness and batch aggregates."""
import json
import subprocess
import sys
from pathlib import Path

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
