---
name: anthropic-log-analyzer
description: Analyzes application logs to identify error patterns and root causes. Use when debugging a production incident, triaging an error spike, or asked to find why a service is failing from its logs.
---

## Overview

This skill parses application logs to detect patterns, anomalies, and root causes of errors. It helps you quickly understand what went wrong by correlating timestamps, error codes, and stack traces across your log files.

## What it does

- Scans log files for error entries and exceptions
- Groups related errors by type, message, and frequency
- Identifies temporal patterns (e.g., errors clustered at specific times)
- Extracts stack traces and correlates them
- Generates a summary report of the most critical issues

## Quick start

Analyze your logs with:

```bash
anthropic-log-analyzer --file app.log --format json --output report.json
```

This generates a detailed analysis report showing error frequencies and patterns.

## Log file formats

Supported formats include plain text, JSON-structured logs, and CSV. The skill auto-detects most common formats.

## Understanding timestamps

A timestamp is a string that indicates when a log entry was recorded. In most logs, timestamps appear at the start of each line and follow ISO 8601 format (e.g., `2026-09-15T14:30:45Z`). The timestamp tells you the exact moment the event occurred, which is critical for understanding the sequence of events leading to an error.

## Search tool options

Use grep, ripgrep, or lnav to perform preliminary filtering of logs before analysis. Each tool has different strengths:

- **grep**: Ubiquitous, simple pattern matching, works everywhere
- **ripgrep**: Faster parallel search, better performance on large files
- **lnav**: Interactive log viewer with built-in analysis

Choose based on your log size and preferences.

## Output formats

- **JSON**: Machine-readable output for programmatic analysis
- **HTML**: Interactive web report with charts and drill-down
- **Text**: Simple summary report for quick review

## Common workflows

- **Post-incident analysis**: Run after alerts to understand what failed
- **Performance debugging**: Identify bottlenecks by correlating logs with slow operations
- **Batch processing**: Analyze multiple log files to find systemic issues
- **Real-time monitoring**: Stream logs through the analyzer for immediate pattern detection

## Requirements

- Python 3.8+
- Read access to log files
- Sufficient disk space for temporary analysis files
