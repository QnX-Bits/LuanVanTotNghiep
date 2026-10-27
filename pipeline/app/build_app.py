"""Đọc kết quả pipeline (data/processed/*.csv) -> sinh app/portfolio_app.html (1 file, mở offline)."""
import json, pathlib, sys
import numpy as np, pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402  (lãi suất phi rủi ro + Sharpe vượt trội dùng chung với pipeline)
AC = list(common.ASSET_CLASSES)            # bản chính 5 lớp (cổ phiếu qua ETF, cổ phiếu BĐS, vàng, trái phiếu, tiền mặt)
AC_LABEL = common.CLASS_LABELS
RP = ["than_trong", "can_bang", "tang_truong"]
HZ = ["ngan_han", "trung_han", "dai_han"]


def build_data():
    perf = pd.read_csv(PROC / "performance_summary.csv")
    alloc = pd.read_csv(PROC / "allocation_current.csv")       # đề xuất HIỆN TẠI (dữ liệu tới tháng cuối)
    sens = pd.read_csv(PROC / "sensitivity_analysis.csv")
    bt = pd.read_csv(PROC / "full_backtest_9scenarios.csv")
    holm = pd.read_csv(PROC / "holm_bonferroni_results.csv")
    r7 = pd.read_csv(PROC / "all_7methods_returns.csv", index_col=0)

    order = ["EqualWeight", "Markowitz", "RiskParity", "HRP", "BlackLitterman", "RL", "MLP_MVO"]
    methods = [m for m in order if m in set(perf["method"])]
    d = {"methods": methods, "risk_profiles": RP, "horizons": HZ,
         "risk_profile_labels": {"than_trong": "Thận trọng", "can_bang": "Cân bằng", "tang_truong": "Tăng trưởng"},
         "horizon_labels": {"ngan_han": "Ngắn hạn (dưới 1 năm)", "trung_han": "Trung hạn (1–5 năm)", "dai_han": "Dài hạn (trên 5 năm)"},
         "horizon_config": {"ngan_han": "tái cân bằng hàng tháng, tiền mặt kỳ hạn 1 tháng",
                            "trung_han": "tái cân bằng hàng quý, tiền mặt kỳ hạn 3 tháng",
                            "dai_han": "tái cân bằng hàng năm, tiền mặt kỳ hạn 12 tháng"},
         "method_labels": {"EqualWeight": "Chia đều (1/N)", "Markowitz": "Markowitz (MVO)",
                           "RiskParity": "Risk Parity", "HRP": "Hierarchical Risk Parity",
                           "BlackLitterman": "Black-Litterman + ML", "RL": "Contextual bandit (phụ lục)",
                           "MLP_MVO": "MVO + mạng nơ-ron (MLP)"},
         "performance": {}, "allocation": {}, "series": {}}
    cols = ["annualised_return", "volatility", "sharpe_ratio", "max_drawdown", "avg_turnover",
            "deposit_annualised_return"]
    for m in methods:
        for p in RP:
            for h in HZ:
                k = (perf.method == m) & (perf.risk_profile == p) & (perf.horizon == h)
                d["performance"].setdefault(m, {}).setdefault(p, {})[h] = {c: float(perf.loc[k, c].iloc[0]) for c in cols}
                a = alloc[(alloc.method == m) & (alloc.risk_profile == p) & (alloc.horizon == h)].iloc[0]
                d["allocation"].setdefault(m, {}).setdefault(p, {})[h] = [
                    {"asset_class": c, "label": AC_LABEL[c], "weight": float(a[f"w_{c}"])} for c in AC]
                g = bt[(bt.method == m) & (bt.risk_profile == p) & (bt.horizon == h)].sort_values("date")
                cum = np.cumprod(1 + g["return"].values)
                d["series"].setdefault(m, {}).setdefault(p, {})[h] = [
                    {"date": str(dt)[:7], "cumulative_growth": float(v)} for dt, v in zip(g["date"], cum)]
    r7.index = pd.to_datetime(r7.index)
    rf = common.load_rf(str(PROC / "asset_panel_standardized.csv"))
    mc = [{"method": c, "sharpe_ratio": common.sharpe(r7[c], rf),
           "mean_monthly_return": float(r7[c].mean())} for c in r7.columns]
    d["methods_comparison"] = sorted(mc, key=lambda x: -x["sharpe_ratio"])
    d["period"] = {"start": str(perf["start"].min()), "end": str(perf["end"].max()),
                   "n_months": int(perf["n_months"].max()),
                   "methods_comparison_start": r7.index.min().strftime("%Y-%m"),
                   "methods_comparison_end": r7.index.max().strftime("%Y-%m"),
                   "methods_comparison_n": int(len(r7))}
    d["risk_bands"] = {k: list(v) for k, v in common.RISK_BANDS.items()}
    d["as_of"] = str(alloc["as_of"].iloc[0])
    oos = pd.DatetimeIndex(sorted(pd.to_datetime(bt["date"]).unique()))
    rf_oos = rf.reindex(oos)
    d["deposit_series"] = [{"date": dt.strftime("%Y-%m"), "cumulative_growth": float(v)}
                           for dt, v in zip(oos, np.cumprod(1 + rf_oos.values))]
    d["sensitivity"] = json.loads(sens.to_json(orient="records"))
    prim = holm[holm["hypothesis"].isin(["H1", "H2", "H3"])]
    d["holm_bonferroni"] = {"n_total": int(len(prim)), "n_significant": int(prim["reject_h0"].sum()),
                            "mde_min": float(prim["mde_sharpe_diff"].min()), "mde_max": float(prim["mde_sharpe_diff"].max()),
                            "results": json.loads(holm.to_json(orient="records"))}
    return d


def main():
    tpl = (ROOT / "app" / "template.html").read_text(encoding="utf8")
    out = ROOT / "app" / "portfolio_app.html"
    out.write_text(tpl.replace("/*__DATA__*/null", json.dumps(build_data(), ensure_ascii=False)), encoding="utf8")
    print(f"[app] Đã tạo {out}")
    return out


if __name__ == "__main__":
    main()
