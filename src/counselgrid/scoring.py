"""Governance & value ranking of outside counsel for a new matter.

Pipeline for every firm on the panel, in order:

1. Conflict gate  -> Hard Block removes the firm outright.
2. MSA gate       -> only firms with an Active Master Service Agreement proceed.
3. Domain gate    -> the firm must have a practice capability in the matter's domain.
4. Scoring        -> remaining firms (including Soft Check firms, which are flagged
                     for an ethics waiver) are scored 0-100 with fixed weights.

Every component is normalized to [0, 1] against the eligible pool so the
breakdown shown to legal ops adds up exactly to the total score.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .conflict_gate import HARD_BLOCK, SOFT_CHECK, ConflictRecord, FirmConflictStatus, screen_counterparty

WEIGHTS: dict[str, float] = {
    "bench_depth": 0.35,
    "cost_efficiency": 0.30,
    "cyber_compliance": 0.20,
    "afa_diversity": 0.15,
}
COMPONENT_LABELS: dict[str, str] = {
    "bench_depth": "Domain bench depth",
    "cost_efficiency": "Cost efficiency vs. budget",
    "cyber_compliance": "Cyber / compliance",
    "afa_diversity": "AFA & diversity governance",
}

OUTCOME_HARD = "Hard Block"
OUTCOME_SOFT = "Soft Check - Waiver Required"
OUTCOME_ELIGIBLE = "Eligible"
OUTCOME_MSA = "Ineligible - MSA"
OUTCOME_DOMAIN = "Ineligible - No Domain Capability"

FEE_STRUCTURES = ("Hourly", "Capped Fee", "Fixed Retainer")
MIN_BUDGET_COVERAGE_HOURS = 150


@dataclass(frozen=True)
class MatterIntake:
    matter_title: str
    department: str
    corporate_domain: str
    counterparty: str
    budget_usd: float
    preferred_fee_structure: str

    def validate(self) -> None:
        if not self.matter_title.strip():
            raise ValueError("Matter title is required.")
        if not self.counterparty.strip():
            raise ValueError("Counterparty / opposing entity is required.")
        if self.budget_usd <= 0:
            raise ValueError("Budget cap must be greater than zero.")
        if self.preferred_fee_structure not in FEE_STRUCTURES:
            raise ValueError(f"Unknown fee structure: {self.preferred_fee_structure}")


@dataclass(frozen=True)
class FirmCandidate:
    firm_id: int
    firm_name: str
    am_law_tier: str
    msa_status: str
    blended_hourly_rate_usd: float
    alternative_fee_arrangement_available: bool
    diversity_certified: bool
    cyber_compliance_score: int
    partner_bench_depth: int | None
    jurisdiction_coverage: str | None


@dataclass
class ScreeningResult:
    firm: FirmCandidate
    outcome: str
    conflict: FirmConflictStatus | None = None
    components: dict[str, float] = field(default_factory=dict)
    score: float | None = None
    flags: list[str] = field(default_factory=list)

    @property
    def is_rankable(self) -> bool:
        return self.outcome in (OUTCOME_ELIGIBLE, OUTCOME_SOFT)

    @property
    def weighted_points(self) -> dict[str, float]:
        return {k: round(100 * WEIGHTS[k] * v, 1) for k, v in self.components.items()}


def _governance_component(firm: FirmCandidate, preferred_fee: str) -> float:
    afa_weight = 0.6 if preferred_fee != "Hourly" else 0.4
    return afa_weight * float(firm.alternative_fee_arrangement_available) + (1 - afa_weight) * float(
        firm.diversity_certified
    )


def evaluate_panel(
    intake: MatterIntake,
    firms: Iterable[FirmCandidate],
    conflicts: Iterable[ConflictRecord],
) -> list[ScreeningResult]:
    """Run all gates and score the surviving firms.

    Returns every firm: rankable firms first (highest score first), followed
    by hard-blocked and ineligible firms with the reason they were excluded.
    """
    intake.validate()
    conflict_status = screen_counterparty(intake.counterparty, conflicts)

    results: list[ScreeningResult] = []
    for firm in firms:
        status = conflict_status.get(firm.firm_id)
        if status and status.level == HARD_BLOCK:
            results.append(ScreeningResult(firm, OUTCOME_HARD, status))
        elif firm.msa_status != "Active":
            results.append(ScreeningResult(firm, OUTCOME_MSA, status, flags=[f"MSA {firm.msa_status}"]))
        elif not firm.partner_bench_depth:
            results.append(ScreeningResult(firm, OUTCOME_DOMAIN, status))
        elif status and status.level == SOFT_CHECK:
            results.append(ScreeningResult(firm, OUTCOME_SOFT, status, flags=["Ethics waiver required"]))
        else:
            results.append(ScreeningResult(firm, OUTCOME_ELIGIBLE, status))

    pool = [r for r in results if r.is_rankable]
    if pool:
        max_depth = max(r.firm.partner_bench_depth or 0 for r in pool)
        min_rate = min(r.firm.blended_hourly_rate_usd for r in pool)
        for r in pool:
            f = r.firm
            r.components = {
                "bench_depth": (f.partner_bench_depth or 0) / max_depth,
                "cost_efficiency": min_rate / f.blended_hourly_rate_usd,
                "cyber_compliance": f.cyber_compliance_score / 100.0,
                "afa_diversity": _governance_component(f, intake.preferred_fee_structure),
            }
            r.score = round(sum(100 * WEIGHTS[k] * v for k, v in r.components.items()), 1)
            coverage = intake.budget_usd / f.blended_hourly_rate_usd
            if coverage < MIN_BUDGET_COVERAGE_HOURS:
                r.flags.append(f"Budget covers only {coverage:,.0f} hrs at blended rate")
            if intake.preferred_fee_structure != "Hourly" and not f.alternative_fee_arrangement_available:
                r.flags.append(f"No AFA: {intake.preferred_fee_structure} unavailable")
            if f.cyber_compliance_score < 75:
                r.flags.append("Cyber score below 75: security review")

    order = {OUTCOME_ELIGIBLE: 0, OUTCOME_SOFT: 0, OUTCOME_HARD: 1, OUTCOME_MSA: 2, OUTCOME_DOMAIN: 3}
    results.sort(key=lambda r: (order[r.outcome], -(r.score or 0), r.firm.firm_name))
    return results


def estimated_hours(budget_usd: float, blended_rate_usd: float) -> int:
    """Hours of blended-rate work the budget buys; used as the hourly-equivalent baseline."""
    return max(0, round(budget_usd / blended_rate_usd))
