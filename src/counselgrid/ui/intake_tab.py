"""Tab 1: Outside Counsel Selection & Automated Conflict Gate."""

from __future__ import annotations

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .. import repository as repo
from ..db import Database
from ..scoring import (
    COMPONENT_LABELS,
    FEE_STRUCTURES,
    OUTCOME_DOMAIN,
    OUTCOME_HARD,
    OUTCOME_MSA,
    OUTCOME_SOFT,
    WEIGHTS,
    MatterIntake,
    ScreeningResult,
    evaluate_panel,
)
from .theme import COMPONENT_COLORS, section

_STATE_KEY = "cg_screening"


def _results_frame(ranked: list[ScreeningResult]) -> pd.DataFrame:
    rows = []
    for rank, r in enumerate(ranked, 1):
        pts = r.weighted_points
        rows.append(
            {
                "Rank": rank,
                "Firm": r.firm.firm_name,
                "Tier": r.firm.am_law_tier,
                "Gate": r.outcome,
                "Score": r.score,
                "Bench (35)": pts["bench_depth"],
                "Cost (30)": pts["cost_efficiency"],
                "Cyber (20)": pts["cyber_compliance"],
                "AFA/Div (15)": pts["afa_diversity"],
                "Partners": r.firm.partner_bench_depth,
                "Blended rate": r.firm.blended_hourly_rate_usd,
                "Flags": "; ".join(r.flags),
            }
        )
    return pd.DataFrame(rows)


def _composition_chart(ranked: list[ScreeningResult]) -> go.Figure:
    top = ranked[:10][::-1]
    fig = go.Figure()
    for key, label in COMPONENT_LABELS.items():
        fig.add_bar(
            y=[r.firm.firm_name for r in top],
            x=[r.weighted_points[key] for r in top],
            name=f"{label} ({int(WEIGHTS[key] * 100)}%)",
            orientation="h",
            marker_color=COMPONENT_COLORS[key],
            hovertemplate="%{y}<br>" + label + ": %{x:.1f} pts<extra></extra>",
        )
    fig.update_layout(
        barmode="stack",
        title="Score composition, top 10 eligible firms",
        height=max(260, 34 * len(top) + 90),
        xaxis=dict(title="Governance score (0-100)", range=[0, 100]),
        yaxis=dict(automargin=True),
    )
    return fig


def _gate_card(result: ScreeningResult, soft: bool) -> str:
    match = result.conflict.strongest_match if result.conflict else None
    detail = (
        f"Registry entry: <b>{escape(match.record.adverse_entity_name)}</b> · {escape(match.record.matter_type)} · "
        f"match {match.score:.0f}/100"
        if match
        else ""
    )
    css = "cg-gate soft" if soft else "cg-gate"
    return (
        f'<div class="{css}"><div class="cg-gate-title">{escape(result.firm.firm_name)}</div>'
        f'<div class="cg-gate-body">{detail}</div></div>'
    )


def _intake_form() -> MatterIntake | None:
    with st.form("matter_intake", border=True):
        st.markdown("**New matter intake**")
        title = st.text_input("Matter title", placeholder="e.g. Carrier contract dispute, Gulf Coast lanes")
        c1, c2 = st.columns(2)
        department = c1.selectbox("Requesting department", repo.DEPARTMENTS)
        domain = c2.selectbox("Corporate domain", repo.CORPORATE_DOMAINS, index=2)
        counterparty = st.text_input(
            "Counterparty / opposing entity",
            placeholder="e.g. Meridian Freight Logistics",
            help="Matched case-insensitively against the conflict registry, ignoring punctuation and legal suffixes.",
        )
        c3, c4 = st.columns(2)
        budget = c3.number_input("Budget cap (USD)", min_value=10_000, value=750_000, step=50_000, format="%d")
        fee = c4.selectbox("Preferred fee structure", FEE_STRUCTURES, index=1)
        submitted = st.form_submit_button("Run conflict gate & rank panel", type="primary", width="stretch")
    if not submitted:
        return None
    intake = MatterIntake(title, department, domain, counterparty, float(budget), fee)
    try:
        intake.validate()
    except ValueError as exc:
        st.error(str(exc))
        return None
    return intake


def _render_assignment(db: Database, intake: MatterIntake, results: list[ScreeningResult]) -> None:
    ranked = [r for r in results if r.is_rankable]
    section("Assign counsel and log engagement")
    if not ranked:
        st.warning("No firm cleared every gate. Escalate to the panel manager to source new counsel.")
        return
    labels = {f"{r.firm.firm_name}  ·  score {r.score:.1f}  ·  {r.outcome}": r for r in ranked}
    choice = st.selectbox("Selected firm", list(labels), index=0)
    selected = labels[choice]
    waiver_ok = True
    if selected.outcome == OUTCOME_SOFT:
        match = selected.conflict.strongest_match if selected.conflict else None
        st.warning(
            f"{selected.firm.firm_name} has a historical relationship with "
            f"{match.record.adverse_entity_name if match else 'the counterparty'}. "
            "An informed-consent conflict waiver must be executed before work begins."
        )
        waiver_ok = st.checkbox("Ethics counsel has approved proceeding subject to an executed waiver.")
    if st.button("Log engagement", type="primary", disabled=not waiver_ok):
        matter_id = repo.record_engagement(db, intake, selected, results)
        st.session_state.pop(_STATE_KEY, None)
        st.session_state["cg_last_matter"] = (matter_id, selected.firm.firm_name, intake.matter_title)
        st.rerun()


def render(db: Database) -> None:
    last = st.session_state.pop("cg_last_matter", None)
    if last:
        st.success(
            f"Matter #{last[0]} “{last[2]}” logged to {last[1]} with status Intake. "
            "The full gate decision for every panel firm was written to the screening audit log."
        )

    form_col, result_col = st.columns([0.36, 0.64], gap="large")
    with form_col:
        intake = _intake_form()
        st.caption(
            "Weights: bench depth 35% · cost efficiency 30% · cyber/compliance 20% · AFA & diversity 15%. "
            "Only firms with an Active MSA and capability in the selected domain are ranked."
        )
    if intake is not None:
        panel = repo.panel_for_domain(db, intake.corporate_domain)
        st.session_state[_STATE_KEY] = (intake, evaluate_panel(intake, panel, repo.conflict_records(db)))

    with result_col:
        stored = st.session_state.get(_STATE_KEY)
        if not stored:
            st.markdown("**How the gate works**")
            st.markdown(
                "1. **Conflict gate.** The counterparty is fuzzy-matched against every firm's registry entries. "
                "Active representation of the counterparty disqualifies the firm; historical work flags it for an "
                "ethics waiver.\n"
                "2. **MSA gate.** Firms whose Master Service Agreement is expired or under review are excluded.\n"
                "3. **Capability gate.** The firm must hold a practice capability in the matter's domain.\n"
                "4. **Ranking.** Survivors are scored on a transparent 100-point scale and the decision is logged."
            )
            return
        intake, results = stored
        ranked = [r for r in results if r.is_rankable]
        hard = [r for r in results if r.outcome == OUTCOME_HARD]
        soft = [r for r in ranked if r.outcome == OUTCOME_SOFT]
        excluded = [r for r in results if r.outcome in (OUTCOME_MSA, OUTCOME_DOMAIN)]

        st.markdown(f"**{intake.matter_title}** · {intake.department} · {intake.corporate_domain}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Panel screened", len(results))
        m2.metric("Hard blocked", len(hard))
        m3.metric("Waiver required", len(soft))
        m4.metric("Eligible & ranked", len(ranked))

        if hard or soft:
            section(f"Conflict gate findings for “{escape(intake.counterparty)}”")
            g1, g2 = st.columns(2)
            with g1:
                st.markdown("**Disqualified: active representation**")
                if hard:
                    st.markdown("".join(_gate_card(r, soft=False) for r in hard), unsafe_allow_html=True)
                else:
                    st.caption("None.")
            with g2:
                st.markdown("**Eligible only with ethics waiver**")
                if soft:
                    st.markdown("".join(_gate_card(r, soft=True) for r in soft), unsafe_allow_html=True)
                else:
                    st.caption("None.")
        else:
            st.info(f"No registry entry resembles “{intake.counterparty}”. No firm is conflicted out.")

    if not stored:
        return
    if ranked:
        section("Governance & value ranking")
        st.dataframe(
            _results_frame(ranked),
            hide_index=True,
            width="stretch",
            column_config={
                "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.1f"),
                "Blended rate": st.column_config.NumberColumn("Blended rate", format="dollar"),
            },
        )
        st.plotly_chart(_composition_chart(ranked), width="stretch", config={"displayModeBar": False})
    if excluded:
        with st.expander(f"Excluded before scoring ({len(excluded)} firms)"):
            st.dataframe(
                pd.DataFrame(
                    {
                        "Firm": [r.firm.firm_name for r in excluded],
                        "Reason": [r.outcome for r in excluded],
                        "MSA status": [r.firm.msa_status for r in excluded],
                        "Registry match": [r.conflict.level if r.conflict else "" for r in excluded],
                    }
                ),
                hide_index=True,
                width="stretch",
            )
    _render_assignment(db, intake, results)
