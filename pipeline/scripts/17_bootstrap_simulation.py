"""
17_bootstrap_simulation.py (đợt 4) - QC 17: thứ hạng có ổn định không?

Mô phỏng N lịch sử (mặc định 1.000) bằng STATIONARY BOOTSTRAP (Politis & Romano 1994,
độ dài khối trung bình 6 tháng) trên return THÁNG của cả 5 lớp cùng lúc (giữ tương quan
chéo và tự tương quan ngắn hạn), kèm các biến kinh tế của đúng tháng được lấy mẫu. Trên
mỗi lịch sử, chạy 5 phương pháp chính qua CÙNG engine (kịch bản Cân bằng/Trung hạn, cùng
độ dài giai đoạn khởi động/kiểm tra như dữ liệu thật) rồi ghi Sharpe ngoài mẫu.

Báo cáo: phân phối Sharpe ngoài mẫu từng phương pháp, xác suất mỗi phương pháp đứng đầu,
và P(A > B) cho các cặp thuộc H1/H2.

Giản lược (cần nêu): BL dùng ElasticNet với siêu tham số CỐ ĐỊNH (trung vị α, l1_ratio đã
chọn trên dữ liệu thật) và feature momentum/vol tính từ chuỗi THÁNG mô phỏng; MLP_MVO và
RL không chạy trong mô phỏng.
PVN_N_BOOT_HIST, PVN_N_JOBS điều chỉnh số lịch sử / số tiến trình.
"""
import os
import warnings

import numpy as np
import pandas as pd
from importlib import import_module

common = import_module("common")
engine_mod = import_module("backtest_engine")
m04 = import_module("04_standardize_panel")
m06 = import_module("06_train_models")

N_HIST = int(os.getenv("PVN_N_BOOT_HIST", "1000"))
N_JOBS = int(os.getenv("PVN_N_JOBS", "2"))
MEAN_BLOCK = 6
SEED = 20261024
METHODS = ["EqualWeight", "Markowitz", "RiskParity", "HRP", "BlackLitterman"]
PROFILE, HORIZON = "can_bang", "trung_han"
SIM_SYMBOL = {"etf": "SIM_ETF", "bat_dong_san": "SIM_BDS", "vang": "GOLD_SJC", "trai_phieu": "VN_BOND_5Y",
              "tien_gui": "DEPOSIT_12M"}
common.UNIVERSES["sim"] = {c: [s] for c, s in SIM_SYMBOL.items()}
PAIRS = [("Markowitz", "EqualWeight"), ("RiskParity", "EqualWeight"), ("HRP", "EqualWeight"),
         ("BlackLitterman", "Markowitz"), ("BlackLitterman", "EqualWeight")]


def stationary_indices(T, mean_block, rng):
    idx = np.empty(T, int)
    idx[0] = rng.randint(T)
    for t in range(1, T):
        idx[t] = rng.randint(T) if rng.rand() < 1 / mean_block else (idx[t - 1] + 1) % T
    return idx


def load_real():
    eng = engine_mod.Engine()
    p = pd.read_csv(common.PANEL_PATH, parse_dates=["date"])
    macro = p[p["symbol"] == "E1VFVN30"].set_index("date")[["term_spread_z", "d_rate_3m_z"]].reindex(eng.months)
    basis = p[p["symbol"] == "GOLD_SJC"].set_index("date")["gold_basis_z"].reindex(eng.months)
    n_pre = eng.months.get_loc(eng.first_decision)
    log = pd.read_csv("data/processed/enet_coefficients.csv")
    return eng.R.copy(), macro.fillna(0.0), basis.fillna(0.0), n_pre, float(log["alpha"].median()), float(log["l1_ratio"].median())


def synth_panel(R, macro, basis, idx, n_pre):
    months = R.index
    Rs = R.values[idx]
    rows = []
    for j, c in enumerate(R.columns):
        r = pd.Series(Rs[:, j], index=months)
        g = pd.DataFrame({"date": months, "symbol": SIM_SYMBOL[c], "asset_class": c, "monthly_return": r.values})
        if c == common.CASH:
            g["price"] = np.append(Rs[1:, j], Rs[-1, j]) * 1200        # lãi suất "cuối tháng" -> rf tháng sau
            g["data_quality"] = "real"
        else:
            g["price"] = (1 + r).cumprod().values
            g["data_quality"] = np.where(np.arange(len(months)) < n_pre, "reconstructed_sim", "real_monthly") \
                if c == "vang" else "real"
            g["mom_1m"] = r.values
            g["mom_3m"] = ((1 + r).rolling(3).apply(np.prod, raw=True) - 1).values
            g["mom_6m"] = ((1 + r).rolling(6).apply(np.prod, raw=True) - 1).values
            g["vol_6m"] = (r.rolling(6, min_periods=3).std() * np.sqrt(12)).values
            for f in m04.SYMBOL_FEATURES:
                g[f + "_z"] = m04.expanding_zscore(g[f]).values
            g["prev_mean"] = r.expanding(min_periods=6).mean().values
            g["ewma_vol"] = r.ewm(halflife=m04.VOL_HALFLIFE, min_periods=6).std().values
            g["term_spread_z"] = macro["term_spread_z"].values[idx]
            g["d_rate_3m_z"] = macro["d_rate_3m_z"].values[idx]
            g["gold_basis_z"] = basis.values[idx] if c == "vang" else 0.0
        rows.append(g)
    return pd.concat(rows, ignore_index=True)


def synth_forecasts(panel, alpha, l1):
    from sklearn.linear_model import ElasticNet
    df = panel[panel["symbol"] != "DEPOSIT_12M"].sort_values(["symbol", "date"]).copy()
    df["realized"] = df.groupby("symbol")["monthly_return"].shift(-1)
    df["z_target"] = (df["realized"] - df["prev_mean"]) / df["ewma_vol"]
    df[m06.FEATURES] = df[m06.FEATURES].fillna(0.0)
    df = df.dropna(subset=["prev_mean", "ewma_vol"])
    months = sorted(df["date"].unique())
    first = df.loc[df["z_target"].notna(), "date"].min() + pd.DateOffset(months=m06.MIN_TRAIN_MONTHS)
    out = []
    for d in [pd.Timestamp(m) for m in months if pd.Timestamp(m) >= first]:
        tr = df[(df["date"] <= d - pd.DateOffset(months=1)) & df["z_target"].notna()]
        te = df[df["date"] == d]
        with warnings.catch_warnings():
            from sklearn.exceptions import ConvergenceWarning
            warnings.simplefilter("ignore", ConvergenceWarning)   # chỉ bỏ cảnh báo hội tụ của chuỗi mô phỏng
            mdl = ElasticNet(alpha=alpha, l1_ratio=l1, max_iter=20000).fit(tr[m06.FEATURES], tr["z_target"])
        z = mdl.predict(te[m06.FEATURES]) - mdl.predict(tr[m06.FEATURES]).mean()
        out.append(pd.DataFrame({"model": "enet", "date": d, "symbol": te["symbol"].values,
                                 "forecast": te["prev_mean"].values + te["ewma_vol"].values * z,
                                 "bench": te["prev_mean"].values, "realized": te["realized"].values}))
    return pd.concat(out, ignore_index=True)


def one_history(args):
    h, R, macro, basis, n_pre, alpha, l1 = args
    rng = np.random.RandomState(SEED + h)
    idx = stationary_indices(len(R), MEAN_BLOCK, rng)
    panel = synth_panel(R, macro, basis, idx, n_pre)
    fc = synth_forecasts(panel, alpha, l1)
    eng = engine_mod.Engine(universe="sim", panel_df=panel, forecast_df=fc)
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        df = eng.run(METHODS, profiles=[PROFILE], horizons=[HORIZON], with_current=False)
    rf = eng.rf
    return [{"history": h, "method": m, "sharpe_ratio": common.sharpe(g.set_index("date")["return"], rf),
             "annualised_return": common.annualised_return(g["return"].values)} for m, g in df.groupby("method")]


def main():
    R, macro, basis, n_pre, alpha, l1 = load_real()
    print(f"Stationary bootstrap: {N_HIST} lịch sử x {len(R)} tháng (khởi động {n_pre}, kiểm tra {len(R) - n_pre - 1}), "
          f"khối TB {MEAN_BLOCK} tháng; ENet α={alpha:.4g}, l1={l1:.2f}; {N_JOBS} tiến trình", flush=True)
    tasks = [(h, R, macro, basis, n_pre, alpha, l1) for h in range(N_HIST)]
    if N_JOBS > 1:
        import multiprocessing as mp
        ctx = mp.get_context("fork" if "fork" in mp.get_all_start_methods() else "spawn")   # Windows: spawn
        with ctx.Pool(N_JOBS) as pool:
            res = pool.map(one_history, tasks, chunksize=10)
    else:
        res = [one_history(t) for t in tasks]
    sims = pd.DataFrame([r for rr in res for r in rr])
    common.write_csv(sims, "data/processed/bootstrap_simulation_sharpe.csv", index=False)
    wide = sims.pivot(index="history", columns="method", values="sharpe_ratio")
    best = wide.idxmax(axis=1).value_counts(normalize=True)
    summ = pd.DataFrame({"mean": wide.mean(), "median": wide.median(), "p05": wide.quantile(0.05),
                         "p95": wide.quantile(0.95), "prob_best": best.reindex(wide.columns).fillna(0.0)})
    summ.index.name = "method"
    common.write_csv(summ.reset_index(), "data/processed/bootstrap_simulation_summary.csv", index=False)
    pr = pd.DataFrame([{"pair": f"{a} > {b}", "prob": float((wide[a] > wide[b]).mean()),
                        "median_diff": float((wide[a] - wide[b]).median())} for a, b in PAIRS])
    common.write_csv(pr, "data/processed/bootstrap_pairwise_prob.csv", index=False)
    print(summ.round(3).to_string())
    print(pr.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
