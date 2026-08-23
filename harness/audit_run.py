#!/usr/bin/env python3
"""Post-run leakage and invariant audits. Run after every run.

Checks, in order:
  leakage     no val/test task id or prompt text appears in any filled
              editor/ranker/learning-rate prompt under runs/<tag>/
  monotone    within each mode, keep_best val_mixed rows never decrease,
              and the best tag (if present) sits on the last
              authoritative-mode keep_best commit
  protected   commits that touch PROTECTED blocks of the skill are epoch
              commits (subject contains 'epoch') or the initial import
  reproposal  no rejected edit rendering re-appears verbatim in a later
              discard row of the same epoch

Usage: audit_run.py --run runs/<tag> --suite tasks/<skill> --skill skills/<skill>/SKILL.md
                    [--results results.tsv] [--best-tag best/<skill>] [--authoritative-mode full]
Exit 0 all pass; 1 any audit failed (report on stdout). Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROTECTED_RE = re.compile(
    r"<!--\s*PROTECTED:([A-Z_]+):START\s*-->[\s\S]*?<!--\s*PROTECTED:\1:END\s*-->")


def load_tsv(path: Path) -> list[dict]:
    rows = []
    header: list[str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if header is None:
            header = parts
            continue
        rows.append(dict(zip(header, parts)))
    return rows


def audit_leakage(run_dir: Path, suite: Path) -> list[str]:
    failures = []
    held_out: list[tuple[str, str]] = []
    for split in ("val", "test"):
        f = suite / f"{split}.jsonl"
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            task = json.loads(line)
            held_out.append((str(task["id"]), split))
            prompt = task.get("prompt") or task.get("prompt_cheap") or ""
            snippet = " ".join(prompt.split())[:120]
            if len(snippet) > 40:
                held_out.append((snippet, f"{split}-prompt-text"))
    # Filled worker prompts are the surface the editor actually sees.
    prompt_files = [p for pattern in ("*editor*", "*ranker*", "*lr*", "*learning_rate*")
                    for p in run_dir.rglob(pattern) if p.is_file() and p.suffix in (".md", ".txt")]
    for pf in prompt_files:
        text = " ".join(pf.read_text(encoding="utf-8", errors="replace").split())
        for needle, kind in held_out:
            if needle in text:
                failures.append(f"leakage: {kind} {needle[:60]!r} found in {pf}")
    return failures


def audit_monotone(rows: list[dict], best_tag: str | None, authoritative: str,
                   repo: Path) -> list[str]:
    failures = []
    by_mode: dict[str, float] = {}
    last_auth_best: str | None = None
    for r in rows:
        if r["status"] == "keep_best":
            score = float(r["val_mixed"])
            prev = by_mode.get(r["mode"])
            if prev is not None and score < prev - 1e-9:
                failures.append(f"monotone: keep_best {r['mode']} decreased "
                                f"{prev} -> {score} at step {r['step']}")
            by_mode[r["mode"]] = score
            if r["mode"] == authoritative:
                last_auth_best = r["commit"]
        if r["status"] == "epoch" and best_tag:
            pass  # epoch rows never move the tag; verified via last_auth_best below
    if best_tag and last_auth_best:
        try:
            tag_sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short=7", best_tag],
                                     capture_output=True, text=True, check=True).stdout.strip()
            if tag_sha != last_auth_best:
                failures.append(f"monotone: {best_tag} at {tag_sha}, expected last "
                                f"authoritative keep_best commit {last_auth_best}")
        except subprocess.CalledProcessError:
            failures.append(f"monotone: best tag {best_tag} missing but keep_best rows exist")
    return failures


def audit_protected(skill_path: Path, repo: Path,
                    since: str | None = None) -> list[str]:
    failures = []
    rel = skill_path.resolve().relative_to(repo.resolve())
    log = subprocess.run(["git", "-C", str(repo), "log", "--format=%h%x09%s", "--", str(rel)],
                         capture_output=True, text=True).stdout.strip().splitlines()
    shas = [l.split("\t") for l in log if l]
    if since:  # audit only the run's own commits: the baseline and older are history
        for i, (sha, _) in enumerate(shas):
            ancestor = subprocess.run(
                ["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, since],
                capture_output=True)
            if ancestor.returncode == 0:  # sha is at or before the baseline
                shas = shas[:i + 1]  # keep one boundary entry; the loop exempts it
                break
    for i, (sha, subject) in enumerate(shas):
        if i == len(shas) - 1:
            continue  # initial import / run baseline may introduce the blocks
        parent = shas[i + 1][0]
        diff_texts = []
        for ref in (sha, parent):
            show = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{rel}"],
                                  capture_output=True, text=True)
            diff_texts.append("\n".join(m.group(0) for m in
                                        PROTECTED_RE.finditer(show.stdout)))
        if diff_texts[0] != diff_texts[1] and "epoch" not in subject.lower():
            failures.append(f"protected: non-epoch commit {sha} ({subject!r}) "
                            "modified a PROTECTED block")
    return failures


EDIT_OP_RE = re.compile(r'^[a-z_]+@"')  # replace@"…", insert_after@"…", …


def audit_reproposal(rows: list[dict]) -> list[str]:
    failures = []
    seen: dict[tuple[str, str], str] = {}
    for r in rows:
        if r["status"] != "discard":
            continue
        for edit in re.split(r"\s\|\s", r["description"]):
            edit = edit.strip()
            # Only edit-op fragments are fingerprints. Prose fragments (gate
            # reasons like "gate reject (paired +0.0190, …)") repeat across
            # steps whenever the numbers coincide; sql05 hit exactly that
            # false positive when two different edits drew identical deltas.
            if not EDIT_OP_RE.match(edit):
                continue
            key = (r["epoch"], edit)
            if key in seen:
                failures.append(f"reproposal: epoch {r['epoch']} step {r['step']} re-proposed "
                                f"rejected edit from step {seen[key]}: {edit[:80]!r}")
            seen[key] = r["step"]
    return failures


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--suite", required=True)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--results", default="results.tsv")
    ap.add_argument("--best-tag", default=None)
    ap.add_argument("--authoritative-mode", default="full")
    ap.add_argument("--since", default=None,
                    help="baseline commit; skill-file history at or before it is "
                         "not audited (default: the run's step-0 commit)")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parent.parent
    rows = load_tsv(Path(args.results)) if Path(args.results).exists() else []
    since = args.since or (rows[0]["commit"] if rows else None)
    failures = (audit_leakage(Path(args.run), Path(args.suite))
                + audit_monotone(rows, args.best_tag, args.authoritative_mode, repo)
                + audit_protected(Path(args.skill), repo, since)
                + audit_reproposal(rows))
    report = {"audits": ["leakage", "monotone", "protected", "reproposal"],
              "status": "pass" if not failures else "fail",
              "failures": failures}
    print(json.dumps(report, indent=2))
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
