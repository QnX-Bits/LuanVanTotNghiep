from __future__ import annotations

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..data.repository import get_active_version, load_frames
from ..domain.allocation import ADVISOR_METHOD, ASSET_CLASSES, allocate_vnd, build_execution
from ..domain.profiling import CAPACITY_TEXT, HORIZON_LABELS, TOLERANCE_TEXT, assess_profile, validate_profile_choice
from ..domain.risk import risk_in_vnd
from ..domain.schedule import next_rebalance_date
from ..domain.why import why_sentences
from ..models import AuditLog, ExecutionRules, Plan, PlanSequence

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DISCLAIMER = "Thông tin tham khảo dựa trên dữ liệu lịch sử, không phải khuyến nghị đầu tư."
DISCLAIMER_EN = "For reference only, based on historical data; not investment advice."
DEFAULT_RULES = {
    "share_lot": 100,
    "etf_lot": 100,
    "etf_symbol": "E1VFVN30",
    "gold_unit": "chi",
    "fund_min_vnd": 100_000,
    "fund_step_vnd": 1_000,
    "re_deviation_threshold_pp": 2.0,
    "early_rebalance_threshold_pp": 5.0,
    "version": "rules-v1",
}


def ensure_default_rules(db: Session) -> ExecutionRules:
    row = db.get(ExecutionRules, "rules-v1")
    if row:
        return row
    row = ExecutionRules(id="rules-v1", rules={**DEFAULT_RULES}, is_current=True)
    db.add(row)
    db.flush()
    return row


def _sequence_code(db: Session, now: datetime) -> str:
    year = now.year
    sequence = db.get(PlanSequence, year)
    if sequence is None:
        sequence = PlanSequence(year=year, last_number=0)
        db.add(sequence)
        db.flush()
    sequence.last_number += 1
    db.flush()
    return f"PVN-{year}-{sequence.last_number:05d}"


def _find_row(frame: pd.DataFrame, **criteria: str) -> pd.Series:
    subset = frame
    for key, value in criteria.items():
        subset = subset[subset[key].astype(str) == str(value)]
    if len(subset) != 1:
        raise ValueError(f"Expected one exact research row, got {len(subset)} for {criteria}")
    return subset.iloc[0]


def build_plan_snapshot(db: Session, user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    amount = int(payload["amount_vnd"])
    if amount < 1_000_000 or amount > 100_000_000_000:
        raise ValueError("Investment amount must be between 1,000,000 and 100,000,000,000 VND")
    assessment = assess_profile(payload["answers"])
    chosen = payload.get("chosen_profile") or assessment.system_profile
    choice_type, ack_version = validate_profile_choice(assessment, chosen, bool(payload.get("acknowledged")))
    locale = "en" if payload.get("locale") == "en" else ("en" if user.get("locale") == "en" else "vi")
    version = get_active_version(db)
    frames = load_frames(db, version.id)
    allocation_row = _find_row(frames["allocation_current.csv"], method=ADVISOR_METHOD, risk_profile=chosen, horizon=assessment.horizon)
    performance_row = _find_row(frames["performance_summary.csv"], method=ADVISOR_METHOD, risk_profile=chosen, horizon=assessment.horizon)
    weight_columns = ["w_co_phieu", "w_bat_dong_san", "w_etf", "w_vang", "w_tien_gui", "w_trai_phieu"]
    weights = {asset: float(allocation_row[column]) for asset, column in zip(ASSET_CLASSES, weight_columns)}
    targets = allocate_vnd(weights, amount)
    panel = frames["asset_panel_standardized.csv"].copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel_month = panel["date"].max()
    prices_row = panel[panel.date == panel_month].set_index("symbol")["price"].astype(float).to_dict()
    # Research CSV encodes listed share/ETF prices in thousand VND and gold in VND per tael.
    rule = db.execute(select(ExecutionRules).where(ExecutionRules.is_current.is_(True))).scalars().first() or ensure_default_rules(db)
    etf_symbol = str(rule.rules.get("etf_symbol", "E1VFVN30"))
    basket = frames.get("re_basket_current.csv")
    exec_rules = dict(rule.rules)
    if basket is not None and len(basket):
        re_symbols = [str(s) for s in basket["symbol"]]
        execution_prices = {str(r.symbol): float(r.price) * 1000 for r in basket.itertuples()}
        exec_rules.update({"re_symbols": re_symbols, "re_basket_year": int(basket["year"].iloc[0])})
    else:
        re_symbols = ["VHM", "NVL", "KDH", "DXG"]
        execution_prices = {symbol: prices_row[symbol] * 1000 for symbol in re_symbols}
    execution_prices[etf_symbol] = prices_row[etf_symbol] * 1000
    execution_prices["GOLD_SJC"] = prices_row["GOLD_SJC"]
    execution = build_execution(targets, execution_prices, amount, exec_rules)
    metric_keys = ("annualised_return", "deposit_annualised_return", "volatility", "sharpe_ratio", "max_drawdown", "avg_turnover", "n_months", "n_rebalances", "start", "end")
    metrics = {key: (int(performance_row[key]) if key in ("n_months", "n_rebalances") else (str(performance_row[key]) if key in ("start", "end") else float(performance_row[key]))) for key in metric_keys}
    risk = risk_in_vnd(amount, weights, metrics, frames["full_backtest_9scenarios.csv"], panel, chosen, assessment.horizon)
    tests = frames["holm_bonferroni_results.csv"]
    now = datetime.now(TZ)
    rebalance_date = next_rebalance_date(now.date(), assessment.horizon)
    why = {
        "vi": why_sentences(assessment, chosen, weights, amount, metrics["annualised_return"], metrics["deposit_annualised_return"], "vi"),
        "en": why_sentences(assessment, chosen, weights, amount, metrics["annualised_return"], metrics["deposit_annualised_return"], "en"),
    }
    snapshot = {
        "answers": assessment.answers,
        "answer_text": {
            "vi": {**{f"T{i}": TOLERANCE_TEXT["vi"][i - 1][assessment.answers[f"T{i}"] - 1] for i in range(1, 5)}, **{f"C{i}": CAPACITY_TEXT["vi"][i - 1][assessment.answers[f"C{i}"] - 1] for i in range(1, 4)}, "H": HORIZON_LABELS[assessment.horizon]["vi"]},
            "en": {**{f"T{i}": TOLERANCE_TEXT["en"][i - 1][assessment.answers[f"T{i}"] - 1] for i in range(1, 5)}, **{f"C{i}": CAPACITY_TEXT["en"][i - 1][assessment.answers[f"C{i}"] - 1] for i in range(1, 4)}, "H": HORIZON_LABELS[assessment.horizon]["en"]},
        },
        "scores": {"tolerance": assessment.tolerance_score, "capacity": assessment.capacity_score},
        "tolerance_profile": assessment.tolerance_profile,
        "capacity_profile": assessment.capacity_profile,
        "system_profile": assessment.system_profile,
        "horizon_cap": assessment.horizon_cap,
        "chosen_profile": chosen,
        "choice_type": choice_type,
        "warnings": list(assessment.warnings),
        "acknowledgement": {"version": ack_version, "text": ("Tôi hiểu mức rủi ro này cao hơn đánh giá của hệ thống và tự chịu trách nhiệm với lựa chọn của mình." if ack_version and locale == "vi" else ("I understand this risk level is higher than the system assessment and accept responsibility for my choice." if ack_version else None)), "accepted_at": now.isoformat() if ack_version else None},
        "horizon": assessment.horizon,
        "amount_vnd": amount,
        "locale": locale,
        "result_version_id": version.id,
        "result_version_label": version.label,
        "manifest_provisional_month": version.manifest.get("provisional_month"),
        "manifest_data_through": version.manifest.get("data_through"),
        "manifest_validation": version.manifest.get("validation"),
        "test_summary": {"count": len(tests), "significant_after_holm": int(tests["reject_h0"].astype(bool).sum())},
        "reference_month": panel_month.strftime("%Y-%m"),
        "weights": weights,
        "targets_vnd": targets,
        "execution": execution,
        "execution_rules_id": rule.id,
        "execution_rules": rule.rules,
        "reference_prices": {key: int(value) for key, value in execution_prices.items()},
        "metrics": metrics,
        "risk_vnd": risk,
        "rebalance_date": rebalance_date.isoformat(),
        "rebalance_note": "hoặc ngày làm việc kế tiếp" if locale == "vi" else "or the next business day",
        "why": why,
        "disclaimer": {"vi": DISCLAIMER, "en": DISCLAIMER_EN},
        "created_at": now.isoformat(),
        "outdated": False,
    }
    return snapshot


def create_plan(db: Session, user: dict[str, Any], payload: dict[str, Any]) -> Plan:
    snapshot = build_plan_snapshot(db, user, payload)
    now = datetime.now(TZ)
    code = _sequence_code(db, now)
    rule_id = snapshot["execution_rules_id"]
    plan = Plan(code=code, user_id=user["key"], version_id=snapshot["result_version_id"], execution_rules_id=rule_id, snapshot=snapshot, created_at=now)
    db.add(plan)
    db.add(AuditLog(id=uuid.uuid4().hex, actor_id=user["key"], action="create_plan", entity="Plan", entity_id=code, after={"result_version_id": snapshot["result_version_id"], "profile": snapshot["chosen_profile"], "horizon": snapshot["horizon"]}))
    db.commit()
    db.refresh(plan)
    return plan


def public_plan(plan: Plan, viewer: dict[str, Any], shared: bool = False, ips: bool = False) -> dict[str, Any]:
    data = dict(plan.snapshot)
    data["outdated"] = bool(data.get("outdated", False))
    data.pop("result_version_id", None)
    data.pop("execution_rules_id", None)
    data["code"] = plan.code
    data["created_at"] = plan.created_at.isoformat()
    if shared:
        data.pop("answers", None)
        data.pop("answer_text", None)
        data.pop("acknowledgement", None)
        data.pop("owner_name", None)
        data.pop("user_id", None)
    elif viewer.get("role") == "admin":
        data["owner_name"] = {"an": "An Nguyễn", "binh": "Bình Trần"}.get(plan.user_id, "Demo user")
    return data


def saved_drift(plan: Plan, active_panel: pd.DataFrame) -> dict[str, Any]:
    snapshot = plan.snapshot
    current = pd.to_datetime(active_panel["date"]).max()
    reference = pd.Period(snapshot["reference_month"], freq="M")
    if pd.Period(current, freq="M") <= reference:
        return {"available": False, "message_vi": "Chưa có dữ liệu giá sau ngày lập kế hoạch.", "message_en": "No market data is available after the plan date."}
    # Revalue the six executed class amounts from the frozen reference point with subsequent class returns.
    from ..domain.risk import class_monthly_returns
    returns = class_monthly_returns(active_panel)
    later = returns[returns.index > pd.Timestamp(reference.start_time)]
    current_values = {}
    for asset in ASSET_CLASSES:
        value = float(snapshot["execution"]["executed_vnd"][asset])
        for ret in later[asset].dropna().tolist():
            value *= 1 + float(ret)
        current_values[asset] = value
    total = sum(current_values.values())
    target_weights = snapshot["weights"]
    drift = {asset: (current_values[asset] / total - float(target_weights[asset])) * 100 for asset in ASSET_CLASSES}
    maximum = max(abs(x) for x in drift.values())
    threshold = float(snapshot.get("execution_rules", {}).get("early_rebalance_threshold_pp", 5.0))
    return {"available": True, "current_values_vnd": current_values, "drift_pp": drift, "max_abs_drift_pp": maximum, "rebalance_early": maximum > threshold, "message_vi": f"Độ lệch lớn nhất {maximum:.2f} điểm %" + (f" — vượt ngưỡng {threshold:g}; cần xem xét tái cân bằng sớm." if maximum > threshold else "."), "message_en": f"Maximum drift {maximum:.2f} percentage points" + (f" — above {threshold:g} pp; consider rebalancing early." if maximum > threshold else ".")}
