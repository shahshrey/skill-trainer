"""Failure-shape diagnosis for per-unit scored attempts (PROGRAM §5).

Suite-agnostic: a "unit" is whatever the suite scores a sequence of:
animation frames, test cases, document pages. The 2026-08-04 production
sweep showed generic worst-unit lists plateau after a few edit rounds;
what unblocks a worker is knowing the SHAPE of the failure (is the whole
attempt uniformly off, or does it break only in specific spans?) and,
for image-like units, WHERE inside a unit the mismatch concentrates.
The harness classifies; each suite maps the classification to its own
domain guidance in its feedback rendering.
"""
from __future__ import annotations

from typing import Callable

import numpy as np


def failure_signature(scores: list[float], threshold: float) -> dict:
    """Classify how an attempt's per-unit scores fail against a threshold.

    Kinds:
    - pass: no unit below threshold.
    - uniform_shortfall: nearly all units fail by a similar margin; some
      global property of the attempt is wrong, not its dynamics.
    - clustered_shortfall: failures form contiguous spans covering a
      minority of units; the attempt is wrong in those spans only.
    - scattered: no clean pattern; per-unit data is the best guide.

    Returns {kind, fail_ranges: [[first, last], ...]} (inclusive ranges).
    """
    fails = [i for i, s in enumerate(scores) if s < threshold]
    if not fails:
        return {"kind": "pass", "fail_ranges": []}
    ranges, start, prev = [], fails[0], fails[0]
    for i in fails[1:]:
        if i != prev + 1:
            ranges.append([start, prev])
            start = i
        prev = i
    ranges.append([start, prev])
    frac = len(fails) / len(scores)
    spread = max(scores) - min(scores)
    if frac >= 0.9 and spread < 0.05:
        kind = "uniform_shortfall"
    elif frac <= 0.5:
        kind = "clustered_shortfall"
    else:
        kind = "scattered"
    return {"kind": kind, "fail_ranges": ranges}


def worst_blocks(cand: np.ndarray, ref: np.ndarray,
                 metric: Callable[[np.ndarray, np.ndarray], float],
                 block: int = 45, k: int = 8,
                 report_below: float = 0.9) -> list[dict]:
    """Localize WHERE two 2D arrays diverge: score aligned square blocks
    with the suite's own metric, return the worst k as canvas fractions
    (resolution-independent, so feedback can express them in the suite's
    native coordinates)."""
    h, w = ref.shape
    rows = []
    for y in range(0, h - block + 1, block):
        for x in range(0, w - block + 1, block):
            s = metric(cand[y:y + block, x:x + block],
                       ref[y:y + block, x:x + block])
            rows.append((s, x, y))
    rows.sort(key=lambda r: r[0])
    return [{"score": round(s, 3), "x_frac": round(x / w, 3),
             "y_frac": round(y / h, 3)}
            for s, x, y in rows[:k] if s < report_below]
