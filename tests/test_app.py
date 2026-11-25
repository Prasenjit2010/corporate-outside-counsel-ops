"""End-to-end UI tests: run the real Streamlit script headlessly against a temp SQLite file."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.setenv("COUNSELGRID_BACKEND", "sqlite")
    monkeypatch.setenv("COUNSELGRID_SQLITE_PATH", str(tmp_path / "ui.db"))
    import streamlit as st

    st.cache_resource.clear()
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def test_app_renders_all_tabs_without_errors(app):
    assert not app.exception
    assert not app.error
    assert [t.label for t in app.tabs] == [
        "Counsel Selection & Conflict Gate",
        "Spend & Compliance Analytics",
        "Conflict & MSA Registry",
    ]
    assert any("does not provide legal advice" in m.value for m in app.markdown)


def test_intake_flow_blocks_conflicted_firms_and_logs_engagement(app):
    app.text_input[0].input("Carrier contract dispute")
    app.text_input[1].input("meridian freight logistics")
    app.button[0].click().run()
    assert not app.exception

    rendered = " ".join(m.value for m in app.markdown)
    assert "Harrow Delacroix LLP" in rendered, "hard-blocked firm must be shown as disqualified"
    assert "Calder Brennan Voss LLP" not in rendered or "Ineligible" in rendered

    log_button = next(b for b in app.button if b.label == "Log engagement")
    log_button.click().run()
    assert not app.exception
    assert any("logged to" in s.value for s in app.success)


def test_log_conflict_form(app):
    form_inputs = [
        t for t in app.text_input if t.label in ("Adverse entity name", "Nature of relationship / matter type")
    ]
    form_inputs[0].input("Northgate Cold Storage LLC")
    form_inputs[1].input("Represents landlord in lease dispute")
    next(b for b in app.button if b.label == "Log conflict entry").click().run()
    assert not app.exception
    assert any("Conflict #46 logged" in s.value for s in app.success)


def test_empty_install_renders(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.setenv("COUNSELGRID_BACKEND", "sqlite")
    monkeypatch.setenv("COUNSELGRID_SEED_DEMO", "false")
    monkeypatch.setenv("COUNSELGRID_SQLITE_PATH", str(tmp_path / "empty.db"))
    import streamlit as st

    st.cache_resource.clear()
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception
    at.text_input[0].input("First matter")
    at.text_input[1].input("Northgate Cold Storage")
    at.button[0].click().run()
    assert not at.exception
    assert any("No firm cleared every gate" in w.value for w in at.warning)
