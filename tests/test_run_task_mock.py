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


def test_smoke_tools_come_from_suite_config(tmp_path):
    # The harness hardcodes no tool checks — the suite's scoring.md
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
