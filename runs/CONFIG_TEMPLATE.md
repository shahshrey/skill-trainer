# Canonical run config template (distilled from runs sql01-sql08)

Copy the JSON into `runs/<tag>/config.json` before launching. Every field
pattern below earned its place in a live run; the notes say why.

```json
{
 "skill": "<skill-name>",
 "tag": "<tag>",
 "backend": "claude | codex | cursor | copilot | mock",
 "model": "<manager model>",
 "rollout_model": "<rollout model. NEVER change mid-tag: changing it makes every score incomparable and forces a fresh tag + re-baseline>",
 "effort": "max (copilot only)",
 "model_note": "Name the EXACT worker CLI invocation. claude: every worker claude -p MUST carry --model <m> (headless claude ignores interactive defaults). copilot: copilot -p \"$(cat <filled>)\" --model <m> --effort max --allow-all-tools --no-color. Rollouts inherit SKILL_TRAINER_MODEL/EFFORT from train.sh; never override per-call.",
 "K": 2,
 "E": 8,
 "L": 5,
 "M": 8,
 "concurrency": {"cheap": 6, "full": 4},
 "boundary": "Natural-language contract the manager obeys literally. Bounded validation runs: 'after logging the results.tsv row for STEP N, write TERMINAL <exhausted: ...> and stop.' Marathons: a wall-clock deadline in UTC. Never launch without one.",
 "gate_modes": {"step": "cheap", "epoch": "cheap-or-full per suite cost"},
 "gate_note": "Run-specific gate instructions: paired gate per PROGRAM §4f with fresh 3-pass baseline as the reference set; primary/secondary suite names; mixed weight; any mechanism this run exists to exercise (§4d2 targeted-fix verification, §4f near-miss retest, §4g2 salvage, §4g3 rewrite). State the run's HYPOTHESIS so the manager optimizes for the test, not the score.",
 "deploy_mode": "package",
 "timeouts": {"cheap": 600, "full": 1800}
}
```

Launch:

```bash
nohup ./train.sh <skill> <tag> <agent-cli> <manager-model> <rollout-model> [effort] \
  >> runs/<tag>/train.log 2>&1 & disown
```

Pre-flight (every launch): branch `train/<skill>/<tag>` created and checked
out; `run_task.py --smoke` passes; no other train.sh running (`pgrep`);
suite build calibrates (`tasks/<suite>/build_suite.py` exit 0).
