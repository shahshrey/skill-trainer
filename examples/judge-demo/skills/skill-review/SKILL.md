---
name: skill-review
description: Reviews and validates agent skills against best practices. Use when asked to review a skill, check a skill, validate a skill, or judge whether a SKILL.md is well written.
---

# Skill Review

## Overview

Validates an agent skill package (a directory holding `SKILL.md` and
optional `references/`, `scripts/`, `assets/`) and reports what should
change.

## Review process

1. Read `SKILL.md` and every other file in the skill directory.
2. Check the frontmatter: it must exist and carry `name` and
   `description`.
3. Read the body for clarity and length (under 500 lines).
4. Report findings in the format below.

## Report format

```
## Skill Review: [skill-name]

### Summary
[1-2 sentence overall assessment]

### Structure
[✓/✗] Directory organization
[✓/✗] File presence

### Frontmatter
[✓/✗] name validation
[✓/✗] description validation

### Description Quality
**Score**: [Strong / Adequate / Needs Work]
**Issues**: [List specific problems]

### Body Analysis
**Line count**: [X] lines
**Token efficiency**: [Good / Could trim]

### Anti-Patterns Found
- [Issue] — Location: `file:line`

### Recommendations
1. [Actionable fix]
```

<!-- PROTECTED:SLOW_UPDATE:START -->
## Conventions (slow update)

Structural conventions live in this block. The slow-update pass owns it;
per-step editors must not modify anything between the protected markers.
<!-- PROTECTED:SLOW_UPDATE:END -->
