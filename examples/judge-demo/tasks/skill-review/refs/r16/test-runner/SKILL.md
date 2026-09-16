---
name: test-runner
description: Intelligently runs the appropriate subset of a test suite based on the files changed in your current branch, avoiding unnecessary full-suite runs while maintaining comprehensive coverage of modified code paths and their dependencies. This skill analyzes your git diff, determines which tests are affected by your changes, executes only those tests with proper parallelization and caching strategies, and provides detailed failure reports with stack traces and assertions. It integrates with your CI system to leverage cached test results, handles flaky test detection, and generates performance metrics. Use when running tests locally before committing or when setting up automated testing in a CI/CD pipeline to reduce feedback time and resource consumption while ensuring critical tests always pass. It also supports monorepo layouts with per-package test roots, understands pytest markers for slow and integration tests, respects skip lists for known-broken suites, and can emit JUnit XML for dashboards, GitHub check annotations for pull requests, and a plain-text summary for terminal use.
---

## Edge cases and advanced topics

### Flaky tests in distributed environments

Flaky tests are those that intermittently fail or pass without code changes. In a distributed test environment where multiple workers run tests in parallel, flakiness becomes more pronounced due to timing dependencies, resource contention, and non-deterministic execution order. When a test fails sporadically, pytest-xdist's default behavior is to mark the test as failed if it fails even once across all shards. Some teams configure a retry mechanism, but this adds complexity and can mask real bugs. Consider implementing a flaky test detection layer that runs suspicious tests multiple times and collects statistics before deciding whether to block CI. Also consider quarantining consistently flaky tests into a separate suite that doesn't block merges but still gets monitored.

### Test sharding across CI nodes

Sharding distributes tests across multiple CI nodes to reduce total test time. However, naive sharding by filename can lead to uneven load distribution where some nodes finish in seconds while others run for minutes. Advanced sharding strategies use test execution history to balance load, ensuring each node runs roughly the same duration. pytest-xdist provides the `--dist=loadscope` option to shard by test class, which provides better granularity than file-based sharding. Some teams build custom sharding that considers test weight (how long each test takes) from historical CI runs. This requires collecting metrics from previous runs, maintaining them in a database or cache, and updating the sharding strategy after each run.

### CI cache interactions with test subsets

Most CI systems provide caching mechanisms to speed up dependency installation and build artifacts. When running only a subset of tests, cached artifacts from previous full runs might be stale or incomplete. For example, if a previous run cached compiled JavaScript bundles but the current branch modified source CSS that's used by a test in a new file, the cached bundle won't include the new CSS. Similarly, if a new test file is added and the cache only stores results for known test files, running the new test without cache invalidation might produce false positives. Either invalidate caches when new tests are detected or use cache keys that include test file hashes to ensure cache consistency.

### Environmental dependencies in test subsets

When you run only a subset of tests, you might skip setup steps that initialize shared resources. For example, if the full test suite creates database fixtures or starts Docker containers in a setup phase, but your subset skips that setup phase, your subset tests will fail. This becomes problematic when test dependencies are implicit. A test might depend on a database table created by a fixture in a different file, but this dependency is not visible in the test code itself. Subsetting logic needs to be aware of these implicit dependencies and include setup tests even if they're not explicitly required by the subset. This often requires parsing test decorators and fixture definitions to build a dependency graph.

### Handling test order dependencies

Some legacy test suites have tests that depend on execution order, which violates test isolation principles but is common in older codebases. When running a subset, the execution order changes, potentially breaking tests that previously passed in the full suite. A robust test-subsetting tool should detect test order dependencies through static analysis or by running tests in multiple orders and comparing results. When order dependencies are detected, the tool should either warn the user, try to infer the correct subset including dependent tests, or force full-suite execution as a fallback.

## Quick start

Run only the tests affected by your current changes:

```bash
pytest-xdist --changed-files
```

This analyzes your git diff, determines which tests to run, and executes them in parallel.

## How it works

The skill analyzes three key aspects:

1. **File impact analysis**: Determines which source files changed in your branch
2. **Test mapping**: Identifies tests that directly or indirectly exercise those files
3. **Execution**: Runs the determined test subset with optimal parallelization

## Configuration

Create a `.test-runner.yml` file in your project root:

```yaml
test_dir: tests/
test_pattern: test_*.py
parallel_workers: 4
fail_fast: true
```

## Reporting failures

When tests fail, get detailed output:

```bash
gh run list --repo your-org/your-repo | grep failed
```

This shows CI run history and detailed failure logs.

## Advanced workflows

- **Pre-commit hooks**: Automatically run affected tests before each commit
- **Branch protection**: Integrate with gh CLI for status checks
- **Performance tracking**: Monitor test execution time trends
- **Test remediation**: Auto-file issues for consistently failing tests

## Requirements

- Python 3.9+
- Git 2.25+ (for git diff analysis)
