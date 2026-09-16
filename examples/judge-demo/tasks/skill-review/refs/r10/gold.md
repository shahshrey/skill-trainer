## Skill Review: markdown-lint

### Summary

Three defects impair this linting guide: the name contains an invalid space character, basic Markdown concepts are explained to agents that already know them, and a referenced helper script is missing.

### Planted defects (must all be found)

1. **name-invalid** — SKILL.md frontmatter line 2: The skill name is `markdown lint` (with a space). Skill names must match the pattern [a-z0-9-].

2. **obvious-explanation** — SKILL.md lines 8-9: A paragraph explains what Markdown headings are and how the hash-symbol syntax works. This is fundamental knowledge that competent agents already possess.

3. **missing-script** — SKILL.md line ~37: The Quick Start section calls `scripts/fix_tables.py`, but that file does not exist in the repository. The `scripts/lint.py` file is present, but `fix_tables.py` is missing.

### What is clean (a good review does NOT flag these)

- Description clearly states purpose and includes a "Use when" trigger clause
- Setup instructions are concrete with working npm and JSON examples
- Common issues section lists realistic linting patterns
- The lint.py script exists and is properly structured
- File layout (SKILL.md plus scripts/) follows conventions

### Expected recommendations

1. Rename the skill: change the frontmatter name from `markdown lint` to `markdown-lint`.

2. Remove the Markdown headings explanation paragraph: it adds noise without value for agent understanding.

3. Either create the missing script `scripts/fix_tables.py` or replace references with `scripts/lint.py`, which already exists.
