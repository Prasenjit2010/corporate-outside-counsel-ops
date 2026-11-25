"""Tab 2: Legal Spend, Rate Benchmarking & Compliance Analytics."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .. import analytics
from .. import repository as repo
from ..db import Database
from .theme import ALERT_COLORS, AMBER, FEE_COLORS, NAVY, NAVY_MID, RED, SLATE_LIGHT, section

_CHART_CONFIG = {"displayModeBar": False}


def _usd(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:,.0f}K"
    return f"${value:,.0f}"


def _spend_chart(matters: pd.DataFrame) -> go.Figure:
    data = analytics.spend_by_department(matters)
    order = data.groupby("internal_department")["actual_spend_usd"].sum().sort_values().index.tolist()
    fig = go.Figure()
    for fee, color in FEE_COLORS.items():
        part = data[data["fee_structure"] == fee].set_index("internal_department").reindex(order).fillna(0)
        fig.add_bar(
            y=order,
            x=part["actual_spend_usd"],
            name=fee,
            orientation="h",
            marker_color=color,
            customdata=part["estimated_budget_usd"],
            hovertemplate="%{y} · " + fee + "<br>Spend %{x:$,.0f}<br>Budget %{customdata:$,.0f}<extra></extra>",
        )
    fig.update_layout(
        barmode="stack",
        title="Legal spend to date by department",
        height=330,
        xaxis=dict(tickprefix="$", tickformat="~s"),
    )
    return fig


def _afa_chart(matters: pd.DataFrame) -> go.Figure:
    savings = analytics.afa_savings(matters)
    labels = [t if len(t) <= 38 else t[:36] + "…" for t in savings["matter_title"]]
    fig = go.Figure()
    fig.add_bar(
        x=labels,
        y=savings["hourly_equivalent_usd"],
        name="Hourly-equivalent cost",
        marker_color=SLATE_LIGHT,
        hovertemplate="%{x}<br>Hourly equivalent %{y:$,.0f}<extra></extra>",
    )
    fig.add_bar(
        x=labels,
        y=savings["actual_spend_usd"],
        name="Actual AFA spend",
        marker_color=NAVY,
        customdata=savings["savings_pct"],
        hovertemplate="%{x}<br>Actual %{y:$,.0f}<br>Saved %{customdata:.0%}<extra></extra>",
    )
    fig.update_layout(
        barmode="group",
        title="Closed AFA matters: actual spend vs. hourly equivalent",
        height=360,
        yaxis=dict(tickprefix="$", tickformat="~s"),
        xaxis=dict(tickangle=-25, automargin=True),
    )
    return fig


def _cyber_chart(firms: pd.DataFrame) -> go.Figure:
    data = firms.sort_values("cyber_compliance_score")
    colors = [
        RED if s < analytics.CYBER_MIN_SCORE else (NAVY if s >= 90 else NAVY_MID)
        for s in data["cyber_compliance_score"]
    ]
    fig = go.Figure(
        go.Bar(
            x=data["cyber_compliance_score"],
            y=data["firm_name"],
            orientation="h",
            marker_color=colors,
            customdata=data[["am_law_tier", "msa_status"]],
            hovertemplate="%{y}<br>Score %{x}<br>%{customdata[0]} · MSA %{customdata[1]}<extra></extra>",
        )
    )
    fig.add_vline(
        x=analytics.CYBER_MIN_SCORE,
        line_dash="dot",
        line_color=RED,
        annotation_text=f"Panel floor {analytics.CYBER_MIN_SCORE}",
        annotation_position="top",
    )
    fig.update_layout(
        title="Cybersecurity compliance score by firm",
        height=24 * len(data) + 110,
        xaxis=dict(range=[50, 100]),
        yaxis=dict(automargin=True),
        showlegend=False,
    )
    return fig


def _rate_chart(firms: pd.DataFrame) -> go.Figure:
    tiers = ["AmLaw 50", "AmLaw 100", "Regional Boutique"]
    fig = go.Figure()
    for tier, color in zip(tiers, [NAVY, NAVY_MID, SLATE_LIGHT], strict=True):
        part = firms[firms["am_law_tier"] == tier]
        fig.add_box(
            y=part["blended_hourly_rate_usd"],
            name=tier,
            marker_color=color,
            boxpoints="all",
            jitter=0.35,
            pointpos=0,
            text=part["firm_name"],
            hovertemplate="%{text}<br>%{y:$,.0f}/hr<extra></extra>",
        )
    fig.update_layout(
        title="Blended hourly rate benchmark by tier", height=330, showlegend=False, yaxis=dict(tickprefix="$")
    )
    return fig


def render(db: Database, today: date) -> None:
    matters = repo.list_matters(db)
    firms = repo.list_firms(db)
    if matters.empty or firms.empty:
        st.info("No matters or firms recorded yet.")
        return
    kpi = analytics.portfolio_kpis(matters, firms, today)

    c = st.columns(5)
    c[0].metric("Spend to date", _usd(kpi["total_spend_usd"]))
    c[1].metric("Open matters", kpi["open_matters"], help=f"{_usd(kpi['open_budget_usd'])} open budget")
    c[2].metric("AFA share of matters", f"{kpi['afa_share']:.0%}")
    c[3].metric("Realized AFA savings", _usd(kpi["afa_savings_usd"]))
    c[4].metric("MSAs needing action", kpi["msa_attention"])

    section("Spend & fee arrangements")
    left, right = st.columns(2, gap="large")
    left.plotly_chart(_spend_chart(matters), width="stretch", config=_CHART_CONFIG)
    right.plotly_chart(_rate_chart(firms), width="stretch", config=_CHART_CONFIG)
    if not analytics.afa_savings(matters).empty:
        st.plotly_chart(_afa_chart(matters), width="stretch", config=_CHART_CONFIG)
    eff = analytics.effective_rate_by_fee_structure(matters)
    if not eff.empty:
        st.caption(
            "Effective rate on closed matters: "
            + " · ".join(
                f"{r.fee_structure} ${r.effective_rate_usd:,.0f}/hr vs ${r.benchmark_rate_usd:,.0f} blended "
                f"({int(r.matters)} matter{'' if int(r.matters) == 1 else 's'})"
                for r in eff.itertuples()
            )
        )

    section("MSA expiration alerts")
    alerts = analytics.msa_alerts(firms, today)
    attention = alerts[alerts["alert_level"] != "Current"]
    if attention.empty:
        st.success("Every Master Service Agreement is current for at least the next 90 days.")
    else:
        view = attention[
            ["firm_name", "am_law_tier", "msa_status", "msa_expiration_date", "days_to_expiry", "alert_level"]
        ].rename(
            columns={
                "firm_name": "Firm",
                "am_law_tier": "Tier",
                "msa_status": "MSA status",
                "msa_expiration_date": "Expires",
                "days_to_expiry": "Days to expiry",
                "alert_level": "Alert",
            }
        )
        st.dataframe(
            view.style.map(lambda v: f"color: {ALERT_COLORS.get(v, NAVY)}; font-weight: 600", subset=["Alert"]),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            f"Alerts: Expired, Critical (≤ {analytics.MSA_CRITICAL_DAYS} days), Renewal Due "
            f"(≤ {analytics.MSA_WARNING_DAYS} days or under review). As of {today:%B %d, %Y}."
        )

    section("Cybersecurity & data-handling compliance")
    st.plotly_chart(_cyber_chart(firms), width="stretch", config=_CHART_CONFIG)
    below = firms[firms["cyber_compliance_score"] < analytics.CYBER_MIN_SCORE]
    if not below.empty:
        st.markdown(
            f"<span style='color:{AMBER};font-size:.85rem'>{len(below)} firms fall below the panel floor and are "
            "flagged for a security review whenever they rank for a matter.</span>",
            unsafe_allow_html=True,
        )
