"""Mock backend: success is a pure function of skill content; failures carry signal."""
import json
import subprocess
import sys
from pathlib import Path

from run_task import normalize, run_mock

HARNESS = Path(__file__).resolve().parent.parent / "harness"

TASK = {
    "id": "mock-001",
    "requires": ["always-cite-sources", "state-a-default-fps"],
    "failure_hints": {
        "always-cite-sources": "the response made factual claims with no citations",
        "state-a-default-fps": "the response listed fps options but never picked one",
    },
}


def test_solved_when_all_rules_present():
    skill = "Always cite sources. State a default fps of 12."
    out = run_mock(TASK, skill, seed=0)
    assert "RESULT: solved" in out
    assert "PASS:always-cite-sources" in out
    assert "SYMPTOM" not in out


def test_rule_matching_is_normalized():
    # "always-cite-sources" must match prose "Always cite sources" (case/punct-insensitive)
    assert normalize("always-cite-sources") in normalize("You should Always Cite Sources!")


def test_failure_emits_symptom_not_rule_text():
    skill = "Always cite sources."  # missing the fps rule
    out = run_mock(TASK, skill, seed=0)
    assert "RESULT: unsolved" in out
    assert "the response listed fps options but never picked one" in out
    assert "state-a-default-fps" not in out.split("RESULT")[0].replace(
        "PASS:always-cite-sources", "")  # missing rule id never leaks


def test_match_alternatives_satisfy_rule():
    task = dict(TASK, match={"state-a-default-fps": ["default fps", "fps defaults to"]})
    skill = "Always cite sources. The fps defaults to 12 unless told otherwise."
    out = run_mock(task, skill, seed=0)
    assert "RESULT: solved" in out


def test_noise_is_seeded_and_deterministic():
    task = dict(TASK, noise=0.5)
    skill = "Always cite sources. State a default fps of 12."
    runs_seed3 = {run_mock(task, skill, seed=3) for _ in range(5)}
    assert len(runs_seed3) == 1  # same seed -> identical output
    outcomes = {("solved" if "RESULT: solved" in run_mock(task, skill, seed=s) else "unsolved")
                for s in range(30)}
    assert outcomes == {"solved", "unsolved"}  # noise actually flips some rollouts


def test_null_task_is_independent_of_skill():
    task = {"id": "null-1", "requires": [], "noise": 0.5}
    for skill in ("skill A", "totally different skill B"):
        results = [("solved" if "RESULT: solved" in run_mock(task, skill, seed=s) else "unsolved")
                   for s in range(20)]
        assert "solved" in results and "unsolved" in results
    # identical across skills: outcome depends only on (id, seed)
    a = [run_mock(task, "skill A", seed=s) for s in range(20)]
    b = [run_mock(task, "skill B", seed=s) for s in range(20)]
    assert a == b


def test_cli_writes_workspace(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text("Always cite sources. State a default fps.", encoding="utf-8")
    workdir = tmp_path / "ws"
    proc = subprocess.run(
        [sys.executable, str(HARNESS / "run_task.py"),
         "--skill", str(skill), "--task-json", json.dumps(TASK),
         "--backend", "mock", "--workdir", str(workdir)],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert (workdir / "task.json").exists()
    assert "RESULT:" in (workdir / "output.txt").read_text(encoding="utf-8")
    result = json.loads(proc.stdout)
    assert result["task"] == "mock-001"


def test_stage_dir_seeds_workspace(tmp_path):
    """--stage copies staged files in; PROMPT_APPEND.txt stays prompt-only."""
    skill = tmp_path / "SKILL.md"
    skill.write_text("Always cite sources. State a default fps.", encoding="utf-8")
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "page.html").write_text("<html>prior attempt</html>")
    (stage / "FEEDBACK.md").write_text("# fix frame 3")
    (stage / "PROMPT_APPEND.txt").write_text("EDIT MODE: improve page.html")
    workdir = tmp_path / "ws"
    proc = subprocess.run(
        [sys.executable, str(HARNESS / "run_task.py"),
         "--skill", str(skill), "--task-json", json.dumps(TASK),
         "--backend", "mock", "--workdir", str(workdir),
         "--stage", str(stage)],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert (workdir / "page.html").read_text() == "<html>prior attempt</html>"
    assert (workdir / "FEEDBACK.md").exists()
    assert not (workdir / "PROMPT_APPEND.txt").exists()


def test_claude_backend_honors_skill_trainer_model_env(monkeypatch):
    from run_task import BACKENDS
    monkeypatch.delenv("SKILL_TRAINER_MODEL", raising=False)
    cmd = BACKENDS["claude"]("p", "s", [])
    assert "--model" not in cmd
    monkeypatch.setenv("SKILL_TRAINER_MODEL", "claude-fable-5")
    cmd = BACKENDS["claude"]("p", "s", ["--extra"])
    i = cmd.index("--model")
    assert cmd[i + 1] == "claude-fable-5" and cmd[-1] == "--extra"


def test_codex_backend_honors_model_and_effort_env(monkeypatch):
    from run_task import BACKENDS
    monkeypatch.delenv("SKILL_TRAINER_MODEL", raising=False)
    monkeypatch.delenv("SKILL_TRAINER_EFFORT", raising=False)
    cmd = BACKENDS["codex"]("p", "s", [])
    assert "-m" not in cmd and not any(a.startswith("model_reasoning_effort") for a in cmd)
    # --full-auto was removed in codex 0.149; workspace-write replaces it
    assert "--full-auto" not in cmd
    assert cmd[cmd.index("--sandbox") + 1] == "workspace-write"
    monkeypatch.setenv("SKILL_TRAINER_MODEL", "gpt-5.3")
    monkeypatch.setenv("SKILL_TRAINER_EFFORT", "high")
    cmd = BACKENDS["codex"]("p", "s", [])
    assert cmd[cmd.index("-m") + 1] == "gpt-5.3"
    assert cmd[cmd.index("-c") + 1] == "model_reasoning_effort=high"


def test_opencode_backend_honors_model_and_effort_env(monkeypatch):
    from run_task import BACKENDS
    monkeypatch.delenv("SKILL_TRAINER_MODEL", raising=False)
    monkeypatch.delenv("SKILL_TRAINER_EFFORT", raising=False)
    cmd = BACKENDS["opencode"]("p", "s", [])
    assert cmd[:3] == ["opencode", "run", "--auto"]
    assert "-m" not in cmd and "--variant" not in cmd
    monkeypatch.setenv("SKILL_TRAINER_MODEL", "anthropic/claude-sonnet-4-5")
    monkeypatch.setenv("SKILL_TRAINER_EFFORT", "high")
    cmd = BACKENDS["opencode"]("p", "s", [])
    assert cmd[cmd.index("-m") + 1] == "anthropic/claude-sonnet-4-5"
    assert cmd[cmd.index("--variant") + 1] == "high"


def test_cursor_backend_honors_model_env(monkeypatch):
    from run_task import BACKENDS
    monkeypatch.delenv("SKILL_TRAINER_MODEL", raising=False)
    cmd = BACKENDS["cursor"]("p", "s", [])
    assert "--model" not in cmd
    monkeypatch.setenv("SKILL_TRAINER_MODEL", "claude-sonnet-5-low")
    cmd = BACKENDS["cursor"]("p", "s", [])
    assert cmd[cmd.index("--model") + 1] == "claude-sonnet-5-low"


def test_smoke_tools_come_from_suite_config(tmp_path):
    # The harness hardcodes no tool checks; the suite's scoring.md
    # `smoke_tools` list owns them (generalization: a non-media suite
    # must not require ffmpeg).
    from run_task import suite_smoke_tools
    suite = tmp_path / "suite"
    suite.mkdir()
    assert suite_smoke_tools(suite) == []  # no scoring.md
    (suite / "scoring.md").write_text(
        '# Scoring\n\n```json\n'
        '{"default_mode": "checklist", "smoke_tools": ["ffmpeg", "sqlite3"]}\n'
        '```\n', encoding="utf-8")
    assert suite_smoke_tools(suite) == ["ffmpeg", "sqlite3"]
    (suite / "scoring.md").write_text("# Scoring\n\nno config block\n",
                                      encoding="utf-8")
    assert suite_smoke_tools(suite) == []


# ---------------------------------------------------------------------------
# Scoring audit: judge checks and weak-signal warnings (Task 6)
# ---------------------------------------------------------------------------

def _smoke(suite, backend=None):
    cmd = [sys.executable, str(HARNESS / "run_task.py"), "--smoke", "--suite", str(suite)]
    if backend:
        cmd += ["--backend", backend]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, json.loads(proc.stdout)


def _write_suite(tmp_path, config, tasks):
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "scoring.md").write_text(
        "# Scoring\n\n```json\n" + json.dumps(config) + "\n```\n", encoding="utf-8")
    (suite / "train.jsonl").write_text(
        "\n".join(json.dumps(t) for t in tasks) + "\n", encoding="utf-8")
    return suite


def test_smoke_judge_suite_checks_pass(tmp_path):
    suite = _write_suite(tmp_path, {"soft_source": "judge", "judge_backend": "mock"},
                         [{"id": "a", "prompt": "p",
                           "scoring": {"mode": "checklist", "required": ["x"],
                                       "judge": {"criteria": [{"id": "c", "desc": "d"}]}}}])
    code, report = _smoke(suite)
    names = [c["check"] for c in report["checks"]]
    assert "judge:prompt" in names and "judge:criteria:a" in names
    assert code == 0


def test_smoke_judged_task_missing_criteria_fails(tmp_path):
    suite = _write_suite(tmp_path, {"soft_source": "judge", "judge_backend": "mock"},
                         [{"id": "a", "prompt": "p", "scoring": {"mode": "checklist",
                                                                 "required": ["x"]}}])
    code, report = _smoke(suite)
    assert code == 1
    bad = [c for c in report["checks"] if c["check"] == "judge:criteria:a"]
    assert bad and bad[0]["ok"] is False


def test_smoke_warns_weak_signal_without_judge(tmp_path):
    suite = _write_suite(tmp_path, {"default_mode": "checklist"},
                         [{"id": "weak", "prompt": "p",
                           "scoring": {"mode": "checklist", "required": []}},
                          {"id": "fine", "prompt": "p",
                           "scoring": {"mode": "exact", "expected": "ok"}}])
    code, report = _smoke(suite)
    assert code == 0                       # warnings never fail smoke
    assert len(report["warnings"]) == 1
    assert "weak" in report["warnings"][0] and "judge" in report["warnings"][0]


def test_smoke_no_warnings_key_regression(tmp_path):
    suite = _write_suite(tmp_path, {"default_mode": "checklist"},
                         [{"id": "fine", "prompt": "p",
                           "scoring": {"mode": "exact", "expected": "ok"}}])
    _, report = _smoke(suite)
    assert report["warnings"] == []
