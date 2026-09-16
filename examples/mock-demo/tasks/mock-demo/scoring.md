# Scoring contract: mock-demo

Suite config (read by `harness/score.py` from the first fenced json block):

```json
{
  "default_mode": "checklist",
  "mixed_weight": 0.5,
  "smoke_tools": []
}
```

Every task runs on the mock backend (`run_task.py --backend mock`), which
emits one `PASS:<rule-id>` line per satisfied rule and a final
`RESULT: solved` or `RESULT: unsolved`. Each task's checklist requires its
`PASS:` lines plus `RESULT: solved`, so `soft` gives partial credit on
multi-rule tasks and `hard` is all-or-nothing.

A rule is satisfied when the skill text contains the rule id (normalized),
or when any single skill line matches every regex in the task's
`match_regex` concept group. The regex path is what makes planted-defect
recovery robust to phrasing: a rediscovered rule counts even when worded
differently, while vague edits still fail.

`noise` is 0 across this suite; scores are fully deterministic per seed.
