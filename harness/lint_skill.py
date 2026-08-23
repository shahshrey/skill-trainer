#!/usr/bin/env python3
"""Deterministic skill-quality gate.

Implements the machine-checkable subset of the skill-quality checklist
(the qualitative remainder is prompts/skill_reviewer.md's job). Pure
stdlib, no LLM calls.

Required checks (any failure -> exit 2, candidate blocked):
  frontmatter (package mode only): name [a-z0-9-] <=64 chars, no
    anthropic/claude; description non-empty <=1024 chars, third-person
    (no "I can"/"You can"), has a what-clause and a when/trigger clause
  body <=500 lines
  markdown-linked local file paths exist
  no Windows-style backslash paths
  growth guard: trainable body (protected blocks excluded) grew <=20%
    vs --prev-skill in one step; growth under --min-growth-chars (900)
    never fails, so small skills can still gain a single rule

Recommended checks (failures -> exit 1, logged but not blocking):
  no time-sensitive phrases ("before August 2025", explicit deadlines)
  no "X or Y or Z" option lists without a stated default
  linked references at most one directory level deep

Usage: lint_skill.py --skill SKILL.md [--deploy-mode package|prompt]
                     [--prev-skill OLD.md] [--max-growth 0.20]
Exit codes: 0 pass, 1 needs-work, 2 fail. JSON report on stdout.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROTECTED_RE = re.compile(
    r"<!--\s*PROTECTED:([A-Z_]+):START\s*-->[\s\S]*?<!--\s*PROTECTED:\1:END\s*-->"
)
CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#\s]+)\)")
WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z0-9_.-]+\\[A-Za-z0-9_.\\-]+\b")
TIME_SENSITIVE_RE = re.compile(
    r"\b(?:before|after|until|as of)\s+(?:January|February|March|April|May|June|July|"
    r"August|September|October|November|December)\s+20\d\d\b",
    re.IGNORECASE,
)
OPTION_LIST_RE = re.compile(r"\b\w[\w./-]*,?\s+or\s+\w[\w./-]*,?\s+or\s+\w[\w./-]*\b", re.IGNORECASE)
FIRST_SECOND_PERSON_RE = re.compile(r"\b(?:I can|I will|you can|you will)\b", re.IGNORECASE)
WHEN_CLAUSE_RE = re.compile(
    r"\b(?:use (?:when|this|it)|trigger|when (?:the user|you|asked|working)|use for)\b",
    re.IGNORECASE,
)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return ({name, description}, body). Minimal YAML: top-level scalar keys only."""
    m = re.match(r"\A---\n([\s\S]*?)\n---\n", text)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    key = None
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if km:
            key = km.group(1)
            val = km.group(2).strip()
            fm[key] = "" if val in (">-", ">", "|", "|-") else val
        elif key and (line.startswith("  ") or line.startswith("\t")):
            fm[key] = (fm[key] + " " + line.strip()).strip()
    return fm, text[m.end():]


def trainable_body(text: str) -> str:
    """Body minus frontmatter and protected blocks — the region editors own."""
    _, body = parse_frontmatter(text)
    return PROTECTED_RE.sub("", body)


def lint(skill_path: Path, deploy_mode: str = "package",
         prev_skill: Path | None = None, max_growth: float = 0.20,
         min_growth_chars: int = 900) -> dict:
    text = skill_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    prose = CODE_BLOCK_RE.sub("", body)  # anti-pattern greps skip code blocks
    required_failures: list[str] = []
    recommended_failures: list[str] = []

    # --- frontmatter (package mode) ---
    if deploy_mode == "package":
        name = fm.get("name", "")
        desc = fm.get("description", "")
        if not re.fullmatch(r"[a-z0-9-]{1,64}", name or ""):
            required_failures.append(f"frontmatter: name {name!r} must match [a-z0-9-], <=64 chars")
        if name and ("anthropic" in name or "claude" in name):
            required_failures.append("frontmatter: name must not contain 'anthropic' or 'claude'")
        if not desc:
            required_failures.append("frontmatter: description missing or empty")
        else:
            if len(desc) > 1024:
                required_failures.append(f"frontmatter: description {len(desc)} chars (>1024)")
            if FIRST_SECOND_PERSON_RE.search(desc):
                required_failures.append("frontmatter: description uses first/second person ('I can'/'You can')")
            if not WHEN_CLAUSE_RE.search(desc):
                required_failures.append("frontmatter: description lacks a when-to-use/trigger clause ('Use when ...')")
            if len(desc.split()) < 8:
                required_failures.append("frontmatter: description too short to state what the skill does")

    # --- body size ---
    body_lines = body.count("\n") + 1
    if body_lines > 500:
        required_failures.append(f"body: {body_lines} lines (>500)")

    # --- referenced paths exist, one level deep ---
    for ref in MD_LINK_RE.findall(body):
        if re.match(r"^[a-z]+://", ref) or ref.startswith("mailto:"):
            continue
        target = (skill_path.parent / ref).resolve()
        if not target.exists():
            required_failures.append(f"paths: linked file {ref!r} does not exist")
        elif len(Path(ref).parts) > 2:
            recommended_failures.append(f"paths: reference {ref!r} nested more than one level deep")

    # --- anti-pattern greps (prose only) ---
    for m in WINDOWS_PATH_RE.finditer(prose):
        required_failures.append(f"anti-pattern: Windows-style path {m.group(0)!r}")
    for m in TIME_SENSITIVE_RE.finditer(prose):
        recommended_failures.append(f"anti-pattern: time-sensitive phrase {m.group(0)!r}")
    for m in OPTION_LIST_RE.finditer(prose):
        window = prose[m.start(): m.end() + 120]
        if not re.search(r"\bdefault", window, re.IGNORECASE):
            recommended_failures.append(
                f"anti-pattern: option list {m.group(0)!r} without a stated default")

    # --- growth guard ---
    if prev_skill is not None:
        prev_len = len(trainable_body(prev_skill.read_text(encoding="utf-8")))
        new_len = len(trainable_body(text))
        if (prev_len > 0 and new_len > prev_len * (1.0 + max_growth)
                and new_len - prev_len > min_growth_chars):
            required_failures.append(
                f"growth: trainable body grew {new_len - prev_len} chars "
                f"({(new_len / prev_len - 1) * 100:.0f}% > {max_growth * 100:.0f}% cap)")

    status = "fail" if required_failures else ("needs_work" if recommended_failures else "pass")
    return {
        "status": status,
        "skill": str(skill_path),
        "body_lines": body_lines,
        "failed_required": required_failures,
        "failed_recommended": recommended_failures,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skill", required=True)
    ap.add_argument("--deploy-mode", choices=["package", "prompt"], default="package")
    ap.add_argument("--prev-skill", default=None,
                    help="pre-edit skill version for the growth guard")
    ap.add_argument("--max-growth", type=float, default=0.20)
    ap.add_argument("--min-growth-chars", type=int, default=900)
    # 400 -> 900 after run sql03: the 400-char floor lint-blocked
    # verified-correct convention edits of +417..+753 chars on a
    # small skill (3 of 8 steps lost to the cap, not to the gate).
    # Bloat over many steps is still bounded by the 20% relative cap.
    args = ap.parse_args()

    report = lint(
        Path(args.skill),
        deploy_mode=args.deploy_mode,
        prev_skill=Path(args.prev_skill) if args.prev_skill else None,
        max_growth=args.max_growth,
        min_growth_chars=args.min_growth_chars,
    )
    print(json.dumps(report, indent=2))
    sys.exit({"pass": 0, "needs_work": 1, "fail": 2}[report["status"]])


if __name__ == "__main__":
    main()
