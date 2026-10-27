"""
11_full_backtest_scenarios.py (đợt 4)
Backtest 9 kịch bản (3 khẩu vị x 3 khung thời gian) cho 7 phương pháp trên bản chính
5 lớp (cổ phiếu qua ETF, cổ phiếu BĐS, vàng, trái phiếu, tiền mặt):
  - 5 phương pháp chính (mục 6.3): EqualWeight, Markowitz, RiskParity, HRP, BlackLitterman (ElasticNet)
  - mở rộng: MLP_MVO; phụ lục: RL (contextual bandit)
Khẩu vị = dải tỷ trọng nhóm rủi ro (cổ phiếu + cổ phiếu BĐS), là RÀNG BUỘC trong MVO/BL
và tầng 1 của thiết kế hai tầng ở EW/RP/HRP. Khung thời gian = tần suất tái cân bằng
(1/3/12 tháng) + kỳ hạn phần tiền mặt; ước lượng chung cho mọi khung.

OUTPUT:
- full_backtest_9scenarios.csv: 1 dòng / (method, profile, horizon, tháng)
- allocation_current.csv: tỷ trọng ĐỀ XUẤT HIỆN TẠI (dữ liệu tới tháng cuối) cho app
- bl_diagnostics.csv: số view, R²_OS, mức tin cậy, Q, π của BL ở từng lần tái cân bằng
"""
import pandas as pd
from importlib import import_module

common = import_module("common")
engine_mod = import_module("backtest_engine")

CORE_METHODS = ["EqualWeight", "Markowitz", "RiskParity", "HRP", "BlackLitterman"]
EXTENSION_METHODS = ["MLP_MVO", "RL"]


def run_full_backtest():
    eng = engine_mod.Engine()
    d0, d1 = eng.oos_decisions[0], eng.oos_decisions[-1]
    print(f"Giai đoạn kiểm tra: return {common.next_month(d0):%Y-%m} -> {common.next_month(d1):%Y-%m} "
          f"({len(eng.oos_decisions)} tháng); đề xuất hiện tại tính tại {eng.current_date:%Y-%m}")
    df = eng.run(CORE_METHODS + EXTENSION_METHODS, record_diag=True)
    common.write_csv(df, "data/processed/full_backtest_9scenarios.csv", index=False)
    common.write_csv(df.attrs["current"], "data/processed/allocation_current.csv", index=False)
    diag = pd.DataFrame(eng.diag)
    diag["horizon"] = diag["k"].map({v["rebalance"]: h for h, v in common.HORIZONS.items()})
    common.write_csv(diag.drop(columns="k"), "data/processed/bl_diagnostics.csv", index=False)
    print(f"Đã lưu: full_backtest_9scenarios.csv ({len(df)} dòng), allocation_current.csv, bl_diagnostics.csv")
    return df


if __name__ == "__main__":
    res = run_full_backtest()
    rf = common.load_rf()
    tbl = res.groupby(["method", "risk_profile", "horizon"]).apply(
        lambda g: common.sharpe(g.set_index("date")["return"], rf), include_groups=False)
    print("\nSharpe VƯỢT TRỘI (năm hóa, net-of-cost):")
    print(tbl.unstack("horizon").round(3))
