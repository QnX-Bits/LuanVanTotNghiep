"""
14_h3_diversification_test.py (đợt 4) - H3 (mục 4.2) + phân rã theo từng lớp (QC 17).

H3: Sharpe danh mục đa tài sản (bản chính 5 lớp) vs danh mục chỉ cổ phiếu-trái phiếu,
cùng engine (cùng giai đoạn, ước lượng, tần suất tái cân bằng, phí, dải khẩu vị).

QC 17: trong giai đoạn vàng tăng mạnh, H3 dễ thành "có vàng vs không có vàng". Bảng
h3_add_one_class.csv thêm TỪNG lớp vào cổ phiếu-trái phiếu (+vàng / +cổ phiếu BĐS /
+tiền mặt) để thấy lớp nào tạo ra chênh lệch.
"""
import numpy as np
import pandas as pd
from importlib import import_module

common = import_module("common")
engine_mod = import_module("backtest_engine")

METHODS = ["EqualWeight", "Markowitz", "RiskParity", "HRP", "BlackLitterman"]
PROFILE, HORIZON = "can_bang", "trung_han"
UNIVERSES = ["h3_2", "h3_plus_vang", "h3_plus_bds", "h3_plus_tien_gui", "main"]
LABELS = {"h3_2": "Cổ phiếu + trái phiếu", "h3_plus_vang": "+ vàng", "h3_plus_bds": "+ cổ phiếu BĐS",
          "h3_plus_tien_gui": "+ tiền mặt", "main": "Bản chính 5 lớp"}


def main():
    rf = common.load_rf()
    out, pairs = [], {}
    for u in UNIVERSES:
        eng = engine_mod.Engine(universe=u)
        df = eng.run(METHODS, profiles=[PROFILE], horizons=[HORIZON], with_current=False)
        if u == "h3_2":
            common.write_csv(df, "data/processed/h3_2asset_backtest.csv", index=False)
        for m, g in df.groupby("method"):
            r = g.set_index("date")["return"]
            out.append({"universe": u, "label": LABELS[u], "method": m, "sharpe_ratio": common.sharpe(r, rf),
                        "annualised_return": common.annualised_return(r.values),
                        "volatility": r.std(ddof=1) * np.sqrt(12), "max_drawdown": common.max_drawdown(r.values)})
            if u in ("h3_2", "main"):
                pairs[f"{m}_{'2asset' if u == 'h3_2' else '5asset'}"] = r
    tbl = pd.DataFrame(out)
    base = tbl[tbl.universe == "h3_2"].set_index("method")["sharpe_ratio"]
    tbl["delta_sharpe_vs_2asset"] = tbl["sharpe_ratio"] - tbl["method"].map(base)
    common.write_csv(tbl, "data/processed/h3_add_one_class.csv", index=False)
    merged = pd.DataFrame(pairs)
    merged.index.name = "date"
    common.write_csv(merged.reset_index(), "data/processed/h3_comparison_pairs.csv", index=False)
    print(tbl.pivot(index="method", columns="label", values="sharpe_ratio")[[LABELS[u] for u in UNIVERSES]].round(3))


if __name__ == "__main__":
    main()
