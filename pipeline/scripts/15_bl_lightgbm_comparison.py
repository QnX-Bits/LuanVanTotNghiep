"""
15_bl_lightgbm_comparison.py (đợt 4) - so sánh NGUỒN VIEW cho Black-Litterman (H2).

ElasticNet (backtest chính) vs LightGBM (cấu hình chọn bằng 1-SE ở 06, đúng cấu hình
dùng trong backtest) vs TabPFN (nếu 06 tạo được dự báo). Cùng engine, cùng kịch bản
Cân bằng/Trung hạn, cùng cơ chế Ω từ kỹ năng ngoài mẫu -> chỉ khác chuỗi dự báo.
"""
import pandas as pd
from importlib import import_module

common = import_module("common")
engine_mod = import_module("backtest_engine")
PROFILE, HORIZON = "can_bang", "trung_han"


def main():
    full = pd.read_csv("data/processed/full_backtest_9scenarios.csv", parse_dates=["date"])
    bl_enet = full[(full["method"] == "BlackLitterman") & (full["risk_profile"] == PROFILE) &
                   (full["horizon"] == HORIZON)].set_index("date")["return"]
    eng = engine_mod.Engine()
    methods = ["BlackLitterman_LGBM"] + (["BlackLitterman_TabPFN"] if "tabpfn" in eng.fc else [])
    df = eng.run(methods, profiles=[PROFILE], horizons=[HORIZON], with_current=False, record_diag=True)
    wide = df.pivot_table(index="date", columns="method", values="return")
    merged = pd.DataFrame({"BlackLitterman_ElasticNet": bl_enet})
    merged["BlackLitterman_LightGBM"] = wide["BlackLitterman_LGBM"]
    if "BlackLitterman_TabPFN" in wide:
        merged["BlackLitterman_TabPFN"] = wide["BlackLitterman_TabPFN"]
    merged = merged.dropna()
    merged.index.name = "date"
    common.write_csv(merged, "data/processed/bl_elasticnet_vs_lightgbm.csv")
    diag = pd.DataFrame(eng.diag)
    if len(diag):
        common.write_csv(diag, "data/processed/bl_diagnostics_lgbm.csv", index=False)
    rf = common.load_rf()
    for c in merged.columns:
        print(f"{c}: Sharpe vượt trội = {common.sharpe(merged[c], rf):.3f}")


if __name__ == "__main__":
    main()
