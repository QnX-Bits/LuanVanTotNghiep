"""
16_sensitivity_analysis.py (đợt 4) - phân tích ĐỘ NHẠY các giả định (kịch bản Cân bằng /
Trung hạn, 5 phương pháp chính). Thay cho bảng "sàn vol tiền gửi" (tham số đã bỏ).

  delta            δ của BL/MVO: 1,5 / 2,5 (gốc) / 4                         (QC 12)
  ewma_halflife    half-life EWMA hiệp phương sai: 12 / 18 (gốc) / 24 tháng   (QC 10)
  rolling_window   cửa sổ trượt trọng số đều 24 / 36 tháng thay cho EWMA      (QC 10)
  rf_shift         lãi tiền gửi +0,5 / +1,0 điểm %/năm (xấp xỉ bình quân NHTM) (QC 5)
  cash_haircut     tắt chênh lệch kỳ hạn của phần tiền mặt                    (QC 5)
  costs            phí đồng nhất 0,15% thay cho vector phí theo lớp            (QC 18)
  gold_recon       bỏ giá vàng dựng lại (vàng chỉ vào danh mục khi đủ 24 tháng thật) (QC 2)
  universe         bản 6 lớp gốc (VN-Index + ETF tách riêng)                  (QC 3)
  bond_views       cho phép view ML cho trái phiếu tổng hợp
"""
import copy
import os

import numpy as np
import pandas as pd
from importlib import import_module

common = import_module("common")
engine_mod = import_module("backtest_engine")
m03 = import_module("03_merge_panel")
m04 = import_module("04_standardize_panel")

METHODS = ["EqualWeight", "Markowitz", "RiskParity", "HRP", "BlackLitterman"]
PROFILE, HORIZON = "can_bang", "trung_han"
SENS_DIR = "data/processed/sensitivity"


def gold_norecon_panel():
    os.makedirs(SENS_DIR, exist_ok=True)
    path = f"{SENS_DIR}/asset_panel_gold_norecon.csv"
    panel, hist = m03.build_panel(gold_recon=0, write_aux=False)
    m04.standardize(hist, panel).to_csv(path, index=False, float_format="%.10g")
    return path


def variants():
    yield "baseline", "gốc", {}, {}
    for v in (1.5, 4.0):
        yield "delta", v, {"DELTA": v}, {}
    for v in (12.0, 24.0):
        yield "ewma_halflife", v, {"EWMA_HALFLIFE": v}, {}
    for v in (24, 36):
        yield "rolling_window", v, {"ROLLING_WINDOW": v}, {}
    for v in (0.005, 0.010):
        yield "rf_shift", v, {"RF_SHIFT": v}, {}
    yield "cash_haircut", "tắt", {"CASH_TERM_SPREAD": {k: 0.0 for k in common.CASH_TERM_SPREAD}}, {}
    yield "costs", "đồng nhất 0,15%", {"CLASS_COSTS": {k: 0.0015 for k in common.CLASS_COSTS}}, {}
    yield "gold_recon", "tắt", {}, {"panel_path": gold_norecon_panel()}
    yield "universe", "6 lớp (VN-Index + ETF)", {}, {"universe": "split6"}
    yield "bond_views", "bật", {"NO_VIEW_CLASSES": {"tien_gui"}}, {}


def main():
    rows = []
    defaults = {k: copy.deepcopy(getattr(common, k)) for k in
                ("DELTA", "EWMA_HALFLIFE", "ROLLING_WINDOW", "RF_SHIFT", "CASH_TERM_SPREAD", "CLASS_COSTS", "NO_VIEW_CLASSES")}
    for param, value, attrs, eng_kw in variants():
        for k, v in attrs.items():
            setattr(common, k, v)
        try:
            eng = engine_mod.Engine(**eng_kw)
            rf = common.load_rf(eng_kw.get("panel_path", common.PANEL_PATH))
            df = eng.run(METHODS, profiles=[PROFILE], horizons=[HORIZON], with_current=False)
            for m, g in df.groupby("method"):
                r = g.set_index("date")["return"]
                rows.append({"parameter": param, "value": str(value), "is_baseline": param == "baseline",
                             "method": m, "sharpe_ratio": common.sharpe(r, rf),
                             "annualised_return": common.annualised_return(r.values),
                             "volatility": r.std(ddof=1) * np.sqrt(12), "max_drawdown": common.max_drawdown(r.values),
                             "avg_w_tien_gui": g["w_tien_gui"].mean(), "avg_w_vang": g["w_vang"].mean(),
                             "n_months": len(r)})
            print(f"  xong: {param} = {value}", flush=True)
        finally:
            for k, v in defaults.items():
                setattr(common, k, copy.deepcopy(v))
    out = pd.DataFrame(rows)
    base = out[out.is_baseline].set_index("method")["sharpe_ratio"]
    out["delta_sharpe_vs_baseline"] = out["sharpe_ratio"] - out["method"].map(base)
    common.write_csv(out, "data/processed/sensitivity_analysis.csv", index=False)
    print(out.pivot_table(index=["parameter", "value"], columns="method", values="sharpe_ratio").round(3))


if __name__ == "__main__":
    main()
