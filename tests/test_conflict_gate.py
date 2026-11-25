import pytest

from counselgrid.conflict_gate import (
    CLEAR,
    HARD_BLOCK,
    SOFT_CHECK,
    ConflictRecord,
    entity_similarity,
    normalize_entity,
    screen_counterparty,
)


def rec(cid, firm, name, severity):
    return ConflictRecord(cid, firm, name, "test matter", severity)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Meridian Freight Logistics, LLC", "meridian freight logistics"),
        ("  KILN & HEARTH Home Goods, Inc. ", "kiln and hearth home goods"),
        ("Sunvale Produce Co-operative", "sunvale produce cooperative"),
        ("The Patentia Licensing Corp.", "patentia licensing"),
        ("Café Holdings Ltd", "cafe holdings"),
    ],
)
def test_normalize_entity(raw, expected):
    assert normalize_entity(raw) == expected


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("meridian freight logistics", "Meridian Freight Logistics, LLC"),
        ("APEXCART", "ApexCart Technologies, Inc."),
        ("Bluewater Container Lines", "Bluewater Container Lines Ltd."),
        ("Crestline Retail Grp", "Crestline Retail Group, Inc."),
    ],
)
def test_variants_match(a, b):
    assert entity_similarity(a, b) >= 88


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Crestline Retail Group", "Harborview Retail Group"),
        ("Vantage Grocers", "Vantage Point Capital"),
        ("Co", "Coalition for Fair Retail Pricing"),
    ],
)
def test_distinct_entities_do_not_match(a, b):
    assert entity_similarity(a, b) < 88


def test_hard_block_takes_precedence_over_soft_check():
    records = [
        rec(1, 7, "Ironbridge Packaging Corporation", SOFT_CHECK),
        rec(2, 7, "Ironbridge Packaging Corp.", HARD_BLOCK),
        rec(3, 9, "Ironbridge Packaging", SOFT_CHECK),
    ]
    result = screen_counterparty("ironbridge packaging", records)
    assert result[7].level == HARD_BLOCK
    assert result[7].strongest_match.record.conflict_id == 2
    assert result[9].level == SOFT_CHECK


def test_cleared_entries_never_block():
    result = screen_counterparty("Greenleaf Pet Supply", [rec(1, 3, "Greenleaf Pet Supply Co", CLEAR)])
    assert result == {}


def test_counterparty_required():
    with pytest.raises(ValueError):
        screen_counterparty("   ", [])
