#!/usr/bin/env python3
"""Markdown linting utility."""

import sys
import json
import subprocess
from pathlib import Path

def run_lint(pattern="**/*.md"):
    """Run markdownlint on the given pattern."""
    try:
        result = subprocess.run(
            ["markdownlint-cli2", pattern],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        print("Error: markdownlint-cli2 not found. Install with: npm install -D markdownlint-cli2")
        return False

if __name__ == "__main__":
    pattern = sys.argv[1] if len(sys.argv) > 1 else "**/*.md"
    success = run_lint(pattern)
    sys.exit(0 if success else 1)
