#!/usr/bin/env python3
"""Mine agent session transcripts for recurring task candidates (plan §10).

Usage:
  harvest.py --source claude|codex|cursor|all --out candidates.jsonl \
             [--project <abs path substring>] [--min-occurrences 2] [--root ~]

Reads (read-only, no network):
  claude  <root>/.claude/projects/*/*.jsonl
  codex   <root>/.codex/sessions/**/*.jsonl
  cursor  <root>/.cursor/projects/*/agent-transcripts/*.jsonl

Groups near-duplicate user requests (token-set Jaccard >= 0.55 after
stopword removal) and emits one candidate per group that recurs in >= 2
distinct sessions (Loopy's recurrence rule; --min-occurrences raises it).
Each candidate carries the representative prompt, occurrence counts, an
observed-outcome guess (the next user message in-session matched against
positive/negative feedback phrases), and file#line source refs. A human
curates candidates into train/val — this tool never writes task files.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STOPWORDS = frozenset(
    "a an and are as at be but by can could do does for from has have how i if in is it its "
    "me my of on or our please should so that the then this to us we what when will with would "
    "you your".split())
POSITIVE = ("thanks", "thank you", "perfect", "great", "works now", "fixed",
            "that works", "lgtm", "looks good", "nice", "awesome")
NEGATIVE = ("still broken", "still not", "doesn't work", "does not work", "not working",
            "wrong", "nope", "fix it", "broken", "still failing", "not fixed", "revert")
META_PREFIXES = ("<", "/", "caveat:", "[request interrupted", "[system", "stop hook")
# harness-injected records carry type:"user" but are not human asks
INJECTED = ("hook feedback:", "system notification", "task-notification",
            "automated background-task event", "this is an automated")
SECRET_RE = re.compile(r"sk-[a-zA-Z0-9]{16,}|api[_-]?key\s*[:=]|BEGIN [A-Z]+ PRIVATE KEY")


def tokens(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", text.lower())) - STOPWORDS


def jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if a or b else 0.0


def flat_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(b.get("text")) for b in content
                         if isinstance(b, dict) and b.get("type") == "text" and b.get("text"))
    return ""


def usable(text: str) -> bool:
    stripped = text.strip().lower()
    if not stripped or stripped.startswith(META_PREFIXES) or "<system-reminder>" in stripped:
        return False
    if any(marker in stripped for marker in INJECTED):
        return False
    if SECRET_RE.search(text):
        return False
    return 6 <= len(tokens(text)) <= 400


def iter_jsonl(path: Path):
    try:
        for n, line in enumerate(path.read_text(encoding="utf-8",
                                                errors="replace").splitlines(), 1):
            if line.strip():
                try:
                    yield n, json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def user_text(rec: dict) -> str:
    """Best-effort user-message text across the three transcript schemas."""
    if rec.get("type") == "user":  # claude code
        msg = rec.get("message") or {}
        return flat_text(msg.get("content")) if msg.get("role") == "user" else ""
    payload = rec.get("payload") if isinstance(rec.get("payload"), dict) else rec
    if payload.get("role") == "user" or payload.get("type") == "user_message":
        return flat_text(payload.get("content") or payload.get("message") or "")
    return ""


def session_files(root: Path, source: str):
    if source in ("claude", "all"):
        yield from sorted((root / ".claude" / "projects").glob("*/*.jsonl"))
    if source in ("codex", "all"):
        yield from sorted((root / ".codex" / "sessions").rglob("*.jsonl"))
    if source in ("cursor", "all"):
        yield from sorted((root / ".cursor" / "projects").glob(
            "*/agent-transcripts/*.jsonl"))


def project_match(rec: dict, path: Path, project: str | None) -> bool:
    if not project:
        return True
    cwd = rec.get("cwd") or rec.get("project") or ""
    return project in str(cwd) or project.replace("/", "-") in str(path)


def collect(root: Path, source: str, project: str | None) -> list[dict]:
    prompts = []
    for path in session_files(root, source):
        session_prompts = []
        for lineno, rec in iter_jsonl(path):
            text = user_text(rec)
            if not text or not project_match(rec, path, project):
                continue
            session_prompts.append({"text": text.strip(), "ref": f"{path}#{lineno}",
                                    "session": str(path), "feedback": None})
        # observed outcome: the NEXT user message often verdicts the previous ask
        for cur, nxt in zip(session_prompts, session_prompts[1:]):
            low = nxt["text"].lower()
            if any(p in low for p in NEGATIVE):
                cur["feedback"] = "negative"
            elif any(p in low for p in POSITIVE):
                cur["feedback"] = "positive"
        prompts += [p for p in session_prompts if usable(p["text"])]
    return prompts


def cluster(prompts: list[dict], threshold: float = 0.55) -> list[list[dict]]:
    clusters: list[tuple[frozenset, list[dict]]] = []
    for p in prompts:
        toks = tokens(p["text"])
        for ctoks, members in clusters:
            if jaccard(toks, ctoks) >= threshold:
                members.append(p)
                break
        else:
            clusters.append((toks, [p]))
    return [members for _, members in clusters]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", choices=["claude", "codex", "cursor", "all"], default="all")
    ap.add_argument("--project", help="substring of the project path to filter on")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-occurrences", type=int, default=2)
    ap.add_argument("--root", default=str(Path.home()),
                    help="transcript tree root (default: home; tests override)")
    args = ap.parse_args()

    prompts = collect(Path(args.root).expanduser(), args.source, args.project)
    candidates = []
    for members in cluster(prompts):
        sessions = {m["session"] for m in members}
        if len(members) < args.min_occurrences or len(sessions) < 2:
            continue
        rep = max(members, key=lambda m: len(m["text"]))
        feedback = [m["feedback"] for m in members if m["feedback"]]
        candidates.append({
            "prompt": rep["text"],
            "occurrences": len(members),
            "sessions": len(sessions),
            "observed_good": (feedback.count("positive") > feedback.count("negative")
                              if feedback else None),
            "sources": sorted(m["ref"] for m in members),
        })
    candidates.sort(key=lambda c: (-c["occurrences"], c["prompt"]))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(c) + "\n" for c in candidates), encoding="utf-8")
    print(json.dumps({"scanned_prompts": len(prompts), "candidates": len(candidates),
                      "out": str(out)}))
    sys.exit(0)


if __name__ == "__main__":
    main()
