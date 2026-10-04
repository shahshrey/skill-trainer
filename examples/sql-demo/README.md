# sql-demo: the tutorial's worked example

The suite that [docs/tutorial](../../docs/tutorial/README.md) builds up
chapter by chapter. It trains a **sql-queries** skill: the agent gets a
small SQLite shop database and a question, and has to answer with one
query whose rows match a reference query. Scoring is deterministic
(`rubric` mode, stdlib only): run both queries, diff the rows.

```
skills/sql-queries/SKILL.md   starting skill: two sentences, on purpose
tasks/sql-queries/
  build_db.py                 regenerates refs/shop.db and refs/schema.sql
  refs/shop.db                14 customers (2 test), 9 products, 63 orders
  train/val/test.jsonl        8 / 4 / 4 questions, each with a reference_sql
  rubric.py                   extract the SQL, run it read-only, diff rows
  scoring.md                  suite config + the house conventions
  failure_classes.md          symptom -> mechanism guide for the editor
```

## What the loop has to learn

The database has house conventions that no fresh agent knows, and the
starting skill states none of them. Training is the process of
discovering, from failed rollouts, which conventions need to be written
down. They live here and not in the suite directory so that nothing a
run reads can hand them to the editor.

- Revenue, spend and "sold" count orders in status `paid`, `shipped`
  or `delivered`. `placed`, `cancelled` and `refunded` never count.
- Test accounts (email ending in `@example.com`) are excluded from every
  report, including plain order counts.
- Product categories are stored in mixed case. Group and filter on
  `LOWER(category)`.
- Money is stored in cents. Report dollars: `ROUND(cents / 100.0, 2)`.
- "Each customer" means every row in `customers`, including the ones with
  no orders (LEFT JOIN, `COUNT(o.id)`).
- Dates are ISO text with a time. "March 2025" is
  `>= '2025-03-01' AND < '2025-04-01'`; an inclusive `<= '2025-03-31'`
  drops that day's orders.
- Rankings break ties by name ascending.
- The reply is one query in one fenced block. A second statement fails
  the run.

Each task ships probes: copies of its reference query with exactly one
convention removed. A rollout whose rows match a probe gets that probe's
symptom class in its checks, and `failure_classes.md` maps the class to
a mechanism without naming the fix.

## Run it

```bash
# every reference query scores 1.0 against itself, naive variants fail
.venv/bin/python -m pytest tests/test_sql_demo.py

# one real rollout + score (Claude Haiku, about 30 seconds)
SKILL_TRAINER_MODEL=claude-haiku-4-5-20251001 .venv/bin/python harness/run_task.py \
  --skill examples/sql-demo/skills/sql-queries/SKILL.md \
  --suite examples/sql-demo/tasks/sql-queries --task t01-total-revenue \
  --backend claude --workdir runs/try/t01_s0
.venv/bin/python harness/score.py --suite examples/sql-demo/tasks/sql-queries \
  --workdir runs/try/t01_s0
```

To train it, copy `tasks/` and `skills/` to the repo root (both are
gitignored there) and follow
[chapter 5 of the tutorial](../../docs/tutorial/05-launch-a-training-run.md).

## What a run looks like

The tutorial's bounded run (Claude Haiku 4.5 rollouts, K=2, four steps
plus one epoch boundary) took val mixed from 0.271 to 0.719 in one
accepted step and 0.813 on the epoch's full pass; two later steps were
rejected by the paired gate and one was a no-op. On the unseen test
split the trained skill scored 0.781 mixed (0.75 hard) against 0.316
(0.0 hard) for the starting skill. Run artifacts stay in your task
repo, not here (PROGRAM.md §8).
