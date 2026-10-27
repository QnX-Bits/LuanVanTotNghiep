from datetime import date
import random

import pytest

from app.domain.allocation import allocate_vnd, build_execution
from app.domain.profiling import assess_profile, allowed_choices, validate_profile_choice
from app.domain.schedule import next_rebalance_date


def test_balanced_profile_scoring_and_warnings():
    data = {"T1": 1, "T2": 2, "T3": 2, "T4": 2, "C1": 2, "C2": 2, "C3": 1, "H": "trung_han"}
    profile = assess_profile(data)
    assert profile.tolerance_score == 7
    assert profile.capacity_score == 5
    assert profile.system_profile == "can_bang"
    assert profile.warnings == ()


def test_conservative_short_profile_has_w1_w2_w4():
    data = {"T1": 3, "T2": 3, "T3": 3, "T4": 3, "C1": 1, "C2": 1, "C3": 1, "H": "ngan_han"}
    profile = assess_profile(data)
    assert profile.system_profile == "than_trong"
    assert set(profile.warnings) == {"W1", "W2", "W4"}


def test_growth_short_is_capped_and_cannot_ack_over_cap():
    data = {"T1": 3, "T2": 3, "T3": 3, "T4": 3, "C1": 3, "C2": 3, "C3": 3, "H": "ngan_han"}
    profile = assess_profile(data)
    assert profile.system_profile == "can_bang"
    assert "W3" in profile.warnings
    choices = {row["profile"]: row["enabled"] for row in allowed_choices(profile)}
    assert choices["tang_truong"] is False
    with pytest.raises(ValueError):
        validate_profile_choice(profile, "tang_truong", acknowledged=True)


def test_largest_remainder_conserves_exact_vnd():
    weights = [0.14145166, 0.05230868, 0.20623965, 0.00367719, 0.07756528, 0.51875754]
    for amount in [1_000_000, 100_000_000, 100_000_000_001]:
        if amount > 100_000_000_000:
            continue
        allocated = allocate_vnd(weights, amount)
        assert sum(allocated.values()) == amount
        assert all(value >= 0 for value in allocated.values())


def test_largest_remainder_conserves_exact_vnd_for_one_thousand_inputs():
    rng = random.Random(20261012)
    for _ in range(1_000):
        raw = [rng.random() for _ in range(6)]
        total = sum(raw)
        weights = [value / total for value in raw]
        amount = rng.randint(1_000_000, 100_000_000_000)
        allocation = allocate_vnd(weights, amount)
        assert sum(allocation.values()) == amount
        assert all(value >= 0 for value in allocation.values())


def test_allocation_matches_research_example():
    weights = [0.14145166, 0.05230868, 0.20623965, 0.00367719, 0.07756528, 0.51875754]
    amounts = allocate_vnd(weights, 100_000_000)
    assert list(amounts.values()) == [14_145_166, 5_230_868, 20_623_965, 367_719, 7_756_528, 51_875_754]


def test_rebalance_calendar_and_leap_day():
    assert next_rebalance_date(date(2026, 10, 12), "ngan_han") == date(2026, 11, 1)
    assert next_rebalance_date(date(2026, 10, 12), "trung_han") == date(2027, 1, 1)
    assert next_rebalance_date(date(2024, 2, 29), "dai_han") == date(2025, 2, 28)


def test_execution_closes_to_amount_and_receives_remainders():
    target = allocate_vnd([0.14145166, 0.05230868, 0.20623965, 0.00367719, 0.07756528, 0.51875754], 100_000_000)
    prices = {"VHM": 68_200, "NVL": 13_200, "KDH": 18_000, "DXG": 11_500, "E1VFVN30": 33_800, "GOLD_SJC": 145_500_000}
    result = build_execution(target, prices, 100_000_000)
    assert result["total_vnd"] == 100_000_000
    assert sum(result["executed_vnd"].values()) == 100_000_000
    assert result["executed_vnd"]["tien_gui"] > target["tien_gui"]
    assert result["max_deviation_pp"] <= 2


def test_execution_uses_current_real_estate_basket():
    target = allocate_vnd([0.0, 0.16, 0.24, 0.03, 0.07, 0.50], 200_000_000)
    prices = {"VHM": 74_050, "NVL": 13_000, "KDH": 17_450, "VPI": 58_091, "E1VFVN30": 33_700, "GOLD_SJC": 139_900_000}
    rules = {"re_symbols": ["VHM", "NVL", "KDH", "VPI"], "re_basket_year": 2026}
    result = build_execution(target, prices, 200_000_000, rules)
    re_lines = [line for line in result["lines"] if line["asset_class"] == "bat_dong_san"]
    assert [line["symbol"] for line in re_lines] == ["VHM", "NVL", "KDH", "VPI"]
    assert all("2026" in line["vehicle"] for line in re_lines)
    assert result["total_vnd"] == 200_000_000
