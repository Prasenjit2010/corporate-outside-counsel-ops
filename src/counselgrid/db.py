"""Storage backends with one small, shared interface.

Repository code writes SQL with ``?`` placeholders; the PostgreSQL backend
translates them to psycopg's ``%s`` style. Rows come back as plain dicts with
NUMERIC values converted to float so both backends feed pandas identically.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from .config import SQL_DIR, Settings

Row = dict[str, Any]


class Rows(list):
    """Query result rows that remember their column names, even when empty."""

    def __init__(self, rows: list[Row], columns: list[str]) -> None:
        super().__init__(rows)
        self.columns = columns


Params = Sequence[Any]


class Session(Protocol):
    def execute(self, sql: str, params: Params = ()) -> None: ...

    def insert_returning(self, sql: str, params: Params, id_column: str) -> int: ...


class Database(Protocol):
    backend: str

    def query(self, sql: str, params: Params = ()) -> Rows: ...

    def transaction(self) -> Any: ...

    def describe(self) -> str: ...


def _split_statements(script: str) -> list[str]:
    """Split a seed script on statement-terminating semicolons outside quotes.

    Full-line ``--`` comments are dropped first so apostrophes in comments
    cannot unbalance the quote tracking.
    """
    body = "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("--"))
    statements: list[str] = []
    buf: list[str] = []
    in_quote = False
    for ch in body:
        if ch == "'":
            in_quote = not in_quote
        if ch == ";" and not in_quote:
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


# ----------------------------------------------------------------------------
# SQLite (local, zero-cloud fallback)
# ----------------------------------------------------------------------------


class _SQLiteSession:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql: str, params: Params = ()) -> None:
        self._conn.execute(sql, tuple(params))

    def insert_returning(self, sql: str, params: Params, id_column: str) -> int:
        cur = self._conn.execute(f"{sql} RETURNING {id_column}", tuple(params))
        return int(cur.fetchone()[0])


class SQLiteDatabase:
    backend = "sqlite"

    def __init__(self, path: Path, sql_dir: Path = SQL_DIR, seed_demo_data: bool = True) -> None:
        self.path = Path(path)
        self.seed_demo_data = seed_demo_data
        self.sql_dir = Path(sql_dir)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, detect_types=0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript((self.sql_dir / "sqlite_schema.sql").read_text(encoding="utf-8"))
            seeded = conn.execute("SELECT COUNT(*) FROM outside_firms").fetchone()[0]
            if self.seed_demo_data and not seeded:
                for stmt in _split_statements((self.sql_dir / "seed.sql").read_text(encoding="utf-8")):
                    conn.execute(stmt)

    def query(self, sql: str, params: Params = ()) -> Rows:
        conn = self._connect()
        try:
            cur = conn.execute(sql, tuple(params))
            columns = [c[0] for c in cur.description]
            return Rows([dict(r) for r in cur.fetchall()], columns)
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        conn = self._connect()
        try:
            yield _SQLiteSession(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def describe(self) -> str:
        return f"Local SQLite · {self.path.name}"


# ----------------------------------------------------------------------------
# PostgreSQL (Supabase)
# ----------------------------------------------------------------------------


def _pg_sql(sql: str) -> str:
    return sql.replace("%", "%%").replace("?", "%s")


def _pg_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


class _PostgresSession:
    def __init__(self, cursor: Any) -> None:
        self._cur = cursor

    def execute(self, sql: str, params: Params = ()) -> None:
        self._cur.execute(_pg_sql(sql), tuple(params))

    def insert_returning(self, sql: str, params: Params, id_column: str) -> int:
        self._cur.execute(f"{_pg_sql(sql)} RETURNING {id_column}", tuple(params))
        return int(self._cur.fetchone()[0])


class PostgresDatabase:
    backend = "postgres"

    def __init__(self, dsn: str, role: str | None = None) -> None:
        import psycopg

        self._psycopg = psycopg
        self._dsn = dsn
        self._role = role
        with self._connect():
            pass

    def _connect(self) -> Any:
        conn = self._psycopg.connect(self._dsn, connect_timeout=10)
        if self._role:
            from psycopg import sql as pgsql

            conn.execute(pgsql.SQL("SET ROLE {}").format(pgsql.Identifier(self._role)))
            conn.commit()
        return conn

    def query(self, sql: str, params: Params = ()) -> Rows:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_pg_sql(sql), tuple(params))
            cols = [c.name for c in cur.description]
            return Rows([{c: _pg_value(v) for c, v in zip(cols, row, strict=True)} for row in cur.fetchall()], cols)

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
            yield _PostgresSession(cur)

    def describe(self) -> str:
        role = f" · role {self._role}" if self._role else ""
        return f"Supabase PostgreSQL{role}"


def open_database(settings: Settings) -> Database:
    if settings.backend == "postgres" and settings.postgres_dsn:
        return PostgresDatabase(settings.postgres_dsn, settings.postgres_role)
    return SQLiteDatabase(settings.sqlite_path, seed_demo_data=settings.seed_demo_data)
