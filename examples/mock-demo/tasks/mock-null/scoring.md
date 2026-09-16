# Scoring contract: mock-null

Suite config (read by `harness/score.py` from the first fenced json block):

```json
{
  "default_mode": "checklist",
  "mixed_weight": 0.5,
  "smoke_tools": []
}
```

Pure-noise null suite: every task has empty `requires` and `noise: 0.5`,
so the mock backend's outcome is a seeded coin flip that no skill edit can
influence. A correct trainer run on this suite accepts ~nothing and ends
in no-progress; an optimizer that "improves" here is fitting noise.
