"""Carry a failed attempt's partial work into the next attempt (PROGRAM §5).

Convention, not suite logic: workers leave their transcript in
output.txt and their analysis scratch as underscore-prefixed files in
the workdir. On archive, harvest() persists the transcript tail (the
worker's closing reasoning; root causes live there when a worker runs
out of budget mid-fix) and the small analysis artifacts. On staging,
stage() re-presents both to the next worker so it starts where the last
one stopped instead of re-deriving the same analysis.

Why this exists: a 2026-08-04 attempt timed out AFTER finding its root
cause, applying zero edits. Under the old flow that 30-minute run was a
total loss; with its conclusion and diff images staged forward, the
retry solved the task.
"""
from __future__ import annotations

import shutil
from pathlib import Path

TAIL_BYTES = 2000
ARTIFACT_GLOB = "_*"
MAX_FILES = 16
MAX_BYTES = 400_000


def harvest(workdir: Path, dest: Path) -> None:
    """Persist the attempt's conclusion + analysis artifacts into an
    archive entry directory."""
    out_txt = workdir / "output.txt"
    if out_txt.exists():
        tail = out_txt.read_bytes()[-TAIL_BYTES:].decode("utf-8", "replace")
        (dest / "conclusion.txt").write_text(tail, encoding="utf-8")
    arts = [p for p in sorted(workdir.glob(ARTIFACT_GLOB))
            if p.is_file() and p.stat().st_size <= MAX_BYTES][:MAX_FILES]
    if arts:
        (dest / "artifacts").mkdir(exist_ok=True)
        for p in arts:
            shutil.copy(p, dest / "artifacts" / p.name)


def stage(entry: Path, dest: Path) -> str:
    """Copy a harvested entry's artifacts into a staging dir and return
    its conclusion text ('' if none) for the suite's feedback rendering."""
    if (entry / "artifacts").is_dir():
        for art in sorted((entry / "artifacts").iterdir()):
            shutil.copy(art, dest / art.name)
    if (entry / "conclusion.txt").exists():
        return (entry / "conclusion.txt").read_text(encoding="utf-8")
    return ""
