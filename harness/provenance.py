"""Verdict provenance: version every stored verdict; re-judge on upgrade.

Lesson (2026-08-06): a human audit found 45 of 53 archived winners were
false positives under a strengthened rubric. A verdict is only as good as
the rubric that produced it, so a durable store must record WHICH rubric
version judged each artifact, and a rubric upgrade must invalidate (not
silently keep) every verdict issued before it.

Suite-agnostic: a verdict is any dict with a truthy/falsy "hard" field;
the version is an opaque string owned by the suite's rubric.

    meta = stamp({"hard": 1, ...}, "v5")      # judged now, by v5
    stale(meta, "v6")   -> True               # v6 shipped: re-judge
    demote(meta, ["live_anim_broken"])        # audit failed it: keep history
"""
from __future__ import annotations

VERSION_KEY = "rubric_version"


def stamp(meta: dict, version: str) -> dict:
    """Mark a verdict as issued by `version` (returns the same dict)."""
    meta[VERSION_KEY] = version
    return meta


def stale(meta: dict, current: str) -> bool:
    """True when the verdict predates `current` and must be re-judged.
    Un-versioned verdicts are always stale: provenance unknown."""
    return meta.get(VERSION_KEY) != current


def demote(meta: dict, reasons: list[str], version: str | None = None) -> dict:
    """Flip a positive verdict to failed, preserving what it used to say
    (`previous`) and why it fell (`demoted_by`). Idempotent on already-
    failed verdicts: only records `previous` once."""
    if meta.get("hard") and "previous" not in meta:
        meta["previous"] = {"hard": meta["hard"],
                            VERSION_KEY: meta.get(VERSION_KEY)}
    meta["hard"] = 0
    meta["demoted_by"] = list(reasons)
    if version is not None:
        stamp(meta, version)
    return meta
