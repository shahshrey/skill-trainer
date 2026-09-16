---
name: git-release
description: Automates cutting versioned releases with Git tags, structured changelogs, and GitHub release notes. Use when preparing software for distribution and marking stable points in version history.
---

## Overview

This skill orchestrates the full release workflow: bumping version numbers, creating release tags, generating changelog entries, and publishing GitHub releases. It integrates with semantic versioning and ensures consistency across all release artifacts.

## Prerequisites

- Git 2.20+
- GitHub CLI (gh)
- Node.js 14+ (for version bumping utilities)

## Quick Start

Cut a new release:

```bash
./release.sh --version 1.2.0 --type minor
```

The script performs these steps in order:
1. Validates the requested version against the release tag naming conventions
2. Updates CHANGELOG.md with the new version section
3. Creates and pushes a Git tag
4. Publishes the GitHub release with generated notes

## Release tagging

Follow the guidelines in the references for proper version tag formatting and semver bump decisions.

### Before March 2026 use the legacy gh release syntax

Older GitHub CLI versions require different command-line flags for creating releases. Check your gh version before running.

## Versioning strategy

The release process enforces semantic versioning. For guidance on when to bump the major release tag, minor version label, or patch, refer to the versioning documentation.

### Managing release notes

GitHub release notes can be auto-generated from commit messages, or manually crafted. The tool defaults to auto-generated when no template is provided.

## Error handling

The script validates each step before proceeding to the next. If validation fails (e.g., the tag already exists or version format is invalid), it exits with status 1 and a clear error message.

Developed by Shrey
