# Scoring contract: sql-queries

Suite config (read by `harness/score.py` from the first fenced json block):

```json
{
  "default_mode": "rubric",
  "mixed_weight": 0.5,
  "smoke_tools": []
}
```

Every task copies `shop.db` and `schema.sql` into the rollout workspace
and asks for one SQLite query. The agent's reply is `output.txt`.

## How a rollout is scored

`rubric.py` extracts the last fenced block from the reply (or the whole
reply when there is no fence), runs it read-only against the suite's
`refs/shop.db` with a five-second limit, and runs the task's
`reference_sql` the same way. The workspace copy is only for the agent
to inspect; edits to it do not change the score.
Rows are compared as sets, numbers within a cent, column names ignored.
Tasks marked `"ordered": true` also compare row order.

- `hard` = 1 only when the row sets match (and the order, when it counts)
- `soft` = 0.3 for a query that runs + 0.2 for the right column count
  + 0.5 scaled by row overlap with the reference

`mixed = 0.5 * hard + 0.5 * soft` is the gate metric.

## What the editor sees

The checks list is the receipt. A wrong answer carries the row diff
(`rows:12!=9`, up to two `missing_row:` / `extra_row:` samples) and a
symptom class. Each task ships probes: copies of the reference query with
exactly one house convention removed. When the agent's rows match a
probe's rows, the checks say `symptom:<class>`, and `failure_classes.md`
maps the class to the mechanism to look at. A wrong answer that matches
no probe is `symptom:unclassified`.

## Where the answers are not

The reference queries encode house conventions on purpose, and the
starting skill states none of them. They are documented in the example's
README, outside this directory, so that nothing a training run reads
(this file, `failure_classes.md`, the receipts) hands them to the editor.
The loop has to find them from symptoms.

## Provenance

`rubric_version` hashes `scoring.md` and `rubric.py`. Editing either
invalidates every prior score: re-baseline, never compare across versions.
`build_db.py` regenerates `refs/shop.db` deterministically; changing the
data changes every reference answer, so treat it like a rubric edit.
