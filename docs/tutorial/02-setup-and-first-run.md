# 2. Setup and first run

By the end of this chapter you will have seen the loop rediscover a rule
that was deleted from a working skill, and refuse to accept anything on
a suite that is pure noise. Both runs use a mock backend for rollouts.
Only the editor calls a model, through `claude -p`, so the whole chapter
costs a few prompts on your existing subscription.

## Install

```bash
git clone https://github.com/shahshrey/skill-trainer
cd skill-trainer
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

`requirements-dev.txt` is pytest and nothing else. The harness is
standard library Python; the only runtime dependency is the agent CLI
you already have.

## Run the tests

```bash
.venv/bin/python -m pytest tests/
```

```
tests/test_apply_edits.py ...........                                    [  7%]
tests/test_audit_run.py ...........                                      [ 15%]
tests/test_coverage.py ......                                            [ 20%]
tests/test_example_suite.py ........                                     [ 26%]
tests/test_gate.py ..........                                            [ 33%]
tests/test_gate_paired.py ................                               [ 44%]
tests/test_git_ritual.py ....                                            [ 47%]
tests/test_judge.py ......................                               [ 63%]
tests/test_lint_skill.py .............s                                  [ 73%]
tests/test_rollout_batch.py ........                                     [ 79%]
tests/test_rollout_batch_contam.py ....                                  [ 82%]
tests/test_run_task_mock.py ..............                               [ 92%]
tests/test_score.py ..........                                           [100%]

======================= 137 passed, 1 skipped in 39.79s ========================
```

Every test is deterministic and makes no model calls. If something fails
here, fix it before going on; nothing downstream will be trustworthy.

## The planted-defect run

`examples/mock-demo` is a small suite with a reference skill of eight
rules. The mock backend "solves" a task when the skill text still
contains the rule the task needs. The meta-eval deletes one rule and
asks: can the loop put it back from failure symptoms alone?

```bash
.venv/bin/python tests/meta_eval.py planted --ablate seamless-loop --max-steps 8
```

```
[planted-d1-1789543903] baseline=0.8750 min_delta=0.0100 target=1.0
  step 1: accept_new_best applied=1 val=1.0000 current=1.0000 streak=0
{
  "run": "planted-d1-1789543903",
  "ablated": ["seamless-loop"],
  "baseline": 0.875,
  "final": 1.0,
  "recovery_rate": 1.0,
  "steps": 1,
  "accepts": 1,
  "terminal": "success",
  "pass": true
}
```

Here is what happened, in order.

The run copied the example into a throwaway git worktree, deleted the
line "A seamless loop is mandatory: the first and last frames must
match" from the skill, and scored the val set. Seven of eight val tasks
pass, one fails: baseline 0.875.

The failing rollout's output is the whole receipt the editor gets:

```
MOCK ROLLOUT task=val-seamless-loop seed=0
SYMPTOM: the animation visibly jumps at the moment it restarts
RESULT: unsolved
```

Notice the symptom describes what went wrong, not what rule is missing.
The editor proposed one edit:

```json
{"op": "insert_after",
 "target": "- Sync same-stage motion: parallel elements depart and arrive together.",
 "content": "- For looping animations, make the closing frame's state identical to the opening frame so the restart is invisible."}
```

Different words from the original, same rule. The suite's regex groups
accept the rephrasing, val went to 1.0, the gate said
`accept_new_best`, and the run hit its target. One step.

Artifacts land in `runs/meta/planted-d1-<timestamp>/`. Look at
`meta/step_1/pre_edit.md` (the skill before the edit) and
`meta/step_1/edits.json` (what the editor returned).

Try it with a different rule, or two at once:

```bash
.venv/bin/python tests/meta_eval.py planted --ablate state-a-default one-term-per-concept
```

## The null run

This is the test most optimizers fail. `mock-null` is a suite where every
task passes half the time regardless of the skill. There is nothing to
learn. A loop that "improves" here is fitting noise.

```bash
.venv/bin/python tests/meta_eval.py null --max-steps 5
```

```
[null-1789543905] baselines=[0.25, 0.4167, 0.5833] min_delta=0.3333
  step 1: noop applied=0 val=0.4167 current=0.4167 streak=1
  step 2: noop applied=0 val=0.4167 current=0.4167 streak=2
  step 3: noop applied=0 val=0.4167 current=0.4167 streak=3
  step 4: noop applied=0 val=0.4167 current=0.4167 streak=4
  step 5: noop applied=0 val=0.4167 current=0.4167 streak=5
{
  "run": "null-1789543905",
  "baseline": 0.4167,
  "steps": 5,
  "accepts": 0,
  "terminal": "exhausted",
  "pass": true
}
```

Two things to see. First, the baseline was measured three times and
came back 0.25, 0.42 and 0.58. That spread became the bar an edit has
to clear (`min_delta=0.3333`). A noisy suite earns a high bar
automatically; on the planted run the three baselines agreed and the
bar was the floor of 0.01.

Second, every step is `noop applied=0`. The editor did propose edits.
The learning-rate controller, which sizes each step from the evidence,
looked at receipts that fail at random and applied none of them. Five
steps, zero accepts, `exhausted`. That is the correct answer.

## What you know now

The loop can recover a real rule from a symptom and will not accept
edits on noise. Both of those are properties of the gate, not of the
editor, and they hold for real suites the same way. Chapter 3 goes
through what a suite is made of; chapter 4 builds one.

Next: [Anatomy of a suite](03-anatomy-of-a-suite.md).
