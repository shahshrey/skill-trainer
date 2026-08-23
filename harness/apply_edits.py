#!/usr/bin/env python3
"""Apply an editor's edit-ops JSON to a skill file, mechanically and safely.

Ops (the editor-prompt contract):
  {"edits": [
    {"op": "append",       "content": "..."},
    {"op": "insert_after", "target": "<exact existing text>", "content": "..."},
    {"op": "replace",      "target": "<exact existing text>", "content": "..."},
    {"op": "delete",       "target": "<exact existing text>"}
  ]}

Guarantees:
- All-or-nothing: if any op fails, the file is not touched.
- Targets must match exactly once inside the *trainable* region (outside
  ``<!-- PROTECTED:...:START/END -->`` blocks and outside frontmatter).
  Zero matches, ambiguous matches, or protected-region matches are errors.
- ``append`` inserts at the end of the trainable body, i.e. before the
  first protected marker (or EOF if none).

Usage: apply_edits.py --skill SKILL.md --edits edits.json [--dry-run]
Exit codes: 0 applied, 2 refused (nothing written; reasons on stderr as JSON).
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
FRONTMATTER_RE = re.compile(r"\A---\n[\s\S]*?\n---\n")


def protected_spans(text: str) -> list[tuple[int, int]]:
    """Spans (start, end) the editor may not touch: frontmatter + protected blocks."""
    spans = [(m.start(), m.end()) for m in PROTECTED_RE.finditer(text)]
    fm = FRONTMATTER_RE.match(text)
    if fm:
        spans.append((fm.start(), fm.end()))
    return sorted(spans)


def _in_protected(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(start < p_end and end > p_start for p_start, p_end in spans)


def _find_target(text: str, target: str, spans: list[tuple[int, int]]) -> tuple[int, int] | str:
    """Locate a unique, unprotected occurrence of target. Returns span or error string."""
    if not target:
        return "empty target"
    positions = []
    idx = text.find(target)
    while idx != -1:
        positions.append(idx)
        idx = text.find(target, idx + 1)
    if not positions:
        return "target not found"
    if len(positions) > 1:
        return f"target ambiguous ({len(positions)} occurrences)"
    start = positions[0]
    end = start + len(target)
    if _in_protected(spans, start, end):
        return "target lies in a protected region (frontmatter or PROTECTED block)"
    return (start, end)


def _append_point(text: str) -> int:
    """End of trainable body = just before the first protected marker, else EOF."""
    m = re.search(r"<!--\s*PROTECTED:[A-Z_]+:START\s*-->", text)
    return m.start() if m else len(text)


def apply_edits(text: str, edits: list[dict]) -> tuple[str, list[str]]:
    """Apply edits sequentially. Returns (new_text, errors). errors non-empty => text unchanged."""
    errors: list[str] = []
    work = text
    for i, edit in enumerate(edits):
        op = edit.get("op")
        spans = protected_spans(work)
        if op == "append":
            content = edit.get("content", "")
            if not content.strip():
                errors.append(f"edit {i}: append with empty content")
                break
            point = _append_point(work)
            insert = ("\n" if point and not work[:point].endswith("\n\n") else "") + content.rstrip("\n") + "\n"
            work = work[:point] + insert + work[point:]
        elif op in ("insert_after", "replace", "delete"):
            loc = _find_target(work, edit.get("target", ""), spans)
            if isinstance(loc, str):
                errors.append(f"edit {i} ({op}): {loc}")
                break
            start, end = loc
            if op == "insert_after":
                content = edit.get("content", "")
                if not content.strip():
                    errors.append(f"edit {i}: insert_after with empty content")
                    break
                work = work[:end] + "\n" + content.rstrip("\n") + work[end:]
            elif op == "replace":
                content = edit.get("content", "")
                if not content.strip():
                    errors.append(f"edit {i}: replace with empty content (use delete)")
                    break
                work = work[:start] + content + work[end:]
            else:  # delete
                work = work[:start] + work[end:]
        else:
            errors.append(f"edit {i}: unknown op {op!r}")
            break
    if errors:
        return text, errors
    return work, []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skill", required=True)
    ap.add_argument("--edits", required=True, help="path to edits JSON, or '-' for stdin")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.edits == "-" else Path(args.edits).read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
        edits = payload["edits"] if isinstance(payload, dict) else payload
        assert isinstance(edits, list)
    except (json.JSONDecodeError, KeyError, AssertionError) as exc:
        print(json.dumps({"applied": 0, "errors": [f"malformed edits JSON: {exc}"]}), file=sys.stderr)
        sys.exit(2)

    skill_path = Path(args.skill)
    text = skill_path.read_text(encoding="utf-8")
    new_text, errors = apply_edits(text, edits)
    if errors:
        print(json.dumps({"applied": 0, "errors": errors}), file=sys.stderr)
        sys.exit(2)
    if not args.dry_run:
        skill_path.write_text(new_text, encoding="utf-8")
    print(json.dumps({"applied": len(edits), "dry_run": args.dry_run}))


if __name__ == "__main__":
    main()
