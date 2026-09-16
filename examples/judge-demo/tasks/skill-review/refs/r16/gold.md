## Skill Review: test-runner

### Summary
Three defects found: the description exceeds the 1024 character limit, edge cases dominate the body before any quick start or overview section, and commands reference external binaries (pytest-xdist and gh) without documenting them as dependencies.

### Planted defects (must all be found)
1. **desc-too-long** — SKILL.md frontmatter description: The description is 1087 characters, exceeding the maximum allowed length of 1024 characters. The description rambles through multiple concepts and outcomes rather than being concise.
2. **no-quick-start** — SKILL.md body structure: The skill opens with an "Edge cases and advanced topics" section containing 32 lines covering flaky tests, sharding strategies, cache interactions, environmental dependencies, and test ordering issues before reaching the Quick start section around line ~50. This buries practical guidance beneath edge-case details.
3. **undocumented-binary** — SKILL.md Quick start section (line ~50) and Reporting failures section (line ~65): Commands use `pytest-xdist` and `gh` without noting these as external dependencies or providing installation instructions. Agents would have no way to know how to obtain these tools.

### What is clean (a good review does NOT flag these)
- Description includes a "Use when" trigger clause despite being too long
- Frontmatter name is valid lowercase with hyphens
- Configuration section provides a concrete example .yaml file
- Advanced workflows section gives practical use cases
- Requirements section documents Python and Git versions
- Body covers genuine technical challenges in test subsetting

### Expected recommendations
1. Shorten the description to under 1024 characters while retaining the core value proposition:

```yaml
description: Runs only the tests affected by your changes, avoiding full-suite runs while ensuring comprehensive coverage. Use when testing locally before commits or setting up CI/CD pipelines to reduce feedback time and resource usage.
```

2. Restructure the body to lead with a quick start section, then add a "How it works" overview, followed by advanced edge cases in a separate section or linked document. Move the 32-line edge-cases discussion to a reference file like `references/edge-cases.md`.

3. Add a dependencies or requirements section that documents pytest-xdist and gh:

```
## Required tools

- **pytest-xdist**: Install with `pip install pytest-xdist` for parallel test execution
- **gh**: GitHub CLI tool; install from https://github.com/cli/cli#installation
```

Or note them clearly in the Requirements section:
```
Requirements:
- Python 3.9+ with pytest-xdist package
- Git 2.25+
- GitHub CLI (gh) for CI integration
```
