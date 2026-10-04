# 4. Build your own suite

This chapter builds a suite from nothing and ends with a baseline score.
The finished suite ships as `examples/sql-demo`, so you can copy it and
skip ahead, but the point is to see the decisions being made. Two of
them went wrong the first time, and those are in here too.

## Pick a skill you can score

The skill is **sql-queries**: given a small SQLite shop database and a
question, answer with one query. It is a good first suite for one
reason. Correctness is a row diff. Run the agent's query, run a
reference query, compare the rows. No opinions involved.

Your own first suite should have that property. If you cannot say what
a correct answer contains without reading it, start somewhere else and
come back to it with chapter 6.

## The database

`build_db.py` writes `refs/shop.db` and `refs/schema.sql` from a fixed
seed. Every reference answer depends on the data, so the data has to be
identical on every machine. Never hand-edit a fixture; edit the
generator and rerun it.

```sql
CREATE TABLE customers (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  email      TEXT NOT NULL,
  country    TEXT NOT NULL,
  signed_up  TEXT NOT NULL          -- ISO date, YYYY-MM-DD
);

CREATE TABLE products (
  id               INTEGER PRIMARY KEY,
  name             TEXT NOT NULL,
  category         TEXT NOT NULL,
  unit_price_cents INTEGER NOT NULL
);

CREATE TABLE orders (
  id           INTEGER PRIMARY KEY,
  customer_id  INTEGER NOT NULL REFERENCES customers(id),
  placed_at    TEXT NOT NULL,        -- ISO timestamp, YYYY-MM-DD HH:MM:SS
  status       TEXT NOT NULL         -- placed | paid | shipped | delivered | cancelled | refunded
);

CREATE TABLE order_items (
  order_id    INTEGER NOT NULL REFERENCES orders(id),
  product_id  INTEGER NOT NULL REFERENCES products(id),
  quantity    INTEGER NOT NULL,
  PRIMARY KEY (order_id, product_id)
);
```

Fourteen customers, nine products, sixty-three orders. The data carries
house conventions on purpose: two customers are test accounts with
real-looking orders, categories are stored as both `Office` and
`office`, three customers never ordered, and only some order statuses
count as revenue. A query that ignores any of these gets different rows.

The conventions are what the skill has to learn. They are listed in
`examples/sql-demo/README.md`, and deliberately nowhere inside the
suite directory. More on that below.

## The starting skill

```markdown
---
name: sql-queries
description: Writes SQLite queries against the shop.db analytics database. Use when asked for a number, a list, or a ranking from the shop database.
---

# sql-queries

Read `schema.sql`, write one SQLite query that answers the question, and
reply with the query.

<!-- PROTECTED:SLOW_UPDATE:START -->
## Conventions (slow update)

Structural conventions live in this block. The slow-update pass owns it;
per-step editors must not modify anything between the protected markers.
<!-- PROTECTED:SLOW_UPDATE:END -->
```

Two sentences, on purpose. A starting skill that already says everything
leaves nothing to measure. If you are training a skill you already use,
start from that; a weak start is for demonstrations.

Lint it before anything else:

```bash
.venv/bin/python harness/lint_skill.py --skill examples/sql-demo/skills/sql-queries/SKILL.md
```

```json
{"status": "pass", "body_lines": 13, "failed_required": [], "failed_recommended": []}
```

The lint gate runs on every candidate during training. A starting skill
that fails it would make every step fail for the same reason.

## Tasks

Sixteen questions, split 8 train, 4 val, 4 test. One line each:

```json
{"id": "t01-total-revenue",
 "prompt": "Write one SQLite query that returns the store's total revenue in dollars, as a single number. The SQLite database `shop.db` is in the current directory and its schema is in `schema.sql`. Reply with the query only.",
 "files": ["refs/shop.db", "refs/schema.sql"],
 "scoring": {"reference_sql": "SELECT ROUND(SUM(oi.quantity * p.unit_price_cents) / 100.0, 2) FROM orders o JOIN customers c ON c.id = o.customer_id JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id WHERE o.status IN ('paid', 'shipped', 'delivered') AND c.email NOT LIKE '%@example.com'",
             "probes": {"...": "..."}}}
```

`files` are copied into the workspace before the agent runs, so the
prompt can say "in the current directory" and mean it. `reference_sql`
is the suite's own field; the harness does not know it exists, only
`rubric.py` reads it. Probes are explained below.

The prompts are phrased the way a colleague would ask. "Total revenue in
dollars." Not "total revenue over orders in status paid, shipped or
delivered, excluding test accounts, in dollars rounded to cents." The
second phrasing would test whether the model can follow instructions.
The first tests whether the skill supplies the instructions, which is
the thing being trained.

Split rules. Val tasks must exercise the same conventions as train tasks
in different questions, or the gate measures nothing the editor could
have learned. Val must not be a paraphrase of train, or the gate
measures memorization. Test is for a final number the run never sees,
which makes it the only number you can quote without a caveat.

One mechanical rule too: the question goes first in the prompt, the
boilerplate after. The post-run leakage audit greps every editor prompt
for the first 120 characters of each val and test prompt. If all your
prompts open with the same paragraph about where the database is, every
train receipt looks like a val leak. The first run of this suite had
the boilerplate first and failed its audit for exactly that reason;
chapter 5 shows what that looks like.

## The rubric

`rubric.py` exposes one function, `score(task, workdir, mode)`, and
returns `{hard, soft, checks}`. Stripped to its shape:

```python
def score(task, workdir, mode="cheap"):
    output = (workdir / "output.txt").read_text()
    sql = extract_sql(output)            # last fenced block, else the whole reply
    if not sql:
        return {"hard": 0, "soft": 0.0, "checks": ["no_sql"]}

    want = run_query(DB, task["scoring"]["reference_sql"])  # DB = suite's refs/shop.db
    try:
        got = run_query(DB, sql)          # read-only, five-second limit
    except sqlite3.Error as exc:
        return {"hard": 0, "soft": 0.0, "checks": [f"sql_error:{exc}"]}

    missing, extra = diff_rows(want, got) # order-insensitive, numbers within a cent
    exact = not missing and not extra
    ...
    return {"hard": int(exact), "soft": soft, "checks": checks}
```

Decisions worth copying:

The agent's SQL is untrusted, so it runs on a read-only connection with
a time limit. A cross join or an endless recursive CTE becomes an
`sql_error` instead of a hung scorer.

The rubric scores against the suite's own `refs/shop.db`, not the copy
in the workspace. The agent gets a copy so it can look at the data, but
an agent that deletes the test accounts from its copy would otherwise
turn the naive query into a pass.

Numbers compare within a cent, and column names are ignored. An agent
that writes `AS total_revenue` where the reference has no alias is not
wrong. An agent that returns 202.6395 where the reference says 202.64
is.

Row order is ignored unless the task says `"ordered": true`. Rankings
say it; aggregates do not.

`soft` is built from stages: 0.3 for a query that runs, 0.2 for the
right column count, 0.5 scaled by how many rows overlap. That gives the
gate something to see when an edit moves a task from "did not run" to
"ran, wrong rows".

The checks carry the diff. `rows:14!=12`, then up to two `missing_row:`
and `extra_row:` samples. That is the evidence an editor reads.

## The scoring contract

`scoring.md` opens with the suite config and then explains, in prose,
how a rollout is scored and what each check means:

```json
{
  "default_mode": "rubric",
  "mixed_weight": 0.5,
  "smoke_tools": []
}
```

`failure_classes.md` maps each symptom class to a mechanism. The
mechanism column names where in the skill to look, never the fix:

```
| class | symptom looks like | mechanism |
|---|---|---|
| ghost-rows | extra customers in a listing, or totals slightly above the reference | rows exist in `customers` that no report should include |
| split-categories | one category appears under several spellings | grouping on the raw stored value instead of a normalized one |
| missing-zero-rows | fewer rows than the reference; the missing ones have zero activity | the join drops entities with nothing on the other side |
```

## Verify the scorer before you spend a model call

The scorer is the part of the suite that can lie to you, so test it
first. `tests/test_sql_demo.py` does three things for every task: the
reference query scored through `score.py` returns exactly `hard 1, soft
1.0`; each probe returns `hard 0` and names its own symptom; the
database rebuilds identically. It also checks that two statements are
rejected, that prose around the fence and a ` ```sqlite ` tag are
tolerated, that a runaway query is cut off, that editing the workspace
database cannot move the score, and that a reshuffled ranking fails an
ordered task.

```bash
.venv/bin/python -m pytest tests/test_sql_demo.py -q
```

```
.........................................                                [100%]
41 passed in 0.95s
```

Write the equivalent for your suite. If the reference does not score
1.0, nothing else in the run means anything.

## One real rollout

Now the first model call. One task, Haiku, then score it:

```bash
SKILL_TRAINER_MODEL=claude-haiku-4-5-20251001 .venv/bin/python harness/run_task.py \
  --skill examples/sql-demo/skills/sql-queries/SKILL.md \
  --suite examples/sql-demo/tasks/sql-queries --task t01-total-revenue \
  --backend claude --workdir runs/try/t01_s0
.venv/bin/python harness/score.py --suite examples/sql-demo/tasks/sql-queries --workdir runs/try/t01_s0
```

Haiku answered:

```sql
SELECT SUM(oi.quantity * p.unit_price_cents) / 100.0 AS total_revenue
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
WHERE o.status IN ('paid', 'shipped', 'delivered');
```

and scored:

```json
{"hard": 0, "soft": 0.5,
 "checks": ["ran", "missing_row:(7605.87,)", "extra_row:(8488.84,)", "symptom:ghost-rows"]}
```

Reasonable query, wrong number. It counted the test accounts. Note that
it got the status filter right on its own by reading the comment in the
schema. Which brings up the first thing that went wrong.

## What went wrong the first time

The first version of this suite had simpler conventions: revenue counts
`paid` orders, prices are in cents, customers include the ones with no
orders. Haiku solved all eight train tasks against the two-sentence
skill. Baseline 1.0. Nothing to train.

The conventions were guessable from the schema. `unit_price_cents` says
what unit it is in. A `status` column with a `paid` value invites a
filter. A capable model reads the schema and does the sensible thing,
and the sensible thing was the house convention.

A suite worth training on needs conventions that are house-specific:
things a careful newcomer would get wrong because there is no way to
know. Test accounts that look like customers. Category values that were
entered by hand over three years. A status ladder where "counts as
revenue" is a business decision. That is what the second version
carries, and its baseline is 0.0 hard.

The lesson generalizes past SQL. Before you write a suite, roll out a
few tasks against a weak skill and look at what a good model does with
no help. If it already succeeds, your skill will not learn anything
because there is nothing to learn.

## Make wrong answers say why

The second thing that went wrong is subtler. A row diff says what was
wrong. It does not say why, and the editor has to guess the mechanism
from `missing_row:(7605.87,) extra_row:(8488.84,)`.

The harness doctrine (PROGRAM.md, section 5c) is blunt about this: a
gate that can fail an artifact must be able to point at the failing
region. Scalar verdicts make editors plateau.

So each task carries probes. A probe is the reference query with exactly
one convention removed. When the agent's rows match a probe's rows, the
rubric adds `symptom:<class>` to the checks, and the class is a row in
`failure_classes.md`:

```python
def symptoms(task, db, got):
    matched = [f"symptom:{name}"
               for name, probe_sql in task["scoring"].get("probes", {}).items()
               if same_rows(run_query(db, probe_sql), got)]
    return matched or ["symptom:unclassified"]
```

The probes were generated from the reference queries by swapping one
slot at a time (`c.email NOT LIKE '%@example.com'` becomes `1 = 1`,
`LOWER(p.category)` becomes `p.category`), and any probe whose rows
happened to equal the reference under this data was dropped, because a
probe that cannot fire is a suite bug. The test file checks that every
remaining probe fires.

`symptom:unclassified` means the answer matched no single-convention
probe, usually because two conventions are missing at once. That is
fine. As the skill learns one, the other becomes classifiable. The
baseline below has three of those.

## Where the answers must not be

The manager agent reads `scoring.md` at setup. Editors read
`failure_classes.md` in every prompt. Neither file may contain the
conventions, or the run is a copy job.

The first draft of `scoring.md` had a "house conventions" section,
because it seemed like documentation. It moved to the example's README
before the training run. Keep your answer key outside the suite
directory, and keep `failure_classes.md` at the level of "where to
look".

One leak the harness does not close: `task.json`, including
`reference_sql`, sits in the rollout workspace next to `shop.db`. An
agent that reads it can copy the answer. For deterministic modes the
project accepts this; the prompt never mentions the file and a rollout
that reads it would be visible in the transcript. If it worries you,
have the rubric look the reference up from the suite by task id instead
of shipping it in the task.

## Baseline over the train split

Roll out all eight train tasks once, with scoring:

```bash
SKILL_TRAINER_MODEL=claude-haiku-4-5-20251001 .venv/bin/python harness/rollout_batch.py \
  --skill examples/sql-demo/skills/sql-queries/SKILL.md \
  --suite examples/sql-demo/tasks/sql-queries \
  --tasks t01-total-revenue,t02-orders-per-customer,t03-orders-in-march,t04-top3-products,t05-german-no-orders,t06-revenue-by-category,t07-avg-order-value,t08-q1-signups-spend \
  --seeds 0 --backend claude --mode cheap --timeout 300 --jobs 4 \
  --score --out runs/try/baseline
```

| task | hard | soft | symptom |
|---|---|---|---|
| t01-total-revenue | 0 | 0.50 | ghost-rows |
| t02-orders-per-customer | 0 | 0.93 | ghost-rows |
| t03-orders-in-march | 0 | 0.50 | ghost-rows |
| t04-top3-products | 0 | 0.60 | ghost-rows |
| t05-german-no-orders | 0 | 0.83 | ghost-rows |
| t06-revenue-by-category | 0 | 0.50 | unclassified |
| t07-avg-order-value | 0 | 0.50 | unclassified |
| t08-q1-signups-spend | 0 | 0.64 | unclassified |

Aggregate: hard 0.0, soft 0.62, mixed 0.31.

Every task fails and five of eight fail the same way. An editor reading
these receipts with the failure-class table in hand should reach for
one rule. Whether it does, and whether the gate agrees, is chapter 5.

## The smoke check

Last thing before a run. The smoke check confirms the suite's declared
tools and dependencies exist and the agent CLI is on the path:

```bash
.venv/bin/python harness/run_task.py --smoke --suite examples/sql-demo/tasks/sql-queries --backend claude
```

```json
{"smoke": "pass", "checks": [{"check": "cli:claude", "ok": true}]}
```

This suite declares nothing beyond the CLI. A suite that needs
`ffmpeg` or a Python package lists it in `smoke_tools` or
`requirements.txt`, and the check fails early instead of at step 3 of an
overnight run.

Next: [Launch a training run](05-launch-a-training-run.md).
