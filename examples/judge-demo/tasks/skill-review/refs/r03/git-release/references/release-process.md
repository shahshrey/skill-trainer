# Git Release Process

This document outlines the standard release process for creating versioned releases with proper Git tags and GitHub integration.

## Release workflow

The release workflow consists of these phases:

1. **Version validation** - Ensure the requested version is valid and not already released
2. **Changelog update** - Add new release section to CHANGELOG.md
3. **Git tagging** - Create and push the version tag
4. **Release publishing** - Create GitHub release with notes

## Tag naming conventions

Release tags follow the pattern `v<major>.<minor>.<patch>` (e.g., `v1.2.3`).

Prerelease tags use the format `v<major>.<minor>.<patch>-<prerelease>` (e.g., `v2.0.0-beta.1`).

## Changelog format

Changelogs should follow the Keep a Changelog format with sections for Added, Changed, Deprecated, Removed, Fixed, and Security.

## Related documentation

For semver bump guidelines, see [versioning-rules.md](versioning-rules.md).
