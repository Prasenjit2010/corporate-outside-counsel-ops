# CounselGrid Architecture

## Layers

```
app.py (Streamlit)
  └─ ui/intake_tab · ui/analytics_tab · ui/registry_tab      presentation only
        │
        ├─ scoring.py ── conflict_gate.py                    pure domain logic, no I/O
        ├─ analytics.py                                      pure pandas
        └─ repository.py                                     the only module that writes SQL
              └─ db.py ── SQLiteDatabase | PostgresDatabase  one interface, two backends
                    └─ config.py                             backend chosen from environment
```

The domain logic (`conflict_gate`, `scoring`, `analytics`) takes plain dataclasses and DataFrames, so it is tested without a database or a browser.

## Backend selection

| Environment | Backend | Notes |
|---|---|---|
| `SUPABASE_DB_URL` unset | SQLite at `data/counselgrid.db` | Schema and seed are applied on first open; seeding happens only when the database is empty |
| `SUPABASE_DB_URL` set | PostgreSQL | Connects, then runs `SET ROLE` to `SUPABASE_DB_ROLE` so RLS governs the session |
| `COUNSELGRID_BACKEND=sqlite` | SQLite | Overrides a configured Supabase URL; useful for air-gapped installs |

Repository SQL uses `?` placeholders and ANSI joins, so the same statements run on both engines. The PostgreSQL backend translates placeholders and converts `Decimal`, `date` and `datetime` values so both backends produce identical DataFrames. `INSERT … RETURNING` is used on both (SQLite 3.35 or later).

## Transactions

`record_engagement` inserts the matter and every per-firm screening row inside one transaction. If any write fails, nothing is recorded, so a matter never exists without its gate decision.

## Security model

| Control | PostgreSQL (Supabase) | SQLite (local) |
|---|---|---|
| Read access | RLS: `authenticated` and `counselgrid_app` can read; `anon` is revoked | File-system permissions on the host |
| Write access | RLS: `counselgrid_app`, or a JWT whose `app_metadata.role` is `legal_ops` or `gc_admin` | The local operator |
| Conflict registry immutability | No UPDATE or DELETE grant to any application role | `BEFORE UPDATE` / `BEFORE DELETE` triggers abort |
| Network exposure | Supabase network restrictions apply | Streamlit binds to `localhost`; telemetry is off; no external assets are loaded |

## Scaling notes

- `conflict_registry` has a `pg_trgm` GIN index on `lower(adverse_entity_name)`. Past roughly 100,000 entries, pre-filter candidates in SQL with `similarity()` before the Python scoring pass instead of loading the whole registry.
- Ethical walls, corporate-family matching and billing enforcement are the natural next modules. Each attaches to the existing `firm_id` and `matter_id` keys without changing the current tables.
