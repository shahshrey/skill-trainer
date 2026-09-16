## Skill Review: csv-cleaner

### Summary
Three defects were planted: the description lacks a trigger clause, options are listed without a stated default, and a magic number (731) appears without justification.

### Planted defects (must all be found)
1. **desc-no-trigger** — SKILL.md frontmatter line 2: description states what the tool does but never says when to use it; no "Use when" clause
2. **options-no-default** — SKILL.md Implementation section lines 10-20: engine options (pandas, polars, duckdb) are listed in example commands with no indication of which is the default
3. **magic-number** — SKILL.md Advanced usage section line 31: text says "sample the first 731 rows" with no explanation for this specific number

### What is clean (a good review does NOT flag these)
- Frontmatter structure and formatting is correct
- The skill name follows lowercase-with-hyphens convention
- Key features list is comprehensive and well-organized
- Configuration example in YAML is valid and clear
- Error handling and performance guidance is documented

### Expected recommendations
1. Add a trigger clause to the description:
```yaml
description: Cleans and normalizes messy CSV files with duplicate handling, missing value imputation, and data type inference. Use when you have raw or partially processed CSV data with quality issues that need to be addressed before analysis or downstream processing.
```
2. Clarify the default engine in the Implementation section by adding text like "pandas is used by default" or marking the first example differently
3. Replace the magic number with a justified statement: "For validation, sample the first 1% of rows before processing the entire file to catch configuration issues early"
