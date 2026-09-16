## Skill Review: sql-migrate

### Summary

Four defects undermine this migration guide: a nested reference chain that creates unnecessary indirection, missing defaults for tool selection, time-sensitive language that will require updates, and imperative voice in the body that violates skill conventions.

### Planted defects (must all be found)

1. **nested-refs** — SKILL.md line ~28 and references/migration-checklist.md: SKILL.md links to references/migration-checklist.md, which in turn links to references/locking-rules.md. The table-locking guidance should appear only in locking-rules.md; this nested chain adds indirection without improving clarity.

2. **options-no-default** — SKILL.md line ~16: The Migration Frameworks section lists "Alembic, Flyway, or raw SQL scripts" without stating which is the default or recommended choice for the team.

3. **body-second-person** — SKILL.md lines 24, 30, and 41: Body text uses second-person imperative voice ("You should choose", "You should plan", "You should always have"), violating the third-person policy.

4. **time-sensitive** — SKILL.md line ~27: The text contains "Until June 2026 the staging cluster runs Postgres 14", a dated conditional that will become stale and misleading after June 2026.

### What is clean (a good review does NOT flag these)

- Description has a clear "Use when" trigger clause and third-person voice
- All referenced files in the checklist exist and are properly structured
- Code examples are concrete and reversible with matching forward/rollback SQL
- Skill name, frontmatter metadata, and directory name all align correctly
- Structure includes overview, principles, examples, techniques, and a working checklist

### Expected recommendations

1. Flatten the reference chain: move the locking-rules content directly into SKILL.md or remove the intermediate reference to migration-checklist.md.

2. Add a default tool recommendation: "Alembic is recommended for applications with version control; use Flyway for Java-heavy stacks; raw SQL scripts for simpler deployments."

3. Replace second-person voice with third-person: Change "You should choose" to "Choose", "You should plan" to "Plan", and "You should always have" to "Always have".

4. Replace time-sensitive language with version-agnostic guidance: Remove "Until June 2026" and instead reference the [Postgres versioning policy](link) or state "Test on the staging cluster version before production deployment."
