"""
13_dashboard_summary_metrics.py (đợt 4)
Chỉ số hiệu quả (mục 6.2) cho mỗi (method x risk_profile x horizon) + bảng THEO NĂM.
- performance_summary.csv: lợi nhuận năm hóa, vol, Sharpe vượt trội, lãi tiền gửi cùng
  kỳ, max drawdown (QC 22: có điểm vốn ban đầu 1,0), turnover, số lần tái cân bằng.
- allocation_by_scenario.csv: tỷ trọng bình quân giai đoạn kiểm tra.
- performance_by_year.csv: Sharpe/lợi nhuận theo năm dương lịch (QC thứ tự làm, mục 4).
"""
import numpy as np
import pandas as pd
from importlib import import_module

common = import_module("common")
RF = common.load_rf()
WEIGHT_COLS = [f"w_{c}" for c in common.OUTPUT_CLASSES]


def compute_metrics(g: pd.DataFrame) -> pd.Series:
    g = g.sort_values("date")
    r = g["return"].values
    n = len(r)
    rf_m = RF.reindex(pd.DatetimeIndex(g["date"])).values
    return pd.Series({
        "annualised_return": common.annualised_return(r),
        "volatility": r.std(ddof=1) * np.sqrt(12) if n > 1 else np.nan,
        "sharpe_ratio": common.sharpe(g.set_index("date")["return"], RF),
        "deposit_annualised_return": common.annualised_return(rf_m),
        "max_drawdown": common.max_drawdown(r),
        "avg_turnover": g["turnover"].mean(),
        "avg_risky_share": g["risky_share"].mean(),
        "n_months": n,
        "n_rebalances": int(g["rebalanced"].sum()),
        "start": g["date"].min().strftime("%Y-%m"),
        "end": g["date"].max().strftime("%Y-%m"),
    })


def by_year(df):
    rows = []
    for (m, p, h), g in df.groupby(["method", "risk_profile", "horizon"]):
        g = g.set_index("date").sort_index()
        for y, gy in g.groupby(g.index.year):
            ex = common.excess(gy["return"], RF)
            rows.append({"method": m, "risk_profile": p, "horizon": h, "year": y, "n_months": len(gy),
                         "return": float(np.prod(1 + gy["return"]) - 1),
                         "deposit_return": float(np.prod(1 + RF.reindex(gy.index)) - 1),
                         "sharpe_ratio": float(ex.mean() / ex.std(ddof=1) * np.sqrt(12)) if len(gy) > 2 else np.nan})
    return pd.DataFrame(rows)


def main():
    df = pd.read_csv("data/processed/full_backtest_9scenarios.csv", parse_dates=["date"])
    summary = df.groupby(["method", "risk_profile", "horizon"]).apply(compute_metrics, include_groups=False).reset_index()
    summary["n_months"] = summary["n_months"].astype(int)
    summary["n_rebalances"] = summary["n_rebalances"].astype(int)
    common.write_csv(summary, "data/processed/performance_summary.csv", index=False)
    alloc = df.groupby(["method", "risk_profile", "horizon"])[WEIGHT_COLS].mean().reset_index()
    common.write_csv(alloc, "data/processed/allocation_by_scenario.csv", index=False)
    yr = by_year(df)
    common.write_csv(yr, "data/processed/performance_by_year.csv", index=False)
    print(summary[(summary.risk_profile == "can_bang") & (summary.horizon == "trung_han")].round(4).to_string(index=False))
    print("\nSharpe theo năm (Cân bằng/Trung hạn):")
    print(yr[(yr.risk_profile == "can_bang") & (yr.horizon == "trung_han")].pivot(
        index="method", columns="year", values="sharpe_ratio").round(2))


if __name__ == "__main__":
    main()
