"""LLM-judge scoring mode, exercised with a fake model (no network, no LLM)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import judge
from score import RUBRIC_FILES, rubric_version, score_task

HARNESS = Path(__file__).resolve().parent.parent / "harness"


def verdict(overall, passed, crit=None, reasoning="because"):
    crit = crit or {"recall": overall, "precision": overall}
    return {"criteria": [{"name": k, "score": v, "evidence": "e"} for k, v in crit.items()],
            "overall": overall, "passed": passed, "reasoning": reasoning}


def make_suite(tmp_path, judge_md="Judge it.", config=None):
    suite = tmp_path / "suite"
    suite.mkdir(exist_ok=True)
    cfg = {"default_mode": "judge", "judge": config or {}}
    (suite / "scoring.md").write_text("```json\n" + json.dumps(cfg) + "\n```\n")
    (suite / "judge.md").write_text(judge_md)
    return suite


def make_ws(tmp_path, name, task, output):
    ws = tmp_path / name
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "task.json").write_text(json.dumps(task))
    (ws / "output.txt").write_text(output)
    return ws


# --- parsing -----------------------------------------------------------------

def test_parse_prefers_tool_call_arguments():
    raw = {"tool_args": verdict(0.8, True), "content": "ignored"}
    v = judge.parse_verdict(raw)
    assert v["overall"] == 0.8 and v["passed"] is True
    assert v["criteria"][0]["name"] == "recall"


def test_parse_falls_back_to_json_in_content_and_strips_think():
    content = ("<think>let me reason\nabout {braces} here</think>\n\n"
               "Here is my verdict:\n" + json.dumps(verdict(0.4, False)) + "\nthanks")
    v = judge.parse_verdict({"tool_args": None, "content": content})
    assert v["overall"] == 0.4 and v["passed"] is False


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        judge.parse_verdict({"tool_args": None, "content": "<think>hmm</think> no json here"})


def test_validate_clamps_scores_and_coerces_passed():
    v = judge.validate_verdict({"criteria": [{"name": "a", "score": 1.7, "evidence": ""}],
                                "overall": -0.2, "passed": "true", "reasoning": "r"})
    assert v["criteria"][0]["score"] == 1.0
    assert v["overall"] == 0.0
    assert v["passed"] is True


def test_validate_derives_missing_overall_from_criteria():
    v = judge.validate_verdict({"criteria": [{"name": "a", "score": 0.2, "evidence": ""},
                                             {"name": "b", "score": 0.6, "evidence": ""}],
                                "passed": False, "reasoning": "r"})
    assert v["overall"] == 0.4


def test_validate_requires_criteria_list():
    with pytest.raises(ValueError):
        judge.validate_verdict({"overall": 0.5, "passed": True, "reasoning": "r"})


# --- reference resolution (dataset vs rubric) ---------------------------------

def test_reference_path_relative_to_suite(tmp_path):
    suite = make_suite(tmp_path)
    (suite / "refs").mkdir()
    (suite / "refs" / "gold.md").write_text("GOLD")
    assert judge.resolve_reference({"reference": "refs/gold.md"}, suite) == "GOLD"
    assert judge.resolve_reference({"reference_text": "inline"}, suite) == "inline"
    assert judge.resolve_reference({}, suite) is None


def test_missing_reference_file_is_a_scoring_error_not_a_zero(tmp_path):
    suite = make_suite(tmp_path)
    with pytest.raises(FileNotFoundError):
        judge.resolve_reference({"reference": "refs/nope.md"}, suite)


def test_messages_carry_prompt_reference_inputs_and_output(tmp_path):
    suite = make_suite(tmp_path, judge_md="RUBRIC TEXT")
    ws = make_ws(tmp_path, "ws", {"prompt": "Do X"}, "THE OUTPUT")
    (ws / "fixture.md").write_text("FIXTURE BODY")
    task = {"prompt": "Do X", "reference_text": "GOLD", "judge_inputs": ["fixture.md"]}
    system, user = judge.build_messages("RUBRIC TEXT", task, "THE OUTPUT", "GOLD",
                                        judge.collect_inputs(task, ws))
    assert "RUBRIC TEXT" in system
    for needle in ("Do X", "GOLD", "FIXTURE BODY", "THE OUTPUT"):
        assert needle in user
    _, user_rubric = judge.build_messages("R", task, "OUT", None, {})
    assert "No reference" in user_rubric


# --- scoring, sampling, caching -----------------------------------------------

def test_judge_output_single_sample(tmp_path):
    suite = make_suite(tmp_path)
    ws = make_ws(tmp_path, "t1_s0", {"id": "t1", "prompt": "p", "reference_text": "g"}, "out")
    calls = []

    def fake(messages, cfg, key):
        calls.append(messages)
        return {"tool_args": verdict(0.9, True, {"recall": 1.0, "precision": 0.8}), "content": ""}

    r = judge.judge_output({"id": "t1", "prompt": "p", "reference_text": "g"}, ws, suite,
                           {"judge": {}}, call_model=fake, api_key="k")
    assert (r["hard"], r["soft"]) == (1, 0.9)
    assert "crit:recall=1.0" in r["checks"] and "crit:precision=0.8" in r["checks"]
    assert "judge:pass" in r["checks"] and "ref:dataset" in r["checks"]
    assert len(calls) == 1
    saved = json.loads((ws / "judge.json").read_text())
    assert saved["samples"][0]["reasoning"] == "because"


def test_three_samples_average_soft_and_majority_hard(tmp_path):
    suite = make_suite(tmp_path, config={"samples": 3})
    ws = make_ws(tmp_path, "t1_s0", {"id": "t1", "prompt": "p"}, "out")
    answers = iter([verdict(0.6, True), verdict(0.3, False), verdict(0.9, True)])

    def fake(messages, cfg, key):
        return {"tool_args": next(answers), "content": ""}

    r = judge.judge_output({"id": "t1", "prompt": "p"}, ws, suite,
                           judge.suite_config(suite), call_model=fake, api_key="k")
    assert r["soft"] == 0.6
    assert r["hard"] == 1
    assert "ref:rubric" in r["checks"]


def test_majority_tie_fails_closed(tmp_path):
    suite = make_suite(tmp_path, config={"samples": 2})
    ws = make_ws(tmp_path, "t1_s0", {"id": "t1", "prompt": "p"}, "out")
    answers = iter([verdict(0.6, True), verdict(0.6, False)])
    r = judge.judge_output({"id": "t1", "prompt": "p"}, ws, suite, {"judge": {"samples": 2}},
                           call_model=lambda m, c, k: {"tool_args": next(answers), "content": ""},
                           api_key="k")
    assert r["hard"] == 0


def test_criteria_weights_override_model_overall(tmp_path):
    suite = make_suite(tmp_path)
    ws = make_ws(tmp_path, "t1_s0", {"id": "t1", "prompt": "p"}, "out")
    v = verdict(0.1, True, {"recall": 1.0, "precision": 0.0})  # model says 0.1
    cfg = {"judge": {"criteria_weights": {"recall": 0.75, "precision": 0.25}}}
    r = judge.judge_output({"id": "t1", "prompt": "p"}, ws, suite, cfg,
                           call_model=lambda m, c, k: {"tool_args": v, "content": ""}, api_key="k")
    assert r["soft"] == 0.75


def test_verdicts_are_cached_per_workspace_and_invalidated_on_change(tmp_path):
    suite = make_suite(tmp_path)
    ws = make_ws(tmp_path, "t1_s0", {"id": "t1", "prompt": "p"}, "out")
    n = {"calls": 0}

    def fake(messages, cfg, key):
        n["calls"] += 1
        return {"tool_args": verdict(0.5, False), "content": ""}

    task = {"id": "t1", "prompt": "p"}
    judge.judge_output(task, ws, suite, {"judge": {}}, call_model=fake, api_key="k")
    judge.judge_output(task, ws, suite, {"judge": {}}, call_model=fake, api_key="k")
    assert n["calls"] == 1  # second scoring is free
    (ws / "output.txt").write_text("different output")
    judge.judge_output(task, ws, suite, {"judge": {}}, call_model=fake, api_key="k")
    assert n["calls"] == 2  # changed output -> fresh verdict
    (suite / "judge.md").write_text("new rubric")
    judge.judge_output(task, ws, suite, {"judge": {}}, call_model=fake, api_key="k")
    assert n["calls"] == 3  # changed rubric -> fresh verdict


def test_malformed_reply_gets_one_retry_then_raises(tmp_path):
    suite = make_suite(tmp_path)
    ws = make_ws(tmp_path, "t1_s0", {"id": "t1", "prompt": "p"}, "out")
    replies = iter([{"tool_args": None, "content": "garbage"},
                    {"tool_args": verdict(0.7, True), "content": ""}])
    r = judge.judge_output({"id": "t1", "prompt": "p"}, ws, suite, {"judge": {}},
                           call_model=lambda m, c, k: next(replies), api_key="k")
    assert r["soft"] == 0.7
    always_bad = lambda m, c, k: {"tool_args": None, "content": "garbage"}  # noqa: E731
    ws2 = make_ws(tmp_path, "t2_s0", {"id": "t2", "prompt": "p"}, "out")
    with pytest.raises(ValueError):
        judge.judge_output({"id": "t2", "prompt": "p"}, ws2, suite, {"judge": {}},
                           call_model=always_bad, api_key="k")


def test_missing_api_key_is_an_error(tmp_path, monkeypatch):
    for name in judge.KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    suite = make_suite(tmp_path)
    ws = make_ws(tmp_path, "t1_s0", {"id": "t1", "prompt": "p"}, "out")
    with pytest.raises(RuntimeError, match="API key"):
        judge.judge_output({"id": "t1", "prompt": "p"}, ws, suite, {"judge": {}},
                           call_model=lambda m, c, k: None, env_file=tmp_path / "none.env")


# --- key loading ---------------------------------------------------------------

def test_api_key_from_env_var_or_dotenv(tmp_path, monkeypatch):
    for name in judge.KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / ".env"
    env.write_text('# comment\nOTHER=1\nMINIMAX-API-KEY="sk-from-file"\n')
    assert judge.load_api_key(env) == "sk-from-file"
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-from-env")
    assert judge.load_api_key(env) == "sk-from-env"  # environment wins
    assert judge.load_api_key(tmp_path / "missing.env") == "sk-from-env"


# --- score.py integration --------------------------------------------------------

def test_judge_md_is_part_of_the_scoring_contract(tmp_path):
    assert "judge.md" in RUBRIC_FILES
    suite = make_suite(tmp_path, judge_md="v1")
    v1 = rubric_version(suite)
    (suite / "judge.md").write_text("v2")
    assert rubric_version(suite) != v1


def test_score_task_judge_mode_uses_judge_module(tmp_path, monkeypatch):
    suite = make_suite(tmp_path)
    task = {"id": "t1", "prompt": "p", "scoring": {"mode": "judge"}}
    ws = make_ws(tmp_path, "t1_s0", task, "some output")
    monkeypatch.setattr(judge, "call_model",
                        lambda m, c, k: {"tool_args": verdict(0.8, True), "content": ""})
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    r = score_task(task, ws, "cheap", {"default_mode": "judge", "judge": {}}, None, suite=suite)
    assert r["mode"] == "judge" and r["hard"] == 1 and r["soft"] == 0.8


def test_score_task_judge_mode_empty_output_never_calls_model(tmp_path, monkeypatch):
    suite = make_suite(tmp_path)
    task = {"id": "t1", "prompt": "p"}
    ws = make_ws(tmp_path, "t1_s0", task, "  \n")
    monkeypatch.setattr(judge, "call_model",
                        lambda m, c, k: (_ for _ in ()).throw(AssertionError("called")))
    r = score_task(task, ws, "cheap", {"default_mode": "judge"}, None, suite=suite)
    assert r["hard"] == 0 and "output_empty" in r["checks"]


# --- readiness check (what gets communicated back to the user) -------------------

def test_check_reports_dataset_vs_rubric_counts_and_missing_refs(tmp_path, monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    suite = make_suite(tmp_path)
    (suite / "refs").mkdir()
    (suite / "refs" / "a.md").write_text("gold a")
    rows = [{"id": "a", "prompt": "p", "reference": "refs/a.md"},
            {"id": "b", "prompt": "p"},
            {"id": "c", "prompt": "p", "reference": "refs/missing.md"}]
    (suite / "train.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    report = judge.check(suite)
    assert report["tasks"]["dataset"] == 1
    assert report["tasks"]["rubric"] == 1
    assert report["tasks"]["missing_reference"] == ["c"]
    assert report["ready"] is False  # a dangling reference blocks the run
    assert any("rubric" in w.lower() for w in report["warnings"])


def test_check_cli_exit_codes(tmp_path, monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    suite = make_suite(tmp_path)
    (suite / "train.jsonl").write_text(json.dumps({"id": "a", "prompt": "p",
                                                   "reference_text": "g"}) + "\n")
    proc = subprocess.run([sys.executable, str(HARNESS / "judge.py"), "--check",
                           "--suite", str(suite)], capture_output=True, text=True)
    assert proc.returncode in (0, 1), proc.stderr  # 1 only when deps are missing
    assert "dataset" in proc.stdout
    (suite / "judge.md").unlink()
    proc = subprocess.run([sys.executable, str(HARNESS / "judge.py"), "--check",
                           "--suite", str(suite)], capture_output=True, text=True)
    assert proc.returncode == 1
