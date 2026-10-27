from __future__ import annotations

from datetime import date
from typing import Any

from dateutil.relativedelta import relativedelta


def next_rebalance_date(plan_date: date, horizon: str) -> date:
    if horizon == "ngan_han":
        return date(plan_date.year + (plan_date.month == 12), 1 if plan_date.month == 12 else plan_date.month + 1, 1)
    if horizon == "trung_han":
        next_month = ((plan_date.month - 1) // 3 + 1) * 3 + 1
        year = plan_date.year
        if next_month > 12:
            year += 1
            next_month = 1
        return date(year, next_month, 1)
    if horizon == "dai_han":
        return plan_date + relativedelta(years=1)
    raise ValueError("Unknown horizon")


def portfolio_drift(
    target_weights: dict[str, float],
    current_values: dict[str, float],
    target_values: dict[str, float],
) -> dict[str, Any]:
    total = sum(float(value) for value in current_values.values())
    if total <= 0:
        return {"weights": {}, "drift_pp": {}, "max_abs_drift_pp": 0.0, "rebalance_early": False}
    current_weights = {key: float(current_values.get(key, 0)) / total for key in target_weights}
    drift = {key: (current_weights[key] - float(target_weights[key])) * 100 for key in target_weights}
    maximum = max((abs(value) for value in drift.values()), default=0.0)
    return {"weights": current_weights, "drift_pp": drift, "max_abs_drift_pp": maximum, "rebalance_early": maximum > 5.0}
