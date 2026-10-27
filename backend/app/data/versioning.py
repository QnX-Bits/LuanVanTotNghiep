from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {
    "performance_summary.csv": ["method", "risk_profile", "horizon", "annualised_return", "volatility", "sharpe_ratio", "deposit_annualised_return", "max_drawdown", "avg_turnover", "n_months", "n_rebalances", "start", "end"],
    "allocation_current.csv": ["method", "risk_profile", "horizon", "as_of", "w_co_phieu", "w_bat_dong_san", "w_etf", "w_vang", "w_tien_gui", "w_trai_phieu"],
    "full_backtest_9scenarios.csv": ["method", "risk_profile", "horizon", "decision_date", "date", "rebalanced", "gross_return", "turnover", "transaction_cost", "return", "w_co_phieu", "w_bat_dong_san", "w_etf", "w_vang", "w_tien_gui", "w_trai_phieu"],
    "holm_bonferroni_results.csv": ["hypothesis", "pair", "p_value", "threshold", "reject_h0", "jk_z_stat", "jk_p_value", "sharpe_diff", "bootstrap_mean_diff", "bootstrap_ci_low", "bootstrap_ci_high", "bootstrap_significant_90", "meaningful_improvement"],
    "all_7methods_returns.csv": ["date", "EqualWeight", "Markowitz", "RiskParity", "HRP", "BlackLitterman", "RL", "MLP_MVO"],
    "sensitivity_analysis.csv": ["parameter", "value", "is_baseline", "method", "sharpe_ratio", "annualised_return", "avg_w_tien_gui", "avg_w_vang", "delta_sharpe_vs_baseline"],
    "model_comparison_summary_with_mlp.csv": ["model", "avg_rmse", "std_rmse", "avg_directional_acc", "avg_directional_acc_ex_deposit", "n_folds"],
    "asset_panel_standardized.csv": ["date", "symbol", "asset_class", "price", "monthly_return", "data_quality"],
}
# File tùy chọn: có thì nạp + kiểm tra cột, không có thì bỏ qua (bản kết quả cũ vẫn hợp lệ)
OPTIONAL_COLUMNS = {
    "re_basket_current.csv": ["year", "symbol", "price"],      # rổ cổ phiếu BĐS năm hiện hành (QC 4) cho luồng thực hiện
}
WEIGHT_COLUMNS = ["w_co_phieu", "w_bat_dong_san", "w_etf", "w_vang", "w_tien_gui", "w_trai_phieu"]
RISK_BANDS = {"than_trong": (0.10, 0.30), "can_bang": (0.40, 0.60), "tang_truong": (0.70, 0.90)}
REQUIRED_SYMBOLS = {"VNINDEX", "VHM", "NVL", "KDH", "DXG", "E1VFVN30", "GOLD_SJC", "DEPOSIT_12M", "VN_BOND_5Y"}
# Mã phụ pipeline tạo khi có dữ liệu bổ sung (QC 4: rổ cổ phiếu BĐS point-in-time; QC 1-2: vàng point-in-time)
OPTIONAL_SYMBOLS = {"RE_BASKET", "GOLD_SJC_RT"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_result_files(processed_dir: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for name in REQUIRED_COLUMNS:
        path = processed_dir / name
        if not path.is_file():
            raise ValueError(f"Missing required result file: {name}")
        result[name] = path.read_bytes()
    for name in OPTIONAL_COLUMNS:
        path = processed_dir / name
        if path.is_file():
            result[name] = path.read_bytes()
    return result


def validate_result_files(files: dict[str, bytes]) -> dict[str, Any]:
    reasons: list[str] = []
    frames: dict[str, pd.DataFrame] = {}
    for name, required in REQUIRED_COLUMNS.items():
        raw = files.get(name)
        if raw is None:
            reasons.append(f"Missing required file: {name}")
            continue
        try:
            from io import BytesIO
            frame = pd.read_csv(BytesIO(raw))
        except Exception as exc:
            reasons.append(f"Cannot read {name}: {exc}")
            continue
        missing = [column for column in required if column not in frame.columns]
        if missing:
            reasons.append(f"{name} missing headers: {', '.join(missing)}")
        frames[name] = frame

    for name, required in OPTIONAL_COLUMNS.items():
        raw = files.get(name)
        if raw is None:
            continue
        try:
            from io import BytesIO
            frame = pd.read_csv(BytesIO(raw))
        except Exception as exc:
            reasons.append(f"Cannot read {name}: {exc}")
            continue
        missing = [column for column in required if column not in frame.columns]
        if missing:
            reasons.append(f"{name} missing headers: {', '.join(missing)}")
        elif frame.empty or pd.to_numeric(frame["price"], errors="coerce").le(0).any():
            reasons.append(f"{name} must list at least one symbol with a positive price")
        frames[name] = frame

    perf = frames.get("performance_summary.csv")
    alloc = frames.get("allocation_current.csv")
    panel = frames.get("asset_panel_standardized.csv")
    if perf is not None:
        if len(perf) != 63:
            reasons.append(f"performance_summary.csv must contain 63 rows, got {len(perf)}")
        for column in ("start", "end", "n_months"):
            if column in perf and perf[column].nunique(dropna=False) != 1:
                reasons.append(f"performance_summary.csv column {column} is not constant")
    if alloc is not None:
        if len(alloc) != 63:
            reasons.append(f"allocation_current.csv must contain 63 rows, got {len(alloc)}")
        if "as_of" in alloc and alloc["as_of"].nunique(dropna=False) != 1:
            reasons.append("allocation_current.csv must have a single as_of")
        if set(WEIGHT_COLUMNS).issubset(alloc.columns):
            weights = alloc[WEIGHT_COLUMNS].apply(pd.to_numeric, errors="coerce")
            sums = weights.sum(axis=1)
            if (weights.isna().any(axis=1) | (weights.lt(0).any(axis=1)) | (weights.gt(1).any(axis=1)) | ((sums - 1).abs().gt(1e-6))).any():
                reasons.append("allocation rows must contain six fractions in [0,1] summing to 1 ± 1e-6")
            if {"risk_profile"}.issubset(alloc.columns):
                risky = weights[["w_co_phieu", "w_bat_dong_san", "w_etf"]].sum(axis=1)
                for idx, row in alloc.iterrows():
                    band = RISK_BANDS.get(str(row["risk_profile"]))
                    if band and not (band[0] - 1e-6 <= risky.iloc[idx] <= band[1] + 1e-6):
                        reasons.append(f"allocation risky share outside band at row {idx}")
                        break
    if panel is not None and {"date", "symbol"}.issubset(panel.columns):
        symbols = set(panel["symbol"].dropna().astype(str))
        if not (REQUIRED_SYMBOLS <= symbols <= REQUIRED_SYMBOLS | OPTIONAL_SYMBOLS):
            reasons.append(f"asset panel symbols differ: missing={sorted(REQUIRED_SYMBOLS-symbols)}, extra={sorted(symbols-REQUIRED_SYMBOLS)}")
        months = pd.to_datetime(panel["date"], errors="coerce").dropna().drop_duplicates().sort_values().tolist()
        if months:
            for first, second in zip(months, months[1:]):
                if second != first + pd.DateOffset(months=1):
                    reasons.append("asset panel monthly index is not continuous")
                    break
    if len(reasons) == 0:
        return {"valid": True, "reasons": [], "rows": {name: len(frame) for name, frame in frames.items()}}
    return {"valid": False, "reasons": reasons, "rows": {name: len(frame) for name, frame in frames.items()}}


def create_manifest(files: dict[str, bytes], label: str, params: dict[str, Any], data_through: dict[str, str], source_commit: str | None = None) -> dict[str, Any]:
    from io import BytesIO
    row_counts = {name: len(pd.read_csv(BytesIO(raw))) for name, raw in files.items()}
    panel_checksum = hashlib.sha256(files["asset_panel_standardized.csv"]).hexdigest()
    provisional_month = None
    panel = pd.read_csv(BytesIO(files["asset_panel_standardized.csv"]), parse_dates=["date"])
    if panel.date.notna().any():
        max_month = panel.date.max()
        # Gold/deposit are MONTHLY series stamped on the 1st (the value stands for the
        # whole month), so only the daily sources tell whether the last month is complete.
        daily = [value for key, value in (data_through or {}).items() if key in ("stocks", "bonds")]
        cutoff = min(pd.Timestamp(value) for value in daily) if daily else max_month + pd.offsets.MonthEnd(0)
        # Complete once daily data reaches the month's last business day (31/08/2026 is a Monday).
        if cutoff.year == max_month.year and cutoff.month == max_month.month and cutoff < max_month + pd.offsets.BMonthEnd(0):
            provisional_month = max_month.strftime("%Y-%m")
    return {
        "label": label,
        "params": params,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit,
        "sha256": {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
        "row_counts": row_counts,
        "validation": validate_result_files(files),
        "data_through": data_through,
        "provisional_month": provisional_month,
        "panel_checksum": panel_checksum,
    }
