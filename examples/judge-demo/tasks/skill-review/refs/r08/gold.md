## Skill Review: slack-notify

### Summary
Three defects were planted: an overly long description exceeding 1024 characters, inconsistent terminology for Slack destinations, and a missing referenced script.

### Planted defects (must all be found)
1. **desc-too-long** — SKILL.md frontmatter description: The description is 1,385 characters (exceeds the 1024-character limit) and contains rambling detail about features, integrations, and customization options instead of a concise summary of what the skill does and when to use it.
2. **inconsistent-terms** — SKILL.md body: The text uses three different terms for the same concept — "channels" (Configuration section: "channel: Target Slack room"), "rooms" (Overview: "designated Slack rooms"), and "conversation" (Quick start: "your designated Slack conversation") — making the skill unclear about whether these terms are equivalent or refer to different Slack objects.
3. **missing-script** — SKILL.md Advanced section: The final paragraph references "scripts/post_message.py for custom message routing logic" but this file does not exist in the skill directory, leaving readers unable to follow the documented pattern.

### What is clean (a good review does NOT flag these)
- Quick start provides clear step-by-step instructions
- Notification types are well-documented with clear purposes
- Message formatting example demonstrates practical usage
- Configuration section lists all parameters with defaults
- scripts/format_blocks.py exists and supports the message formatting examples

### Expected recommendations
1. Replace the frontmatter description with a concise one:
```yaml
description: Sends build, test, and deployment notifications to Slack with rich formatting. Use to notify your team about pipeline status and deployment outcomes.
```
2. Standardize terminology throughout the document — pick one term (recommend "channel") and use it consistently:
   - Change "designated Slack rooms" to "designated Slack channels"
   - Change "your designated Slack conversation" to "your designated Slack channel"
   - All references in Configuration, Overview, and Quick start should use "channel" uniformly
3. Either create scripts/post_message.py with routing logic or remove the reference from the Advanced section if the use case is not yet implemented.
