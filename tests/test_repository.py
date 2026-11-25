import sqlite3
from datetime import date

import pytest

from counselgrid import repository as repo
from counselgrid.conflict_gate import HARD_BLOCK, SOFT_CHECK, screen_counterparty
from counselgrid.scoring import OUTCOME_HARD, MatterIntake, evaluate_panel


def test_seed_volumes(db):
    assert len(repo.list_firms(db)) == 30
    assert len(repo.list_capabilities(db)) >= 75
    assert len(repo.list_conflicts(db)) == 45
    assert len(repo.list_matters(db)) == 25


def test_seed_covers_required_hubs_and_domains(db):
    firms = repo.list_firms(db)
    assert {"New York", "Chicago", "Dallas", "Washington", "Bentonville", "Little Rock", "San Francisco"} <= set(
        firms["hq_city"]
    )
    assert set(repo.list_capabilities(db)["corporate_domain"]) == set(repo.CORPORATE_DOMAINS)
    severities = repo.list_conflicts(db)["conflict_severity"].value_counts()
    assert severities[HARD_BLOCK] > 0 and severities[SOFT_CHECK] > 0 and severities["Clear"] > 0


def test_no_seeded_matter_is_assigned_to_a_hard_blocked_firm(db):
    records = repo.conflict_records(db)
    for m in repo.list_matters(db).itertuples():
        status = screen_counterparty(m.opposing_or_counterparty_entity, records).get(m.selected_firm_id)
        assert status is None or status.level != HARD_BLOCK, m.matter_title


def test_seeding_is_idempotent(tmp_path):
    from counselgrid.db import SQLiteDatabase

    path = tmp_path / "again.db"
    SQLiteDatabase(path)
    assert len(repo.list_firms(SQLiteDatabase(path))) == 30


def test_empty_install_without_demo_data(tmp_path):
    from counselgrid.db import SQLiteDatabase

    empty = SQLiteDatabase(tmp_path / "empty.db", seed_demo_data=False)
    assert repo.list_firms(empty).empty
    assert repo.list_matters(empty).empty


def _intake(counterparty="Meridian Freight Logistics"):
    return MatterIntake(
        "Carrier dispute", "Supply Chain", "Supply Chain & Commercial Contracts", counterparty, 900_000, "Capped Fee"
    )


def test_record_engagement_writes_matter_and_full_audit(db):
    intake = _intake()
    results = evaluate_panel(intake, repo.panel_for_domain(db, intake.corporate_domain), repo.conflict_records(db))
    top = next(r for r in results if r.is_rankable)
    matter_id = repo.record_engagement(db, intake, top, results)

    matter = repo.list_matters(db).set_index("matter_id").loc[matter_id]
    assert matter["selected_firm_id"] == top.firm.firm_id
    assert matter["status"] == "Intake"
    assert matter["estimated_hours"] == round(900_000 / top.firm.blended_hourly_rate_usd)

    log = repo.screening_log(db, matter_id)
    assert len(log) == 30
    blocked = log[log["gate_outcome"] == "Hard Block"]
    assert "Harrow Delacroix LLP" in set(blocked["firm_name"])
    assert blocked["match_score"].min() >= 88


def test_record_engagement_refuses_blocked_firm(db):
    intake = _intake()
    results = evaluate_panel(intake, repo.panel_for_domain(db, intake.corporate_domain), repo.conflict_records(db))
    blocked = next(r for r in results if r.outcome == OUTCOME_HARD)
    with pytest.raises(ValueError):
        repo.record_engagement(db, intake, blocked, results)
    assert len(repo.list_matters(db)) == 25


def test_log_conflict_and_validation(db):
    new_id = repo.log_conflict(db, 1, "  Northgate Cold Storage LLC ", "Lease dispute", SOFT_CHECK, date(2026, 11, 20))
    row = repo.list_conflicts(db).set_index("conflict_id").loc[new_id]
    assert row["adverse_entity_name"] == "Northgate Cold Storage LLC"
    with pytest.raises(ValueError):
        repo.log_conflict(db, 1, " ", "x", SOFT_CHECK, date.today())
    with pytest.raises(ValueError):
        repo.log_conflict(db, 1, "X Corp", "x", "Maybe", date.today())


def test_conflict_registry_is_append_only(db):
    conn = sqlite3.connect(db.path)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE conflict_registry SET conflict_severity = 'Clear' WHERE conflict_id = 1")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM conflict_registry WHERE conflict_id = 1")
    conn.close()
