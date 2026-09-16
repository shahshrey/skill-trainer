# Migration Checklist

Use this checklist before any schema migration to production.

## Pre-Deployment

- [ ] Migration reversibility tested with actual rollback
- [ ] Schema changes validated on staging environment
- [ ] Data backfill logic handles concurrent writes
- [ ] No new dependencies on undeployed application code
- [ ] Downtime window communicated to stakeholders

## Locking Strategy

For detailed table-locking guidance and strategies to minimize impact during execution, see [locking-rules.md](locking-rules.md).

## Testing

- [ ] Forward migration completes in < 30 seconds on production data size
- [ ] Rollback completes successfully
- [ ] Application continues serving requests during migration
- [ ] No transaction log growth beyond normal during execution
