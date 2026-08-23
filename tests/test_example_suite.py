"""The bundled examples/mock-demo suite must keep working on a fresh
clone: meta_eval.py seeds its worktrees from it, and the README points at
it as the task-suite template. Deterministic, no LLM calls."""
import json
import re
from pathlib import Path

from lint_skill import lint
from run_task import normalize, run_mock
from score import score_task, suite_config

REPO = Path(__file__).resolve().parent.parent
EX = REPO / "examples" / "mock-demo"
SKILL = EX / "skills" / "mock-demo" / "SKILL.md"
DEMO = EX / "tasks" / "mock-demo"
NULL = EX / "tasks" / "mock-null"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def test_skill_contains_every_ablatable_rule_and_slow_update_block():
    from meta_eval import ABLATABLE, SLOW_RE
    text = SKILL.read_text()
    for rule, line in ABLATABLE.items():
        assert line in text, f"ABLATABLE line for {rule} missing from SKILL.md"
    assert SLOW_RE.search(text), "SKILL.md lacks the PROTECTED:SLOW_UPDATE block"


def test_skill_passes_lint_in_both_deploy_modes():
    for mode in ("prompt", "package"):
        report = lint(SKILL, deploy_mode=mode)
        assert report["status"] == "pass", (mode, report)


def test_demo_tasks_all_solve_against_reference_skill():
    skill_text = SKILL.read_text()
    for split in ("train", "val"):
        for task in load_jsonl(DEMO / f"{split}.jsonl"):
            out = run_mock(task, skill_text, seed=0)
            assert "RESULT: solved" in out, (task["id"], out)


def test_demo_tasks_fail_with_symptom_when_their_rule_is_ablated():
    from meta_eval import ABLATABLE
    for task in load_jsonl(DEMO / "val.jsonl"):
        rule = task["requires"][0]
        ablated = SKILL.read_text().replace(ABLATABLE[rule], "")
        out = run_mock(task, ablated, seed=0)
        assert "RESULT: unsolved" in out, (task["id"], out)
        assert "SYMPTOM:" in out
        # symptoms must describe the failure without leaking the rule
        assert normalize(rule) not in normalize(out.split("SYMPTOM:", 1)[1])


def test_regex_concept_groups_accept_rephrasings_not_vague_edits():
    # a rephrased seamless-loop rule must count; a vague line must not
    task = next(t for t in load_jsonl(DEMO / "val.jsonl")
                if t["requires"] == ["seamless-loop"])
    base = SKILL.read_text().replace(
        "- A seamless loop is mandatory: the first and last frames must match.\n", "")
    rephrased = base + "\n- End every loop on its opening frame so the first and last frames align.\n"
    assert "RESULT: solved" in run_mock(task, rephrased, seed=0)
    vague = base + "\n- Make the animation look polished.\n"
    assert "RESULT: unsolved" in run_mock(task, vague, seed=0)


def test_scoring_contract_scores_mock_output(tmp_path):
    config = suite_config(DEMO)
    assert config.get("default_mode") == "checklist"
    task = load_jsonl(DEMO / "val.jsonl")[0]
    (tmp_path / "output.txt").write_text(run_mock(task, SKILL.read_text(), seed=0))
    res = score_task(task, tmp_path, "cheap", config, rubric=None)
    assert res["hard"] == 1 and res["soft"] == 1.0


def test_null_suite_is_pure_noise():
    for split in ("train", "val"):
        rows = load_jsonl(NULL / f"{split}.jsonl")
        assert rows, f"mock-null {split}.jsonl is empty"
        for task in rows:
            assert task["requires"] == []
            assert task["noise"] > 0
    # outcome must be skill-independent: same seed, wildly different skills
    task = load_jsonl(NULL / "val.jsonl")[0]
    outs = {run_mock(task, skill, seed=7) for skill in ("", SKILL.read_text(), "x" * 5000)}
    assert len(outs) == 1


def test_ablation_regexes_are_valid_and_line_anchored():
    for task in load_jsonl(DEMO / "train.jsonl") + load_jsonl(DEMO / "val.jsonl"):
        for rule, regexes in task.get("match_regex", {}).items():
            assert regexes, (task["id"], rule)
            for rx in regexes:
                re.compile(rx)  # must not raise
