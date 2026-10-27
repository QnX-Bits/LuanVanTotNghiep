"""
18_attribution_decomposition.py (đợt 4) - PHÂN RÃ ĐÓNG GÓP cho Chương 4 (QC 8).

Với mỗi phương pháp chính x khẩu vị (khung Trung hạn), tách Sharpe thành:
  - hiệu ứng dải          = Sharpe(thực tế) - Sharpe(cùng phương pháp, KHÔNG có dải)
  - hiệu ứng chia trong nhóm = Sharpe(thực tế) - Sharpe(cùng tỷ trọng 3 nhóm rủi ro /
                              phòng thủ / tiền mặt nhưng chia ĐỀU trong mỗi nhóm)
  - hiệu ứng chia nhóm     = Sharpe(chia đều trong nhóm) - Sharpe(Equal Weight cùng khẩu vị)
và đóng góp lợi nhuận theo lớp: Σ_t w_i,t r_i,t+1 / Σ_t r_p,t+1 (trước phí) - cho thấy
bao nhiêu lợi nhuận đến từ vàng. Thêm thống kê dải bị chạm (sàn/trần) ở mọi kịch bản và
tương quan return giữa các phương pháp.
"""
import numpy as np
import pandas as pd
from importlib import import_module

common = import_module("common")
engine_mod = import_module("backtest_engine")

METHODS = ["EqualWeight", "Markowitz", "RiskParity", "HRP", "BlackLitterman"]
HORIZON = "trung_han"


def contributions(df):
    rows = []
    for (m, p, h), g in df.groupby(["method", "risk_profile", "horizon"]):
        tot = g["gross_return"].sum()
        row = {"method": m, "risk_profile": p, "horizon": h, "total_gross_return_sum": tot}
        for c in common.ASSET_CLASSES:
            if f"r_{c}" in g:
                row[f"share_{c}"] = float((g[f"w_{c}"] * g[f"r_{c}"]).sum() / tot) if tot != 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def band_binding(df):
    rows = []
    for (m, p, h), g in df[df["rebalanced"]].groupby(["method", "risk_profile", "horizon"]):
        lo, hi = common.RISK_BANDS[p]
        s = g["risky_share"]
        rows.append({"method": m, "risk_profile": p, "horizon": h, "n_rebalances": len(g),
                     "share_at_floor": float((s <= lo + 1e-6).mean()), "share_at_ceiling": float((s >= hi - 1e-6).mean())})
    return pd.DataFrame(rows)


def main():
    rf = common.load_rf()
    full = pd.read_csv("data/processed/full_backtest_9scenarios.csv", parse_dates=["date"])
    eng = engine_mod.Engine()
    nb = eng.run(METHODS, horizons=[HORIZON], with_current=False, band=False)
    sl = eng.run([f"SleeveEW:{m}" for m in METHODS], horizons=[HORIZON], with_current=False)
    sh = lambda g: common.sharpe(g.set_index("date")["return"], rf)
    rows = []
    for p in common.RISK_BANDS:
        act = full[(full.horizon == HORIZON) & (full.risk_profile == p)]
        ew = sh(act[act.method == "EqualWeight"])
        for m in METHODS:
            a = sh(act[act.method == m])
            n = sh(nb[(nb.method == m) & (nb.risk_profile == p)])
            s = sh(sl[(sl.method == f"SleeveEW:{m}") & (sl.risk_profile == p)])
            rows.append({"method": m, "risk_profile": p, "sharpe_actual": a, "sharpe_no_band": n,
                         "sharpe_sleeve_equal": s, "sharpe_equal_weight": ew,
                         "band_effect": a - n, "within_group_effect": a - s, "group_split_effect": s - ew,
                         "avg_risky_share_actual": act[act.method == m]["risky_share"].mean(),
                         "avg_risky_share_no_band": nb[(nb.method == m) & (nb.risk_profile == p)]["risky_share"].mean()})
    dec = pd.DataFrame(rows)
    contrib = contributions(full)
    dec = dec.merge(contrib[contrib.horizon == HORIZON][["method", "risk_profile", "share_vang"]],
                    on=["method", "risk_profile"], how="left").rename(columns={"share_vang": "gold_return_share"})
    common.write_csv(dec, "data/processed/attribution_decomposition.csv", index=False)
    common.write_csv(contrib, "data/processed/return_contribution_by_class.csv", index=False)
    bb = band_binding(full)
    common.write_csv(bb, "data/processed/band_binding_stats.csv", index=False)

    cb = full[(full.risk_profile == "can_bang") & (full.horizon == HORIZON)].pivot_table(index="date", columns="method", values="return")
    corr = cb.corr()
    common.write_csv(corr, "data/processed/method_return_correlation.csv")
    off = corr.values[~np.eye(len(corr), dtype=bool)]
    print(dec.round(3).to_string(index=False))
    print(f"\nTương quan trung vị giữa return các phương pháp (Cân bằng/Trung hạn): {np.median(off):.2f}")
    print(bb[bb.horizon == HORIZON].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
