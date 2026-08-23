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


if __name__ == "__main__":
    raise SystemExit("CLI lands in a later commit")
