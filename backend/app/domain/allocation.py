from __future__ import annotations

import math
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

ASSET_CLASSES = ("co_phieu", "bat_dong_san", "etf", "vang", "tien_gui", "trai_phieu")
# Phương pháp của luồng tư vấn: Risk Parity (đã chốt sau góp ý GVHD). Đọc từ cấu hình để
# app và nghiên cứu không lệch nhau (QC 23); không chọn theo Sharpe backtest.
ADVISOR_METHOD = os.getenv("PVN_ADVISOR_METHOD", "RiskParity")
ADVISOR_METHOD_LABEL = {"RiskParity": "Risk Parity", "HRP": "Hierarchical Risk Parity"}.get(ADVISOR_METHOD, ADVISOR_METHOD)
# Bản nghiên cứu chính có 5 lớp: lớp cổ phiếu thực hiện qua ETF (cột w_etf), w_co_phieu = 0.
ASSET_LABELS = {
    "co_phieu": {"vi": "Cổ phiếu (VN-Index)", "en": "Stocks (VN-Index)"},
    "bat_dong_san": {"vi": "Cổ phiếu BĐS", "en": "Real-estate stocks"},
    "etf": {"vi": "Cổ phiếu (ETF E1VFVN30)", "en": "Equities (E1VFVN30 ETF)"},
    "vang": {"vi": "Vàng SJC", "en": "SJC gold"},
    "tien_gui": {"vi": "Tiền gửi 12 tháng", "en": "12-month deposit"},
    "trai_phieu": {"vi": "Trái phiếu (quỹ trái phiếu mở)", "en": "Bonds (open-ended bond fund)"},
}
# Mặc định cho bản kết quả cũ; bản có re_basket_current.csv truyền rules["re_symbols"] = thành viên rổ năm hiện hành.
SHARE_SYMBOLS = ("VHM", "NVL", "KDH", "DXG")


def allocate_vnd(weights: dict[str, float] | list[float], amount: int) -> dict[str, int]:
    if amount < 0 or int(amount) != amount:
        raise ValueError("amount must be a non-negative whole VND amount")
    if isinstance(weights, list):
        if len(weights) != len(ASSET_CLASSES):
            raise ValueError("six weights are required")
        weight_map = dict(zip(ASSET_CLASSES, weights))
    else:
        weight_map = {key: float(weights[key]) for key in ASSET_CLASSES}
    vals = [float(weight_map[key]) for key in ASSET_CLASSES]
    if any(not math.isfinite(w) or w < 0 or w > 1 for w in vals):
        raise ValueError("weights must be finite fractions in [0, 1]")
    if abs(sum(vals) - 1.0) > 1e-6:
        raise ValueError("weights must sum to one")

    exact = [Decimal(str(weight_map[key])) * Decimal(int(amount)) for key in ASSET_CLASSES]
    floors = [int(value.to_integral_value(rounding="ROUND_FLOOR")) for value in exact]
    remainder = int(amount) - sum(floors)
    order = sorted(range(len(exact)), key=lambda i: (-(exact[i] - floors[i]), i))
    for i in order[:remainder]:
        floors[i] += 1
    return dict(zip(ASSET_CLASSES, floors))


def _amount_line(asset: str, target: int, minimum: int = 100_000, step: int = 1_000) -> tuple[int, str | None]:
    if target < minimum:
        return 0, f"Target {target} VND is below the minimum {minimum} VND."
    executed = target // step * step
    return executed, None


def build_execution_once(target: dict[str, int], prices: dict[str, float], amount: int, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    rules = rules or {}
    share_lot = max(1, int(rules.get("share_lot", 100)))
    etf_lot = max(1, int(rules.get("etf_lot", 100)))
    fund_min = max(0, int(rules.get("fund_min_vnd", 100_000)))
    fund_step = max(1, int(rules.get("fund_step_vnd", 1_000)))
    etf_symbol = str(rules.get("etf_symbol", "E1VFVN30"))
    gold_unit = str(rules.get("gold_unit", "chi"))
    share_symbols = tuple(rules.get("re_symbols") or SHARE_SYMBOLS)
    basket_year = rules.get("re_basket_year")
    lines: list[dict[str, Any]] = []
    executed: dict[str, int] = {key: 0 for key in ASSET_CLASSES}
    leftovers: dict[str, int] = {}

    # VN-Index proxy and bond proxy are amount-based, rounded down to 1,000 VND.
    for asset, vehicle in (("co_phieu", "Quỹ cổ phiếu đại diện VN-Index"), ("trai_phieu", "Chứng chỉ quỹ trái phiếu mở (nghiên cứu dùng NAV quỹ DCBF)")):
        target_vnd = target[asset]
        bought, reason = _amount_line(asset, target_vnd, fund_min, fund_step)
        if asset == "co_phieu" and target_vnd == 0:
            reason = "Bản nghiên cứu 5 lớp không phân bổ riêng cho VN-Index; lớp cổ phiếu được thực hiện qua ETF."
        executed[asset] = bought
        leftovers[asset] = target_vnd - bought
        lines.append({"asset_class": asset, "vehicle": vehicle, "units": bought, "unit_label": "theo số tiền", "unit_price": None, "amount": bought, "target": target_vnd, "deviation_pp": 0.0, "note": reason})

    # Real-estate basket members (equal weight), lots of 100 shares each.
    re_target = target["bat_dong_san"]
    n_re = len(share_symbols)
    per_stock_target = re_target / n_re
    remaining = re_target
    held = {symbol: 0 for symbol in share_symbols}
    shares = {symbol: 0 for symbol in share_symbols}
    unit_prices = {symbol: int(Decimal(str(prices[symbol]))) for symbol in share_symbols}
    while True:
        candidates = []
        for rank, symbol in enumerate(share_symbols):
            lot_cost = unit_prices[symbol] * share_lot
            shortfall = per_stock_target - held[symbol]
            if lot_cost <= remaining and shortfall > 0:
                candidates.append((-shortfall, rank, symbol, lot_cost))
        if not candidates:
            break
        _, _, symbol, lot_cost = min(candidates)
        shares[symbol] += share_lot
        held[symbol] += lot_cost
        remaining -= lot_cost
    executed["bat_dong_san"] = re_target - remaining
    leftovers["bat_dong_san"] = remaining
    for symbol in share_symbols:
        line_amount = held[symbol]
        note = None
        if shares[symbol] == 0:
            note = f"Mục tiêu {int(per_stock_target):,} ₫ nhỏ hơn một lô {share_lot} cổ phiếu ({unit_prices[symbol] * share_lot:,} ₫)."
        lines.append({"asset_class": "bat_dong_san", "vehicle": (f"Cổ phiếu {symbol} (rổ BĐS nghiên cứu {basket_year})" if basket_year else f"Cổ phiếu {symbol} (mã đại diện nghiên cứu)"), "units": shares[symbol], "unit_label": "cổ phiếu", "unit_price": unit_prices[symbol], "amount": line_amount, "target": int(per_stock_target), "deviation_pp": 0.0, "note": note, "symbol": symbol})

    # ETF: indivisible lots of 100 units.
    etf_target = target["etf"]
    etf_unit = int(Decimal(str(prices[etf_symbol])))
    etf_lot_cost = etf_unit * etf_lot
    etf_lots = etf_target // etf_lot_cost if etf_lot_cost else 0
    executed["etf"] = etf_lots * etf_lot_cost
    leftovers["etf"] = etf_target - executed["etf"]
    lines.append({"asset_class": "etf", "vehicle": f"ETF {etf_symbol}", "units": etf_lots * etf_lot, "unit_label": f"chứng chỉ (lô {etf_lot})", "unit_price": etf_unit, "amount": executed["etf"], "target": etf_target, "deviation_pp": 0.0, "note": f"Mục tiêu {target['etf']:,} ₫ nhỏ hơn một lô ETF ({etf_lot_cost:,} ₫)." if etf_lots == 0 else None})

    # SJC gold is bought in whole chi; 1 chi = 0.1 luong.
    gold_target = target["vang"]
    gold_unit_price = int((Decimal(str(prices["GOLD_SJC"])) / (Decimal(10) if gold_unit == "chi" else Decimal(1))).to_integral_value(rounding=ROUND_HALF_UP))
    gold_units = gold_target // gold_unit_price if gold_unit_price else 0
    executed["vang"] = gold_units * gold_unit_price
    leftovers["vang"] = gold_target - executed["vang"]
    gold_label = "chỉ" if gold_unit == "chi" else "lượng"
    lines.append({"asset_class": "vang", "vehicle": "Vàng miếng SJC", "units": gold_units, "unit_label": gold_label, "unit_price": gold_unit_price, "amount": executed["vang"], "target": gold_target, "deviation_pp": 0.0, "note": f"Số tiền mục tiêu {gold_target:,} ₫ nhỏ hơn 1 {gold_label} vàng ({gold_unit_price:,} ₫)." if gold_units == 0 else None})

    # The 12-month deposit receives its target and every indivisible remainder.
    deposit_target = target["tien_gui"]
    deposit_amount = deposit_target + sum(leftovers.values())
    deposit_label = "Tiền gửi có kỳ hạn 12 tháng" if deposit_amount >= 1_000_000 else "Tiền mặt chờ đầu tư"
    executed["tien_gui"] = deposit_amount
    lines.append({"asset_class": "tien_gui", "vehicle": deposit_label, "units": deposit_amount, "unit_label": "theo số tiền", "unit_price": None, "amount": deposit_amount, "target": deposit_target, "deviation_pp": 0.0, "note": f"Bao gồm {sum(leftovers.values()):,} ₫ phần lẻ." if sum(leftovers.values()) else None})

    total = sum(executed.values())
    if total != amount:
        raise ArithmeticError(f"Execution plan does not balance: {total} != {amount}")
    for line in lines:
        asset = line["asset_class"]
        if asset == "bat_dong_san":
            per_stock_target = target[asset] / n_re
            line["deviation_pp"] = round((line["amount"] / amount - per_stock_target / amount) * 100, 8) if amount else 0
        elif asset == "tien_gui":
            line["deviation_pp"] = round((executed[asset] / amount - target[asset] / amount) * 100, 8) if amount else 0
        else:
            line["deviation_pp"] = round((executed[asset] / amount - target[asset] / amount) * 100, 8) if amount else 0
    deviations = {key: (executed[key] / amount - target[key] / amount) * 100 for key in ASSET_CLASSES} if amount else {key: 0.0 for key in ASSET_CLASSES}
    max_asset = max(ASSET_CLASSES, key=lambda key: abs(deviations[key]))
    return {"lines": lines, "executed_vnd": executed, "leftovers_vnd": leftovers, "deviation_pp": deviations, "max_deviation_pp": max(abs(x) for x in deviations.values()), "max_deviation_asset": max_asset, "total_vnd": total}


def build_execution(target: dict[str, int], prices: dict[str, float], amount: int, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    rules = rules or {}
    deviation_threshold = float(rules.get("re_deviation_threshold_pp", 2.0))
    plan = build_execution_once(target, prices, amount, rules)
    if plan["max_deviation_pp"] > deviation_threshold:
        minimum = None
        for candidate in range(1_000_000, 2_000_000_001, 1_000_000):
            candidate_target = allocate_target_at_amount(target, amount, candidate)
            if build_execution_once(candidate_target, prices, candidate, rules)["max_deviation_pp"] <= deviation_threshold:
                minimum = candidate
                break
        plan["deviation_warning"] = {
            "max_deviation_pp": plan["max_deviation_pp"],
            "asset_class": plan["max_deviation_asset"],
            "min_amount_vnd": minimum,
            "text_vi": (f"Với số tiền này, kế hoạch không thể thực hiện sát tỷ trọng mục tiêu (lệch tối đa {plan['max_deviation_pp']:.2f} điểm % ở {ASSET_LABELS[plan['max_deviation_asset']]['vi']}). Số tiền tối thiểu để lệch không quá {deviation_threshold:g} điểm %: {minimum:,} ₫ (tham khảo)." if minimum else f"Với số tiền này, kế hoạch không thể thực hiện sát tỷ trọng mục tiêu (lệch tối đa {plan['max_deviation_pp']:.2f} điểm % ở {ASSET_LABELS[plan['max_deviation_asset']]['vi']}). Số tiền tối thiểu để lệch không quá {deviation_threshold:g} điểm %: trên 2 tỷ ₫ (tham khảo)."),
        }
    else:
        plan["deviation_warning"] = None
    return plan


def allocate_target_at_amount(original: dict[str, int], original_amount: int, amount: int) -> dict[str, int]:
    if original_amount <= 0:
        raise ValueError("original amount must be positive")
    weights = {key: original[key] / original_amount for key in ASSET_CLASSES}
    return allocate_vnd(weights, amount)
