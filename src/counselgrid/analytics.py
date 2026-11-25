"""Spend, rate-benchmarking and compliance metrics. Pure pandas, no I/O."""

from __future__ import annotations

from datetime import date

import pandas as pd

AFA_STRUCTURES = ("Capped Fee", "Fixed Retainer")
MSA_WARNING_DAYS = 90
MSA_CRITICAL_DAYS = 30
CYBER_MIN_SCORE = 75


def spend_by_department(matters: pd.DataFrame) -> pd.DataFrame:
    """Actual spend and budget by department and fee structure."""
    if matters.empty:
        return pd.DataFrame(
            columns=["internal_department", "fee_structure", "actual_spend_usd", "estimated_budget_usd"]
        )
    return (
        matters.groupby(["internal_department", "fee_structure"], as_index=False)[
            ["actual_spend_usd", "estimated_budget_usd"]
        ]
        .sum()
        .sort_values("actual_spend_usd", ascending=False)
    )


def afa_savings(matters: pd.DataFrame) -> pd.DataFrame:
    """Realized savings on closed AFA matters versus the hourly-equivalent cost.

    Hourly equivalent = estimated hours x the firm's blended hourly rate. Only
    closed matters are counted so in-flight spend is never reported as savings.
    """
    closed = matters[(matters["status"] == "Closed") & (matters["fee_structure"].isin(AFA_STRUCTURES))].copy()
    if closed.empty:
        return closed.assign(hourly_equivalent_usd=[], savings_usd=[], savings_pct=[])
    closed["hourly_equivalent_usd"] = closed["estimated_hours"] * closed["blended_hourly_rate_usd"]
    closed["savings_usd"] = closed["hourly_equivalent_usd"] - closed["actual_spend_usd"]
    closed["savings_pct"] = closed["savings_usd"] / closed["hourly_equivalent_usd"]
    return closed.sort_values("savings_usd", ascending=False)


def effective_rate_by_fee_structure(matters: pd.DataFrame) -> pd.DataFrame:
    """Effective $/hour on closed matters, by fee structure, against the blended-rate benchmark."""
    closed = matters[(matters["status"] == "Closed") & (matters["estimated_hours"] > 0)].copy()
    if closed.empty:
        return pd.DataFrame(columns=["fee_structure", "effective_rate_usd", "benchmark_rate_usd", "matters"])
    closed["effective_rate_usd"] = closed["actual_spend_usd"] / closed["estimated_hours"]
    return closed.groupby("fee_structure", as_index=False).agg(
        effective_rate_usd=("effective_rate_usd", "mean"),
        benchmark_rate_usd=("blended_hourly_rate_usd", "mean"),
        matters=("matter_id", "count"),
    )


def msa_alerts(firms: pd.DataFrame, today: date) -> pd.DataFrame:
    """Every firm's MSA position with an alert level, most urgent first."""
    df = firms.copy()
    df["days_to_expiry"] = df["msa_expiration_date"].map(lambda d: (d - today).days)

    def level(row: pd.Series) -> str:
        if row["msa_status"] == "Expired" or row["days_to_expiry"] < 0:
            return "Expired"
        if row["days_to_expiry"] <= MSA_CRITICAL_DAYS:
            return "Critical"
        if row["days_to_expiry"] <= MSA_WARNING_DAYS or row["msa_status"] == "Under Review":
            return "Renewal Due"
        return "Current"

    df["alert_level"] = df.apply(level, axis=1)
    rank = {"Expired": 0, "Critical": 1, "Renewal Due": 2, "Current": 3}
    return df.sort_values(
        by=["alert_level", "days_to_expiry"], key=lambda s: s.map(rank) if s.name == "alert_level" else s
    )


def portfolio_kpis(matters: pd.DataFrame, firms: pd.DataFrame, today: date) -> dict[str, float]:
    open_matters = matters[matters["status"] != "Closed"]
    savings = afa_savings(matters)
    alerts = msa_alerts(firms, today)
    return {
        "total_spend_usd": float(matters["actual_spend_usd"].sum()),
        "open_matters": int(len(open_matters)),
        "open_budget_usd": float(open_matters["estimated_budget_usd"].sum()),
        "afa_share": float(matters["fee_structure"].isin(AFA_STRUCTURES).mean()) if len(matters) else 0.0,
        "afa_savings_usd": float(savings["savings_usd"].sum()) if not savings.empty else 0.0,
        "msa_attention": int(alerts["alert_level"].isin(["Expired", "Critical", "Renewal Due"]).sum()),
        "below_cyber_floor": int((firms["cyber_compliance_score"] < CYBER_MIN_SCORE).sum()),
    }
