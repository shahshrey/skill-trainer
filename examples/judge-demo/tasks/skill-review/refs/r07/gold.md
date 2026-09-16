## Skill Review: image-resize

### Summary
Three defects were planted: a Windows-style backslash path in the code example, missing documentation of the ImageMagick binary dependency, and a description lacking a trigger clause.

### Planted defects (must all be found)
1. **windows-path** — SKILL.md How to use section: The command shows `scripts\resize.py` with a backslash instead of the forward slash `scripts/resize.py`; this fails on Unix-like systems and violates platform-agnostic path conventions.
2. **undocumented-binary** — SKILL.md Features and command sections: The skill describes resizing and format conversion operations that depend on ImageMagick's `convert` command, but never lists it as a system requirement or dependency; users may attempt to run the script and encounter "command not found" errors without understanding what is missing.
3. **desc-no-trigger** — SKILL.md frontmatter: The description "Batch resize and convert images for the web with format optimization and quality control" says what the skill does but provides no "Use when..." clause; readers cannot determine whether they should invoke this skill for their task.

### What is clean (a good review does NOT flag these)
- Overview section clearly explains purpose and use cases
- Configuration section documents all parameters with sensible defaults
- Quality presets provide shorthand options for common scenarios
- Output structure example is clear and well-formatted

### Expected recommendations
1. Fix the path in the code example:
```bash
python scripts/resize.py \
  --input /path/to/images \
  ...
```
2. Add ImageMagick as a documented dependency in a new "Requirements" or "Setup" section:
```
## Requirements

- Python 3.8+
- ImageMagick (`convert` command) — install via `brew install imagemagick` (macOS), `apt-get install imagemagick` (Ubuntu), or `choco install imagemagick` (Windows)
- Python packages: Pillow (fallback if ImageMagick unavailable)
```
3. Expand the description to include a trigger clause:
```yaml
description: Batch resize and convert images to web-optimized formats. Use when preparing product photos, blog images, or illustration sets for responsive website delivery.
```
