"""Data access for CounselGrid. All SQL lives here; callers get DataFrames or domain objects."""

from __future__ import annotations

from datetime import date

import pandas as pd

from .conflict_gate import SEVERITIES, ConflictRecord
from .db import Database, Rows
from .scoring import FirmCandidate, MatterIntake, ScreeningResult, estimated_hours

DEPARTMENTS = ("Supply Chain", "Corporate Affairs", "M&A", "HR", "Engineering")
CORPORATE_DOMAINS = (
    "M&A / Corporate Governance",
    "International Trade & Customs",
    "Supply Chain & Commercial Contracts",
    "IP & Patent Litigation",
    "Regulatory & Antitrust",
    "Labor & Employment",
    "Data Privacy & Cybersecurity",
)
MATTER_STATUSES = ("Intake", "Active", "On Hold", "Closed")

_BOOL_COLUMNS = ("diversity_certified", "alternative_fee_arrangement_available")


def _frame(rows: Rows) -> pd.DataFrame:
    df = pd.DataFrame(list(rows), columns=rows.columns)
    for col in _BOOL_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype(bool)
    return df


def list_firms(db: Database) -> pd.DataFrame:
    rows = db.query(
        """
        SELECT f.firm_id, f.firm_name, f.hq_city, f.state, f.am_law_tier, f.diversity_certified,
               f.msa_status, f.msa_expiration_date, f.blended_hourly_rate_usd,
               f.alternative_fee_arrangement_available, f.cyber_compliance_score,
               (SELECT COUNT(*) FROM firm_practice_capabilities c WHERE c.firm_id = f.firm_id) AS practice_count,
               (SELECT COUNT(*) FROM conflict_registry r
                 WHERE r.firm_id = f.firm_id AND r.conflict_severity <> 'Clear') AS open_conflicts
        FROM outside_firms f
        ORDER BY f.firm_name
        """
    )
    df = _frame(rows)
    if not df.empty:
        df["msa_expiration_date"] = pd.to_datetime(df["msa_expiration_date"]).dt.date
    return df


def list_capabilities(db: Database) -> pd.DataFrame:
    return _frame(
        db.query(
            """
            SELECT c.capability_id, c.firm_id, f.firm_name, c.corporate_domain,
                   c.partner_bench_depth, c.jurisdiction_coverage
            FROM firm_practice_capabilities c
            JOIN outside_firms f ON f.firm_id = c.firm_id
            ORDER BY f.firm_name, c.corporate_domain
            """
        )
    )


def list_conflicts(db: Database) -> pd.DataFrame:
    df = _frame(
        db.query(
            """
            SELECT r.conflict_id, r.firm_id, f.firm_name, r.adverse_entity_name, r.matter_type,
                   r.conflict_severity, r.logged_date
            FROM conflict_registry r
            JOIN outside_firms f ON f.firm_id = r.firm_id
            ORDER BY r.logged_date DESC, r.conflict_id DESC
            """
        )
    )
    if not df.empty:
        df["logged_date"] = pd.to_datetime(df["logged_date"]).dt.date
    return df


def conflict_records(db: Database) -> list[ConflictRecord]:
    rows = db.query(
        "SELECT conflict_id, firm_id, adverse_entity_name, matter_type, conflict_severity FROM conflict_registry"
    )
    return [ConflictRecord(**row) for row in rows]


def list_matters(db: Database) -> pd.DataFrame:
    df = _frame(
        db.query(
            """
            SELECT m.matter_id, m.internal_department, m.matter_title, m.corporate_domain,
                   m.opposing_or_counterparty_entity, m.estimated_budget_usd, m.selected_firm_id,
                   f.firm_name, f.blended_hourly_rate_usd, m.fee_structure, m.status,
                   m.estimated_hours, m.actual_spend_usd, m.created_at
            FROM matter_engagements m
            LEFT JOIN outside_firms f ON f.firm_id = m.selected_firm_id
            ORDER BY m.created_at DESC, m.matter_id DESC
            """
        )
    )
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True, format="mixed").dt.tz_localize(None)
    return df


def panel_for_domain(db: Database, corporate_domain: str) -> list[FirmCandidate]:
    rows = db.query(
        """
        SELECT f.firm_id, f.firm_name, f.am_law_tier, f.msa_status, f.blended_hourly_rate_usd,
               f.alternative_fee_arrangement_available, f.diversity_certified, f.cyber_compliance_score,
               c.partner_bench_depth, c.jurisdiction_coverage
        FROM outside_firms f
        LEFT JOIN firm_practice_capabilities c
               ON c.firm_id = f.firm_id AND c.corporate_domain = ?
        ORDER BY f.firm_id
        """,
        (corporate_domain,),
    )
    return [
        FirmCandidate(
            firm_id=int(r["firm_id"]),
            firm_name=r["firm_name"],
            am_law_tier=r["am_law_tier"],
            msa_status=r["msa_status"],
            blended_hourly_rate_usd=float(r["blended_hourly_rate_usd"]),
            alternative_fee_arrangement_available=bool(r["alternative_fee_arrangement_available"]),
            diversity_certified=bool(r["diversity_certified"]),
            cyber_compliance_score=int(r["cyber_compliance_score"]),
            partner_bench_depth=None if r["partner_bench_depth"] is None else int(r["partner_bench_depth"]),
            jurisdiction_coverage=r["jurisdiction_coverage"],
        )
        for r in rows
    ]


def log_conflict(
    db: Database,
    firm_id: int,
    adverse_entity_name: str,
    matter_type: str,
    conflict_severity: str,
    logged_date: date,
) -> int:
    name = adverse_entity_name.strip()
    if not name:
        raise ValueError("Adverse entity name is required.")
    if not matter_type.strip():
        raise ValueError("Matter type / nature of relationship is required.")
    if conflict_severity not in SEVERITIES:
        raise ValueError(f"Unknown conflict severity: {conflict_severity}")
    with db.transaction() as tx:
        return tx.insert_returning(
            """
            INSERT INTO conflict_registry (firm_id, adverse_entity_name, matter_type, conflict_severity, logged_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(firm_id), name, matter_type.strip(), conflict_severity, logged_date.isoformat()),
            "conflict_id",
        )


def record_engagement(
    db: Database,
    intake: MatterIntake,
    selected: ScreeningResult,
    screening: list[ScreeningResult],
) -> int:
    """Create the matter and write the full gate decision for every firm, atomically."""
    intake.validate()
    if not selected.is_rankable:
        raise ValueError(f"{selected.firm.firm_name} is not eligible ({selected.outcome}).")
    hours = estimated_hours(intake.budget_usd, selected.firm.blended_hourly_rate_usd)
    with db.transaction() as tx:
        matter_id = tx.insert_returning(
            """
            INSERT INTO matter_engagements (internal_department, matter_title, corporate_domain,
                opposing_or_counterparty_entity, estimated_budget_usd, selected_firm_id, fee_structure,
                status, estimated_hours, actual_spend_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Intake', ?, 0)
            """,
            (
                intake.department,
                intake.matter_title.strip(),
                intake.corporate_domain,
                intake.counterparty.strip(),
                float(intake.budget_usd),
                selected.firm.firm_id,
                intake.preferred_fee_structure,
                hours,
            ),
            "matter_id",
        )
        for result in screening:
            match = result.conflict.strongest_match if result.conflict else None
            tx.execute(
                """
                INSERT INTO conflict_screening_log (matter_id, firm_id, gate_outcome, matched_entity,
                    match_score, governance_score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    matter_id,
                    result.firm.firm_id,
                    result.outcome,
                    match.record.adverse_entity_name if match else None,
                    match.score if match else None,
                    result.score,
                ),
            )
    return matter_id


def screening_log(db: Database, matter_id: int) -> pd.DataFrame:
    return _frame(
        db.query(
            """
            SELECT s.screening_id, f.firm_name, s.gate_outcome, s.matched_entity, s.match_score,
                   s.governance_score, s.screened_at
            FROM conflict_screening_log s
            JOIN outside_firms f ON f.firm_id = s.firm_id
            WHERE s.matter_id = ?
            ORDER BY s.governance_score DESC, f.firm_name
            """,
            (int(matter_id),),
        )
    )
