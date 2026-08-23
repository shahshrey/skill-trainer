"""Attempt-escalation policy for iterate-until-solved drivers (PROGRAM §5).

Suite-agnostic on purpose: the inputs are facts any driver can observe
(consecutive no-progress rounds, whether the last attempt hit its time
budget) and the outputs are dispatch knobs every suite has (time budget,
whether to stage from the best prior attempt or author from scratch).
Nothing here knows how a suite scores or diagnoses.

Lessons encoded (2026-08-04 GIF production sweep):
- Re-dispatching an identical configuration after a no-progress round is
  waste; two refs burned rounds 5-6 producing byte-identical attempts.
- A timeout with no edits applied usually means the analysis budget ate
  the fix budget; the retry needs more time, not a different strategy.
- After repeated stalls, edit-from-feedback staging holds the worker in
  the same local optimum; a scratch attempt re-rolls the approach.
"""
from __future__ import annotations


def next_plan(stalls: int, timed_out: bool, base_timeout: int) -> dict:
    """Dispatch plan for an unsolved item's next attempt.

    stalls: consecutive prior rounds that archived nothing new for this
    item (0 = last round made progress). timed_out: the item's last
    attempt ran out its time budget. Returns {timeout, stage}.
    """
    plan = {"timeout": base_timeout, "stage": True}
    if timed_out or stalls >= 1:
        plan["timeout"] = base_timeout * 2
    if stalls >= 2 and stalls % 2 == 0:
        plan["stage"] = False   # break the local optimum: author from scratch
    return plan


def update_stalls(stalls: dict[str, int], progressed: dict[str, bool]) -> None:
    """Fold one round's outcome into the per-item stall counters."""
    for item, ok in progressed.items():
        stalls[item] = 0 if ok else stalls.get(item, 0) + 1
