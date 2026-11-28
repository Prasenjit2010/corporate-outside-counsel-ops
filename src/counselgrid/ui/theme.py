"""Visual system: corporate-governance palette, page CSS and the Plotly template."""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

NAVY = "#14284B"
NAVY_MID = "#3C5A86"
SLATE = "#64748B"
SLATE_LIGHT = "#A9B6C8"
RULE = "#D9DFE7"
SURFACE = "#F4F6F9"
INK = "#0E1726"

RED = "#B42318"
AMBER = "#B54708"
GREEN = "#067647"

FEE_COLORS = {"Hourly": NAVY, "Capped Fee": NAVY_MID, "Fixed Retainer": SLATE_LIGHT}
ALERT_COLORS = {"Expired": RED, "Critical": AMBER, "Renewal Due": "#9A6700", "Current": GREEN}
COMPONENT_COLORS = {
    "bench_depth": NAVY,
    "cost_efficiency": NAVY_MID,
    "cyber_compliance": "#7C93B5",
    "afa_diversity": SLATE_LIGHT,
}

_FONT = "Inter, 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"

_CSS = f"""
<style>
  html, body, [class*="css"] {{ font-family: {_FONT}; }}
  .block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1360px; }}
  h1, h2, h3, h4 {{ color: {INK}; letter-spacing: -0.01em; }}
  .cg-masthead {{
      display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: .75rem;
      border-bottom: 2px solid {NAVY}; padding-bottom: .7rem; margin-bottom: .9rem;
  }}
  .cg-wordmark {{ font-size: 1.55rem; font-weight: 700; color: {NAVY}; line-height: 1.1; }}
  .cg-wordmark span {{ font-weight: 400; color: {SLATE}; }}
  .cg-sub {{ font-size: .86rem; color: {SLATE}; margin-top: .2rem; }}
  .cg-env {{
      font-size: .74rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em;
      color: {NAVY}; border: 1px solid {RULE}; background: {SURFACE}; padding: .3rem .6rem; border-radius: 3px;
  }}
  .cg-notice {{
      border-left: 3px solid {NAVY}; background: {SURFACE}; color: {INK};
      font-size: .82rem; line-height: 1.45; padding: .6rem .85rem; margin: 0 0 1.1rem 0;
  }}
  .cg-notice b {{ color: {NAVY}; }}
  .cg-section {{
      font-size: .74rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em;
      color: {SLATE}; border-bottom: 1px solid {RULE}; padding-bottom: .3rem; margin: 1.3rem 0 .7rem 0;
  }}
  .cg-gate {{ border: 1px solid {RULE}; border-top: 3px solid {RED}; padding: .7rem .9rem; margin-bottom: .6rem; }}
  .cg-gate.soft {{ border-top-color: {AMBER}; }}
  .cg-gate-title {{ font-weight: 650; color: {INK}; font-size: .92rem; }}
  .cg-gate-body {{ font-size: .82rem; color: {SLATE}; margin-top: .15rem; }}
  div[data-testid="stMetric"] {{ border: 1px solid {RULE}; padding: .55rem .8rem; background: #FFFFFF; }}
  div[data-testid="stMetricLabel"] p {{
      font-size: .74rem; text-transform: uppercase; letter-spacing: .05em; color: {SLATE};
  }}
  div[data-testid="stMetricValue"] {{ color: {NAVY}; font-size: 1.45rem; }}
  .stTabs [data-baseweb="tab-list"] {{ gap: 1.6rem; border-bottom: 1px solid {RULE}; }}
  .stTabs [data-baseweb="tab"] {{ padding-left: 0; padding-right: 0; font-weight: 600; }}
  .cg-footer {{
      margin-top: 2.5rem; border-top: 1px solid {RULE}; padding-top: .6rem; font-size: .74rem; color: {SLATE};
  }}
  @media (max-width: 640px) {{ .cg-wordmark {{ font-size: 1.2rem; }} }}
</style>
"""


def apply_page_style() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def register_plotly_template() -> None:
    template = go.layout.Template(
        layout=go.Layout(
            font=dict(family=_FONT, size=12, color=INK),
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            colorway=[NAVY, NAVY_MID, SLATE_LIGHT, SLATE, "#7C93B5"],
            margin=dict(l=8, r=8, t=44, b=8),
            title=dict(
                font=dict(size=13, color=INK),
                x=0.01,
                xanchor="left",
                xref="container",
                y=0.985,
                yanchor="top",
                yref="container",
            ),
            xaxis=dict(gridcolor="#EDF0F4", linecolor=RULE, zerolinecolor=RULE, ticks=""),
            yaxis=dict(gridcolor="#EDF0F4", linecolor=RULE, zerolinecolor=RULE, ticks=""),
            legend=dict(orientation="h", yanchor="top", y=-0.12, x=0, title_text=""),
            hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=RULE, font=dict(color=INK)),
        )
    )
    pio.templates["counselgrid"] = template
    pio.templates.default = "counselgrid"


def section(label: str) -> None:
    st.markdown(f'<div class="cg-section">{label}</div>', unsafe_allow_html=True)
