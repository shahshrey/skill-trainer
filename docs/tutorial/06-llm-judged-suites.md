# 6. LLM-judged suites

Some skills produce output no script can grade. A code review. A piece
of UI. A paragraph that is supposed to read as if a person wrote it. For
these, the `judge` scoring mode asks a language model for a structured
verdict and feeds the same `hard` and `soft` numbers into the unchanged
gate.

This is a separate way to measure, not a shortcut. Before you reach for
it, ask whether a checklist or a rubric script could do the job. A
deterministic score is free, repeatable and cannot be talked into a
pass. A judge is none of those things. Use it when you must.

The example is `examples/judge-demo`, which trains a **skill-review**
skill: the agent gets a skill package with planted defects and writes a
review. The judge grades the review against a gold review.

## What you need

```bash
.venv/bin/pip install -r requirements-judge.txt
echo 'MINIMAX-API-KEY=your-key' > .env
```

The judge is MiniMax M3 through its OpenAI-compatible API, driven by
LangChain. `.env` is gitignored. `MINIMAX_API_KEY` in the environment
works too.

## The suite layout

```
tasks/skill-review/
  judge.md                the judge prompt: criteria, weights, pass rule
  scoring.md              default_mode judge, samples, criteria_weights
  train/val/test.jsonl    8 / 4 / 4 tasks; each carries a reference
  refs/<id>/<dirname>/    the flawed skill package the agent reviews
  refs/<id>/gold.md       the gold review, the task's reference
  refs/<id>/defects.json  the planted defects, for humans and tests
  failure_classes.md      judge criterion -> skill mechanism guide
```

A judged task looks like this:

```json
{"id": "r01", "suite": "review",
 "prompt": "Review the agent skill package in the directory `./pdf-extract/` ...",
 "files": ["refs/r01/pdf-extract"],
 "reference": "refs/r01/gold.md",
 "judge_inputs": ["pdf-extract/SKILL.md"]}
```

`files` copies the flawed package into the workspace. `reference` is
what a good answer looks like. `judge_inputs` are workspace globs whose
contents the judge also sees, so it can check claims in the review
against the file that was reviewed.

## Reference or rubric

The judge needs a definition of good. There are two ways to give it one.

A reference per task is the strong option and the default. The judge's
job becomes comparison: did this review find what the gold review found,
did it invent problems the gold review says are not there. The loop
climbs toward a concrete target, the same as with a deterministic suite.
Every task in judge-demo has one.

A rubric only, with no reference, means `judge.md` alone describes the
ideal. This works exactly as well as the prompt is written and no
better. The check command warns about it:

```bash
.venv/bin/python harness/judge.py --check --suite examples/judge-demo/tasks/skill-review
```

```json
{
  "key": true,
  "judge_md": true,
  "model": "MiniMax-M3",
  "samples": 3,
  "tasks": {
    "dataset": 16,
    "rubric": 0,
    "missing_reference": [],
    "by_split": {
      "train": {"dataset": 8, "rubric": 0},
      "val": {"dataset": 4, "rubric": 0},
      "test": {"dataset": 4, "rubric": 0}
    }
  },
  "warnings": []
}
```

`dataset` counts tasks with a reference. If you write a rubric-only
suite, expect a warning per task and expect to spend real time on
`judge.md`.

## Writing judge.md

The judge prompt is part of the scoring contract, hashed into
`rubric_version` like `rubric.py`. Change it mid-run and every earlier
verdict is void.

The judge-demo prompt has four parts, and yours should too.

What is being graded, stated plainly. "Grade the review, not the
skill." A judge that wanders off and evaluates the wrong artifact gives
you confident nonsense.

Criteria, each scored 0.0 to 1.0, each with a rule for how to score it.
The demo's `defect_recall` is found divided by planted, with half
credit for a symptom noticed but misdiagnosed. `precision` starts at
1.0 and loses 0.25 per invented problem. Numbers, not adjectives.

Weights. The demo puts 0.5 on recall, 0.2 each on precision and
actionability, 0.1 on format. These go in `scoring.md` too, and the
harness uses its copy: the judge's own arithmetic is ignored so the
aggregation cannot drift with the model.

A pass rule. `passed` is true only when recall is at least 0.75 and
precision at least 0.5. `hard` for the task is 1 when a majority of the
samples say passed.

The rest of the file is the input layout the judge will receive and an
instruction to return a structured verdict. `judge.py` sends the prompt
with the review, the reference and the judge inputs, and asks for the
verdict through a tool schema, with JSON in the content as fallback.

## One judged rollout

Roll out one task with Haiku and score it:

```bash
SKILL_TRAINER_MODEL=claude-haiku-4-5-20251001 .venv/bin/python harness/run_task.py \
  --skill examples/judge-demo/skills/skill-review/SKILL.md \
  --suite examples/judge-demo/tasks/skill-review --task r01 --backend claude \
  --workdir runs/try/judge_r01
.venv/bin/python harness/score.py --suite examples/judge-demo/tasks/skill-review \
  --workdir runs/try/judge_r01
```

```json
{
  "mode": "cheap",
  "rubric_version": "032b423accec",
  "tasks": {
    "judge_r01": {
      "hard": 0,
      "soft": 0.6817,
      "checks": [
        "crit:defect_recall=0.75",
        "crit:precision=0.4167",
        "crit:actionability=0.75",
        "crit:format=0.7333",
        "judge:fail",
        "ref:dataset"
      ],
      "mode": "judge"
    }
  },
  "aggregate": {"overall": {"n": 1, "hard": 0.0, "soft": 0.6817, "mixed": 0.3408}}
}
```

The review found three of four planted defects and invented one. Recall
cleared the bar, precision did not, so the task fails. `soft` is the
weighted mean over three samples.

The checks are verdicts. The feedback is in `judge.json` in the
workspace, one entry per sample, with the judge's evidence per
criterion:

```
defect_recall 0.75: Found 3 of 4 planted defects: name-invalid (FOUND:
"name: PDF_Extract uses mixed case and underscores ..."), windows-path
(FOUND: "Path separator inconsistency ..."), missing-script (FOUND:
"References scripts/extract_tables.py ... but file does not exist").
desc-second-person was MISSED: review explicitly marked description as
"[✓] description validation" ... failing to identify the "You can
extract" second-person voice problem.

precision 0.75: One clear fabrication: "Document error exit codes
explicitly" ... the reference explicitly lists "Error handling and exit
codes follow standard conventions" under "What is clean" ...
```

That text is what the manager puts into editor receipts for judged
suites. An editor reading it can see the skill needs a check for
second-person descriptions. An editor reading only `crit:defect_recall
=0.75` cannot.

## Cost and noise

Three samples per verdict at temperature 0. A judge is still a model,
and repeated verdicts on the same output differ. The sample mean and
the paired gate's z-test absorb that; dropping to one sample to save
money makes the gate blind. Verdicts are cached per workspace in
`judge.json`, so rescoring a batch you have already judged is free.

For a judged suite, cheap and full gate modes are the same pass. Set
`gate_modes` to cheap for both step and epoch in `config.json`.

## What a judged run looked like

A bounded 8-step run of judge-demo (Haiku rollouts, K=2, three judge
samples) took val mixed from 0.335 to 0.774. Five of the eight steps
were rejected. Every accepted edit was a review check the judge's
evidence said was missing. On the unseen test split the trained skill
scored 0.610 against 0.389 for the starting one. The details are in
`examples/judge-demo/README.md`.

Back to the [index](README.md).
