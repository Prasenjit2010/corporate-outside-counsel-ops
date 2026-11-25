"""Automated conflict gate.

Compares a proposed counterparty against every outside firm's entries in the
conflict registry using case-insensitive fuzzy matching on normalized entity
names. The gate is deliberately over-inclusive: a false positive costs an
ethics reviewer a few minutes, a false negative can disqualify counsel
mid-matter. Every match is surfaced with its score so a human makes the call.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field

from rapidfuzz import fuzz

HARD_BLOCK = "Hard Block - Active Representation"
SOFT_CHECK = "Soft Check - Historical/Waivable"
CLEAR = "Clear"
SEVERITIES = (HARD_BLOCK, SOFT_CHECK, CLEAR)

MATCH_THRESHOLD = 88.0
SUBSET_MIN_CHARS = 5

_LEGAL_SUFFIXES = {
    "inc",
    "incorporated",
    "llc",
    "l l c",
    "ltd",
    "limited",
    "corp",
    "corporation",
    "co",
    "company",
    "lp",
    "llp",
    "plc",
    "pllc",
    "pc",
    "gmbh",
    "sa",
    "ag",
    "nv",
    "bv",
}
_PUNCT = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")


def normalize_entity(name: str) -> str:
    """Canonical form used for matching: ASCII, lower case, no punctuation or legal suffixes."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    text = text.casefold().replace("&", " and ")
    text = text.replace("co-operative", "cooperative").replace("co-op", "cooperative")
    text = _SPACES.sub(" ", _PUNCT.sub(" ", text)).strip()
    tokens = text.split(" ") if text else []
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    if tokens and tokens[0] == "the":
        tokens.pop(0)
    return " ".join(tokens)


def entity_similarity(a: str, b: str) -> float:
    """Similarity in [0, 100] between two entity names.

    Uses the best of full-string ratio and token-sort ratio, plus token-set
    ratio (which treats "ApexCart" and "ApexCart Technologies" as a match)
    when the shorter name is distinctive enough to avoid matching on a single
    generic word.
    """
    na, nb = normalize_entity(a), normalize_entity(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 100.0
    score = max(fuzz.ratio(na, nb), fuzz.token_sort_ratio(na, nb))
    if min(len(na), len(nb)) >= SUBSET_MIN_CHARS:
        score = max(score, fuzz.token_set_ratio(na, nb))
    return round(float(score), 1)


@dataclass(frozen=True)
class ConflictRecord:
    conflict_id: int
    firm_id: int
    adverse_entity_name: str
    matter_type: str
    conflict_severity: str


@dataclass(frozen=True)
class ConflictMatch:
    record: ConflictRecord
    score: float


@dataclass
class FirmConflictStatus:
    firm_id: int
    level: str = CLEAR
    matches: list[ConflictMatch] = field(default_factory=list)

    @property
    def strongest_match(self) -> ConflictMatch | None:
        relevant = [m for m in self.matches if m.record.conflict_severity == self.level] or self.matches
        return max(relevant, key=lambda m: m.score) if relevant else None


def screen_counterparty(
    counterparty: str,
    conflicts: Iterable[ConflictRecord],
    threshold: float = MATCH_THRESHOLD,
) -> dict[int, FirmConflictStatus]:
    """Return the conflict status of every firm that has a registry match.

    Firms absent from the result have no Hard Block or Soft Check entry that
    resembles the counterparty. Entries already marked ``Clear`` by ethics
    review never block, but are not reported as matches either.
    """
    if not counterparty or not counterparty.strip():
        raise ValueError("A counterparty or opposing entity name is required to run the conflict gate.")
    results: dict[int, FirmConflictStatus] = {}
    for record in conflicts:
        if record.conflict_severity == CLEAR:
            continue
        score = entity_similarity(counterparty, record.adverse_entity_name)
        if score < threshold:
            continue
        status = results.setdefault(record.firm_id, FirmConflictStatus(firm_id=record.firm_id))
        status.matches.append(ConflictMatch(record=record, score=score))
        if record.conflict_severity == HARD_BLOCK:
            status.level = HARD_BLOCK
        elif status.level != HARD_BLOCK:
            status.level = SOFT_CHECK
    return results
