from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.database.schema import MIGRATION_001, MIGRATION_002, MIGRATION_003, MIGRATION_004, MIGRATION_005, MIGRATION_006, MIGRATION_007, MIGRATION_008, MIGRATION_009, MIGRATION_010, MIGRATION_011, MIGRATION_012, MIGRATION_013, MIGRATION_014
from app.utils.formatters import utc_now_iso


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "001_initial_schema", MIGRATION_001),
    Migration(2, "002_add_indexes", MIGRATION_002),
    Migration(3, "003_add_account_capabilities", MIGRATION_003),
    Migration(4, "004_add_campaign_tables", MIGRATION_004),
    Migration(5, "005_telegram_sessions_and_authorization", MIGRATION_005),
    Migration(6, "006_group_management", MIGRATION_006),
    Migration(7, "007_member_management", MIGRATION_007),
    Migration(8, "008_campaign_management", MIGRATION_008),
    Migration(9, "009_operations_hardening", MIGRATION_009),
    Migration(10, "010_license_system", MIGRATION_010),
    Migration(11, "011_member_pool_target_actions", MIGRATION_011),
    Migration(12, "012_telegram_operations_account_pool", MIGRATION_012),
    Migration(13, "013_account_safety_limits", MIGRATION_013),
    Migration(14, "014_avatar_photo_cache", MIGRATION_014),
)


def _is_duplicate_column_error(exc: Exception) -> bool:
    """SQLite raises 'duplicate column name' when an ALTER TABLE ADD COLUMN
    targets a column that already exists.  This is harmless and should be
    ignored so that migrations are safely retryable."""
    msg = str(exc).lower()
    return "duplicate column name" in msg


def apply_migrations(connection, migrations: Iterable[Migration] = MIGRATIONS) -> int:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied = {
        int(row[0])
        for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    }
    latest = max(applied, default=0)
    for migration in migrations:
        if migration.version in applied:
            latest = max(latest, migration.version)
            continue
        statements_skipped = 0
        statements_applied = 0
        for statement in migration.sql.split(";"):
            statement = statement.strip()
            if not statement:
                continue
            try:
                connection.execute(statement)
                statements_applied += 1
            except Exception as exc:
                if _is_duplicate_column_error(exc):
                    statements_skipped += 1
                    continue
                raise
        # Record the migration as applied even if some columns already existed.
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
            (migration.version, migration.name, utc_now_iso()),
        )
        connection.commit()
        latest = migration.version
    return latest
