## Skill Review: i18n-extract

### Summary
Three defects found: a Windows backslash path in the quick start command, nested reference files where pluralization rules are split across documents, and a description missing a "Use when" trigger clause.

### Planted defects (must all be found)
1. **windows-path** — SKILL.md Quick start section, line ~12: The command shows `scripts\extract.py` using a backslash, which is a Windows path separator and breaks on Unix-like systems where forward slashes are required.
2. **nested-refs** — SKILL.md line ~22 links references/formats.md, which line ~12 links references/plural-rules.md: Pluralization rule content is housed only in plural-rules.md; formats.md merely references it rather than containing the needed information, creating a nested reference problem.
3. **desc-no-trigger** — SKILL.md frontmatter description: The description states what the skill does but lacks any "Use when" clause or conditional trigger, leaving readers uncertain about when to apply it.

### What is clean (a good review does NOT flag these)
- Description has clear, third-person language explaining the extraction functionality
- frontmatter name is valid lowercase with hyphens
- All referenced files exist and are accessible
- Code blocks and command syntax (aside from the path) are well-formed
- Requirements section properly documents Python version dependencies

### Expected recommendations
1. Change the Quick start command to use forward slashes: `python scripts/extract.py --source src/ --output locales/ --format json`
2. Move the pluralization content from references/plural-rules.md directly into references/formats.md, or restructure so the primary reference (formats.md) contains the critical pluralization information needed for understanding the extraction process.
3. Add a trigger clause to the description:

```yaml
description: Extracts translatable strings from source code into locale files for internationalization projects. Use when setting up multi-language support or maintaining translation catalogs for your application.
```
