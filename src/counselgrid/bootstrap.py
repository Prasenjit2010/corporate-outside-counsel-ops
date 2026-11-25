"""Provision a Supabase (PostgreSQL) database for CounselGrid.

    python -m counselgrid.bootstrap            # schema + RLS, then seed if empty
    python -m counselgrid.bootstrap --no-seed  # schema + RLS only

Connects with SUPABASE_DB_URL as the migrating user (normally ``postgres``).
The application itself then runs as ``SUPABASE_DB_ROLE`` (counselgrid_app),
so every read and write it performs is governed by the RLS policies.
"""

from __future__ import annotations

import argparse
import sys

from .config import SQL_DIR, load_settings

TABLES = ("outside_firms", "firm_practice_capabilities", "conflict_registry", "matter_engagements")


def provision(dsn: str, seed: bool = True) -> dict[str, int]:
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
        already_seeded = conn.execute("SELECT COUNT(*) FROM outside_firms").fetchone()[0] > 0
        if seed and not already_seeded:
            with conn.transaction():
                conn.execute((SQL_DIR / "seed.sql").read_text(encoding="utf-8"))
                conn.execute((SQL_DIR / "post_seed.sql").read_text(encoding="utf-8"))
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply CounselGrid schema, RLS policies and seed data to Supabase.")
    parser.add_argument("--no-seed", action="store_true", help="apply schema and RLS only")
    args = parser.parse_args(argv)

    settings = load_settings()
    if settings.backend != "postgres" or not settings.postgres_dsn:
        print("SUPABASE_DB_URL is not set (or COUNSELGRID_BACKEND=sqlite). Nothing to provision.", file=sys.stderr)
        return 2
    counts = provision(settings.postgres_dsn, seed=not args.no_seed)
    for table, count in counts.items():
        print(f"{table:<28} {count:>5} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
