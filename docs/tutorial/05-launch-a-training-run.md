# 5. Launch a training run

This chapter launches a bounded run on the suite from chapter 4, then
reads what came out. The run in these pages used Claude Haiku 4.5 for
rollouts and the `claude` CLI's default model as the manager: four
steps plus one epoch boundary, about 45 minutes and roughly 130 Haiku
rollouts.

The short version: val went from 0.27 to 0.81. One step was accepted,
two were rejected, one was a no-op, and the rejections are the
interesting part.

## Put the suite where the run expects it

A run trains `skills/<name>/SKILL.md` against `tasks/<name>/`, both at
the repo root. Both directories are gitignored, so your suite stays out
of the framework's history:

```bash
cp -r examples/sql-demo/tasks/sql-queries tasks/sql-queries
cp -r examples/sql-demo/skills/sql-queries skills/sql-queries
```

The manager commits every accepted edit to `SKILL.md`, so the skill
file has to be tracked; force-add it once. Nothing under `tasks/` should
ever be committed.

If your checkout has uncommitted work, run in a worktree instead. The
manager runs `git reset --hard` on every rejected step, which discards
uncommitted changes to tracked files. That is what this tutorial did:

```bash
git worktree add -b train/sql-queries/tut01 runs/tutorial_wt/tut01 HEAD
ln -s "$(pwd)/.venv" runs/tutorial_wt/tut01/.venv
cp -r examples/sql-demo/tasks runs/tutorial_wt/tut01/tasks
cp -r examples/sql-demo/skills runs/tutorial_wt/tut01/skills
cd runs/tutorial_wt/tut01
git add -f tasks skills && git commit -m "seed sql-queries suite"
```

## Write the config

Copy the JSON from `runs/CONFIG_TEMPLATE.md` into
`runs/<tag>/config.json` and fill it in. This run's:

```json
{
 "skill": "sql-queries",
 "tag": "tut01",
 "backend": "claude",
 "model": "claude CLI default (train.sh passes no --model for the manager)",
 "rollout_model": "claude-haiku-4-5-20251001",
 "model_note": "Rollouts: run_task.py reads SKILL_TRAINER_MODEL=claude-haiku-4-5-20251001 from train.sh; never override per call. Editor/ranker/learning-rate/slow-update/meta-memory workers: plain `claude -p` with the manager's default model.",
 "K": 2,
 "E": 4,
 "L": 5,
 "M": 8,
 "concurrency": {"cheap": 4, "full": 4},
 "boundary": "Bounded tutorial run. Complete steps 1 through 4, then run the epoch-1 boundary (PROGRAM 4h moves 1-3 and the 4h2 coverage check). After logging the epoch rows for epoch 1, write runs/tut01/TERMINAL as `exhausted: tutorial boundary, 4 steps + epoch 1` and stop.",
 "gate_modes": {"step": "cheap", "epoch": "full"},
 "gate_note": "Paired gate per PROGRAM 4f with a fresh 3-pass baseline as the reference set. Single suite (primary), mixed weight 0.5. Rubric mode is deterministic and cheap/full are the same pass. HYPOTHESIS: the starting skill omits house conventions that the receipts surface as symptom:<class> checks (see tasks/sql-queries/failure_classes.md); edits that state one convention at a time, scoped to the failing shape, should clear the gate.",
 "deploy_mode": "package",
 "timeouts": {"cheap": 300, "full": 600}
}
```

The fields that matter most:

`K` is rollouts per val task per step. With 4 val tasks, every gate
decision rests on 8 rollouts. Two is the floor for a real model; the
paired gate needs repeated seeds to separate an edit's effect from
the model's own variance.

`E` is steps per epoch. At each epoch boundary the run does a full-mode
val pass, reruns the train sample under the old and new skill, and
rewrites the protected block and `META.md`. Four is short; the default
is eight. Short here so the tutorial shows a boundary.

`L` caps edits per step, `M` is the train sample size per epoch.

`boundary` is a sentence the manager obeys literally. Never launch
without one. A run with no boundary runs until you kill it, and a
killed run has no `TERMINAL`, so `train.sh` relaunches it.

`rollout_model` must never change within a tag. Every score in
`results.tsv` was produced by that model, and a different model's
scores are not comparable. New model, new tag, new baseline.

`gate_note` is where you write the run's hypothesis. The manager reads
it. Writing "I think the skill is missing X" makes the manager optimize
for testing that, which is a better run than one optimizing for the
number.

## Launch

```bash
.venv/bin/python harness/run_task.py --smoke --suite tasks/sql-queries --backend claude
nohup ./train.sh sql-queries tut01 claude "" claude-haiku-4-5-20251001 >> runs/tut01/train.log 2>&1 & disown
```

The arguments are skill, tag, agent CLI, manager model (empty for the
CLI's default), rollout model. For the other CLIs:

```bash
./train.sh sql-queries tut01 codex gpt-5.3 gpt-5.3-mini
./train.sh sql-queries tut01 copilot "" "" max      # sixth arg: reasoning effort
./train.sh sql-queries tut01 cursor claude-sonnet-5-low
./train.sh sql-queries tut01 opencode
```

`train.sh` builds the manager prompt from `PROGRAM.md`, launches the
agent CLI with it, and loops until `runs/<tag>/TERMINAL` exists. On
macOS it wraps the launch in `caffeinate` so the laptop does not sleep
through the night.

## What to watch

The run writes three things you can read while it goes.

`runs/<tag>/train.log` is `train.sh`'s own log: one line per manager
launch, and the manager's final message when a session ends. Most of
the time it is one line long.

`runs/<tag>/results.tsv` gets one row per step. This is the file to
keep open:

```bash
watch -n 30 'column -t -s $"\t" runs/tut01/results.tsv'
```

`runs/<tag>/step_<n>/` fills up per step: `skill/` (the snapshot the
rollouts ran against), `cheap/` or `full/` (one workspace per rollout
plus `scores.json`), `targeted_fix/` (the re-run of the train rollouts
the edit was aimed at), and `PENDING.json` while the step's val batch is
in flight. Beside them, `step_<n>_editor.md` is the filled editor prompt
and `step_<n>_edits.json` is what came back.

The first thing the manager does is the baseline: three full val passes
against the starting skill. Three, because the spread between them is
the run's noise floor and the paired gate's reference set. On this
suite that is 24 Haiku rollouts before any edit is proposed. All three
came back identical (0.2708), so the noise floor was zero.

## The run dies and that is fine

The manager is an agent session. It will run out of context, or the
API will hiccup, or the laptop will sleep. `train.sh` relaunches it
and the resume ritual at the top of `PROGRAM.md` reconstructs the
state from disk: the branch, the config, `results.tsv`, any
`PENDING.json` for a step that was mid-batch.

You will see this in `train.log` as repeated "launching manager" lines.
Each one is a fresh session that read the disk and continued. Nothing
scored is lost, because every batch is dispatched detached and writes
its own `scores.json`. This run happened to finish in one session.

## Reading results.tsv

```
# run=tut01 skill=sql-queries backend=claude K=2 E=4 L=5
# min_delta_cheap=0.01 min_delta_full=0.01
commit   epoch step mode  val_mixed val_hard val_soft n_val_rollouts status    edits_applied description
ed13550  0     0    cheap 0.2708    0.0000   0.5417   8              keep_best 0             baseline (mean of 3)
8abc467  1     1    cheap 0.7188    0.6250   0.8125   8              keep      3             ghost-rows filter + order-status scope + category-case
c5f9955  1     2    cheap 0.8125    0.7500   0.8750   8              discard   1             replace@"Exclude test accounts — add...": "every query touching orders must join customers..."
29b46ad  1     3    cheap 0.6250    0.5000   0.7500   8              discard   1             insert_after@"Exclude test accounts — add...": "For queries that return count/sum of orders but do not list customers, still add JOIN customers..."
8abc467  1     4    cheap                    0              discard   0             noop: learning_rate=0
8abc467  1     4    full  0.8125    0.7500   0.8750   8              keep_best 0             epoch 1 authoritative pass
7d7f932  1     4    full  0.8125    0.7500   0.8750   8              epoch     0             epoch 1 boundary slow_update applied
```

(`sec_mixed`, the secondary-suite column, is empty for a single-suite
run and is omitted above.)

Column by column. `commit` is the candidate that was scored; after a
discard the branch is back on the previous commit, which is why step 4
shows step 1's SHA. `mode` is the gate mode the rollouts ran in;
scores never compare across modes. `val_mixed`, `val_hard`, `val_soft`
are the aggregate over `n_val_rollouts` (4 tasks times K=2).
`status` is the gate's verdict. `description` is the manager's
one-liner, and for discards it holds the rejected edit text, which is
the buffer future editors are shown so they do not retry it.

Now the story the rows tell.

### Step 1: three conventions from five receipts

The editor got eight failed train receipts, five of them tagged
`symptom:ghost-rows`, and the failure-class table. It proposed three
edits:

```json
{"reasoning": "All 8 tasks failed: ghost-rows (5/8), order-status scope and category case normalize the rest.",
 "edits": [
  {"op": "append", "content": "\n## Query conventions\n\n**Exclude test accounts** — add `c.email NOT LIKE '%@example.com'` to every query that joins `customers`."},
  {"op": "append", "content": "\n**Order status scope** — for revenue sums, order counts, and averages, filter `o.status IN ('paid', 'shipped', 'delivered')`; when the customer join is a LEFT JOIN, apply the filter inside `CASE WHEN o.status IN (...) THEN ... END` rather than in WHERE."},
  {"op": "append", "content": "\n**Category case** — use `LOWER(p.category)` in both `SELECT` and `GROUP BY` when grouping by product category."}]}
```

It found the test-account rule from the symptom name and the extra
rows, the status rule from the `totals-too-high` probe, and the
category rule from the split rows. None of those are in any file the
editor can read. The gate:

```json
{"action": "accept_new_best",
 "reason": "paired mean delta +0.4479 over 8 pairs (se 0.1399) is significant and beats best",
 "paired": {"n_pairs": 8, "references": 3, "mean_delta": 0.447912, "se": 0.139921, "z_stat": 3.201}}
```

Val mixed 0.27 to 0.72, hard 0 to 0.625. Five of eight val rollouts
now solve their task.

### Step 2: a higher score, rejected

Step 2 scored 0.8125, above step 1's 0.7188, and was discarded. This is
the paired gate doing its job:

```json
{"action": "reject",
 "reason": "paired mean delta +0.0938 not significant (need > 0 and >= 1.645 * se 0.1699)",
 "paired": {"n_pairs": 8, "mean_delta": 0.09375, "se": 0.169936, "z_stat": 0.552}}
```

Per task, the edit fixed both `v04-never-sold` rollouts and broke one
of two `v02-customers-per-country` rollouts. Net positive on average,
but with 8 pairs and that much disagreement the standard error is
bigger than the gain. z = 0.55 against a bar of 1.645. An aggregate
would have taken this edit; the paired test would not, and it was
right not to: the edit ("every query touching orders must join
customers") is broader than the evidence, and step 3 shows what
happens when you push in that direction.

### Step 3: a real regression

The editor tried a narrower version of the same idea, scoped to count
queries. Val dropped to 0.625. The rows for `v02` went from one solve
to none. `META.md`, written at the epoch boundary, diagnosed it:

> Steps 2 and 3 both attempted to extend the customer-join requirement
> to order-count-only queries. Both regressed. Root cause: adding a
> customers join to a pure order-count query caused the model to also
> apply the status scope filter, under-counting (11 vs 16 expected).
> Coupling two independent conventions into one structural change is
> the main regression risk.

That paragraph is the optimizer's own memory. The next epoch's editors
read it.

### Step 4: nothing

After two rejects the learning-rate controller looked at the editor's
proposals, which were variations on the same rejected idea, and applied
zero of them. `noop: learning_rate=0`. Not a failure; a controller
declining to spend a val batch on an edit the buffer already says will
not pass.

### The epoch boundary

Three rows at step 4. First, a full-mode val pass on the epoch's
accepted skill: 0.8125, logged `keep_best` because full mode is the
authoritative one and this is where the best tag moves. Second (not a
row), the slow-update worker rewrote the protected block and the
meta-memory worker rewrote `META.md`. Third, a full val pass on the
result: 0.8125 again, logged `epoch`. The protected-block change did
not lose anything, so it stayed.

Why is the full pass 0.8125 when the step-1 cheap pass on the same
commit was 0.7188? Haiku is not deterministic across calls. Same skill,
same tasks, one more solve this time. This is the variance the paired
gate exists to handle, and why K=1 is only for mock runs.

## Reading the branch

```
7d7f932 epoch 1 boundary: slow_update + meta_memory
8abc467 step 1: add ghost-rows, order-status, category-case conventions
ed13550 seed sql-queries suite for tutorial run tut01
```

Two commits of training. The rejected candidates are not on the branch;
they were reset away. `best/sql-queries` points at `8abc467`.

`git diff ed13550 8abc467 -- skills/sql-queries/SKILL.md` is the step-1
edit above. `git diff 8abc467 7d7f932` is the epoch boundary, which
filled the protected block:

```markdown
<!-- PROTECTED:SLOW_UPDATE:START -->
## Conventions (slow update)

**Force a customer join when orders is the only table** — if the query
touches `orders` but not `customers`, add `JOIN customers c ON
o.customer_id = c.id` and `c.email NOT LIKE '%@example.com'` to the
WHERE clause. Never skip this; the email exclusion is required on every
query that reads from `orders`.

**Status filter is for financial metrics only** — apply `o.status IN
('paid', 'shipped', 'delivered')` when computing revenue, totals, or
averages. Do NOT apply it to a plain count of orders in a time window
(e.g., "orders placed in March") — count every non-test-account order
regardless of status for those questions.
<!-- PROTECTED:SLOW_UPDATE:END -->
```

Look at what the slow update did. It took the idea steps 2 and 3
failed with and split it into the two independent rules META.md said
had been wrongly coupled. The val pass after it held at 0.8125. Whether
those two rules are an improvement is a question for epoch 2; the
boundary pass only proves they are not a regression.

## The test split

The run never touched `test.jsonl`. Rolling its four tasks out twice
each against the starting skill and the trained one gives the number
you can quote:

```bash
.venv/bin/python harness/rollout_batch.py --skill <skill snapshot>/SKILL.md \
  --suite tasks/sql-queries --tasks x01-monthly-revenue,x02-refunds-per-customer,x03-top-category,x04-stationery-units \
  --seeds 0,1 --backend claude --mode cheap --timeout 300 --jobs 4 --score --out runs/tut01/test_<which>
```

| task | starting skill | trained skill |
|---|---|---|
| x01-monthly-revenue | 0, 0 (ghost-rows) | 1, 1 |
| x02-refunds-per-customer | 0, 0 (ghost-rows) | 1, 1 |
| x03-top-category | 0, 0 (unclassified) | 0, 0 |
| x04-stationery-units | 0, 0 (unclassified) | 1, 1 |
| aggregate mixed | 0.316 | 0.781 |
| aggregate hard | 0.00 | 0.75 |

Three of four unseen questions now solve on both seeds. The one that
does not, top category by revenue, is the shape the skill still has no
rule for: a ranking over a case-normalized group with a status filter,
and the model applies two of the three conventions and misses one.
That is what epoch 2 would be for.

The trained reply for the refunds task, for the record:

```sql
SELECT
  c.name,
  COUNT(o.id) AS refunded_orders
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id AND o.status = 'refunded'
WHERE c.email NOT LIKE '%@example.com'
GROUP BY c.id, c.name
ORDER BY c.name;
```

The starting skill's reply to the same prompt was the same query without
the email filter: 14 rows instead of 12.

## The audit

`audit_run.py` runs after every run. It checks that no val or test
prompt text reached an editor, that the best tag never moved on a
non-authoritative score, that protected blocks were only changed at
boundaries, that rejected edits were not re-proposed verbatim, and that
every score in the run carries the same `rubric_version`.

```bash
.venv/bin/python harness/audit_run.py --run runs/tut01 --suite tasks/sql-queries --skill sql-queries
```

This run failed it:

```
"status": "fail",
"failures": [
  "leakage: val-prompt-text 'The SQLite database `shop.db` is in the current directory an' found in runs/tut01/step_1_editor.md",
  ...
```

Every editor prompt, every val and test task. Not because val leaked.
The audit greps editor prompts for the first 120 characters of every
held-out prompt, and in the version of the suite this run used, every
prompt opened with the same 130-character sentence about where the
database is. Train receipts in the editor prompt matched that sentence,
which is what the audit is for, and the audit cannot tell a shared
preamble from a leak.

The other four audits passed. The fix is on the suite side, and the
shipped `examples/sql-demo` has it: the question first, the boilerplate
after, so the first 120 characters of every prompt are unique to that
task. Chapter 4 lists this among the split rules. If you copy the
example, your audit will be clean. If you write your own prompts,
front-load what varies.

## After the run

The trained skill is on the branch. Merge it, or copy `SKILL.md` into
your agent's skills directory. Keep the run directory if you want the
receipts; delete it if you do not, nothing else refers to it.

For a real run: keep `E` at 8, set the boundary in wall-clock hours or
a target score, size `K` to your model's variance, and launch it
before you go to bed.

Next: [LLM-judged suites](06-llm-judged-suites.md).
