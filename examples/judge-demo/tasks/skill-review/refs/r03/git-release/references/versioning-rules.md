# Semantic Versioning Rules

This document defines the semver bump decision matrix for release versions.

## Bump decisions

Use these rules to determine which component of the version to increment:

### MAJOR version bump (X.0.0)

Increment the major release tag when:
- Making incompatible API changes
- Removing deprecated features
- Making breaking changes to behavior or configuration
- Changing the minimum required dependency versions in a backward-incompatible way

Examples: v1.0.0 → v2.0.0, v2.3.1 → v3.0.0

### MINOR version bump (x.Y.0)

Increment the minor version label when:
- Adding new features in a backward-compatible manner
- Adding new public APIs or commands
- Extending configuration options
- Deprecating features (with notice for future removal)

Examples: v1.0.0 → v1.1.0, v2.3.0 → v2.4.0

### PATCH version bump (x.y.Z)

Increment the patch component when:
- Fixing bugs in existing functionality
- Fixing security vulnerabilities
- Improving performance without API changes
- Updating documentation or examples

Examples: v1.0.0 → v1.0.1, v2.3.1 → v2.3.2

## Prerelease versions

Use prerelease tags (e.g., v2.0.0-alpha, v2.0.0-rc.1) for testing before stable releases. Increment the prerelease identifier or move to stable release based on testing completion.
