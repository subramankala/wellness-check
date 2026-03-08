from __future__ import annotations

from pathlib import Path

import psycopg


def ensure_migration_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS mw_schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )


def applied_versions(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM mw_schema_migrations")
        rows = cur.fetchall()
    versions: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            versions.add(str(row["version"]))
        else:
            versions.add(str(row[0]))
    return versions


def migration_files(migrations_dir: Path) -> list[Path]:
    return sorted(migrations_dir.glob("*.sql"))


def apply_migrations(conn: psycopg.Connection, migrations_dir: Path) -> None:
    ensure_migration_table(conn)
    done = applied_versions(conn)
    for migration in migration_files(migrations_dir):
        version = migration.stem
        if version in done:
            continue
        sql_text = migration.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql_text)
            cur.execute("INSERT INTO mw_schema_migrations (version) VALUES (%s)", (version,))
        conn.commit()
