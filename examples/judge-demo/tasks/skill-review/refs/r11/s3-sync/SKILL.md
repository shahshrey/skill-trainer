---
name: s3-sync
description: You can use this to synchronize a local directory to an S3 bucket with built-in safeguards against accidental deletion of remote objects. Use when deploying static assets or performing bulk uploads to cloud storage with confidence in data safety.
---

## Overview

Syncing to S3 requires careful handling to prevent accidental data loss. This skill covers syncing strategies that protect against destructive operations while maintaining high throughput and efficient incremental uploads.

## Core Concepts

S3 sync operations compare local and remote state, then copy differences to the bucket. The key risk is the `--delete` flag, which removes remote objects that no longer exist locally. Safe syncing requires understanding:

- Comparing file modification times and ETags
- Excluding sensitive files from sync
- Validating deletions before applying them
- Dry-run mode for previewing changes

## Safe Sync Pattern

Always use `--dryrun` first to preview changes:

```bash
aws s3 sync ./build/ s3://my-bucket/assets/ \
  --dryrun \
  --exclude "*.map" \
  --exclude ".git/*"
```

Then apply the sync without the `--dryrun` flag:

```bash
aws s3 sync ./build/ s3://my-bucket/assets/ \
  --exclude "*.map" \
  --exclude ".git/*" \
  --delete
```

## Performance Tuning

For large uploads, increase parallelism:

```bash
aws configure set default.s3.max_concurrent_requests 23
aws configure set default.s3.max_bandwidth 100MB/s
```

## Excluding Files

Create a `.s3exclude` file to skip files during sync:

```
.git
*.tmp
node_modules/
.env
.env.local
```

Then use in your sync command:

```bash
aws s3 sync ./dist/ s3://bucket/ --exclude-from .s3exclude
```

## Monitoring

Check upload progress in real time:

```bash
aws s3 sync ./large-files/ s3://bucket/ --profile prod --verbose
```

## Checklist

- [ ] Dry-run validates expected changes
- [ ] Sensitive files are properly excluded
- [ ] S3 bucket has versioning enabled
- [ ] Sync excludes development artifacts
- [ ] Bandwidth and concurrency configured
- [ ] Team is aware of sync schedule
