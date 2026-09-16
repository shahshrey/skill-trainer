# judge-demo: an LLM-judged training suite

A complete suite for the `judge` scoring mode. It trains a **skill-review**
skill (reviews other agent skills against best practices) on 16 synthetic
skill packages with planted defects, scored by MiniMax M3 through
`harness/judge.py`.

```
skills/skill-review/        the trainable skill: a deliberately weakened
                            starting point (report format only, no
                            checklist) so the loop has something to learn
tasks/skill-review/
  judge.md                  the judge prompt: 4 criteria, weights, pass rule
  scoring.md                suite config: default_mode judge, 3 samples
  train/val/test.jsonl      8 / 4 / 4 tasks; each carries a reference
  refs/<id>/<dirname>/      the flawed skill package the agent reviews
  refs/<id>/defects.json    the planted defects (machine-readable)
  refs/<id>/gold.md         the gold review = the task's reference
  failure_classes.md        judge check -> skill mechanism guide
```

## Dataset mode

Every task carries a `reference` (its gold review), so the judge grades
closeness to a concrete target: defect recall against the planted list,
precision against the "what is clean" list, actionability, and format.
`harness/judge.py --check --suite examples/judge-demo/tasks/skill-review`
prints the per-split mode report.

## Run it

```bash
.venv/bin/pip install -r requirements-judge.txt        # LangChain + OpenAI client
echo 'MINIMAX-API-KEY=...' > .env                       # gitignored
.venv/bin/python harness/judge.py --check --suite examples/judge-demo/tasks/skill-review

# one rollout + judge verdict
SKILL_TRAINER_MODEL=claude-haiku-4-5-20251001 .venv/bin/python harness/run_task.py \
  --skill examples/judge-demo/skills/skill-review/SKILL.md \
  --suite examples/judge-demo/tasks/skill-review --task r01 --backend claude \
  --workdir runs/try/r01_s0
.venv/bin/python harness/score.py --suite examples/judge-demo/tasks/skill-review \
  --workdir runs/try/r01_s0
```

To train: copy `tasks/` and `skills/` into the repo root (both are
gitignored there), write `runs/<tag>/config.json` from
`runs/CONFIG_TEMPLATE.md` with `backend: claude` and
`rollout_model: claude-haiku-4-5-20251001`, and launch
`./train.sh skill-review <tag> claude "" claude-haiku-4-5-20251001`.

## What a run looks like

A bounded 8-step run of this suite (Claude Haiku 4.5 rollouts, K=2,
MiniMax M3 judge with 3 samples) took val mixed from 0.335 (baseline) to
0.517 (step 1), 0.637 (step 4), and 0.774 after the epoch-boundary slow
update; five steps were rejected by the paired gate. Every accepted edit
was a review check the judge's feedback said was missing. On the unseen
test split the trained skill scored 0.610 against 0.389 for the starting
skill. Run artifacts stay in your task repo, not here (PROGRAM.md §8).

## Defect catalogue

name-invalid, name-reserved, desc-second-person, desc-no-trigger,
desc-vague, desc-too-long, windows-path, nested-refs, time-sensitive,
options-no-default, inconsistent-terms, obvious-explanation,
extraneous-files, missing-script, magic-number, body-second-person,
no-quick-start, dir-name-mismatch, undocumented-binary. Each fixture
plants 3 or 4 of these and is otherwise clean; `defects.json` is the
ground truth and `gold.md` is what the judge compares reviews against.
