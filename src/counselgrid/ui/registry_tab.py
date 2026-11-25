"""Tab 3: Conflict & MSA Governance Registry."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from .. import repository as repo
from ..conflict_gate import SEVERITIES, entity_similarity
from ..db import Database
from .theme import AMBER, GREEN, RED, section

_SEVERITY_COLORS = {SEVERITIES[0]: RED, SEVERITIES[1]: AMBER, SEVERITIES[2]: GREEN}


def _contains(series: pd.Series, needle: str) -> pd.Series:
    return series.fillna("").str.contains(needle, case=False, regex=False)


def _msa_registry(firms: pd.DataFrame) -> None:
    section("Master Service Agreement registry")
    c1, c2, c3 = st.columns([0.5, 0.25, 0.25])
    search = c1.text_input("Search firms", placeholder="Firm name or city", key="msa_search")
    statuses = c2.multiselect("MSA status", ["Active", "Under Review", "Expired"], key="msa_status")
    tiers = c3.multiselect("Tier", ["AmLaw 50", "AmLaw 100", "Regional Boutique"], key="msa_tier")
    view = firms
    if search:
        view = view[_contains(view["firm_name"], search) | _contains(view["hq_city"], search)]
    if statuses:
        view = view[view["msa_status"].isin(statuses)]
    if tiers:
        view = view[view["am_law_tier"].isin(tiers)]
    st.dataframe(
        view[
            [
                "firm_name",
                "hq_city",
                "state",
                "am_law_tier",
                "msa_status",
                "msa_expiration_date",
                "blended_hourly_rate_usd",
                "alternative_fee_arrangement_available",
                "diversity_certified",
                "cyber_compliance_score",
                "practice_count",
                "open_conflicts",
            ]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "firm_name": "Firm",
            "hq_city": "HQ",
            "state": "State",
            "am_law_tier": "Tier",
            "msa_status": "MSA status",
            "msa_expiration_date": "MSA expires",
            "blended_hourly_rate_usd": st.column_config.NumberColumn("Blended rate", format="dollar"),
            "alternative_fee_arrangement_available": st.column_config.CheckboxColumn("AFA"),
            "diversity_certified": st.column_config.CheckboxColumn("Diversity cert."),
            "cyber_compliance_score": st.column_config.ProgressColumn("Cyber", min_value=0, max_value=100, format="%d"),
            "practice_count": "Practices",
            "open_conflicts": "Open conflicts",
        },
    )
    st.caption(f"{len(view)} of {len(firms)} panel firms shown.")


def _conflict_disclosures(conflicts: pd.DataFrame) -> None:
    section("Conflict disclosures")
    c1, c2 = st.columns([0.6, 0.4])
    search = c1.text_input(
        "Search disclosures",
        placeholder="Adverse entity, firm or matter type",
        key="conflict_search",
        help="Entity search is fuzzy: 'apexcart' finds 'ApexCart Technologies, Inc.'",
    )
    severities = c2.multiselect("Severity", list(SEVERITIES), key="conflict_severity")
    view = conflicts
    if search:
        fuzzy = view["adverse_entity_name"].map(lambda name: entity_similarity(search, name) >= 80)
        view = view[fuzzy | _contains(view["firm_name"], search) | _contains(view["matter_type"], search)]
    if severities:
        view = view[view["conflict_severity"].isin(severities)]
    shown = view[["conflict_id", "logged_date", "firm_name", "adverse_entity_name", "matter_type", "conflict_severity"]]
    st.dataframe(
        shown.style.map(
            lambda v: f"color: {_SEVERITY_COLORS.get(v, 'inherit')}; font-weight: 600", subset=["conflict_severity"]
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "conflict_id": "ID",
            "logged_date": "Logged",
            "firm_name": "Firm",
            "adverse_entity_name": "Adverse entity",
            "matter_type": "Nature of relationship",
            "conflict_severity": "Severity",
        },
    )
    st.download_button(
        "Export disclosures (CSV)",
        shown.to_csv(index=False).encode("utf-8"),
        file_name=f"counselgrid-conflict-disclosures-{date.today():%Y%m%d}.csv",
        mime="text/csv",
    )


def _log_conflict_form(db: Database, firms: pd.DataFrame, conflicts: pd.DataFrame) -> None:
    section("Log a new adverse-party conflict")
    if firms.empty:
        st.caption("Add panel firms to the database before logging conflict disclosures.")
        return
    firm_names = dict(zip(firms["firm_name"], firms["firm_id"], strict=True))
    with st.form("log_conflict", clear_on_submit=True):
        c1, c2 = st.columns(2)
        firm = c1.selectbox("Outside firm", list(firm_names))
        entity = c2.text_input("Adverse entity name", placeholder="Full legal name, e.g. Ironbridge Packaging Corp.")
        c3, c4, c5 = st.columns([0.45, 0.35, 0.2])
        matter_type = c3.text_input(
            "Nature of relationship / matter type", placeholder="e.g. Represents supplier in breach of contract claim"
        )
        severity = c4.selectbox("Severity", SEVERITIES)
        logged = c5.date_input("Logged date", value=date.today(), max_value=date.today())
        submitted = st.form_submit_button("Log conflict entry", type="primary")
    if not submitted:
        return
    try:
        conflict_id = repo.log_conflict(db, int(firm_names[firm]), entity, matter_type, severity, logged)
    except ValueError as exc:
        st.error(str(exc))
        return
    similar = conflicts[conflicts["adverse_entity_name"].map(lambda n: entity_similarity(entity, n) >= 88)]
    st.success(f"Conflict #{conflict_id} logged for {firm}. Entries are append-only and cannot be edited.")
    if not similar.empty:
        st.info(
            "Related registry entries for this entity: "
            + "; ".join(f"{r.firm_name} ({r.conflict_severity})" for r in similar.itertuples())
        )


def _engagement_register(db: Database) -> None:
    section("Engagement register & screening audit trail")
    matters = repo.list_matters(db)
    st.dataframe(
        matters[
            [
                "matter_id",
                "created_at",
                "internal_department",
                "matter_title",
                "opposing_or_counterparty_entity",
                "firm_name",
                "fee_structure",
                "status",
                "estimated_budget_usd",
                "actual_spend_usd",
            ]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "matter_id": "Matter",
            "created_at": st.column_config.DatetimeColumn("Opened", format="YYYY-MM-DD"),
            "internal_department": "Department",
            "matter_title": "Matter title",
            "opposing_or_counterparty_entity": "Counterparty",
            "firm_name": "Counsel",
            "fee_structure": "Fee",
            "status": "Status",
            "estimated_budget_usd": st.column_config.NumberColumn("Budget", format="dollar"),
            "actual_spend_usd": st.column_config.NumberColumn("Spend", format="dollar"),
        },
    )
    if matters.empty:
        st.caption("No matters have been logged yet.")
        return
    options = {f"#{r.matter_id} · {r.matter_title}": int(r.matter_id) for r in matters.itertuples()}
    pick = st.selectbox("View conflict-gate decision for matter", list(options), key="audit_matter")
    log = repo.screening_log(db, options[pick])
    if log.empty:
        st.caption("This matter predates CounselGrid screening; no gate decision is on file.")
    else:
        st.dataframe(
            log.drop(columns=["screening_id"]),
            hide_index=True,
            width="stretch",
            column_config={
                "firm_name": "Firm",
                "gate_outcome": "Gate outcome",
                "matched_entity": "Matched registry entity",
                "match_score": "Match",
                "governance_score": "Score",
                "screened_at": "Screened",
            },
        )


def render(db: Database) -> None:
    firms = repo.list_firms(db)
    conflicts = repo.list_conflicts(db)
    _msa_registry(firms)
    _conflict_disclosures(conflicts)
    _log_conflict_form(db, firms, conflicts)
    _engagement_register(db)
