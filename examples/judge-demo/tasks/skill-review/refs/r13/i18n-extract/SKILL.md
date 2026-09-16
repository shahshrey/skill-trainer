---
name: i18n-extract
description: Extracts translatable strings from source code into locale files for internationalization projects
---

## Overview

This skill automates the process of identifying and extracting user-facing strings from source code and organizing them into locale-specific translation files. It scans your codebase for marked translatable content and generates locale files (JSON, YAML, or PO format) that translators can work with.

## What it does

- Scans source code for translation markers (e.g., `i18n("key")`, `t("message")`)
- Extracts strings while preserving context and pluralization rules
- Generates locale files in your chosen format
- Validates extracted strings for consistency
- Updates existing locale files without losing manual translations

## Quick start

Run the extraction script on your project:

```bash
python scripts\extract.py --source src/ --output locales/ --format json
```

This scans the `src/` directory and generates JSON locale files in the `locales/` folder.

## Configuration options

Customize extraction with these flags:

- `--source` (required): Directory containing source files to scan
- `--output` (required): Output directory for locale files
- `--format`: Choose `json` (default), `yaml`, or `po` format
- `--languages`: Comma-separated list of target languages

## Handling pluralization

Different languages have different pluralization rules. See the reference files for detailed information:

- Basic format specifications: [references/formats.md](references/formats.md)
- Language-specific plural rules: [references/plural-rules.md](references/plural-rules.md)

## Common workflows

- **Initial setup**: Run extraction on a fresh project to create base locale files
- **Incremental updates**: Run periodically to find new strings as you add features
- **Consistency checks**: Validate that all marked strings follow your project's conventions
- **Batch updates**: Process multiple projects with different format requirements

## Requirements

- Python 3.8+
- Source files must use consistent translation markers
- Output directory must exist or be creatable
