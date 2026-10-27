"""
12_holm_bonferroni_comparison.py (đợt 4) - kiểm định Sharpe (mục 6.7) + độ mạnh.

Sửa theo QC 15-16:
- Kiểm định CHÍNH: Ledoit & Wolf (2008) - studentized circular block bootstrap, sai số
  chuẩn HAC (delta method) - không giả định iid chuẩn. JK-Memmel giữ để đối chiếu với
  đề cương.
- Holm-Bonferroni chỉ trên các cặp THUỘC giả thuyết, tách theo HỌ: H1 (EW vs MVO/RP/HRP),
  H2 (Markowitz vs BL với từng nguồn view + so chéo các nguồn view, đúng mục 6.7 đề
  cương), H3 (5 lớp vs cổ phiếu-trái phiếu, 5 phương pháp). H4/RL ở phụ lục và MLP_MVO
  (mở rộng) có họ riêng, không pha loãng H1-H3. Cột holm_primary: Holm trên toàn bộ
  họ chính H1+H2+H3 (bảo thủ hơn) để tham khảo.
- Độ mạnh: báo chênh lệch Sharpe TỐI THIỂU phát hiện được (α = 0,10 hai phía, power
  80%) = (z_0,95 + z_0,80) x SE, khoảng tin cậy 90% và số tháng cần để phát hiện
  chênh lệch 0,3. Không có ý nghĩa -> kết luận "không đủ độ mạnh để phân biệt", KHÔNG
  phải "không khác biệt".
- Deflated Sharpe Ratio (Bailey & López de Prado 2014) cho từng phương pháp ở kịch bản
  chính, với số cấu hình đã thử N = 63 (QC) và N = 252 (4 vòng x 63).
"""
import numpy as np
import pandas as pd
from importlib import import_module
from scipy import stats

common = import_module("common")

SCENARIO_PROFILE, SCENARIO_HORIZON = "can_bang", "trung_han"
METHODS_ORDER = ["EqualWeight", "Markowitz", "RiskParity", "HRP", "BlackLitterman", "RL", "MLP_MVO"]
ALPHA = 0.10
POWER = 0.80
BLOCK = 4
N_BOOT = 4999
SEED = 42
N_TRIALS = (63, 252)
EULER = 0.5772156649


# ---------- Ledoit & Wolf (2008) ----------
def _sr_diff_and_grad(Y):
    mu_a, mu_b, g_a, g_b = Y.mean(axis=0)
    va, vb = g_a - mu_a ** 2, g_b - mu_b ** 2
    d = mu_a / np.sqrt(va) - mu_b / np.sqrt(vb)
    grad = np.array([g_a / va ** 1.5, -g_b / vb ** 1.5, -mu_a / (2 * va ** 1.5), mu_b / (2 * vb ** 1.5)])
    return d, grad


def _hac(Y, lag):
    X = Y - Y.mean(axis=0)
    T = len(X)
    S = X.T @ X / T
    for k in range(1, lag + 1):
        G = X[k:].T @ X[:-k] / T
        S += (1 - k / (lag + 1)) * (G + G.T)
    return S


def lw2008(ra, rb, block=BLOCK, n_boot=N_BOOT, seed=SEED):
    """Trả về (ΔSR tháng, SE, p-value hai phía, phân vị (d*-d)/se* 5% và 95%, trung bình d*)."""
    ra, rb = np.asarray(ra, float), np.asarray(rb, float)
    Y = np.column_stack([ra, rb, ra ** 2, rb ** 2])
    T = len(Y)
    d, grad = _sr_diff_and_grad(Y)
    lag = int(np.floor(4 * (T / 100) ** (2 / 9)))
    se = float(np.sqrt(grad @ _hac(Y, lag) @ grad / T))
    rng = np.random.RandomState(seed)
    l = int(np.ceil(T / block))
    tstats, dstars = np.empty(n_boot), np.empty(n_boot)
    for m in range(n_boot):
        starts = rng.randint(0, T, l)
        idx = ((starts[:, None] + np.arange(block)[None, :]) % T)
        Ys = Y[idx.ravel()]
        ds, gs = _sr_diff_and_grad(Ys)
        Z = (Ys - Ys.mean(axis=0)).reshape(l, block, 4).sum(axis=1) / np.sqrt(block)
        Psi = Z.T @ Z / l
        se_s = np.sqrt(max(gs @ Psi @ gs, 1e-30) / (l * block))
        tstats[m] = (ds - d) / se_s
        dstars[m] = ds
    p = (np.sum(np.abs(tstats) >= abs(d) / se) + 1) / (n_boot + 1)
    q05, q95 = np.percentile(tstats, [5, 95])
    return d, se, float(p), q05, q95, float(dstars.mean())


def holm(pvals: pd.Series, alpha=ALPHA):
    order = pvals.sort_values()
    m = len(order)
    thr = pd.Series(alpha / (m - np.arange(m)), index=order.index)
    rej = pd.Series(False, index=order.index)
    for i, k in enumerate(order.index):
        if order[k] <= thr[k]:
            rej[k] = True
        else:
            break
    return thr.reindex(pvals.index), rej.reindex(pvals.index)


# ---------- Deflated Sharpe ----------
def deflated_sharpe(r_ex, sr_trials_monthly, n_trials):
    r = np.asarray(r_ex, float)
    T = len(r)
    sr = r.mean() / r.std(ddof=1)
    g3 = stats.skew(r)
    g4 = stats.kurtosis(r, fisher=False)
    v = np.var(sr_trials_monthly, ddof=1)
    sr0 = np.sqrt(v) * ((1 - EULER) * stats.norm.ppf(1 - 1 / n_trials) + EULER * stats.norm.ppf(1 - 1 / (n_trials * np.e)))
    z = (sr - sr0) * np.sqrt(T - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)
    return float(stats.norm.cdf(z)), float(sr0 * np.sqrt(12))


def scenario_returns(path="data/processed/full_backtest_9scenarios.csv"):
    df = pd.read_csv(path, parse_dates=["date"])
    s = df[(df["risk_profile"] == SCENARIO_PROFILE) & (df["horizon"] == SCENARIO_HORIZON)]
    piv = s.pivot_table(index="date", columns="method", values="return")
    return piv[[m for m in METHODS_ORDER if m in piv.columns]], df


def build_pairs(ret, rf):
    ex = ret.apply(lambda c: common.excess(c, rf))
    pairs = []
    for m in ("Markowitz", "RiskParity", "HRP"):
        pairs.append(("H1", f"{m} vs EqualWeight", ex[m], ex["EqualWeight"]))
    try:
        blv = pd.read_csv("data/processed/bl_elasticnet_vs_lightgbm.csv", index_col=0, parse_dates=True)
    except FileNotFoundError:
        blv = pd.DataFrame({"BlackLitterman_ElasticNet": ret["BlackLitterman"]})
    blv = blv.apply(lambda c: common.excess(c, rf))
    short = lambda c: "BL-" + c.replace("BlackLitterman_", "")
    for c in blv.columns:
        pairs.append(("H2", f"{short(c)} vs Markowitz", blv[c], ex["Markowitz"].reindex(blv.index)))
    cols = list(blv.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            pairs.append(("H2", f"{short(cols[i])} vs {short(cols[j])}", blv[cols[i]], blv[cols[j]]))
    try:
        h3 = pd.read_csv("data/processed/h3_comparison_pairs.csv", parse_dates=["date"]).set_index("date")
        for m in ("EqualWeight", "Markowitz", "RiskParity", "HRP", "BlackLitterman"):
            a, b = f"{m}_5asset", f"{m}_2asset"
            if a in h3 and b in h3:
                sub = h3[[a, b]].dropna()
                pairs.append(("H3", f"{m}: 5 lớp vs cổ phiếu-trái phiếu", common.excess(sub[a], rf), common.excess(sub[b], rf)))
    except FileNotFoundError:
        print("CHƯA có h3_comparison_pairs.csv - chạy 14 trước.")
    if "RL" in ex:
        for m in ("EqualWeight", "Markowitz", "RiskParity", "HRP", "BlackLitterman"):
            pairs.append(("H4 (phụ lục)", f"RL vs {m}", ex["RL"], ex[m]))
    if "MLP_MVO" in ex:
        pairs.append(("Mở rộng", "MLP_MVO vs Markowitz", ex["MLP_MVO"], ex["Markowitz"]))
    return pairs


def main():
    rf = common.load_rf()
    ret, full = scenario_returns()
    ret = ret.dropna()
    T = len(ret)
    print(f"Kịch bản chính {SCENARIO_PROFILE}/{SCENARIO_HORIZON}: {T} tháng "
          f"({ret.index.min():%Y-%m} -> {ret.index.max():%Y-%m})")
    z_mde = stats.norm.ppf(1 - ALPHA / 2) + stats.norm.ppf(POWER)
    rows = []
    for fam, name, a, b in build_pairs(ret, rf):
        a, b = a.dropna(), b.reindex(a.index).dropna()
        a = a.reindex(b.index)
        d, se, p, q05, q95, dmean = lw2008(a.values, b.values)
        jz, jp = common.jobson_korkie_memmel(a.values, b.values)
        ann = np.sqrt(12)
        ci_lo, ci_hi = (d - q95 * se) * ann, (d - q05 * se) * ann
        mde = z_mde * se * ann
        rows.append({"hypothesis": fam, "pair": name, "n_months": len(a),
                     "sharpe_a": common.sharpe(a), "sharpe_b": common.sharpe(b),
                     "sharpe_diff": d * ann, "lw_se": se * ann, "p_value": p,
                     "jk_z_stat": jz, "jk_p_value": jp,
                     "bootstrap_mean_diff": dmean * ann, "bootstrap_ci_low": ci_lo, "bootstrap_ci_high": ci_hi,
                     "bootstrap_significant_90": bool(not (ci_lo <= 0 <= ci_hi)),
                     "mde_sharpe_diff": mde, "months_needed_for_0.3": int(np.ceil(len(a) * (mde / 0.3) ** 2))})
    res = pd.DataFrame(rows)
    res["threshold"], res["reject_h0"] = np.nan, False
    for fam, g in res.groupby("hypothesis"):
        thr, rej = holm(g["p_value"])
        res.loc[g.index, "threshold"], res.loc[g.index, "reject_h0"] = thr, rej
    prim = res["hypothesis"].isin(["H1", "H2", "H3"])
    _, rej_p = holm(res.loc[prim, "p_value"])
    res["holm_primary_reject"] = False
    res.loc[prim, "holm_primary_reject"] = rej_p
    res["meaningful_improvement"] = res["reject_h0"] & (res["sharpe_diff"].abs() >= 0.1)
    res["conclusion"] = np.where(
        res["reject_h0"], "khác biệt có ý nghĩa (sau Holm trong họ)",
        np.where(res["sharpe_diff"].abs() < res["mde_sharpe_diff"],
                 "không đủ độ mạnh để phân biệt (|ΔSharpe| < ngưỡng phát hiện)",
                 "không đủ bằng chứng sau hiệu chỉnh Holm"))
    res = res.sort_values(["hypothesis", "p_value"]).reset_index(drop=True)
    common.write_csv(res, "data/processed/holm_bonferroni_results.csv", index=False)

    # Deflated Sharpe
    sr_trials = []
    rf_full = rf
    for _, g in full.groupby(["method", "risk_profile", "horizon"]):
        x = common.excess(g.set_index("date")["return"], rf_full)
        sr_trials.append(x.mean() / x.std(ddof=1))
    dsr = []
    for m in ret.columns:
        x = common.excess(ret[m], rf)
        row = {"method": m, "sharpe_ratio": common.sharpe(ret[m], rf), "n_months": len(x),
               "skew": float(stats.skew(x)), "kurtosis": float(stats.kurtosis(x, fisher=False))}
        for n in N_TRIALS:
            p, sr0 = deflated_sharpe(x, sr_trials, n)
            row[f"dsr_N{n}"], row[f"sr0_annual_N{n}"] = p, sr0
        dsr.append(row)
    dsr = pd.DataFrame(dsr)
    common.write_csv(dsr, "data/processed/deflated_sharpe.csv", index=False)
    ret.to_csv("data/processed/all_7methods_returns.csv", float_format="%.10g")

    show = ["hypothesis", "pair", "sharpe_diff", "bootstrap_ci_low", "bootstrap_ci_high", "p_value", "jk_p_value",
            "threshold", "reject_h0", "mde_sharpe_diff", "months_needed_for_0.3"]
    print(res[show].round(3).to_string(index=False))
    print(f"\nCó ý nghĩa sau Holm (theo họ): {int(res['reject_h0'].sum())}/{len(res)}; "
          f"họ chính H1-H3 gộp: {int(res['holm_primary_reject'].sum())}/{int(prim.sum())}")
    print("\nDeflated Sharpe:")
    print(dsr.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
