---
name: markdown lint
description: Lint and auto-fix common formatting issues in Markdown documents, including heading hierarchy, table alignment, and link validation. Use when enforcing consistent documentation style across a project or repository.
---

## Overview

Markdown linting ensures that documentation is readable, consistent, and free of common formatting errors. This skill covers using linters to catch issues that are easy to miss in manual review: broken references, inconsistent spacing, and improperly nested headings.

## What Are Markdown Headings?

Markdown headings are created using hash symbols (#) at the start of a line. A single hash (#) creates an H1 heading (the largest), two hashes (##) create an H2 heading, and so on up to six hashes for H6. Headings organize content into a hierarchy and are used by screen readers and table-of-contents generators. They should follow a logical structure where you never skip levels—you cannot jump from H1 directly to H3. Headings can contain formatting like bold or italics, but this should be used sparingly.

## Setup

Install markdownlint-cli2 for modern linting:

```bash
npm install -D markdownlint-cli2
```

Configure rules in `.markdownlint.json`:

```json
{
  "extends": "markdownlint/style/prettier",
  "md003": {"style": "consistent"},
  "md013": {"line_length": 100}
}
```

## Common Issues

The linter catches these patterns automatically:

- Missing or malformed link text `[link](url)` syntax
- Inconsistent heading hierarchy (H1 → H3 without H2)
- Trailing whitespace and inconsistent spacing
- Table rows with misaligned pipes `|`
- List markers mixing bullets and numbers

## Quick Start

Run the linter on all Markdown files:

```bash
markdownlint-cli2 "**/*.md"
```

Auto-fix issues using the helper script:

```bash
scripts/fix_tables.py --dry-run docs/
```

Then apply fixes:

```bash
scripts/fix_tables.py docs/
```

## Best Practices

- Run linting in CI/CD to catch issues before merge
- Fix linting errors early rather than accumulating debt
- Use consistent heading structure across all documents
- Validate all external links monthly

## Customization

Override specific rules for special cases:

```markdown
<!-- markdownlint-disable MD013 -->
This paragraph exceeds 100 characters but is necessary for readability in this context.
<!-- markdownlint-enable MD013 -->
```

## Checklist

- [ ] Lint configuration committed to repository
- [ ] CI checks run markdownlint on all PRs
- [ ] All headings follow hierarchy rules
- [ ] No orphaned or empty sections
- [ ] All links validate successfully
