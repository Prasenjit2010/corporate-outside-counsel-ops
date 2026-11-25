import math

import pytest

from counselgrid.conflict_gate import HARD_BLOCK, SOFT_CHECK, ConflictRecord
from counselgrid.scoring import (
    OUTCOME_DOMAIN,
    OUTCOME_ELIGIBLE,
    OUTCOME_HARD,
    OUTCOME_MSA,
    OUTCOME_SOFT,
    WEIGHTS,
    FirmCandidate,
    MatterIntake,
    estimated_hours,
    evaluate_panel,
)


def firm(fid, *, msa="Active", rate=800.0, afa=True, div=True, cyber=85, depth=10):
    return FirmCandidate(fid, f"Firm {fid}", "AmLaw 100", msa, rate, afa, div, cyber, depth, "NY")


def intake(counterparty="Acme Widgets Inc.", budget=500_000, fee="Capped Fee"):
    return MatterIntake("Test matter", "Supply Chain", "Supply Chain & Commercial Contracts", counterparty, budget, fee)


def test_weights_sum_to_one():
    assert math.isclose(sum(WEIGHTS.values()), 1.0)


def test_gates_apply_in_order():
    firms = [
        firm(1),
        firm(2, msa="Expired"),
        firm(3, depth=None),
        firm(4),
        firm(5, msa="Expired"),
    ]
    conflicts = [
        ConflictRecord(1, 4, "Acme Widgets", "x", HARD_BLOCK),
        ConflictRecord(2, 1, "ACME Widgets, LLC", "x", SOFT_CHECK),
        ConflictRecord(3, 5, "Acme Widgets", "x", HARD_BLOCK),
    ]
    by_id = {r.firm.firm_id: r for r in evaluate_panel(intake(), firms, conflicts)}
    assert by_id[1].outcome == OUTCOME_SOFT and "Ethics waiver required" in by_id[1].flags
    assert by_id[2].outcome == OUTCOME_MSA
    assert by_id[3].outcome == OUTCOME_DOMAIN
    assert by_id[4].outcome == OUTCOME_HARD and by_id[4].score is None
    assert by_id[5].outcome == OUTCOME_HARD, "a hard conflict is reported even when the MSA is also lapsed"


def test_score_breakdown_adds_up_and_ranks_descending():
    firms = [firm(1, rate=1200, depth=30, cyber=95), firm(2, rate=600, depth=8, cyber=70, afa=False), firm(3)]
    results = evaluate_panel(intake(), firms, [])
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    for r in results:
        assert r.outcome == OUTCOME_ELIGIBLE
        assert 0 <= r.score <= 100
        assert math.isclose(sum(r.weighted_points.values()), r.score, abs_tol=0.25)


def test_best_in_pool_components_hit_maximum():
    results = evaluate_panel(intake(), [firm(1, rate=500, depth=40), firm(2, rate=1000, depth=10)], [])
    best = {r.firm.firm_id: r for r in results}
    assert best[1].components["bench_depth"] == 1.0
    assert best[1].components["cost_efficiency"] == 1.0
    assert best[2].components["cost_efficiency"] == pytest.approx(0.5)


def test_fee_preference_shifts_governance_weighting():
    afa_only = firm(1, afa=True, div=False)
    div_only = firm(2, afa=False, div=True)
    afa_pref = {r.firm.firm_id: r for r in evaluate_panel(intake(fee="Fixed Retainer"), [afa_only, div_only], [])}
    hourly = {r.firm.firm_id: r for r in evaluate_panel(intake(fee="Hourly"), [afa_only, div_only], [])}
    assert afa_pref[1].components["afa_diversity"] > afa_pref[2].components["afa_diversity"]
    assert hourly[2].components["afa_diversity"] > hourly[1].components["afa_diversity"]
    assert any("No AFA" in f for f in afa_pref[2].flags)


def test_budget_and_cyber_flags():
    results = evaluate_panel(intake(budget=50_000), [firm(1, rate=1000, cyber=60)], [])
    flags = " ".join(results[0].flags)
    assert "Budget covers only 50 hrs" in flags
    assert "Cyber score below 75" in flags


@pytest.mark.parametrize(
    "bad",
    [
        MatterIntake("", "HR", "Labor & Employment", "X", 1, "Hourly"),
        MatterIntake("T", "HR", "Labor & Employment", "", 1, "Hourly"),
        MatterIntake("T", "HR", "Labor & Employment", "X", 0, "Hourly"),
        MatterIntake("T", "HR", "Labor & Employment", "X", 1, "Contingency"),
    ],
)
def test_invalid_intake_rejected(bad):
    with pytest.raises(ValueError):
        evaluate_panel(bad, [firm(1)], [])


def test_estimated_hours():
    assert estimated_hours(500_000, 1_000) == 500
