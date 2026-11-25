"""Supabase / PostgreSQL migration and RLS tests.

Run against a disposable database:
    COUNSELGRID_TEST_PG_DSN=postgresql://postgres@localhost/counselgrid_test pytest tests/test_postgres_rls.py
"""

import json
import os
from datetime import date

import pytest

DSN = os.environ.get("COUNSELGRID_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="COUNSELGRID_TEST_PG_DSN not set")


@pytest.fixture(scope="module")
def provisioned():
    import psycopg

    from counselgrid.bootstrap import provision

    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            "DROP TABLE IF EXISTS conflict_screening_log, matter_engagements, conflict_registry, "
            "firm_practice_capabilities, outside_firms CASCADE"
        )
    counts = provision(DSN)
    provision(DSN)  # re-running the migration must be harmless
    return counts


def test_provision_counts(provisioned):
    assert provisioned["outside_firms"] == 30
    assert provisioned["firm_practice_capabilities"] >= 75
    assert provisioned["conflict_registry"] == 45
    assert provisioned["matter_engagements"] == 25


def test_app_role_full_flow(provisioned):
    from counselgrid import repository as repo
    from counselgrid.db import PostgresDatabase
    from counselgrid.scoring import MatterIntake, evaluate_panel

    db = PostgresDatabase(DSN, role="counselgrid_app")
    assert len(repo.list_firms(db)) == 30
    intake = MatterIntake("PG flow", "HR", "Labor & Employment", "United Retail Workers", 400_000, "Hourly")
    results = evaluate_panel(intake, repo.panel_for_domain(db, intake.corporate_domain), repo.conflict_records(db))
    top = next(r for r in results if r.is_rankable)
    matter_id = repo.record_engagement(db, intake, top, results)
    assert matter_id > 25
    assert len(repo.screening_log(db, matter_id)) == 30
    new_conflict = repo.log_conflict(db, 2, "Northgate Cold Storage", "Lease", "Clear", date(2026, 11, 1))
    assert new_conflict > 45


def _as(conn, role, claims=None):
    conn.execute(f"SET ROLE {role}")
    conn.execute("SELECT set_config('request.jwt.claims', %s, false)", (json.dumps(claims or {}),))


def test_rls_policies(provisioned):
    import psycopg

    with psycopg.connect(DSN, autocommit=True) as conn:
        _as(conn, "counselgrid_app")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE conflict_registry SET conflict_severity = 'Clear' WHERE conflict_id = 1")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM conflict_registry WHERE conflict_id = 1")
        conn.execute("RESET ROLE")

        _as(conn, "anon")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM outside_firms")
        conn.execute("RESET ROLE")

        _as(conn, "authenticated", {"app_metadata": {"role": "viewer"}})
        assert conn.execute("SELECT COUNT(*) FROM outside_firms").fetchone()[0] == 30
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO conflict_registry (firm_id, adverse_entity_name, matter_type, conflict_severity) "
                "VALUES (1, 'X Corp', 'y', 'Clear')"
            )
        conn.execute("RESET ROLE")

        _as(conn, "authenticated", {"app_metadata": {"role": "legal_ops"}})
        conn.execute(
            "INSERT INTO conflict_registry (firm_id, adverse_entity_name, matter_type, conflict_severity) "
            "VALUES (1, 'Legal Ops Entry LLC', 'y', 'Clear')"
        )
        conn.execute("RESET ROLE")
