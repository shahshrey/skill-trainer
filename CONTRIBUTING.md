# Contributing to skill-trainer

Thanks for wanting to make the trainer better. A few ground rules keep it
trainable.

## Dev setup

```bash
uv venv .venv && uv pip install -r requirements-dev.txt -p .venv/bin/python
.venv/bin/python -m pytest tests/
```

All tests are deterministic and make **no LLM calls** — that's a hard
invariant, not a current state. A PR that adds a test needing an API key or
network access will be asked to mock it.

## What's welcome

- **Harness improvements** — better scoring aggregation, gate statistics,
  rollout supervision, resume robustness.
- **New agent backends** — `harness/run_task.py` has a per-backend command
  table; adding one is usually a few lines plus a smoke check.
- **New scoring modes** — `harness/score.py` currently ships `exact`,
  `checklist`, `command`, and `rubric`.
- **Prompt template improvements** — `prompts/` is part of the framework;
  changes should explain what failure mode they fix.
- **Docs** — anything that shortens the path from clone to first training
  run.

## What belongs elsewhere

Task suites and trained skills live in *your* working copy, not in this
repo — `tasks/` and `skills/` are gitignored by design (see `PROGRAM.md`
§8). A test file belongs in `tests/` only if it exercises `harness/` code
with no dependency on any specific task.

## Ground truth is sacred

The core promise of the trainer is that the thing being optimized cannot
touch the thing doing the measuring. Changes that let the manager modify
`harness/`, read `val.jsonl`, or compare scores across gate modes break
the whole design and will be declined regardless of how convenient they
are.

## PRs

- Run `pytest tests/` before opening.
- Keep changes focused; explain the failure mode or workflow the change
  addresses.
- New harness behavior needs a deterministic test beside it.
