## Skill Review: git-release

### Summary
Three defects were planted: reference documentation is unnecessarily nested across three files, a time-sensitive conditional with a March 2026 cutoff, and inconsistent terminology for tags and versions throughout the body.

### Planted defects (must all be found)
1. **nested-refs** — SKILL.md line 18 and references/release-process.md line 20: Release process documentation links to versioning rules, but versioning rules content should live directly where referenced, not nested two levels deep; readers must jump between three files to find semver bump criteria
2. **time-sensitive** — SKILL.md lines 22-23: conditional "Before March 2026 use the legacy gh release syntax" will become obsolete and confusing after that date; all documentation should be version-agnostic or use version checks instead
3. **inconsistent-terms** — SKILL.md lines 8, 13, and 21: uses "release tags" (line 8), "version tag" (line 21), and "release tag" (line 13) to refer to the same Git tag concept; terminology must be consistent

### What is clean (a good review does NOT flag these)
- Frontmatter is properly formatted with name, description, and trigger clause
- Prerequisites are realistic and well-specified
- Quick Start section provides clear command examples
- Error handling and validation steps are documented
- File structure and path conventions are correct

### Expected recommendations
1. Consolidate versioning guidance: Move the semver bump rules from nested files into a single references/versioning-rules.md that is the single source of truth, and link to it only once from SKILL.md's Versioning strategy section
2. Remove the dated conditional. Replace "Before March 2026 use the legacy gh release syntax" with something version-agnostic: "Older GitHub CLI versions require different command-line flags; check your gh version with `gh --version` before running"
3. Use consistent terminology throughout. Choose one term (e.g., "version tag" or "release tag") and use it consistently. Update lines 8, 13, and 21 to use the same term everywhere
