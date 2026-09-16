---
name: cron-schedule
description: Helps with scheduling things. Use when recurring jobs need a schedule.
---

## Overview

Cron is the standard Unix scheduler for running tasks on a recurring basis. This skill covers syntax, testing, and monitoring cron jobs to ensure reliability.

## Cron Syntax

A cron expression consists of five fields: minute, hour, day of month, month, and day of week. Each field can be a specific value, a range, a list, or an asterisk for "any":

```
* * * * *
│ │ │ │ │
│ │ │ │ └─ Day of Week (0-6, 0=Sunday)
│ │ │ └─── Month (1-12)
│ │ └───── Day of Month (1-31)
│ └─────── Hour (0-23)
└───────── Minute (0-59)
```

Examples:
- `0 0 * * *` - Every day at midnight
- `0 2 * * 0` - Every Sunday at 2 AM
- `*/5 * * * *` - Every 5 minutes
- `0 9-17 * * 1-5` - Every weekday at 9 AM through 5 PM

## Setting Up a Cron Task

Create an entry using `crontab -e`:

```bash
# Edit the current user's crontab
crontab -e

# List the current scheduled tasks
crontab -l

# Remove all jobs for the current user
crontab -r
```

A typical cron job for a backup:

```bash
0 3 * * * /usr/local/bin/backup.sh >> /var/log/backup.log 2>&1
```

## Monitoring Job Execution

Check the system log to see if the scheduled entry ran:

```bash
grep CRON /var/log/syslog
# or on macOS
log stream --predicate 'process == "cron"'
```

View job output by redirecting to a log file (as in the backup example above). Ensure the entry has write permissions to the log directory.

## Common Pitfalls

- Not specifying absolute paths: the task runs in a minimal environment
- Forgetting to redirect output: cron discards stdout unless captured
- Not testing the job command directly: debug before adding to cron
- Failing to handle the job exit status: non-zero exits should trigger alerts

## Debugging

Test the entry command in your shell before scheduling:

```bash
# Test the backup script manually
/usr/local/bin/backup.sh

# Check the exit code
echo $?
```

Also verify that the job can find all dependencies it needs:

```bash
# Run the job in a minimal environment similar to cron
env -i HOME=$HOME /usr/local/bin/backup.sh
```

## Checklist

- [ ] Task command tested directly in shell
- [ ] Job uses absolute paths to all scripts and binaries
- [ ] Output is redirected to a log file
- [ ] Log directory exists and is writable
- [ ] Job exit status is monitored
- [ ] Backup or remediation task is scheduled during low-load windows
