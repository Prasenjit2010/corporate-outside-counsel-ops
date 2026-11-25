from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from counselgrid import analytics
from counselgrid import repository as repo
from counselgrid.config import load_settings

TODAY = date(2026, 11, 25)


def test_afa_savings_only_counts_closed_afa_matters(db):
    matters = repo.list_matters(db)
    savings = analytics.afa_savings(matters)
    assert not savings.empty
    assert set(savings["status"]) == {"Closed"}
    assert set(savings["fee_structure"]) <= set(analytics.AFA_STRUCTURES)
    assert (savings["savings_usd"] > 0).all()


def test_spend_by_department_reconciles(db):
    matters = repo.list_matters(db)
    by_dept = analytics.spend_by_department(matters)
    assert by_dept["actual_spend_usd"].sum() == pytest.approx(matters["actual_spend_usd"].sum())


def test_msa_alert_levels():
    firms = pd.DataFrame(
        {
            "firm_name": ["A", "B", "C", "D", "E"],
            "msa_status": ["Active", "Active", "Active", "Expired", "Under Review"],
            "msa_expiration_date": [
                date(2027, 9, 1),
                date(2026, 12, 10),
                date(2027, 1, 30),
                date(2027, 6, 1),
                date(2027, 8, 1),
            ],
        }
    )
    levels = analytics.msa_alerts(firms, TODAY).set_index("firm_name")["alert_level"].to_dict()
    assert levels == {"A": "Current", "B": "Critical", "C": "Renewal Due", "D": "Expired", "E": "Renewal Due"}


def test_kpis(db):
    kpi = analytics.portfolio_kpis(repo.list_matters(db), repo.list_firms(db), TODAY)
    assert kpi["open_matters"] > 0
    assert 0 < kpi["afa_share"] < 1
    assert kpi["msa_attention"] >= 3


def test_backend_defaults_to_sqlite_without_credentials():
    s = load_settings({})
    assert s.backend == "sqlite" and s.postgres_dsn is None
    assert s.sqlite_path.name == "counselgrid.db"


def test_backend_uses_supabase_when_configured():
    s = load_settings({"SUPABASE_DB_URL": "postgresql://u:p@h:5432/postgres", "SUPABASE_DB_ROLE": "counselgrid_app"})
    assert s.backend == "postgres" and s.postgres_role == "counselgrid_app"


def test_local_override_wins_over_supabase(tmp_path):
    s = load_settings(
        {
            "SUPABASE_DB_URL": "postgresql://x",
            "COUNSELGRID_BACKEND": "sqlite",
            "COUNSELGRID_SQLITE_PATH": str(tmp_path / "x.db"),
        }
    )
    assert s.backend == "sqlite" and s.postgres_dsn is None
    assert s.sqlite_path == Path(tmp_path / "x.db")


def test_demo_seed_flag():
    assert load_settings({}).seed_demo_data is True
    assert load_settings({"COUNSELGRID_SEED_DEMO": "false"}).seed_demo_data is False
    with pytest.raises(ValueError):
        load_settings({"COUNSELGRID_SEED_DEMO": "maybe"})


def test_invalid_backend_rejected():
    with pytest.raises(ValueError):
        load_settings({"COUNSELGRID_BACKEND": "mysql"})
    with pytest.raises(ValueError):
        load_settings({"COUNSELGRID_BACKEND": "postgres"})
