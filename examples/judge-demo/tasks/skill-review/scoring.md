# Scoring contract: skill-review (LLM judge, dataset mode)

Suite config (read by `harness/score.py` from the first fenced json block):

```json
{
  "default_mode": "judge",
  "mixed_weight": 0.5,
  "smoke_tools": [],
  "judge": {
    "model": "MiniMax-M3",
    "samples": 3,
    "temperature": 0,
    "criteria_weights": {
      "defect_recall": 0.5,
      "precision": 0.2,
      "actionability": 0.2,
      "format": 0.1
    }
  }
}
```

Every task hands the agent a synthetic skill package under `refs/<id>/`
with 3 or 4 defects planted from a fixed catalogue (see
`refs/<id>/defects.json`) and asks for a review. The rollout's final
message is the review; it lands in `output.txt`.

## How a rollout is scored

`harness/judge.py` sends the review to the judge model with the prompt in
`judge.md`, the task's `reference` (the gold review `refs/<id>/gold.md`),
and the reviewed `SKILL.md` (`judge_inputs`). The judge returns a
structured verdict: one score per criterion, an overall, a pass flag, and
reasoning. Three samples are drawn at temperature 0 and combined:

- `soft` = mean over samples of the weighted criterion score
  (`criteria_weights` above; the model's own `overall` is ignored so the
  aggregation is fixed by the suite, not by the judge's arithmetic)
- `hard` = 1 when a majority of samples say `passed` (recall >= 0.75 and
  precision >= 0.5), else 0

`mixed = 0.5 * hard + 0.5 * soft` is the gate metric, as for every suite.

## Dataset mode vs rubric mode

Every task in this suite carries a `reference`, so the loop climbs toward
a dataset of gold reviews: the target is concrete and the judge's job is
comparison, not taste. Run `harness/judge.py --check --suite <this dir>`
to see the per-split mode report; it warns when any task falls back to
rubric-only judging, which depends entirely on how well `judge.md`
describes the ideal.

## Provenance

`rubric_version` hashes `scoring.md` and `judge.md`. Editing either
(criteria, weights, samples, model) invalidates every prior verdict:
re-baseline, never compare across versions. Verdicts are cached per
workspace in `judge.json`; rescoring an unchanged batch is free.

`noise`: the judge is an LLM, so repeated verdicts on the same output can
differ even at temperature 0. The 3-sample average and the paired gate's
z-test absorb that; do not lower the sample count below 3 for real runs.
