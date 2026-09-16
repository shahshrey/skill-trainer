# Translation File Formats

This guide covers the supported formats for locale files in i18n extraction.

## Supported formats

- **JSON**: Simple key-value pairs, recommended for web projects
- **YAML**: Human-readable format with nested structures
- **PO**: Portable Object format, standard in GNU gettext

## Format selection

Choose based on your tooling and translator preference:

- Use **JSON** for JavaScript/Node.js projects with simple structures
- Use **YAML** for Python projects with complex nesting needs
- Use **PO** for projects using GNU gettext ecosystem

## Pluralization rules

Language-specific plural rules are critical for correct translation. See [references/plural-rules.md](references/plural-rules.md) for details on handling plurals in each language.

## Best practices

- Keep keys descriptive and lowercase with hyphens
- Group related strings together
- Include context comments for translators
- Validate extracted strings match your markers
