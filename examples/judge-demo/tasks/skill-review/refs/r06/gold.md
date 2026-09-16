## Skill Review: changelog-writer

### Summary
Three defects were planted: a reserved word in the skill name, edge cases documented before the overview, and an unexplained magic number in the grouping limit.

### Planted defects (must all be found)
1. **name-reserved** — SKILL.md frontmatter: The name field contains `claude-changelog-writer`; names must not include "claude" or "anthropic" to avoid confusion with Anthropic-authored tools.
2. **no-quick-start** — SKILL.md document structure: The "Edge Cases and Squash Merge Handling" section (30+ lines) appears at the very top, before the Overview and Quick start sections; this buries actionable guidance under implementation details, making it hard for readers to get started quickly.
3. **magic-number** — SKILL.md Category defaults section: The statement "Group at most 17 PRs per section" provides no justification; readers don't know why 17 was chosen or whether the number is arbitrary, a performance limit, or a UX heuristic.

### What is clean (a good review does NOT flag these)
- Description includes a clear trigger clause ("Use when preparing a release")
- Category rules are well-defined with sensible defaults
- Example demonstrates realistic output format
- All configuration parameters are documented

### Expected recommendations
1. Rename the skill: change the name from `claude-changelog-writer` to `changelog-writer`.
2. Restructure the document: move "Edge Cases and Squash Merge Handling" to the end (as an appendix or advanced reference section), so the Overview and Quick start appear immediately after the frontmatter for readers who don't need edge case details yet.
3. Add context to the magic number:
```
Group at most 17 PRs per section (a balance between completeness and readability; larger groups are hard to scan in a single viewport).
```
