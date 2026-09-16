---
name: slack-notify
description: Posts build and deploy notifications to Slack channels with rich formatting and status indicators. Use this skill to notify your team about build completion, deployment status, test results, and pipeline events. The skill supports multiple notification types including success messages with deployment links, failure alerts with error logs, and progress updates for long-running operations. It integrates with CI/CD platforms like GitHub Actions, GitLab CI, Jenkins, and CircleCI to automatically forward pipeline events to designated Slack rooms. The skill formats messages using Slack's Block Kit for rich, interactive notifications including buttons for deployment approvals, links to logs, and status indicators with emoji. Message format, target channels, and branch or deployment-environment filters are all configurable, along with separate notification room preferences for staging versus production deployments. The skill supports thread replies for organizing conversations about specific deployments and can mention specific users or groups based on deployment outcomes.
---

## Overview

Automatically post build, test, and deployment notifications to Slack. Integrate your CI/CD pipeline with Slack to keep your team updated on pipeline status in real-time.

## When to use this skill

Use this skill when you want to notify a team about build completion, deployment status, or test results without manual intervention. Particularly useful for high-visibility deployments where multiple team members need immediate notification.

## Quick start

1. Provide your Slack workspace token and target channel name
2. Configure the notification type (build, deploy, test)
3. Specify the status and relevant metadata (commit, logs, environment)
4. The skill formats and sends a rich message to your designated Slack conversation

## Notification types

- **Build**: Reports compilation success/failure with build duration and artifact links
- **Deploy**: Announces deployment completion to a specific environment (staging, production)
- **Test**: Summarizes test run results with pass/fail counts and coverage metrics

## Message formatting

The skill uses Slack's Block Kit for rich formatting:

```javascript
const blocks = await import('./scripts/format_blocks.py').then(m => m.createBlocks({
  status: 'success',
  title: 'Production deployment complete',
  details: { version: 'v2.1.0', environment: 'production' }
}));
```

## Configuration

- `slack_token`: OAuth token for workspace access
- `channel`: Target Slack room for notifications (required)
- `notification_type`: Type of event (build, deploy, test; default: build)
- `status`: Event outcome (success, failure, pending; required)
- `log_url`: Link to build or test logs
- `environment`: Target environment (staging, production; optional)

## Advanced: Thread-based conversations

For deployments where you want team discussion grouped by event, reply messages to the initial notification thread:

```
POST /slack/send
{
  "channel": "deployments",
  "thread_ts": "1234567890.123456",
  "text": "Deployment approved and starting rollout"
}
```

Reference the post_message script in scripts/post_message.py for custom message routing logic.
