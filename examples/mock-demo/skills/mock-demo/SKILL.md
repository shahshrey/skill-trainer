---
name: mock-demo
description: Reference skill for the trainer's meta-evaluation. Produces short explainer documents and looping demo animations, scored by the deterministic mock backend. Use when validating the training loop itself rather than training a real skill.
---

# mock-demo

Reference skill for `tests/meta_eval.py`. The mock backend scores a task by
checking that the rules below survive in this file, so every rule line is
load-bearing: ablate one and the tasks that require it start failing with
symptoms in their output.

## Rules

- Cite your sources for every factual claim.
- When options exist, state a default and move on.
- Verify before delivery: open the artifact and look at it.
- Use one term per concept throughout a document.
- Prefer examples over prose when explaining behavior.
- A seamless loop is mandatory: the first and last frames must match.
- Match canvas dimensions to the spec exactly before rendering.
- Sync same-stage motion: parallel elements depart and arrive together.

<!-- PROTECTED:SLOW_UPDATE:START -->
## Conventions (slow update)

Structural conventions live in this block. The slow-update pass owns it;
per-step editors must not modify anything between the protected markers.
<!-- PROTECTED:SLOW_UPDATE:END -->
