# Database Migrations System

## Overview

TheseusInsight now includes an automatic database migration system that runs on FastAPI startup. This ensures the database schema is always up-to-date with the latest changes.

## How It Works

1. **On Startup**: When the FastAPI application starts, it automatically checks for pending migrations
2. **Migration Tracking**: Applied migrations are tracked in the `schema_migrations` table
3. **Ordered Execution**: Migrations are applied in version order (1, 2, 3, etc.)
4. **Failure Handling**: If a migration fails, the system stops to prevent inconsistent state

## Migration Files

Current migrations in order:
1. `init_schema_postgres.sql` - Initial database schema
2. `migrate_to_profiles.sql` - Adds research profiles feature
3. `profiles_trends_integration.sql` - Integrates profiles with trends

## Testing Migrations

To manually test the migration system:

```bash
python scripts/test_migrations.py
```

This will:
- Check database connectivity
- Run any pending migrations
- Verify all critical tables exist
- Check for the default profile

## Adding New Migrations

To add a new migration:

1. Create a new SQL file in the `scripts/` directory
2. Add it to the `migrations` list in `theseus_insight/db/migrations.py`:
   ```python
   self.migrations = [
       (1, "init_schema_postgres.sql", "Initial database schema"),
       (2, "migrate_to_profiles.sql", "Add research profiles feature"),
       (3, "profiles_trends_integration.sql", "Integrate profiles with trends"),
       (4, "your_new_migration.sql", "Description of changes"),  # Add here
   ]
   ```
3. The migration will run automatically on next startup

## Troubleshooting

If you encounter migration issues:

1. **Check logs**: Migration status is printed during startup
2. **Manual verification**: Run `scripts/test_migrations.py`
3. **Database access**: Ensure PostgreSQL is running and accessible
4. **Fresh start**: If needed, drop and recreate the database, then migrations will run fresh

## Environment Variables

- `DATABASE_URL`: PostgreSQL connection string (default: `postgresql://theseus:theseus@localhost:5432/theseusdb`)