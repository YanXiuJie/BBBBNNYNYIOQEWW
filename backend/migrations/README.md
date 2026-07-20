# Database Migrations

## Overview

This directory contains SQL migration scripts for the Adaptive Math AI database schema.

## Running Migrations

### MySQL Development and Testing

The project now uses MySQL as the default database for development and tests.

```powershell
cd backend
& 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe' -uroot -p adaptive_math_ai < migrations\add_comprehensive_practice_tables.sql
```

If the database does not exist yet, the backend will create it automatically on startup.

## Migration Files

### `add_comprehensive_practice_tables.sql`

Adds comprehensive practice system tables and fields:

- `comprehensive_practice_sessions` table
- `style_preferences` table
- `questions.presentation_style` field
- `questions.hint_level2_ms` field
- `questions.hint_level3_ms` field

**Created:** 2026-06-17  
**Required for:** Comprehensive practice feature (FYP Phase 2)

## Troubleshooting

### Error: "table already exists"

The migration has already been applied. Safe to ignore.

### Error: "duplicate column name"

Some fields already exist in your schema. You can comment out those lines in the migration SQL and re-run.

## Future Migrations

For new schema changes:

1. Create a new SQL file with timestamp: `YYYY-MM-DD-description.sql`
2. Document the change in this README
3. Update `app/models.py` with the new schema
4. Test migration on a copy of production data before applying to production

## Alembic (Future Work)

For production-grade migrations, consider setting up Alembic:

```powershell
pip install alembic
alembic init migrations
```

This would provide:

- Version-controlled schema changes
- Rollback capability
- Automatic migration generation from model changes
