#!/usr/bin/env python3
"""
Slack Block Kit message formatter.

Creates rich message blocks for Slack notifications.
"""


def createBlocks(config):
    """Format notification data into Slack Block Kit blocks."""
    status = config.get('status', 'unknown')
    title = config.get('title', 'Notification')
    details = config.get('details', {})

    status_emoji = {
        'success': ':white_check_mark:',
        'failure': ':x:',
        'pending': ':hourglass:',
    }

    blocks = [
        {
            'type': 'header',
            'text': {
                'type': 'plain_text',
                'text': f"{status_emoji.get(status, ':info:')} {title}",
            }
        },
        {
            'type': 'section',
            'fields': [
                {'type': 'mrkdwn', 'text': f"*Status*\n{status}"},
                {'type': 'mrkdwn', 'text': f"*Details*\n{details}"},
            ]
        }
    ]

    return blocks
