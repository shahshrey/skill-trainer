#!/usr/bin/env python3
"""Score rollout outputs -> per-task {hard, soft} and batch aggregates.

Usage:
  score.py --suite tasks/X --workdir runs/tag/step_1/task_id [--mode cheap|full]
  score.py --suite tasks/X --batch runs/tag/step_1 [--mode cheap|full]

Each task workspace must contain task.json (written by run_task.py) and
output.txt. Batch mode scores every immediate subdirectory holding task.json.

Scoring mode comes from task["scoring"]["mode"], falling back to the suite
default declared in the first fenced ```json block of tasks/X/scoring.md:
  exact      task["scoring"]["expected"] regex searched in output; hard 0/1
  checklist  task["scoring"]["required"] substrings; soft = found/total,
             hard = all found
  command    task["scoring"]["command"] run with cwd=workdir and
             TASK_OUTPUT=<output.txt>; exit 0 -> hard 1
  rubric     tasks/X/rubric.py::score(task, workdir, mode) -> {hard, soft, checks}
             (suite-specific deps allowed there; this harness core is stdlib)

Judged suites (soft_source "judge" in the task or suite config): hard stays from the mode above; soft is read from judge.json written by judge.py. Scoring itself stays deterministic and makes no LLM calls.

Batch aggregates are reported overall and per task["suite"] value (e.g.
"clone" vs "workflow-A") so the manager can apply the two-suite gate rule.
mixed = (1-w)*hard + w*soft with w from suite config (default 0.5).

Deterministic; no LLM calls. Exit 0 on success, 2 on scoring errors.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

FENCED_JSON_RE = re.compile(r"```json\s*\n([\s\S]*?)\n```")


def suite_config(suite: Path) -> dict:
    scoring_md = suite / "scoring.md"
    if scoring_md.exists():
        m = FENCED_JSON_RE.search(scoring_md.read_text(encoding="utf-8"))
        if m:
            return json.loads(m.group(1))
    return {}


def load_rubric(suite: Path):
    rubric_path = suite / "rubric.py"
    if not rubric_path.exists():
        raise FileNotFoundError(f"scoring mode 'rubric' but {rubric_path} is missing")
    spec = importlib.util.spec_from_file_location("suite_rubric", rubric_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply_judge_soft(result: dict, workdir: Path, output: str) -> dict:
    """Overlay the judge's soft score onto a deterministically-scored
    result. Reads judge.json only — score.py itself never calls an LLM."""
    judge_path = workdir / "judge.json"
    if not judge_path.exists():
        raise FileNotFoundError(
            f"soft_source 'judge' but {judge_path} is missing; run judge.py first")
    judged = json.loads(judge_path.read_text(encoding="utf-8"))
    sha = hashlib.sha256(output.encode("utf-8")).hexdigest()
    if judged.get("output_sha256") != sha:
        raise ValueError(f"{judge_path} is stale (output.txt changed); re-run judge.py")
    return dict(result,
                soft=round(float(judged["soft"]), 4),
                soft_source="judge",
                checks=list(result["checks"]) + [
                    f"judge:{cid}:{int(v)}"
                    for cid, v in sorted(judged["criteria"].items())])


def _deterministic_score(task: dict, workdir: Path, mode: str, config: dict, rubric) -> dict:
    scoring = dict(task.get("scoring") or {})
    scoring.setdefault("mode", config.get("default_mode", "checklist"))
    output_path = workdir / "output.txt"
    output = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    smode = scoring["mode"]

    if not output.strip() and smode != "rubric":
        return {"hard": 0, "soft": 0.0, "checks": ["output_empty"], "mode": smode}

    if smode == "exact":
        ok = re.search(scoring["expected"], output) is not None
        return {"hard": int(ok), "soft": float(ok),
                "checks": ["expected_found" if ok else "expected_missing"], "mode": smode}

    if smode == "checklist":
        required = scoring.get("required") or []
        if not required:
            return {"hard": 0, "soft": 0.0, "checks": ["checklist_empty"], "mode": smode}
        found = [r for r in required if r in output]
        missing = [r for r in required if r not in found]
        return {"hard": int(not missing), "soft": round(len(found) / len(required), 4),
                "checks": [f"found:{r}" for r in found] + [f"missing:{r}" for r in missing],
                "mode": smode}

    if smode == "command":
        env = dict(os.environ, TASK_OUTPUT=str(output_path))
        # shell=True is safe here: the command comes from the human-curated
        # task suite (read-only during training), never from agent output.
        proc = subprocess.run(scoring["command"], shell=True, cwd=workdir, env=env,
                              capture_output=True, text=True, timeout=120)
        ok = proc.returncode == 0
        return {"hard": int(ok), "soft": float(ok),
                "checks": [f"command_exit:{proc.returncode}"], "mode": smode}

    if smode == "rubric":
        result = rubric.score(task, workdir, mode)
        return {"hard": int(result["hard"]), "soft": round(float(result["soft"]), 4),
                "checks": list(result.get("checks", [])), "mode": smode}

    raise ValueError(f"unknown scoring mode {smode!r}")


def score_task(task: dict, workdir: Path, mode: str, config: dict, rubric) -> dict:
    scoring = dict(task.get("scoring") or {})
    result = _deterministic_score(task, workdir, mode, config, rubric)
    if (scoring.get("soft_source", config.get("soft_source")) == "judge"
            and "output_empty" not in result["checks"]):
        output_path = workdir / "output.txt"
        output = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
        result = apply_judge_soft(result, workdir, output)
    return result


def aggregate(results: dict[str, dict], suites: dict[str, str], weight: float) -> dict:
    def agg(ids: list[str]) -> dict:
        hards = [results[i]["hard"] for i in ids]
        softs = [results[i]["soft"] for i in ids]
        hard = sum(hards) / len(hards)
        soft = sum(softs) / len(softs)
        return {"n": len(ids), "hard": round(hard, 4), "soft": round(soft, 4),
                "mixed": round((1 - weight) * hard + weight * soft, 4)}

    out = {"overall": agg(list(results))}
    by_suite: dict[str, list[str]] = {}
    for tid, suite_name in suites.items():
        by_suite.setdefault(suite_name, []).append(tid)
    if len(by_suite) > 1 or (by_suite and next(iter(by_suite)) != "primary"):
        out["by_suite"] = {name: agg(ids) for name, ids in sorted(by_suite.items())}
    return out


def _score_one(payload: tuple[str, str, str]) -> tuple[str, dict, str]:
    """Pool worker: score one workspace (rubric re-loaded per process;
    render-heavy rubrics dwarf the import cost)."""
    suite_s, wd_s, mode = payload
    suite, wd = Path(suite_s), Path(wd_s)
    config = suite_config(suite)
    task = json.loads((wd / "task.json").read_text(encoding="utf-8"))
    smode = (task.get("scoring") or {}).get(
        "mode", config.get("default_mode", "checklist"))
    rubric = load_rubric(suite) if smode == "rubric" else None
    result = dict(score_task(task, wd, mode, config, rubric),
                  task=str(task.get("id")),
                  suite=str(task.get("suite", "primary")))
    return wd.name, result, str(task.get("suite", "primary"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--suite", required=True, help="tasks/<skill-name> directory")
    ap.add_argument("--workdir", help="single task workspace to score")
    ap.add_argument("--batch", help="directory of task workspaces")
    ap.add_argument("--mode", choices=["cheap", "full"], default="cheap")
    ap.add_argument("--jobs", type=int,
                    default=int(os.environ.get("SKILL_TRAINER_SCORE_JOBS", "1")),
                    help="parallel scoring workers (render-heavy rubrics "
                         "are wall-clock bound; sequential scoring of a "
                         "large batch was the 2026-08-06 bottleneck)")
    args = ap.parse_args()
    if bool(args.workdir) == bool(args.batch):
        ap.error("exactly one of --workdir / --batch is required")

    suite = Path(args.suite)
    config = suite_config(suite)
    weight = float(config.get("mixed_weight", 0.5))

    workdirs = ([Path(args.workdir)] if args.workdir else
                sorted(d for d in Path(args.batch).iterdir()
                       if d.is_dir() and (d / "task.json").exists()))
    if not workdirs:
        print(json.dumps({"error": "no task workspaces found"}), file=sys.stderr)
        sys.exit(2)

    # Key by workspace name: K rollouts of one task are K separate
    # samples (the gate compares means over K x |val|), never collapsed.
    results: dict[str, dict] = {}
    suites: dict[str, str] = {}
    payloads = [(str(suite), str(wd), args.mode) for wd in workdirs]
    try:
        if args.jobs > 1:
            with ProcessPoolExecutor(max_workers=args.jobs) as ex:
                scored = list(ex.map(_score_one, payloads))
        else:
            scored = [_score_one(p) for p in payloads]
        for key, result, suite_name in scored:
            results[key] = result
            suites[key] = suite_name
    except Exception as exc:  # noqa: BLE001; a scoring bug must read as crash, not 0.0
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        sys.exit(2)

    report = {"mode": args.mode, "tasks": results,
              "aggregate": aggregate(results, suites, weight)}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
