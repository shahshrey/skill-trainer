# Table-Level Locking Rules

## Lock Types in Postgres

Different DDL statements acquire different lock levels:

- **ACCESS SHARE**: Used by SELECT; multiple concurrent queries allowed
- **ROW SHARE**: Used by SELECT FOR SHARE; allows other readers
- **ROW EXCLUSIVE**: Used by UPDATE/DELETE; blocks other writers
- **SHARE**: Allows concurrent readers only
- **EXCLUSIVE**: Blocks all other access

## High-Concurrency Tables

For tables with sustained write traffic:

1. Use `ALTER TABLE ... ADD COLUMN` with `DEFAULT` to avoid full table rewrites
2. Create indexes `CONCURRENTLY` to avoid blocking writes
3. Backfill data in small batches with pauses between commits
4. Drop constraints only after the column is no longer in use

## Production Strategies

- Schedule migrations during low-traffic windows (2am-4am UTC)
- Use application-level feature flags to toggle behavior during deployment
- Monitor `pg_stat_activity` for long-running transactions before migration
- Keep rollback instructions readily available in the runbook

## Monitoring

Watch these metrics during migration execution:

- `max_locks_per_transaction` to ensure enough lock budget
- Query queue depth on the connection pool
- Replication lag if using streaming replication
