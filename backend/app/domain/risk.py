from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import pandas as pd

from .allocation import ADVISOR_METHOD, ASSET_CLASSES


def round_vnd(value: float | Decimal) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def class_monthly_returns(panel: pd.DataFrame) -> pd.DataFrame:
    needed = {"date", "asset_class", "monthly_return"}
    if not needed.issubset(panel.columns):
        raise ValueError("asset panel is missing date, asset_class or monthly_return")
    p = panel.copy()
    p["date"] = pd.to_datetime(p["date"])
    return p.groupby(["date", "asset_class"], dropna=False)["monthly_return"].mean().unstack("asset_class").reindex(columns=ASSET_CLASSES).sort_index()


def risk_in_vnd(
    amount: int,
    weights: dict[str, float],
    metrics: dict[str, Any],
    backtest: pd.DataFrame,
    panel: pd.DataFrame,
    profile: str,
    horizon: str,
) -> dict[str, Any]:
    drawdown = float(metrics["max_drawdown"])
    loss = round_vnd(amount * drawdown)
    remaining = amount + loss

    scenario = backtest[
        (backtest["method"] == ADVISOR_METHOD)
        & (backtest["risk_profile"] == profile)
        & (backtest["horizon"] == horizon)
    ].copy()
    scenario["date"] = pd.to_datetime(scenario["date"])
    scenario = scenario.sort_values("date")
    returns = scenario["return"].astype(float).tolist()
    windows: list[float] = []
    for start in range(max(0, len(returns) - 11)):
        window = returns[start : start + 12]
        if len(window) == 12:
            growth = 1.0
            for value in window:
                growth *= 1 + value
            windows.append(growth - 1)
    if not windows:
        raise ValueError("The source scenario has no complete 12-month windows")
    windows.sort()
    median = windows[len(windows) // 2]
    low, high = windows[0], windows[-1]
    negative = sum(value < 0 for value in windows)

    class_returns = class_monthly_returns(panel)
    complete = class_returns.dropna(subset=list(ASSET_CLASSES))
    vn = class_returns["co_phieu"].dropna()
    s1_date = vn.loc[vn.index.isin(complete.index)].idxmin()
    notable_down = None
    stock_returns = vn.sort_index()
    for current in reversed(stock_returns.index.tolist()):
        prior = stock_returns.loc[stock_returns.index < current].tail(24).dropna()
        if len(prior) >= 12:
            threshold = 2 * float(prior.std(ddof=1))
            if float(stock_returns.loc[current]) <= -threshold:
                notable_down = current
                break
    s2_date = notable_down or s1_date

    def stress(date: pd.Timestamp) -> dict[str, Any]:
        row = class_returns.loc[date]
        portfolio_return = sum(float(weights[key]) * float(row[key]) for key in ASSET_CLASSES)
        return {
            "month": date.strftime("%Y-%m"),
            "portfolio_return": portfolio_return,
            "change_vnd": round_vnd(amount * portfolio_return),
            "class_returns": {key: float(row[key]) for key in ASSET_CLASSES},
        }

    return {
        "max_drawdown": drawdown,
        "drawdown_loss_vnd": loss,
        "remaining_vnd": remaining,
        "windows_12m": {"min": low, "median": median, "max": high, "negative_count": negative, "count": len(windows), "min_vnd": round_vnd(amount * low), "median_vnd": round_vnd(amount * median), "max_vnd": round_vnd(amount * high)},
        "last_12_months": [{"month": pd.Timestamp(row.date).strftime("%Y-%m"), "return": float(row["return"])} for _, row in scenario.tail(12).iterrows()],
        "stress_s1": stress(pd.Timestamp(s1_date)),
        "stress_s2": stress(pd.Timestamp(s2_date)),
    }
