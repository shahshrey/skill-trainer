#!/usr/bin/env python3
"""Evidence-coverage audit: can the train split teach what val is failing?

The loop's editors see TRAIN receipts only (val receipts would leak the
gate). When a val failure mode never occurs in train, hill-climbing is
evidence-starved: it burns steps proposing edits that cannot target the
real gap (run sql05: a stable plateau of val-only misses produced 3 noop
steps and 3 insignificant candidates in one epoch). This tool makes that
condition detectable instead of implicit.

Method (suite-agnostic, stdlib, deterministic):
- A rollout's failure signature = the frozenset of its NORMALIZED check
  strings minus the suite's benign set. Checks are normalized by
  collapsing digits ("row_f1_0.372" -> "row_f1_#", "command_exit:1" ->
  "command_exit:#") so magnitudes don't fragment classes. The benign set =
  every normalized check observed on any PASSING (hard==1) rollout across
  all provided batches.
- Signatures observed in failing val rollouts but never in failing train
  rollouts are `val_only` — the starvation signal.

LEAKAGE SAFETY: the report contains check-class names and counts ONLY —
never task ids, workspace names, prompts, or outputs. It is safe to place
in META.md / editor-visible context; the post-run leakage audit stays
clean by construction.

Usage:
  coverage.py --train A/scores.json [B/scores.json ...]
              --val   C/scores.json [D/scores.json ...]
              [--primary-suite query]
Exit 0 always; the finding is in the JSON (starved: true|false).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def normalize(check: str) -> str:
    return NUM_RE.sub("#", str(check))


def _entries(paths: list[str], primary: str | None) -> list[dict]:
    out = []
    for p in paths:
        tasks = json.loads(Path(p).read_text(encoding="utf-8"))["tasks"]
        for entry in tasks.values():
            if primary is None or str(entry.get("suite", "primary")) == primary:
                out.append(entry)
    return out


def report(train: list[dict], val: list[dict]) -> dict:
    benign: set[str] = set()
    for e in train + val:
        if e.get("hard") == 1:
            benign.update(normalize(c) for c in e.get("checks", []))

    def signatures(entries: list[dict]) -> dict[frozenset, int]:
        sigs: dict[frozenset, int] = {}
        for e in entries:
            if e.get("hard") == 1:
                continue
            sig = frozenset(normalize(c) for c in e.get("checks", [])) - benign
            if sig:
                sigs[sig] = sigs.get(sig, 0) + 1
        return sigs

    tr, va = signatures(train), signatures(val)
    val_only = {s: n for s, n in va.items()
                if not any(s <= t or t <= s for t in tr)}

    def render(sigs: dict[frozenset, int]) -> list[dict]:
        return sorted(({"checks": sorted(s), "rollouts": n}
                       for s, n in sigs.items()),
                      key=lambda d: (-d["rollouts"], d["checks"]))

    n_val_fail = sum(va.values())
    return {
        "train_rollouts": len(train), "val_rollouts": len(val),
        "train_failing": sum(tr.values()), "val_failing": n_val_fail,
        "val_only_signatures": render(val_only),
        "train_covered_signatures": render({s: n for s, n in va.items()
                                            if s not in val_only}),
        "starved": bool(val_only),
        "starved_fraction": round(sum(val_only.values()) / n_val_fail, 4)
        if n_val_fail else 0.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--train", nargs="+", required=True,
                    help="train-batch scores.json file(s)")
    ap.add_argument("--val", nargs="+", required=True,
                    help="val-batch scores.json file(s)")
    ap.add_argument("--primary-suite", default=None)
    args = ap.parse_args()
    print(json.dumps(report(_entries(args.train, args.primary_suite),
                            _entries(args.val, args.primary_suite)),
                     indent=2))


if __name__ == "__main__":
    main()
