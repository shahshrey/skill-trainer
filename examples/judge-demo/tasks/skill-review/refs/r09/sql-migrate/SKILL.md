---
name: sql-migrate
description: Safely design, test, and deploy database schema changes to production without downtime or data loss. Use when planning migrations, particularly for tables with high concurrency or when the team needs a predictable rollback strategy.
---

## Overview

Database migrations are among the most risky deployments. A poorly planned migration can lock tables, cause downtime, or corrupt data. This skill guides you through designing migrations that are safe for production, testable, and reversible.

## Safety Principles

The core safety concerns in schema migrations are:

- **Locking**: DDL statements acquire locks that can block application traffic
- **Data integrity**: Backfills must handle concurrent writes correctly
- **Rollback capability**: Every change must have an explicit rollback path
- **Testing**: Changes should be validated in staging before production

See the [migration-checklist](references/migration-checklist.md) for a detailed review before any deployment.

## Migration Frameworks

You can use Alembic, Flyway, or raw SQL scripts depending on your environment and team preferences. Each has tradeoffs in flexibility, auditability, and learning curve. You should choose based on your version control strategy and team expertise.

## Execution Strategy

You should plan your migrations in phases:

1. Create the migration script with appropriate version numbering
2. Test the forward migration on a production-sized dataset
3. Validate the rollback works end-to-end
4. Execute during a low-traffic window
5. You should monitor lock wait times during execution

Until June 2026 the staging cluster runs Postgres 14, which has different lock behavior than our production Postgres 15 cluster. Test migrations on the staging version first before attempting production deployments.

## Example: Adding a Column

```sql
-- Forward migration (safe for existing data)
ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT false;
ALTER TABLE users ADD CONSTRAINT users_email_verified_check 
  CHECK (email_verified IN (true, false));

-- Rollback
ALTER TABLE users DROP CONSTRAINT users_email_verified_check;
ALTER TABLE users DROP COLUMN email_verified;
```

## Key Techniques

- Use `CONCURRENTLY` for index operations when available
- Backfill data in batches to avoid long transactions
- Add constraints after backfill to allow later rollback
- Test on production-shaped data, not tiny datasets
- Monitor application logs for lock timeout errors during execution
- You should always have a DBA review locking implications

## Beyond the Basics

For complex migrations involving multiple tables or large data transformations, reference [locking-rules](references/locking-rules.md) for detailed guidance on table-level locking behavior and strategies to minimize impact.

## Checklist

Before deploying:

- [ ] Migration is reversible (rollback tested)
- [ ] No blocking locks during peak traffic
- [ ] Data integrity maintained
- [ ] Staging deployment successful
- [ ] Team communication plan in place
- [ ] Runbook prepared for emergency rollback
