"""CounselGrid Streamlit entry point:  streamlit run app.py"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from counselgrid import __version__  # noqa: E402
from counselgrid.config import load_settings  # noqa: E402
from counselgrid.db import Database, open_database  # noqa: E402
from counselgrid.ui import analytics_tab, intake_tab, registry_tab  # noqa: E402
from counselgrid.ui.theme import apply_page_style, register_plotly_template  # noqa: E402

GOVERNANCE_NOTICE = (
    "<b>Internal legal operations system.</b> CounselGrid supports conflict screening, outside counsel "
    "panel management and matter intake for an in-house legal department. It does not provide legal advice, "
    "does not predict case outcomes and is not available to the public. Every conflict finding, waiver and "
    "engagement decision remains the responsibility of a licensed attorney and the organization's ethics counsel."
)


@st.cache_resource(show_spinner="Opening governance database…")
def get_database() -> Database:
    return open_database(load_settings())


def main() -> None:
    st.set_page_config(page_title="CounselGrid", page_icon="⚖️", layout="wide")
    apply_page_style()
    register_plotly_template()

    try:
        db = get_database()
    except Exception as exc:  # surfaced to the operator instead of a stack trace
        st.error(f"Could not open the database: {exc}")
        st.caption("Check SUPABASE_DB_URL in .env, or remove it to run on the local SQLite database.")
        st.stop()

    st.markdown(
        f"""
        <div class="cg-masthead">
          <div>
            <div class="cg-wordmark">CounselGrid <span>/ Outside Counsel &amp; Conflict Governance</span></div>
            <div class="cg-sub">Matter intake · Conflict gate · Panel governance · Spend analytics</div>
          </div>
          <div class="cg-env">{db.describe()}</div>
        </div>
        <div class="cg-notice">{GOVERNANCE_NOTICE}</div>
        """,
        unsafe_allow_html=True,
    )

    selection, spend, registry = st.tabs(
        ["Counsel Selection & Conflict Gate", "Spend & Compliance Analytics", "Conflict & MSA Registry"]
    )
    with selection:
        intake_tab.render(db)
    with spend:
        analytics_tab.render(db, date.today())
    with registry:
        registry_tab.render(db)

    st.markdown(
        f'<div class="cg-footer">CounselGrid v{__version__} · Internal use only · Not legal advice · '
        "Conflict registry is append-only and every engagement decision is audit-logged.</div>",
        unsafe_allow_html=True,
    )


main()
