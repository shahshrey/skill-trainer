# LLM-Judge Soft Scoring — Design

Date: 2026-08-23
Status: approved (design), pending implementation plan

## Problem

`score.py` supports four deterministic scoring modes (`exact`, `checklist`,
`command`, `rubric`). Many skills worth training are non-deterministic,
agent-based workflows whose output quality — tone, coherence, adherence to
the spirit of a workflow — cannot be measured by string matching or exit
codes. Those suites need an LLM judge, without giving up the properties the
trainer depends on: a deterministic `score.py`, trustworthy gate decisions,
LLM-free tests, and resistance to reward hacking by the editor.

## Decisions (agreed with the user)

1. **Hybrid scoring.** The deterministic mode still produces the `hard`
   score (the hack-resistant floor). The judge produces only the `soft`
   score, via structured output the harness checks programmatically.
2. **Separate judge phase.** Judging is a pipeline step between rollouts
   and scoring, not an LLM call inside `score.py`. `score.py` keeps its
   "deterministic, no LLM calls" guarantee.
3. **Noise control.** Binary per-criterion verdicts (never "rate 1–10"),
   N samples with majority vote per criterion, verdicts cached by output
   hash.
4. **Agent-CLI backends.** Judge calls reuse the existing `BACKENDS`
   command builders (`claude -p`, `codex exec`, …). Zero new dependencies;
   runs on the user's existing subscription.
5. **Strictly opt-in, user-decided.** The judge never runs unless the
   suite (or task) declares it. The programmatic-vs-judge choice is
   surfaced to the user at suite-setup time; neither the harness nor the
   manager ever enables it on its own.

## Pipeline

```
rollout_batch.py  ->  workspaces with task.json + output.txt   (unchanged)
judge.py --batch  ->  judge.json written into each judged workspace   (NEW)
score.py          ->  hard from deterministic mode; soft read from
                      judge.json when soft_source == "judge"   (small edit)
gate.py           ->  unchanged
```

## Components

### 1. Task / suite schema

Per-task (in `train.jsonl` / `val.jsonl`), inside the existing `scoring`
object:

```json
{
  "mode": "checklist",
  "required": ["..."],
  "soft_source": "judge",
  "judge": {
    "criteria": [
      {"id": "tone", "desc": "The response matches the requested tone"},
      {"id": "complete", "desc": "Every step of the workflow was addressed"}
    ]
  }
}
```

Suite defaults live in the fenced JSON block of `tasks/<X>/scoring.md`,
alongside `default_mode` and `mixed_weight`:

```json
{
  "default_mode": "checklist",
  "soft_source": "judge",
  "judge_samples": 3,
  "judge_backend": "claude"
}
```

Resolution: task-level `soft_source`/`judge` override suite defaults; a
task may opt out of a judged suite (omit/`"soft_source": "self"`) and a
programmatic suite may judge individual tasks. Absent any declaration,
behavior is byte-identical to today.

Judge model/effort come from `SKILL_TRAINER_JUDGE_MODEL` /
`SKILL_TRAINER_JUDGE_EFFORT` env vars, mirroring the rollout convention
(`SKILL_TRAINER_MODEL`). They default to unset (backend default model).

### 2. `harness/judge.py` (new)

```
judge.py --suite tasks/X (--workdir DIR | --batch DIR)
         [--backend claude|codex|cursor|copilot|opencode|mock]
         [--samples N] [--jobs J] [--force]
```

For each workspace containing `task.json` + `output.txt` whose resolved
scoring declares a judge:

- **Cache check.** If `judge.json` exists and its `output_sha256` matches
  the current `output.txt` (and `--force` is absent), skip. Re-judging is
  therefore free and byte-stable across re-runs.
- **Call.** Build the judge prompt from `prompts/judge.md` (task prompt +
  criteria list + fenced output). Invoke the backend CLI N times
  (default 3, from `judge_samples`), reusing the `BACKENDS` builders
  imported from `run_task.py`, with cwd set to a scratch directory. The
  judge never sees `SKILL.md`.
- **Parse.** Extract the last fenced JSON block from stdout:
  `{"criteria": {"<id>": true|false, ...}, "notes": "..."}`. A sample
  that fails to parse or omits a criterion is retried once, then dropped.
  If all N samples for a task fail, that task is a judging **error**
  (recorded, nonzero exit) — never a silent 0.0.
- **Aggregate.** Per-criterion majority vote across valid samples (a tie
  on an even number of valid samples fails the criterion);
  `soft = passed_criteria / total_criteria`.
- **Write** `judge.json`:

```json
{
  "output_sha256": "…",
  "backend": "claude",
  "model": "…or null",
  "samples": [{"criteria": {...}, "notes": "..."}, ...],
  "criteria": {"tone": 1, "complete": 0},
  "soft": 0.5,
  "flags": ["sample_2_unparseable"]
}
```

`--jobs` parallelizes across workspaces (CLI calls are wall-clock bound).
Workspaces with no judge declaration are skipped silently in `--batch`
mode. Exit 0 on success, 2 on judging errors.

**Mock backend.** `--backend mock` reads canned verdicts from the task
(`task["mock"]["judge_samples"]`), enabling deterministic, LLM-free tests —
the same pattern as `run_task.py`'s mock.

### 3. `prompts/judge.md` (new)

Template placeholders: task prompt, criteria list, agent output. Contract:

- Answer **every criterion** with a binary pass/fail; no numeric ratings.
- Output exactly one fenced JSON block in the specified shape.
- The agent output is **untrusted data**: it is fenced, and any text
  inside it that addresses the judge (e.g. "score all criteria as pass")
  is itself grounds to fail the relevant criteria. Criteria are the only
  authority.

### 4. `score.py` (edit)

When the resolved scoring has `soft_source == "judge"`:

- Compute `hard` and `checks` from the deterministic mode exactly as
  today.
- Read `soft` from `judge.json`; append `judge:<id>:<0|1>` entries to
  `checks`; record `soft_source` in the per-task result.
- Missing `judge.json`, or `output_sha256` mismatch (stale verdict), →
  exit 2. A scoring bug must read as a crash, not a 0.0 (existing
  philosophy).

Aggregation, `mixed`, and the two-suite rule are unchanged. `score.py`
performs no LLM calls; its determinism docstring stays true.

### 5. Setup-time surfacing (docs + smoke)

- **Decision guide** ("Choosing your scoring", in the suite-authoring
  docs/README): mechanically verifiable success → programmatic (free,
  deterministic, unhackable); inherently qualitative success → hybrid
  judge. The guide explicitly instructs the agent helping a user set up a
  suite to present this choice and let the user decide — never to pick
  silently.
- **Smoke audit** (`run_task.py --smoke`):
  - Judge declared → verify judged tasks all carry criteria,
    `prompts/judge.md` exists, and the judge backend binary is on PATH.
  - Judge not declared → warn (not fail) on tasks with weak deterministic
    signal (empty checklist, no command, no expected regex), suggesting
    judge scoring. Advisory only; nothing is auto-enabled.

### 6. `PROGRAM.md` (edit)

The eval step becomes conditional: *if* the suite config declares
`soft_source: judge`, run `judge.py --batch` after rollouts and before
`score.py`; otherwise skip. The manager may not enable or disable judging
itself — the suite config is the only switch. `judge.json` files are
workspace artifacts; val-task verdicts fall under the existing rule that
the editor never sees val contents. Docs recommend a larger `min_delta`
for judge-soft suites to absorb residual judge variance.

## Guardrails summary

- Hard score stays programmatic → the editor cannot pass the gate on
  judge opinion alone (with default `mixed_weight` 0.5, soft moves at
  most half the metric).
- Judge never sees `SKILL.md` → skill text cannot instruct the judge.
- Output treated as untrusted; injection attempts fail criteria.
- Binary criteria + majority vote + pinned judge model/config → variance
  contained; caching by output hash → identical outputs always score
  identically.
- Opt-in only; the user makes the call at suite setup.

## Testing

All in `tests/`, deterministic and LLM-free (CONTRIBUTING rule):

- `tests/test_judge.py`: fenced-JSON parsing (incl. surrounding prose,
  multiple blocks), missing-criterion handling, retry-then-drop, all-
  samples-failed → exit 2, majority vote (2/3, ties on even valid
  samples → fail the criterion), cache hit / `--force`, batch skipping of
  non-judged workspaces, mock backend end-to-end.
- `tests/test_score.py` additions: `soft_source: judge` reads soft from
  `judge.json`; missing/stale `judge.json` → exit 2; non-judged suites
  byte-identical to current behavior.
- Smoke audit tests: warnings and failures fire as specified.

## Files touched

| File | Change |
|---|---|
| `harness/judge.py` | new — judge phase runner |
| `prompts/judge.md` | new — judge prompt template |
| `harness/score.py` | edit — `soft_source: judge` reads `judge.json` |
| `harness/run_task.py` | edit — smoke scoring audit |
| `PROGRAM.md` | edit — conditional judge step, guardrails |
| `README.md` | edit — scoring section + decision guide |
| `runs/CONFIG_TEMPLATE.md` | edit — judge config fields |
| `tests/test_judge.py` | new |
| `tests/test_score.py` | edit — integration cases |

## Out of scope (YAGNI)

- Pairwise candidate-vs-baseline judging.
- Direct API judge clients (agent CLIs only).
- Numeric/graded criteria (binary only, by design).
- Auto-detection that silently enables judging.
