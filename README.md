# skill-trainer

**Stop writing skills. Start training them.**

A standalone, self-contained system that *trains* an agent skill — a
`SKILL.md` document — against a scored task suite, using an agent-driven
hill-climbing loop with git as the checkpoint mechanism.

Zero framework dependencies. The harness is plain Python (stdlib + numpy);
the optimizer is a manager agent following [`PROGRAM.md`](PROGRAM.md);
everything that "learns" is markdown. Requires only git, Python 3.11+, and
one or more agent CLIs (`claude -p`, `codex exec`, `cursor-agent`,
`copilot`).

## How it works

1. An **editor** agent proposes a small set of bounded edits to `SKILL.md`
   based on failure/success evidence from training tasks.
2. The manager applies the edits, runs `harness/lint_skill.py` (a
   deterministic skill-quality gate), and commits.
3. Parallel **rollout workers** run the candidate skill against a held-out
   validation set the editor never saw; `harness/score.py` produces a number.
4. Strictly better → the branch advances. Otherwise → `git reset --hard`.
5. Every step is logged to `results.tsv` (including rejected edit text — a
   rejected-edit buffer fed back to future editors).
6. Every E steps, an epoch boundary runs a slow-update regression check and
   refreshes the optimizer-side memory (`META.md`).

Training runs happen on branches named `train/<skill-name>/<tag>`, and the
manager survives crashes: `train.sh` relaunches it until a terminal state
exists, and the resume ritual in `PROGRAM.md` §0 reconstructs everything
from disk.

Guardrails are structural, not aspirational: the editor never sees
validation tasks, the manager cannot modify the harness or the task suite,
scores never compare across gate modes, and post-run audits
(`harness/audit_run.py`) grep for leakage.

## Quick start

```bash
git clone https://github.com/shahshrey/skill-trainer
cd skill-trainer
uv venv .venv && uv pip install -r requirements-dev.txt -p .venv/bin/python

# The trainer tests itself deterministically — no LLM calls:
.venv/bin/python -m pytest tests/
```

To train something real you bring a **task suite** (see below). The mock
backend lets you exercise the whole loop without an agent CLI or API costs
first:

```bash
# Meta-evaluation: can the trainer recover a deliberately deleted rule?
.venv/bin/python tests/meta_eval.py planted --ablate <rule-id>
# Null test: does it correctly reject noise?
.venv/bin/python tests/meta_eval.py null
# Full machinery: epochs, slow updates, audits
.venv/bin/python tests/meta_eval.py epochs
```

## Bring your own task suite

This repo is the **framework only** (see `PROGRAM.md` §8). Task suites and
the skills they train live in your own working copy — `tasks/` and
`skills/` are gitignored here by design. A suite is a directory:

```
tasks/<skill-name>/
  train.jsonl        tasks the editor learns from
  val.jsonl          held-out gate tasks — the editor NEVER sees these
  test.jsonl         optional final held-out set
  scoring.md         scoring contract: suite config (first ```json block),
                     smoke_tools, optional example-template packaging rules
  rubric.py          score(task, workdir, mode) -> {hard, soft, checks}
                     (only needed for rubric-mode scoring)
  requirements.txt   suite-specific deps (installed into .venv)
  refs/              any reference files tasks list under "files"
```

Each line of a `.jsonl` file is a task: `{"id": ..., "prompt": ...,
"files": [...], "scoring": {...}}`. Four scoring modes are built in —
`exact` (regex on output), `checklist` (required substrings), `command`
(exit code), and `rubric` (your `rubric.py`). Scoring is deterministic and
makes no LLM calls.

The skill being trained lives at `skills/<skill-name>/SKILL.md`, with
optimizer memory in `META.md` beside it.

## Launching a training run

```bash
# One-time: verify tooling against your suite
.venv/bin/python harness/run_task.py --smoke --suite tasks/<skill> --backend claude

# Launch (keeps the manager alive until a terminal state):
./train.sh <skill-name> <tag> claude
```

Before a real run, copy `runs/CONFIG_TEMPLATE.md`'s JSON into
`runs/<tag>/config.json` — every field pattern in it earned its place in a
live run. The manager reads `PROGRAM.md` and takes it from there; it will
not stop until `runs/<tag>/TERMINAL` exists.

## Layout

```
PROGRAM.md            manager agent instructions (the heart)
train.sh              relaunch wrapper — keeps the manager alive
prompts/              worker prompt templates (editor, ranker, rollout, ...)
harness/              the ONLY Python code; read-only during training
runs/CONFIG_TEMPLATE.md  canonical run config, distilled from live runs
tests/                deterministic framework tests + meta_eval.py
tasks/<name>/         your task suites (gitignored — yours to provide)
skills/<name>/        SKILL.md (trainable) + META.md (optimizer memory)
runs/<tag>/           per-run artifacts (gitignored)
results.tsv           training log (untracked)
```

`harness/` and `tasks/*/val.jsonl` are ground truth: the manager must never
modify them, and the editor must never see val task contents.

Rollout batches go through `harness/rollout_batch.py` — N parallel
private-workspace workers with heartbeat supervision (a stale worker is
killed and requeued once). `harness/harvest.py` mines Claude/Codex/Cursor
session transcripts for recurring requests to grow task suites from
(≥2 distinct sessions before a candidate is emitted; a human curates).

## Meta-evaluation

The trainer itself is tested (see `tests/`): deterministic gate/edit/lint
tests against a mock backend, planted-defect recovery, a null (noise) test,
and post-run leakage audits.

## Design provenance (ideas, not code)

- **autoresearch** (Karpathy) — outer loop mechanics: commit/reset as
  accept/reject, `results.tsv`, never-stop autonomy.
- **Loopy** — loop-design rules: signal vs gate separation, explicit
  terminal states, run receipts, no self-approval.
- **SkillOpt** — optimizer mechanics: mixed validation gate, edit budgets,
  ranking, autonomous learning rate, rejected-edit buffer, protected
  sections, meta-memory, harvesting.
- **skill-review** — the skill-quality standard enforced by
  `harness/lint_skill.py` and the editor prompts.

## License

[MIT](LICENSE)
