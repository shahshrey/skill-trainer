<p align="center">
  <img src="assets/banner.png" width="900px" alt="skill-trainer: stop writing skills, start training them">
</p>

<div align="center">

# skill-trainer

**Your agent's `SKILL.md` is a guess. Train it until it's a measurement.**

An agent-driven hill-climbing loop that trains skill files against scored
task suites. Git is the checkpoint mechanism, markdown is the model, and
every accepted edit earned its place on a held-out validation set.

Works with Claude Code, Codex, GitHub Copilot, Cursor, and opencode. Your
coding agent is the editor, the rollout worker, and the manager.

[![tests](https://github.com/shahshrey/skill-trainer/actions/workflows/tests.yml/badge.svg)](https://github.com/shahshrey/skill-trainer/actions/workflows/tests.yml)
[![python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**[Run it now](#run-it-now)** · **[How it works](#how-it-works)** · **[What a run produces](#what-a-run-produces)** · **[Bring your own task](#bring-your-own-task-suite)** · **[Launch a training run](#launch-a-real-training-run)**

</div>

---

Skills today are written once, by feel, and never verified. skill-trainer
closes the loop: propose a small edit, run the candidate against tasks the
editor never saw, keep it only if the score strictly improves. Rejected
edits roll back with `git reset --hard` and get fed to future editors as
evidence of what didn't work.

The harness is plain Python with one `pip install -r requirements.txt`
(LangChain and Pydantic, for the LLM judge), the optimizer is a manager
agent following [`PROGRAM.md`](PROGRAM.md), and everything that "learns"
is markdown. Rollouts and editing go through the agent CLI you already
have, billed on the same models and subscription your coding agent
already uses; only `judge`-mode suites need an API key of their own.

## Prerequisites

- Python 3.11+ and git.
- At least one agent CLI installed and authenticated: `claude`, `codex`,
  `copilot`, `cursor-agent`, or `opencode`.
- Any platform with bash. On macOS, `train.sh` additionally blocks system
  sleep (via `caffeinate`) so overnight runs survive; elsewhere it runs
  unwrapped.

## Run it now

Start with the framework's own test suite — deterministic, mock backend,
no model calls:

```bash
git clone https://github.com/shahshrey/skill-trainer
cd skill-trainer

# with uv:
uv venv .venv && uv pip install -r requirements-dev.txt -p .venv/bin/python
# or with plain pip:
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

.venv/bin/python -m pytest tests/
```

Then watch it actually train, using the bundled example suite
([`examples/mock-demo`](examples/mock-demo)). The meta-eval deletes a
known-good rule from the reference skill and measures whether the loop can
rediscover it from failure symptoms alone. Rollouts stay mocked; only the
editor makes model calls (through `claude -p`), so it costs a handful of
prompts:

```bash
.venv/bin/python tests/meta_eval.py planted --ablate seamless-loop --max-steps 8
```

And the null test, the one most optimizers fail, checks that on a
pure-noise suite the trainer correctly accepts ~nothing:

```bash
.venv/bin/python tests/meta_eval.py null --max-steps 5
```

## How it works

<p align="center">
  <img src="assets/training-loop.gif" width="900px" alt="Animated diagram of one training step: the editor agent proposes bounded edits, the lint gate checks them, the candidate is committed, parallel rollout workers run held-out val tasks, score.py produces a number, and the verdict either keeps the edit (branch advances) or rejects it (git reset --hard, edit goes to the rejected buffer)">
</p>

1. An editor agent proposes a small set of bounded edits to `SKILL.md`,
   grounded in failure and success evidence from training tasks.
2. The manager applies them, runs the lint gate, and commits the
   candidate.
3. Parallel rollout workers run the candidate against a held-out
   validation set. `score.py` turns the outputs into a number,
   deterministically by default, or through a structured LLM judge for
   suites that opt into `judge` mode.
4. If the candidate is strictly better, the branch advances. Otherwise
   `git reset --hard`, and the rejected edit text goes into a buffer
   future editors read.
5. Every step lands in `results.tsv`. Every E steps, an epoch boundary runs
   a slow-update regression check and refreshes the optimizer's own memory
   (`META.md`).

The manager is expected to die (context exhaustion, sleep, API errors).
`train.sh` relaunches it until a terminal state exists, and the resume
ritual in `PROGRAM.md` §0 reconstructs everything from disk. Training runs
live on branches named `train/<skill-name>/<tag>`.

The guardrails are structural, not aspirational: the editor never sees val
tasks, the manager cannot modify the harness or the task suite, scores
never compare across gate modes or rubric versions (every `scores.json`
is stamped with a hash of the scoring contract; the gate refuses
mismatches), and post-run audits (`harness/audit_run.py`) grep for
leakage and rubric drift.

## What a run produces

- **The trained skill**, at `skills/<skill-name>/SKILL.md` on the
  `train/<skill-name>/<tag>` branch. Best checkpoints are git-tagged; every
  accepted step is a commit you can diff to see exactly what the training
  changed and why.
- **`results.tsv`** — one append-only row per step: commit, epoch, step,
  gate mode, val scores (mixed/hard/soft), rollout count, keep/discard
  status, and a one-line description of the edits tried.
- **`runs/<tag>/`** — per-step artifacts: rollout workspaces, editor
  transcripts, score reports, and finally `TERMINAL`, a one-line
  `<state>: <reason>` file (`success`, `no-progress`, `blocked`, ...)
  that is the only way a run ends.

### What it costs

The test suite and all mock rollouts are free — no model calls at all. The
meta-eval makes a few editor calls per step through `claude -p`. A real
training run is the expensive mode: each step is roughly one editor call
plus K × |val| rollouts through your agent CLI, so an overnight run means
hundreds of rollouts on your existing subscription. Size K, the val set,
and `--max-steps` accordingly; there is no separate API bill.

## Bring your own task suite

This repo is the framework only (see `PROGRAM.md` §8). Task suites and
the skills they train live in your working copy; `tasks/` and `skills/`
are gitignored here by design.

**Step 1: find the tasks.** The best training tasks are the requests you
already make of your agent over and over, especially the ones it gets
wrong. Write those down as prompts, and for each one decide what a correct
answer must contain. That second part is the work: a task without a
checkable outcome cannot gate an edit, and nothing in this framework can
invent it for you.

**Step 2: shape the suite.** The bundled
[`examples/mock-demo`](examples/mock-demo) is a complete working suite to
copy as a starting point. A suite is a directory:

```
tasks/<skill-name>/
  train.jsonl        tasks the editor learns from
  val.jsonl          held-out gate tasks; the editor NEVER sees these
  test.jsonl         optional final held-out set
  scoring.md         scoring contract: suite config (first fenced json
                     block), smoke_tools, example-template packaging rules
  rubric.py          score(task, workdir, mode) -> {hard, soft, checks}
                     (only needed for rubric-mode scoring)
  requirements.txt   suite-specific deps (installed into .venv)
  refs/              any reference files tasks list under "files"
```

Each line of a `.jsonl` file is a task: `{"id": ..., "prompt": ...,
"files": [...], "scoring": {...}}`. Five scoring modes are built in:
`exact` (regex on output), `checklist` (required substrings), `command`
(exit code), `rubric` (your `rubric.py`), and `judge` (an LLM judge, below).
The first four are deterministic and make no LLM calls.

### LLM-judged suites

Some skills cannot be scored deterministically: UI design, how human a
text reads, the quality of a review. The `judge` mode asks an LLM for a
**structured verdict** and feeds the same hard/soft numbers into the
unchanged paired gate. It is a separate way to measure, not a replacement:
a suite picks its mode in `scoring.md`.

```
tasks/<skill-name>/
  judge.md           the judge prompt for THIS skill: criteria, weights,
                     what "pass" means (part of the scoring contract)
  scoring.md         {"default_mode": "judge", "judge": {"samples": 3, ...}}
  train.jsonl        each task may carry "reference": "<path>" (a good
                     output) and "judge_inputs": ["<workdir globs>"]
```

The judge needs a definition of *good*, and there are two ways to give it
one, in order of preference:

1. **A dataset.** Give each task a `reference`: what a good output looks
   like for that prompt. The judge scores closeness to the reference, so
   the loop climbs toward a concrete target exactly like a deterministic
   suite. This is the default and the one to reach for first.
2. **A rubric only.** No reference; `judge.md` alone describes the ideal.
   This works only as well as the rubric is written.

`harness/judge.py --check --suite tasks/<skill>` reports which mode each
task runs in, warns about rubric-only tasks, and verifies the key, the
dependency, and every reference path. `run_task.py --smoke` runs the same
check for judge suites.

The judge model is MiniMax M3 through its OpenAI-compatible API, driven by
the LangChain SDK (`with_structured_output` over the verdict schema,
`method="function_calling"`, the only method M3 honours; think-stripped
content JSON as the fallback). Nothing is truncated: judge inputs go in
whole and no output cap is sent unless the suite sets `max_tokens`. Put
the key in the repo `.env` as `MINIMAX-API-KEY=...` (or export
`MINIMAX_API_KEY`).
Verdicts are cached per workspace in `judge.json`, `judge.md` is hashed
into `rubric_version`, and `examples/judge-demo` is a complete judged suite
that trains a skill-review skill against 16 synthetic flawed skills.

The skill being trained lives at `skills/<skill-name>/SKILL.md`, with
optimizer memory in `META.md` beside it.

## Launch a real training run

```bash
# One-time: verify tooling against your suite
.venv/bin/python harness/run_task.py --smoke --suite tasks/<skill> --backend claude

# Launch; keeps the manager alive until a terminal state.
# The third argument picks the agent: claude | codex | copilot | cursor | opencode
# Optional args 4-6: manager model, rollout model, reasoning effort.
./train.sh <skill-name> <tag> claude
./train.sh <skill-name> <tag> codex gpt-5.3
./train.sh <skill-name> <tag> cursor claude-sonnet-5-low
```

Before a real run, copy `runs/CONFIG_TEMPLATE.md`'s JSON into
`runs/<tag>/config.json` and adjust it for your suite. The manager reads
`PROGRAM.md` and takes it from there; it will not stop until
`runs/<tag>/TERMINAL` exists.

## Layout

```
PROGRAM.md            manager agent instructions; the whole loop is here
train.sh              relaunch wrapper; keeps the manager alive
prompts/              worker prompt templates (editor, ranker, rollout, ...)
harness/              the training engine; read-only during training
examples/mock-demo/   complete example suite; template + meta-eval fixture
examples/judge-demo/  LLM-judged suite: skill-review trained on flawed skills
runs/CONFIG_TEMPLATE.md  canonical run config
tests/                deterministic framework tests + meta_eval.py
tasks/<name>/         your task suites (gitignored; yours to provide)
skills/<name>/        SKILL.md (trainable) + META.md (optimizer memory)
runs/<tag>/           per-run artifacts (gitignored)
results.tsv           training log (untracked)
```

`harness/` and `tasks/*/val.jsonl` are ground truth: the manager must never
modify them, and the editor must never see val task contents.

Rollout batches go through `harness/rollout_batch.py`: N parallel
private-workspace workers with heartbeat supervision (the dispatcher kills
a stale worker and requeues it once).

## Contributing

Harness improvements, new scoring modes, new agent backends, and doc fixes
are all welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). The one rule:
`tests/` must stay deterministic and LLM-free.

---

<div align="center">
<sub>MIT · See <a href="LICENSE">LICENSE</a></sub>
</div>
