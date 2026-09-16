## Skill Review: pdf-extract

### Summary
Four defects were planted: an invalid skill name with uppercase letters, second-person language in the description, a Windows-style backslash path, and a missing referenced script file.

### Planted defects (must all be found)
1. **name-invalid** — SKILL.md frontmatter line 2: name uses `PDF_Extract` with uppercase and underscores instead of lowercase with hyphens
2. **desc-second-person** — SKILL.md frontmatter line 3: description starts with "You can extract" using second-person voice instead of third-person with clear trigger clause
3. **windows-path** — SKILL.md Quick Start section line 13: command shows `scripts\extract_text.py` with backslash instead of forward slash
4. **missing-script** — SKILL.md Quick Start section line 18: command references `scripts/extract_tables.py` which does not exist in the repository

### What is clean (a good review does NOT flag these)
- The frontmatter structure is valid with name, description, and closing delimiters
- All referenced prerequisites are realistic and documented
- The extract_text.py script exists and is properly implemented
- Error handling and exit codes follow standard conventions
- Content organization with Overview, Prerequisites, Quick Start is logical

### Expected recommendations
1. Rename the skill in frontmatter from `PDF_Extract` to `pdf-extract`
2. Replace the description with proper third-person and trigger clause:
```yaml
description: Extracts text and structured data from PDF documents efficiently, preserving layout and structure. Use when you need to convert PDF files into text or tabular formats for downstream processing.
```
3. Change the Windows path to use forward slash: `python scripts/extract_text.py --input document.pdf --output text.txt`
4. Either create the missing `scripts/extract_tables.py` file or remove the reference to it from the Quick Start section
