#!/usr/bin/env python3
"""Run one task against a skill via an agent CLI (or the mock backend).

Usage:
  run_task.py --skill skills/X/SKILL.md --suite tasks/X --task <id> \
              --backend mock|claude|codex|cursor --workdir runs/tag/step_1/task_id \
              [--mode cheap|full] [--timeout 300] [--seed 0] [--agent-arg ...]
  run_task.py --smoke --suite tasks/X [--backend claude]

Behavior:
- Resolves the task by id from the suite's train/val/test .jsonl files
  (or takes it inline via --task-json).
- Creates the workdir, writes task.json there, copies any task "files"
  (e.g. reference GIFs) from the suite dir into it.
- Invokes the backend with the task prompt; the skill text is injected
  (claude: --append-system-prompt; codex/cursor: prepended to the prompt).
- Captures stdout+stderr to <workdir>/output.txt. Prints a result JSON.
- Times out: SIGTERM at --timeout, SIGKILL at 2x. Exit 124 on timeout.

Mock backend (for testing the trainer itself): a task carries
  requires:      ["<rule-id>", ...]  — solved iff every rule-id, normalized
                 (lowercase, punctuation -> space), appears in the skill text
  match:         {"<rule-id>": ["<alt phrase>", ...]} — optional alternative
                 phrasings that also satisfy the rule
  match_regex:   {"<rule-id>": ["<regex>", ...]} — optional concept groups:
                 the rule is also satisfied if any single skill LINE matches
                 ALL of the regexes (case-insensitive). Robust to phrasing,
                 so planted-defect recovery measures inference from
                 symptoms, not phrase luck; vague edits still fail.
  failure_hints: {"<rule-id>": "<symptom>"} — on failure, output contains the
                 symptom for each missing rule (never the rule text/id)
  noise:         0..1 — seeded per-(task,seed) probability of flubbing one
                 satisfied rule (or, with empty requires, of failing outright)

--smoke verifies: suite requirements.txt deps importable, every binary in
the suite's scoring.md `smoke_tools` list on PATH, chromium installed
(when playwright is a dep), backend CLI on PATH.
Stdlib-only; no network calls of its own.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Per-backend command builders. prompt is passed as a single argument; the
# defaults give the target agent non-interactive file/shell access, which
# agentic tasks (write HTML, run capture.py) require.
BACKENDS = {
    "claude": lambda prompt, skill_text, extra: (
        ["claude", "-p", prompt, "--append-system-prompt", skill_text,
         "--dangerously-skip-permissions",
         *(["--model", os.environ["SKILL_TRAINER_MODEL"]]
           if os.environ.get("SKILL_TRAINER_MODEL") else []), *extra]),
    "codex": lambda prompt, skill_text, extra: (
        ["codex", "exec", "--full-auto", *extra, "--",
         skill_text + "\n\n---\n\n" + prompt]),
    # Cursor agent CLI (headless). --trust skips the workspace-trust prompt,
    # --force auto-allows commands; both are required for unattended runs.
    # Model id bakes in reasoning effort (e.g. cursor-grok-4.5-high), so
    # SKILL_TRAINER_MODEL carries the full id and there is no effort flag.
    # The trailing "--" is load-bearing: injected skill text often starts
    # with "---" frontmatter, which the CLI otherwise parses as an option.
    "cursor": lambda prompt, skill_text, extra: (
        ["cursor-agent", "-p", "--force", "--trust",
         *(["--model", os.environ["SKILL_TRAINER_MODEL"]]
           if os.environ.get("SKILL_TRAINER_MODEL") else []),
         *extra, "--", skill_text + "\n\n---\n\n" + prompt]),
    # GitHub Copilot CLI (headless). No system-prompt flag, so the skill is
    # prepended like codex/cursor. Model/effort via env so batches stay
    # uniform: SKILL_TRAINER_MODEL (e.g. gpt-5.6-sol), SKILL_TRAINER_EFFORT.
    "copilot": lambda prompt, skill_text, extra: (
        ["copilot", "-p", skill_text + "\n\n---\n\n" + prompt,
         "--allow-all-tools", "--no-color",
         *(["--model", os.environ["SKILL_TRAINER_MODEL"]]
           if os.environ.get("SKILL_TRAINER_MODEL") else []),
         *(["--effort", os.environ["SKILL_TRAINER_EFFORT"]]
           if os.environ.get("SKILL_TRAINER_EFFORT") else []), *extra]),
}
BACKEND_BINARIES = {"claude": "claude", "codex": "codex", "cursor": "cursor-agent",
                    "copilot": "copilot"}

# pip requirement name -> import name, for --smoke
IMPORT_NAMES = {"pillow": "PIL", "playwright": "playwright", "numpy": "numpy", "pytest": "pytest"}


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def load_task(suite: Path, task_id: str) -> dict:
    for split in ("train", "val", "test"):
        path = suite / f"{split}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if str(item.get("id")) == task_id:
                item.setdefault("split", split)
                return item
    raise SystemExit(f"task {task_id!r} not found in {suite}/{{train,val,test}}.jsonl")


def run_mock(task: dict, skill_text: str, seed: int) -> str:
    requires = list(task.get("requires", []))
    hints = task.get("failure_hints", {}) or {}
    noise = float(task.get("noise", 0.0) or 0.0)
    rng = random.Random(f"{task.get('id')}:{seed}")
    norm_skill = normalize(skill_text)
    match = task.get("match", {}) or {}
    match_regex = task.get("match_regex", {}) or {}
    skill_lines = skill_text.splitlines()

    def satisfied_by_skill(rule: str) -> bool:
        phrases = [rule, *match.get(rule, [])]
        if any(normalize(p) in norm_skill for p in phrases):
            return True
        regexes = match_regex.get(rule, [])
        return bool(regexes) and any(
            all(re.search(rx, line, re.IGNORECASE) for rx in regexes)
            for line in skill_lines)

    satisfied = [r for r in requires if satisfied_by_skill(r)]
    missing = [r for r in requires if r not in satisfied]

    if noise > 0 and satisfied and rng.random() < noise:
        missing.append(satisfied.pop(rng.randrange(len(satisfied))))

    lines = [f"MOCK ROLLOUT task={task.get('id')} seed={seed}"]
    lines += [f"PASS:{r}" for r in satisfied]
    for r in missing:
        lines.append(f"SYMPTOM: {hints.get(r, 'the response failed one of the task requirements')}")

    if requires:
        solved = not missing
    else:
        # Pure-noise null-test task: outcome independent of skill.
        solved = not (noise > 0 and rng.random() < noise)
    lines.append(f"RESULT: {'solved' if solved else 'unsolved'}")
    return "\n".join(lines) + "\n"


def run_agent(backend: str, prompt: str, skill_text: str, extra: list[str],
              workdir: Path, timeout: int) -> tuple[int, float]:
    cmd = BACKENDS[backend](prompt, skill_text, extra)
    out_path = workdir / "output.txt"
    # The target agent's python3 must resolve to this venv (playwright,
    # Pillow, numpy — as the task prompts promise).
    env = dict(os.environ)
    env["PATH"] = f"{Path(sys.executable).parent}:{env.get('PATH', '')}"
    start = time.monotonic()
    with out_path.open("w", encoding="utf-8") as out:
        proc = subprocess.Popen(cmd, cwd=workdir, stdout=out, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, env=env)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=timeout)  # grace up to 2x total
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            code = 124
    return code, time.monotonic() - start


def suite_smoke_tools(suite: Path) -> list[str]:
    """Binaries the suite declares in scoring.md's fenced json config
    (`smoke_tools`). The suite owns its tooling needs — the harness
    hardcodes none (an unconditional ffmpeg check once blocked non-media
    suites on machines without it)."""
    scoring_md = suite / "scoring.md"
    if not scoring_md.exists():
        return []
    m = re.search(r"```json\s*\n([\s\S]*?)\n```", scoring_md.read_text(encoding="utf-8"))
    if not m:
        return []
    try:
        return list(json.loads(m.group(1)).get("smoke_tools", []))
    except (json.JSONDecodeError, AttributeError):
        return []


def smoke(suite: Path | None, backend: str | None) -> int:
    checks: list[tuple[str, bool, str]] = []
    have_playwright = False
    if suite is not None:
        req = suite / "requirements.txt"
        if req.exists():
            for line in req.read_text(encoding="utf-8").splitlines():
                name = re.split(r"[<>=!\[ ;#]", line.strip(), 1)[0].lower()
                if not name:
                    continue
                mod = IMPORT_NAMES.get(name, name.replace("-", "_"))
                try:
                    importlib.import_module(mod)
                    checks.append((f"dep:{name}", True, ""))
                    have_playwright = have_playwright or name == "playwright"
                except ImportError as exc:
                    checks.append((f"dep:{name}", False, str(exc)))
        for tool in suite_smoke_tools(suite):
            checks.append((f"tool:{tool}", shutil.which(tool) is not None, "not on PATH"))
    if have_playwright:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                ok = Path(p.chromium.executable_path).exists()
            checks.append(("chromium", ok, "run: playwright install chromium"))
        except Exception as exc:  # noqa: BLE001 — report any failure mode
            checks.append(("chromium", False, str(exc)))
    if backend and backend != "mock":
        binary = BACKEND_BINARIES[backend]
        checks.append((f"cli:{binary}", shutil.which(binary) is not None, "not on PATH"))

    ok = all(passed for _, passed, _ in checks)
    print(json.dumps({
        "smoke": "pass" if ok else "fail",
        "checks": [{"check": c, "ok": p, **({"detail": d} if not p else {})} for c, p, d in checks],
    }, indent=2))
    return 0 if ok else 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skill", help="path to the SKILL.md snapshot")
    ap.add_argument("--suite", help="tasks/<skill-name> directory")
    ap.add_argument("--task", help="task id (looked up in the suite jsonl files)")
    ap.add_argument("--task-json", help="inline task JSON (alternative to --task)")
    ap.add_argument("--backend", choices=["mock", *BACKENDS], default="mock")
    ap.add_argument("--workdir", help="workspace directory for this rollout")
    ap.add_argument("--mode", choices=["cheap", "full"], default="cheap")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--agent-arg", action="append", default=[],
                    help="extra CLI arg passed through to the agent (repeatable)")
    ap.add_argument("--stage", help="directory whose files are copied into the "
                    "workdir before the agent runs (edit-from-feedback mode); "
                    "its PROMPT_APPEND.txt, if present, is appended to the "
                    "prompt instead of copied")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    if args.smoke:
        sys.exit(smoke(Path(args.suite) if args.suite else None,
                       args.backend if args.backend != "mock" else None))

    if not (args.skill and args.workdir and (args.task or args.task_json)):
        ap.error("--skill, --workdir, and --task/--task-json are required (unless --smoke)")

    skill_path = Path(args.skill).resolve()
    skill_text = skill_path.read_text(encoding="utf-8")
    if args.task_json:
        task = json.loads(args.task_json)
    else:
        if not args.suite:
            ap.error("--suite is required with --task")
        task = load_task(Path(args.suite), args.task)

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "task.json").write_text(json.dumps(task, indent=2), encoding="utf-8")
    for rel in task.get("files", []):
        src = Path(args.suite) / rel if args.suite else Path(rel)
        dest = workdir / Path(rel).name
        if src.exists() and not dest.exists():
            shutil.copy(src, dest)

    prompt_append = ""
    if args.stage:
        # Staging lives here (not in the dispatcher) so a heartbeat requeue,
        # which wipes the workdir, re-stages automatically.
        for f in sorted(Path(args.stage).glob("*")):
            if f.name == "PROMPT_APPEND.txt":
                prompt_append = "\n\n" + f.read_text(encoding="utf-8").strip()
            elif f.is_file():
                shutil.copy(f, workdir / f.name)

    if args.backend == "mock":
        output = run_mock(task, skill_text, args.seed)
        (workdir / "output.txt").write_text(output, encoding="utf-8")
        code, duration = 0, 0.0
    else:
        prompt = task.get(f"prompt_{args.mode}") or task.get("prompt")
        if not prompt:
            raise SystemExit(f"task {task.get('id')!r} has no prompt/prompt_{args.mode} field")
        prompt = (f"{prompt}\n\nThe skill directory (with any supporting "
                  f"subdirectories it ships, e.g. scripts/, assets/, examples/, "
                  f"references/) is at: {skill_path.parent}\n"
                  f"Work inside the current directory.{prompt_append}")
        code, duration = run_agent(args.backend, prompt, skill_text,
                                   args.agent_arg, workdir, args.timeout)

    print(json.dumps({
        "task": task.get("id"), "backend": args.backend, "mode": args.mode,
        "seed": args.seed, "exit_code": code, "duration_s": round(duration, 1),
        "output": str(workdir / "output.txt"),
        "timed_out": code == 124,
    }))
    sys.exit(0 if code == 0 else (124 if code == 124 else 1))


if __name__ == "__main__":
    main()
