# mock-demo: the bundled example suite

A complete, self-contained task suite and reference skill, used two ways:

1. **Meta-evaluation.** `tests/meta_eval.py` copies this directory into its
   worktree so `planted` (ablate a rule, measure recovery) and `null`
   (pure-noise suite, measure false accepts) run on a fresh clone with no
   setup. Rollouts use the mock backend; only the editor calls a model.
2. **Template.** This is the shape of a real suite. To start your own:

   ```bash
   cp -r examples/mock-demo/tasks/mock-demo tasks/<your-skill>
   cp -r examples/mock-demo/skills/mock-demo skills/<your-skill>
   ```

   then replace the mock-backend fields (`requires`, `match_regex`,
   `failure_hints`, `noise`) with real prompts and one of the four scoring
   modes (`exact`, `checklist`, `command`, `rubric`). Your copies stay out
   of git: `tasks/` and `skills/` are gitignored by design (PROGRAM.md §8).

## Layout

```
skills/mock-demo/SKILL.md    reference skill; every rule line is load-bearing
tasks/mock-demo/             the trainable suite (deterministic, noise 0)
  train.jsonl                8 single-rule + 2 two-rule tasks
  val.jsonl                  one task per rule; ablating a rule fails exactly one
  scoring.md                 checklist scoring against the mock backend's output
  failure_classes.md         symptom-class -> mechanism guide for the editor
tasks/mock-null/             pure-noise suite for the null test (noise 0.5)
```

The invariants that make this suite work (rule ids resolvable in the skill
text, every canonical rule line satisfying its own `match_regex` group,
failure hints never leaking rule text) are enforced by
`tests/test_example_suite.py`.
