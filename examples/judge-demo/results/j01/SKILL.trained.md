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
3. Validate the description:
   - Length ≤1024 chars
   - Has 'Use when…' trigger clause
   - Uses third-person/imperative voice (no 'you')
   - States a default whenever options exist
3. Check body length (under 500 lines) and defect presence.
4. Scan for defects:
   - Name: invalid chars, reserved words (claude/skill/mcp), directory mismatch
   - References: Windows paths, nested chains, missing scripts
   - Terms: inconsistent usage, obvious explanations, magic numbers
   - Voice: second-person body text
   - Prerequisites: undocumented binaries (grep config for tool names)

   - Structure: extraneous files (README.md, CHANGELOG.md, EXAMPLES.md in root)

   - Defaults: option lists ('use X or Y or Z') without stated preference
5. Report findings in the format below. Every finding must quote the offending text and cite its location (file:line). Do not flag aspects absent from the defect list above.

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


For description defects, include a corrected YAML block:
```yaml
description: [fixed text]
```
```

<!-- PROTECTED:SLOW_UPDATE:START -->
## Conventions (slow update)

**Terms — synonym proliferation: how to scan**
Build an explicit list of every distinct noun the body uses for each core concept (the thing being scheduled, the agent role, the configuration unit, etc.). If any concept has 3 or more names, or if names shift between sections without a stated equivalence (e.g., "tasks" in the overview, "jobs" in the usage section, "entries" in the config section), flag `inconsistent-terms`. Do not rely on skimming — enumerate the terms mechanically before deciding.

**Name — character-by-character directory match**
Compare the `name:` frontmatter value to the parent directory name one character at a time. A trailing suffix difference (e.g., `cron-schedule` vs `cron-scheduler`) is a mismatch. So are prefix differences and internal differences. Do not accept "close enough" — every character position must be identical.

**References — follow nested chains**
Open every file inside `references/`. For each file, check whether it contains any further file paths or URLs presented as required reading or dependencies. If it does, flag `nested-refs`. One level of traversal is required; you must actually read each reference file, not just list its name.

**Defaults — when NOT to flag**
Flag `options-no-default` only when ALL listed alternatives apply in the same runtime environment and the document states no preference. Do NOT flag:
- Platform-specific alternatives where each branch applies only on a different OS (e.g., `ps aux` on Linux vs `Activity Monitor` on macOS)
- Conditional alternatives where the stated condition already determines which one to use
If a reader would use at most one option given their environment or context, it is not a Defaults violation.
<!-- PROTECTED:SLOW_UPDATE:END -->
