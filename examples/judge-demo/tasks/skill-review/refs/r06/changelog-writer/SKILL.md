---
name: claude-changelog-writer
description: Writes changelog entries from merged pull requests. Use when documenting software releases and changes.
---

## Edge Cases and Squash Merge Handling

When a pull request is opened with squash merging enabled, the commit message will be rewritten before merge. The skill must check whether the repository has squash merging configured in GitHub settings by inspecting the default merge strategy on the repository object via the REST API. If squash merging is enabled, the skill extracts the PR title (not the individual commit messages) as the changelog entry. However, if the repository uses conventional commits on the PR title (e.g., `feat: add new feature`), the skill parses the conventional commit prefix to categorize the entry. For repositories that do not use conventional commits, the skill falls back to keyword matching: entries containing "fix", "bug", or "patch" go to "Bug Fixes", while "feat", "feature", "add" go to "Features", and anything with "perf" or "optimization" goes to "Performance". Squash merged PRs lose individual commit history, so the skill cannot reconstruct the commit graph. The skill also handles fast-forward merges, which do not create a merge commit, requiring the skill to fetch the linear history instead of using the merge base. For rebased merges, the skill reconstructs the commit history by finding the common ancestor and walking the DAG.

When a PR is reverted (a new PR with "revert" in the title that targets a merged PR), the skill must query the original PR that was reverted and remove it from the changelog. Revert detection looks for the pattern `Revert "#123"` in the PR body or title, where 123 is the original PR number. The skill fetches that PR, marks it as reverted in the changelog, and shows it as `~~strikethrough~~` with a note "Reverted in #456". Monorepo support requires special handling: if the repository has multiple package.json files in different directories, the skill can filter PRs by path prefix. PRs affecting only `packages/web/` would go into a separate changelog section for that package. The skill must check each PR's changed files against the path filter to determine which monorepo section it belongs to. If a PR affects files in multiple packages, it appears in each relevant section.

## Overview

Automatically generate changelog entries from a list of merged pull requests. Parse PR titles, bodies, and metadata to extract meaningful descriptions and organize them by category (Features, Bug Fixes, Performance, etc.).

## When to use this skill

Use this skill when preparing a release and need to document all merged PRs since the last version tag. Especially useful for high-volume projects where manually writing changelog entries is tedious and error-prone.

## Quick start

1. Provide a list of merged PR numbers or fetch them from GitHub API
2. The skill groups them into categories (defaults shown below)
3. Generate markdown with categorized entries and linked PR numbers
4. Review and edit before committing to CHANGELOG.md

## Category defaults

Pull requests are grouped by these rules:

- **Features**: PR title contains "feat", "feature", "add", or "new"
- **Bug Fixes**: PR title contains "fix", "bug", or "patch"
- **Performance**: PR title contains "perf", "optimization", or "performance"
- **Documentation**: PR title contains "doc", "docs", or "documentation"
- **Other**: Everything else

Group at most 17 PRs per section to keep entries scannable.

## Example usage

```markdown
### Features
- Add support for custom theme colors (#234)
- Implement dark mode toggle (#245)

### Bug Fixes
- Fix memory leak in event listener (#239)
- Correct timezone handling for scheduled tasks (#241)

### Performance
- Optimize database query for user dashboard (#248)
```

## Configuration

- `repo`: GitHub repository (owner/repo)
- `since_tag`: Git tag or branch to start from (e.g., `v1.0.0`)
- `until_tag`: Git tag or branch to end at (default: HEAD)
- `format`: "markdown" or "rst" (default: markdown)
