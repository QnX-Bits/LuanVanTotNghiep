from __future__ import annotations

import math

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from ..auth import current_user
from ..data.repository import get_active_version, load_frames, version_public
from ..domain.allocation import ADVISOR_METHOD
from ..models import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/compare")
def compare(user: dict = Depends(current_user), db: Session = Depends(get_db), profile: str = "can_bang", horizon: str = "trung_han"):
    version = get_active_version(db)
    frames = load_frames(db, version.id)
    backtest = frames["full_backtest_9scenarios.csv"]
    methods = ["EqualWeight", "Markowitz", "RiskParity", "HRP", "BlackLitterman", "RL", "MLP_MVO"]
    cohort = backtest[(backtest.risk_profile == profile) & (backtest.horizon == horizon)].copy()
    cohort["date"] = pd.to_datetime(cohort.date)
    cohort = cohort.sort_values("date")
    series = []
    for method in methods:
        group = cohort[cohort.method == method]
        cumulative = 1.0
        values = []
        for _, row in group.iterrows():
            cumulative *= 1 + float(row["return"])
            values.append({"month": pd.Timestamp(row.date).strftime("%Y-%m"), "value": cumulative - 1})
        series.append({"method": method, "returns": values})
    panel = frames["asset_panel_standardized.csv"]
    rf = panel[panel.symbol == "DEPOSIT_12M"].copy()
    rf["date"] = pd.to_datetime(rf.date)
    month_set = set(cohort.date.tolist())
    rf = rf[rf.date.isin(month_set)].sort_values("date")
    cumulative = 1.0
    deposit = []
    for _, row in rf.iterrows():
        cumulative *= 1 + float(row.monthly_return)
        deposit.append({"month": row.date.strftime("%Y-%m"), "value": cumulative - 1})
    series.append({"method": "Deposit 12M", "returns": deposit})
    perf = frames["performance_summary.csv"]
    selected = perf[(perf.risk_profile == profile) & (perf.horizon == horizon)]
    stats = [{"method": row.method, "annualised_return": float(row.annualised_return), "deposit_annualised_return": float(row.deposit_annualised_return), "volatility": float(row.volatility), "sharpe_ratio": float(row.sharpe_ratio), "max_drawdown": float(row.max_drawdown), "avg_turnover": float(row.avg_turnover), "n_months": int(row.n_months), "start": str(row.start), "end": str(row.end)} for _, row in selected.iterrows()]
    alloc = frames["allocation_current.csv"]
    allocation = alloc[(alloc.method == ADVISOR_METHOD) & (alloc.risk_profile == profile) & (alloc.horizon == horizon)]
    row = allocation.iloc[0]
    weights = {key.removeprefix("w_"): float(row[key]) for key in ("w_co_phieu", "w_bat_dong_san", "w_etf", "w_vang", "w_tien_gui", "w_trai_phieu")}
    holm = frames["holm_bonferroni_results.csv"]
    significant = int(holm[holm.hypothesis.isin(["H1", "H2", "H3"])]["reject_h0"].astype(bool).sum())
    return {"version": version_public(version, user["role"]), "profile": profile, "horizon": horizon, "advisor_method": ADVISOR_METHOD, "series": series, "metrics": stats, "target_weights": weights, "significant_tests": significant, "disclaimer_vi": "Thông tin tham khảo dựa trên dữ liệu lịch sử, không phải khuyến nghị đầu tư."}


@router.get("/methodology")
def methodology(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    version = get_active_version(db)
    frames = load_frames(db, version.id)
    table = frames["holm_bonferroni_results.csv"].copy()
    rows = []
    for _, row in table.iterrows():
        rows.append({"hypothesis": str(row.hypothesis), "pair": str(row.pair), "p_value": float(row.p_value), "jk_memmel_p_value": float(row.jk_p_value), "holm_threshold": float(row.threshold), "significant_after_holm": bool(row.reject_h0), "sharpe_difference": float(row.sharpe_diff), "bootstrap_mean_difference_unadjusted": float(row.bootstrap_mean_diff), "bootstrap_90_ci_low_unadjusted": float(row.bootstrap_ci_low), "bootstrap_90_ci_high_unadjusted": float(row.bootstrap_ci_high), "bootstrap_significant_90_unadjusted": bool(row.bootstrap_significant_90), "meaningful_improvement": bool(row.meaningful_improvement),
                     "minimum_detectable_difference": _num(row, "mde_sharpe_diff"), "months_needed_for_0_3": _num(row, "months_needed_for_0.3"), "conclusion": str(row.get("conclusion", ""))})
    primary = [row for row in rows if row["hypothesis"] in ("H1", "H2", "H3")]
    return {"version": version_public(version, user["role"]), "method": "Ledoit–Wolf (2008) studentized circular block bootstrap (HAC); Holm–Bonferroni within each hypothesis family; Jobson–Korkie–Memmel for reference", "bootstrap_adjusted": True, "rows": rows, "significant_count": sum(row["significant_after_holm"] for row in primary), "row_count": len(primary), "all_row_count": len(rows)}


def _num(row, key):
    value = row.get(key) if hasattr(row, "get") else None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else value


@router.get("/sensitivity")
def sensitivity(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    version = get_active_version(db)
    table = load_frames(db, version.id)["sensitivity_analysis.csv"]
    return {"version": version_public(version, user["role"]), "rows": [{"parameter": str(row.parameter), "value": str(row.value), "is_baseline": bool(row.is_baseline), "method": str(row.method), "sharpe_ratio": float(row.sharpe_ratio), "annualised_return": float(row.annualised_return), "delta_sharpe_vs_baseline": float(row.delta_sharpe_vs_baseline), "avg_deposit_weight": float(row.avg_w_tien_gui), "avg_gold_weight": float(row.avg_w_vang)} for _, row in table.iterrows()]}


@router.get("/models")
def models(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    version = get_active_version(db)
    table = load_frames(db, version.id)["model_comparison_summary_with_mlp.csv"]
    return {"version": version_public(version, user["role"]), "rows": [{"model": str(row.model), "avg_rmse": float(row.avg_rmse), "std_rmse": _num(row, "std_rmse"), "avg_directional_accuracy": _num(row, "avg_directional_acc"), "avg_directional_accuracy_ex_deposit": _num(row, "avg_directional_acc_ex_deposit"), "folds": int(row.n_folds), "r2_os": _num(row, "r2_os_pooled"), "clark_west_p": _num(row, "cw_pvalue"), "rank_ic": _num(row, "rank_ic_mean"), "classes_with_positive_r2": _num(row, "n_classes_r2_pos")} for _, row in table.iterrows()]}
