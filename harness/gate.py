#!/usr/bin/env python3
"""Pure gate math: accept / reject a candidate skill's validation scores.

Gate semantics (PROGRAM.md §4f); min-delta and two-suite rules
included. No side effects; the manager owns git.

Rules:
- Comparison metric is ``mixed = (1-w)*hard + w*soft`` (default w=0.5).
- Accept requires ``candidate > current + min_delta`` on the primary suite.
- Two-suite rule: additionally ``secondary >= current_secondary - min_delta``
  (the secondary suite is a regression constraint, never an averaged term).
- ``accept_new_best`` additionally requires ``candidate > best``. Whether a
  given evaluation is allowed to move the best tag (authoritative mode) is
  the caller's concern; pass ``best_eligible=False`` to cap at ``accept``.
- Scores from different modes are never compared; callers track
  current/best per mode and must not mix them.

CLI: gate.py --candidate 0.71 --current 0.65 --best 0.70 --min-delta 0.02
             [--cand-secondary 0.5 --current-secondary 0.55] [--no-best]
Prints a JSON decision. Exit 0 always (the decision is in the JSON).
"""
from __future__ import annotations

import argparse
import json


def mixed_score(hard: float, soft: float, soft_weight: float = 0.5) -> float:
    """Project (hard, soft) onto the single comparison metric."""
    w = max(0.0, min(1.0, float(soft_weight)))
    return (1.0 - w) * float(hard) + w * float(soft)


def decide(
    candidate: float,
    current: float,
    best: float,
    min_delta: float,
    *,
    cand_secondary: float | None = None,
    current_secondary: float | None = None,
    best_eligible: bool = True,
) -> dict:
    """Return the gate decision for one candidate evaluation.

    Returns a dict with:
      action: "accept_new_best" | "accept" | "reject"
      reason: one line explaining the decision
      new_current / new_best / new_current_secondary: values after the
        decision (unchanged on reject).
    """
    if (cand_secondary is None) != (current_secondary is None):
        raise ValueError("secondary scores must be provided for both candidate and current, or neither")

    if candidate <= current + min_delta:
        return _result(
            "reject",
            f"primary {candidate:.4f} <= current {current:.4f} + min_delta {min_delta:.4f}",
            current, best, current_secondary,
        )

    if cand_secondary is not None and cand_secondary < current_secondary - min_delta:
        return _result(
            "reject",
            f"secondary regression: {cand_secondary:.4f} < {current_secondary:.4f} - min_delta {min_delta:.4f}",
            current, best, current_secondary,
        )

    new_secondary = cand_secondary if cand_secondary is not None else None
    if best_eligible and candidate > best:
        return _result(
            "accept_new_best",
            f"primary {candidate:.4f} beats current {current:.4f} and best {best:.4f}",
            candidate, candidate, new_secondary,
        )
    return _result(
        "accept",
        f"primary {candidate:.4f} beats current {current:.4f} (best {best:.4f} unchanged)",
        candidate, best, new_secondary,
    )


def _result(action: str, reason: str, new_current: float, new_best: float,
            new_current_secondary: float | None) -> dict:
    out = {
        "action": action,
        "reason": reason,
        "new_current": round(new_current, 6),
        "new_best": round(new_best, 6),
    }
    if new_current_secondary is not None:
        out["new_current_secondary"] = round(new_current_secondary, 6)
    return out


def _mixed_of(entry: dict, weight: float) -> float:
    return mixed_score(entry["hard"], entry["soft"], weight)


def _mean_sd(xs: list[float]) -> tuple[float, float]:
    n = len(xs)
    mean = sum(xs) / n
    if n < 2:
        return mean, 0.0
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    return mean, var ** 0.5


def decide_paired(
    candidate_tasks: dict,
    reference_tasks_list: list[dict],
    *,
    current: float,
    best: float,
    primary_suite: str | None = None,
    secondary_suite: str | None = None,
    mixed_weight: float = 0.5,
    z: float = 1.645,
    min_pairs: int = 6,
    best_eligible: bool = True,
) -> dict:
    """Paired-seed gate: compare candidate vs reference on IDENTICAL
    (task, seed) rollouts, so shared task/seed difficulty cancels out.

    Motivation (runs m72h/m72hf/sql01): aggregate-vs-aggregate gating with a
    spread-derived min_delta cannot resolve real gains smaller than the
    batch noise. m72hf discarded a +0.07 candidate by 0.001 and sql01's
    noise spread (0.087) dwarfed its own bar (0.029). Pairing per rollout
    removes the between-rollout variance component that both sides share.

    candidate_tasks / reference_tasks_list: the "tasks" dict of scores.json
    (workspace-name keyed; entries carry hard, soft and optionally suite).
    Multiple reference batches (e.g. the 3 baseline passes) are averaged
    per workspace key before pairing.

    Accept requires, on the primary suite: n_pairs >= min_pairs AND
    mean(delta) > 0 AND mean(delta) >= z * se(delta)  (one-sided; se = 0
    when every delta is identical). Secondary suite (when present) must not
    show a *significant* regression: reject when mean < 0 and |mean| >=
    z * se. `current`/`best` are aggregate primary mixed scores kept for
    reporting and best-tag continuity.
    """
    refs: dict[str, list[float]] = {}
    for ref_tasks in reference_tasks_list:
        for key, entry in ref_tasks.items():
            refs.setdefault(key, []).append(_mixed_of(entry, mixed_weight))

    def suite_of(entry: dict) -> str:
        return str(entry.get("suite", "primary"))

    deltas: dict[str, list[float]] = {}
    cand_primary_mixed: list[float] = []
    unpaired = 0
    for key, entry in candidate_tasks.items():
        s = suite_of(entry)
        cmx = _mixed_of(entry, mixed_weight)
        if primary_suite is None or s == primary_suite:
            cand_primary_mixed.append(cmx)
        if key not in refs:
            unpaired += 1
            continue
        deltas.setdefault(s, []).append(cmx - sum(refs[key]) / len(refs[key]))

    primary_key = primary_suite if primary_suite is not None else \
        (next(iter(deltas)) if len(deltas) == 1 else "primary")
    primary = deltas.get(primary_key, [])
    stats: dict = {"n_pairs": len(primary), "unpaired": unpaired,
                   "references": len(reference_tasks_list)}
    cand_aggregate = (sum(cand_primary_mixed) / len(cand_primary_mixed)
                      if cand_primary_mixed else 0.0)
    stats["candidate_aggregate"] = round(cand_aggregate, 6)

    def rejected(reason: str) -> dict:
        return dict(_result("reject", reason, current, best, None), paired=stats)

    if len(primary) < min_pairs:
        return rejected(f"insufficient pairs: {len(primary)} < {min_pairs}")

    mean_d, sd_d = _mean_sd(primary)
    se_d = sd_d / (len(primary) ** 0.5)
    stats.update(mean_delta=round(mean_d, 6), se=round(se_d, 6),
                 z_stat=round(mean_d / se_d, 3) if se_d else None)

    if not (mean_d > 0 and mean_d >= z * se_d):
        return rejected(
            f"paired mean delta {mean_d:+.4f} not significant "
            f"(need > 0 and >= {z} * se {se_d:.4f})")

    if secondary_suite is not None and deltas.get(secondary_suite):
        mean_s, sd_s = _mean_sd(deltas[secondary_suite])
        se_s = sd_s / (len(deltas[secondary_suite]) ** 0.5)
        stats.update(secondary_mean_delta=round(mean_s, 6),
                     secondary_se=round(se_s, 6))
        if mean_s < 0 and -mean_s >= z * se_s:
            return rejected(
                f"secondary regression significant: mean delta {mean_s:+.4f} "
                f"(se {se_s:.4f})")

    reason = (f"paired mean delta {mean_d:+.4f} over {len(primary)} pairs "
              f"(se {se_d:.4f}) is significant")
    if best_eligible and cand_aggregate > best:
        return dict(_result("accept_new_best", reason + " and beats best",
                            cand_aggregate, cand_aggregate, None), paired=stats)
    return dict(_result("accept", reason, cand_aggregate, best, None),
                paired=stats)


def min_delta_from_baseline(baseline_scores: list[float], floor: float = 0.01) -> float:
    """min_delta = max(floor, spread of repeated baseline val passes)."""
    if not baseline_scores:
        raise ValueError("need at least one baseline score")
    spread = max(baseline_scores) - min(baseline_scores)
    return max(floor, spread)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--candidate", type=float)
    ap.add_argument("--current", type=float, required=True)
    ap.add_argument("--best", type=float, required=True)
    ap.add_argument("--min-delta", type=float)
    ap.add_argument("--cand-secondary", type=float, default=None)
    ap.add_argument("--current-secondary", type=float, default=None)
    ap.add_argument("--no-best", action="store_true",
                    help="evaluation is not in the run's authoritative mode; cap at 'accept'")
    ap.add_argument("--paired", action="store_true",
                    help="paired-seed gate over scores.json files (preferred)")
    ap.add_argument("--candidate-scores", nargs="+",
                    help="candidate scores.json file(s); several merge by "
                         "workspace key (seed-extension retest)")
    ap.add_argument("--reference-scores", nargs="+", default=[],
                    help="one or more reference scores.json (same task+seed grid)")
    ap.add_argument("--primary-suite", default=None)
    ap.add_argument("--secondary-suite", default=None)
    ap.add_argument("--mixed-weight", type=float, default=0.5)
    ap.add_argument("--z", type=float, default=1.645)
    ap.add_argument("--min-pairs", type=int, default=6)
    args = ap.parse_args()

    if args.paired:
        if not (args.candidate_scores and args.reference_scores):
            ap.error("--paired requires --candidate-scores and --reference-scores")
        from pathlib import Path
        # multiple candidate files merge by workspace key (near-miss retest:
        # the seed-extension batch unions with the original val batch)
        cand: dict = {}
        for path in args.candidate_scores:
            cand.update(json.loads(Path(path).read_text())["tasks"])
        refs = [json.loads(Path(p).read_text())["tasks"]
                for p in args.reference_scores]
        print(json.dumps(decide_paired(
            cand, refs, current=args.current, best=args.best,
            primary_suite=args.primary_suite,
            secondary_suite=args.secondary_suite,
            mixed_weight=args.mixed_weight, z=args.z,
            min_pairs=args.min_pairs, best_eligible=not args.no_best,
        ), indent=2))
        return

    if args.candidate is None or args.min_delta is None:
        ap.error("scalar mode requires --candidate and --min-delta")
    print(json.dumps(decide(
        args.candidate, args.current, args.best, args.min_delta,
        cand_secondary=args.cand_secondary,
        current_secondary=args.current_secondary,
        best_eligible=not args.no_best,
    ), indent=2))


if __name__ == "__main__":
    main()
