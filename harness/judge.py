#!/usr/bin/env python3
"""Judge rollout outputs with an LLM -> judge.json per workspace.

Usage:
  judge.py --suite tasks/X (--workdir DIR | --batch DIR)
           [--backend claude|codex|cursor|copilot|opencode|mock]
           [--samples N] [--jobs J] [--force] [--timeout 120]

Runs BETWEEN rollouts and scoring. For each workspace whose resolved
scoring declares soft_source "judge" (task-level, or the suite default in
tasks/X/scoring.md's fenced json), calls the judge backend N times with
prompts/judge.md, majority-votes binary per-criterion verdicts, and writes
judge.json. score.py then reads judge.json deterministically; this file is
the only harness code that makes LLM calls for scoring.

Opt-in only: workspaces with no judge declaration are skipped silently.
Verdicts cache by output sha256 (--force re-judges). The judge never sees
SKILL.md; agent output is passed as untrusted data. Judge model/effort come
from SKILL_TRAINER_JUDGE_MODEL / SKILL_TRAINER_JUDGE_EFFORT.

Mock backend (for testing the trainer itself): task["mock"]["judge_outputs"]
is a list of canned judge stdout strings; sample i uses judge_outputs[i % len].

Exit 0 on success (including nothing to judge), 2 on judging errors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from run_task import BACKENDS
from score import suite_config

PROMPT_TEMPLATE = Path(__file__).resolve().parent.parent / "prompts" / "judge.md"
FENCED_RE = re.compile(r"```(?:json)?\s*\n([\s\S]*?)\n```")
JUDGE_SYSTEM = ("You are a strict evaluation judge. Follow the instructions in "
                "the message exactly. Do not use tools or write files. "
                "Respond with only the required JSON.")


def resolve_judge(task: dict, config: dict) -> dict | None:
    """Task-level soft_source overrides the suite default; only 'judge'
    activates judging. Declared-but-malformed criteria are a config bug."""
    scoring = task.get("scoring") or {}
    source = scoring.get("soft_source", config.get("soft_source", "self"))
    if source != "judge":
        return None
    criteria = list((scoring.get("judge") or {}).get("criteria") or [])
    if not criteria or not all(c.get("id") and c.get("desc") for c in criteria):
        raise ValueError(
            f"task {task.get('id')!r}: soft_source 'judge' requires "
            "scoring.judge.criteria as [{id, desc}, ...]")
    return {"criteria": criteria,
            "samples": int(config.get("judge_samples", 3)),
            "backend": config.get("judge_backend")}


def parse_verdict(stdout: str, criteria_ids: list[str]) -> dict | None:
    """Last valid fenced JSON block wins (models often think aloud first);
    bare JSON output is accepted as a fallback. Every criterion must be
    present as a real bool; extra keys are ignored."""
    candidates = [*reversed(FENCED_RE.findall(stdout)), stdout.strip()]
    for raw in candidates:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        crit = data.get("criteria") if isinstance(data, dict) else None
        if isinstance(crit, dict) and all(isinstance(crit.get(c), bool) for c in criteria_ids):
            return {"criteria": {c: bool(crit[c]) for c in criteria_ids},
                    "notes": str(data.get("notes", ""))}
    return None


def majority(samples: list[dict], criteria_ids: list[str]) -> tuple[dict[str, int], float]:
    """Strict majority per criterion; a tie fails it (conservative: quality
    must be evident, and gate inflation is worse than deflation)."""
    n = len(samples)
    criteria = {c: int(sum(s["criteria"][c] for s in samples) * 2 > n)
                for c in criteria_ids}
    soft = round(sum(criteria.values()) / len(criteria_ids), 4)
    return criteria, soft


class JudgeError(Exception):
    """A judged workspace produced no usable verdict; crash, never 0.0."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mock_sample(task: dict, i: int) -> str:
    outputs = list((task.get("mock") or {}).get("judge_outputs") or [])
    if not outputs:
        raise JudgeError(f"task {task.get('id')!r}: mock judge backend needs "
                         "task['mock']['judge_outputs']")
    return outputs[i % len(outputs)]


def build_prompt(task: dict, criteria: list[dict], output: str) -> str:
    """str.replace, never .format: agent output and task prompts contain
    braces. AGENT_OUTPUT goes last so placeholder-looking text inside the
    output cannot be re-substituted."""
    template = PROMPT_TEMPLATE.read_text(encoding="utf-8")
    criteria_block = "\n".join(f"- {c['id']}: {c['desc']}" for c in criteria)
    return (template
            .replace("{TASK_PROMPT}", str(task.get("prompt", "")))
            .replace("{CRITERIA}", criteria_block)
            .replace("{AGENT_OUTPUT}", output))


def run_judge_backend(backend: str, prompt: str, timeout: int) -> str:
    """One judge CLI call in a throwaway scratch dir (the judge needs no
    files and must not touch the rollout workspace). The judge never sees
    SKILL.md: the skill_text slot carries only the judge system line.
    Timeout returns "" and counts as an unparseable sample upstream."""
    cmd = BACKENDS[backend](prompt, JUDGE_SYSTEM, [])
    with tempfile.TemporaryDirectory(prefix="judge_") as scratch:
        try:
            proc = subprocess.run(cmd, cwd=scratch, capture_output=True,
                                  text=True, stdin=subprocess.DEVNULL,
                                  timeout=timeout)
        except subprocess.TimeoutExpired:
            return ""
    return (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")


def collect_samples(task: dict, backend: str, n: int, prompt: str,
                    criteria_ids: list[str], timeout: int) -> tuple[list[dict], list[str]]:
    """N samples; an unparseable sample gets one retry, then a flag."""
    samples, flags = [], []
    for i in range(n):
        verdict = None
        for _attempt in range(2):
            if backend == "mock":
                stdout = _mock_sample(task, i)
            else:
                stdout = run_judge_backend(backend, prompt, timeout)  # Task 3
            verdict = parse_verdict(stdout, criteria_ids)
            if verdict is not None:
                break
        if verdict is None:
            flags.append(f"sample_{i}_unparseable")
        else:
            samples.append(verdict)
    return samples, flags


def judge_workspace(suite: Path, workdir: Path, backend: str | None,
                    samples: int | None, force: bool, timeout: int) -> dict:
    config = suite_config(suite)
    task = json.loads((workdir / "task.json").read_text(encoding="utf-8"))
    spec = resolve_judge(task, config)
    if spec is None:
        return {"status": "skipped"}
    output_path = workdir / "output.txt"
    output = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    if not output.strip():
        # score.py's output_empty early-return owns this case; a verdict
        # on nothing would only mask a rollout failure.
        return {"status": "empty"}
    sha = _sha256(output)
    judge_path = workdir / "judge.json"
    if judge_path.exists() and not force:
        try:
            if json.loads(judge_path.read_text(encoding="utf-8")).get("output_sha256") == sha:
                return {"status": "cached"}
        except json.JSONDecodeError:
            pass  # corrupt cache -> re-judge
    resolved_backend = backend or spec["backend"]
    if not resolved_backend:
        raise JudgeError(f"task {task.get('id')!r}: no judge backend "
                         "(pass --backend or set judge_backend in scoring.md)")
    n = samples or spec["samples"]
    criteria_ids = [c["id"] for c in spec["criteria"]]
    prompt = ("" if resolved_backend == "mock"
              else build_prompt(task, spec["criteria"], output))  # Task 3
    verdicts, flags = collect_samples(task, resolved_backend, n, prompt,
                                      criteria_ids, timeout)
    if not verdicts:
        raise JudgeError(f"task {task.get('id')!r}: all {n} judge samples unparseable")
    criteria, soft = majority(verdicts, criteria_ids)
    judge_path.write_text(json.dumps({
        "output_sha256": sha,
        "backend": resolved_backend,
        "model": os.environ.get("SKILL_TRAINER_MODEL"),
        "samples": verdicts,
        "criteria": criteria,
        "soft": soft,
        "flags": flags,
    }, indent=2), encoding="utf-8")
    return {"status": "judged", "soft": soft}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--suite", required=True, help="tasks/<skill-name> directory")
    ap.add_argument("--workdir", help="single task workspace to judge")
    ap.add_argument("--batch", help="directory of task workspaces")
    ap.add_argument("--backend", choices=["mock", *BACKENDS],
                    help="overrides scoring.md judge_backend")
    ap.add_argument("--samples", type=int, help="overrides scoring.md judge_samples")
    ap.add_argument("--jobs", type=int,
                    default=int(os.environ.get("SKILL_TRAINER_JUDGE_JOBS", "1")),
                    help="parallel judge workers (CLI calls are wall-clock bound)")
    ap.add_argument("--force", action="store_true", help="ignore cached judge.json")
    ap.add_argument("--timeout", type=int, default=120, help="per-sample timeout (s)")
    args = ap.parse_args()
    if bool(args.workdir) == bool(args.batch):
        ap.error("exactly one of --workdir / --batch is required")

    # Judge model/effort ride the same env vars BACKENDS reads, remapped
    # once at startup (judge.py makes only judge calls, so this is safe).
    # When the JUDGE var is set, copy it to the dst var so BACKENDS picks it
    # up.  When it is absent or empty, *remove* the dst var so BACKENDS emits
    # no --model/effort flags and the backend's default model judges instead
    # of silently inheriting the rollout model from train.sh.
    for src, dst in (("SKILL_TRAINER_JUDGE_MODEL", "SKILL_TRAINER_MODEL"),
                     ("SKILL_TRAINER_JUDGE_EFFORT", "SKILL_TRAINER_EFFORT")):
        if os.environ.get(src):
            os.environ[dst] = os.environ[src]
        else:
            os.environ.pop(dst, None)

    suite = Path(args.suite)
    workdirs = ([Path(args.workdir)] if args.workdir else
                sorted(d for d in Path(args.batch).iterdir()
                       if d.is_dir() and (d / "task.json").exists()))

    statuses: dict[str, str] = {}
    errors: dict[str, str] = {}

    def one(wd: Path) -> None:
        try:
            statuses[wd.name] = judge_workspace(
                suite, wd, args.backend, args.samples, args.force, args.timeout)["status"]
        except Exception as exc:  # noqa: BLE001; a judging bug must read as crash
            errors[wd.name] = f"{type(exc).__name__}: {exc}"

    if args.jobs > 1:
        with ThreadPoolExecutor(max_workers=args.jobs) as ex:
            list(ex.map(one, workdirs))
    else:
        for wd in workdirs:
            one(wd)

    summary = {k: sorted(n for n, s in statuses.items() if s == k)
               for k in ("judged", "cached", "skipped", "empty")}
    if errors:
        print(json.dumps({**summary, "errors": errors}), file=sys.stderr)
        sys.exit(2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
