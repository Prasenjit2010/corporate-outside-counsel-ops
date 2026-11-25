"""Runtime configuration.

The storage backend is chosen from the environment:

* ``SUPABASE_DB_URL`` set  -> PostgreSQL (Supabase), governed by RLS.
* ``SUPABASE_DB_URL`` unset -> local SQLite file, created and seeded on first run.

``COUNSELGRID_BACKEND=sqlite`` forces the local fallback even when a Supabase
URL is present, which is how a firm guarantees nothing leaves the machine.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_ROOT / "sql"
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "counselgrid.db"

Backend = Literal["postgres", "sqlite"]


@dataclass(frozen=True)
class Settings:
    backend: Backend
    postgres_dsn: str | None
    postgres_role: str | None
    sqlite_path: Path
    seed_demo_data: bool = True


def _read_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file. Existing environment variables win."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_settings(env: Mapping[str, str] | None = None, env_file: Path | None = None) -> Settings:
    if env is None:
        merged = _read_env_file(env_file or PROJECT_ROOT / ".env")
        merged.update(os.environ)
        env = merged

    dsn = (env.get("SUPABASE_DB_URL") or "").strip() or None
    forced = (env.get("COUNSELGRID_BACKEND") or "").strip().lower()
    if forced not in ("", "postgres", "sqlite"):
        raise ValueError(f"COUNSELGRID_BACKEND must be 'postgres' or 'sqlite', got {forced!r}")
    if forced == "postgres" and dsn is None:
        raise ValueError("COUNSELGRID_BACKEND=postgres requires SUPABASE_DB_URL")

    backend: Backend = "postgres" if dsn and forced != "sqlite" else "sqlite"
    role = (env.get("SUPABASE_DB_ROLE") or "").strip() or None
    sqlite_path = Path(env.get("COUNSELGRID_SQLITE_PATH") or DEFAULT_SQLITE_PATH)
    if not sqlite_path.is_absolute():
        sqlite_path = PROJECT_ROOT / sqlite_path

    seed_flag = (env.get("COUNSELGRID_SEED_DEMO") or "true").strip().lower()
    if seed_flag not in ("true", "false", "1", "0", "yes", "no"):
        raise ValueError(f"COUNSELGRID_SEED_DEMO must be true or false, got {seed_flag!r}")

    return Settings(
        backend=backend,
        postgres_dsn=dsn if backend == "postgres" else None,
        postgres_role=role if backend == "postgres" else None,
        sqlite_path=sqlite_path,
        seed_demo_data=seed_flag in ("true", "1", "yes"),
    )
