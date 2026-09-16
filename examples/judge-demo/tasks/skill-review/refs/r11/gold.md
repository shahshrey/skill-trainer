## Skill Review: s3-sync

### Summary

Four defects compromise this S3 syncing guide: the description uses second-person voice, user-facing install documentation clutters the skill directory, a magic number lacks justification, and required CLI tools are never documented as dependencies.

### Planted defects (must all be found)

1. **desc-second-person** — SKILL.md frontmatter line 2: The description starts with "You can use this to synchronize", violating third-person voice. Should read "Synchronizes a local directory..."

2. **extraneous-files** — README.md in skill directory: User-facing documentation with installation instructions is placed in the skill directory. Such docs should not be bundled with the skill itself.

3. **magic-number** — SKILL.md line ~32: The command sets `max_concurrent_requests 23` without explaining why this specific number is chosen or how to tune it for different environments.

4. **undocumented-binary** — SKILL.md lines 18, 27, 47, 52: All commands use the `aws` CLI, but the skill never documents AWS CLI as a required dependency. An agent would not know what needs to be installed.

### What is clean (a good review does NOT flag these)

- Overview explains the core risk (accidental deletion) clearly
- Safe patterns are documented with dry-run-first methodology
- Exclusion patterns are concrete and practical
- Checklist covers essential safety steps
- Code examples show actual command syntax and flags

### Expected recommendations

1. Correct the description to third-person: "Synchronizes a local directory to an S3 bucket with built-in safeguards against accidental deletion of remote objects. Use when deploying static assets or performing bulk uploads to cloud storage with confidence in data safety."

2. Remove README.md from the skill directory or relocate user documentation to a separate docs/ folder outside the skill.

3. Explain the magic number: "Set `max_concurrent_requests` to 23 for most environments; adjust based on your network bandwidth and S3 rate limits (higher for fast connections, lower for shared networks)."

4. Add a Dependencies section to the skill body documenting AWS CLI as a required tool:
   ```
   ## Dependencies
   - AWS CLI v2 or later (install with `brew install awscli` on macOS or `pip install awscli`)
   - Valid AWS credentials configured via `aws configure`
   ```
