"""
06_train_models.py (đợt 4) - dự báo return tháng kế tiếp NGOÀI MẪU, point-in-time.

Tại MỖI tháng quyết định d (từ khi có >= 12 tháng train), mỗi mô hình được train
trên cửa sổ MỞ RỘNG (mọi dòng có nhãn đã biết: t <= d-1) rồi dự báo cho d+1. Chuỗi
dự báo này dùng CHUNG cho (i) đánh giá kỹ năng dưới đây và (ii) backtest BL /
MLP_MVO (backtest_engine đọc data/processed/forecasts_oos.csv) - không còn hai
quy trình train khác nhau như bản cũ (nested CV ở 06, cấu hình khác ở backtest).

Sửa theo QC 14:
- Target CHUẨN HÓA: z = (r_{t+1} - m_t) / σ_t, m_t = trung bình lịch sử (expanding)
  của chính mã, σ_t = độ lệch chuẩn EWMA tới t. NVL/DXG (vol 50-60%) không còn chi
  phối hàm loss; trung bình theo lớp nằm ngoài mô hình (m_t) nên KHÔNG bị phạt.
  Dự báo f = m_t + σ_t ẑ; mô hình không có tín hiệu (ẑ = 0) trùng benchmark.
- Feature chỉ còn tín hiệu (bỏ dummy lớp), tiền gửi bị loại khỏi ML. Dự báo chỉ giữ
  phần lệch do tín hiệu: ẑ = g(x_d) - trung bình g(x) trên mẫu train, nên một mô
  hình co về hằng số (như ENet bản cũ, 0/10 hệ số khác 0) cho đúng benchmark.
- ElasticNet: ElasticNetCV với cả đường alpha (100 giá trị) x l1_ratio {0,1;0,5;0,9;1}.
- LightGBM: tune lại mỗi 12 tháng bằng CV theo thời gian (05, purge 1 tháng) trên
  lưới nông (max_depth 1-3, num_leaves 2-7, lr 0,01/0,05 + early stopping theo thời
  gian, min_child_samples 20-80, subsample 0,7, colsample 0,7, reg_lambda 1/10),
  chọn theo quy tắc 1-SE; backtest dùng ĐÚNG cấu hình đã chọn.
- Thước đo: R²_OS theo từng lớp (Campbell & Thompson 2008), kiểm định Clark-West
  (2007), rank IC giữa các lớp, độ chính xác chiều so với trung bình lịch sử.
  Không dùng RMSE gộp các mã.
- Dấu kỳ vọng ĐỊNH TRƯỚC của feature (EXPECTED_SIGN) - so với hệ số ElasticNet
  ước lượng ở enet_coefficients.csv.
"""
import os
import warnings

import numpy as np
import pandas as pd
from importlib import import_module
from scipy import stats

common = import_module("common")
cvmod = import_module("05_purged_walkforward_cv")

PANEL_PATH = common.PANEL_PATH
OUT_DIR = "data/processed"
FEATURES = ["mom_1m_z", "mom_3m_z", "mom_6m_z", "vol_6m_z", "term_spread_z", "d_rate_3m_z", "gold_basis_z"]
EXPECTED_SIGN = {   # định trước, có cơ sở kinh tế
    "mom_1m_z": +1, "mom_3m_z": +1, "mom_6m_z": +1,   # time-series momentum (Moskowitz, Ooi & Pedersen 2012)
    "vol_6m_z": -1,                                     # vol cao -> lợi nhuận/rủi ro thấp (Moreira & Muir 2017)
    "term_spread_z": +1,                                # chênh lệch kỳ hạn cao -> phần bù rủi ro cao (Fama & French 1989)
    "d_rate_3m_z": -1,                                  # lãi suất tăng -> bất lợi cho tài sản rủi ro & trái phiếu
    "gold_basis_z": -1,                                 # chênh lệch SJC cao -> có xu hướng thu hẹp
}
PREDICT_SYMBOLS = common.ML_SYMBOLS + ["VNINDEX"]       # VNINDEX chỉ dự báo (bản 6 lớp), không train
MIN_TRAIN_MONTHS = 12
RETUNE_EVERY = 12
SEED = 42

LGBM_GRID = [dict(max_depth=d, num_leaves=l, learning_rate=lr, min_child_samples=mc, reg_lambda=rl)
             for d in (1, 2, 3) for l in (2, 3, 5, 7) if l <= 2 ** d
             for lr in (0.01, 0.05) for mc in (20, 40, 80) for rl in (1.0, 10.0)]
LGBM_FIXED = dict(subsample=0.7, subsample_freq=1, colsample_bytree=0.7, n_estimators=600,
                  random_state=SEED, n_jobs=1, deterministic=True, force_row_wise=True, verbose=-1)


# ============================================
# DỮ LIỆU
# ============================================
def prepare(panel_path=PANEL_PATH) -> pd.DataFrame:
    p = pd.read_csv(panel_path, parse_dates=["date"])
    p = p[p["symbol"].isin(PREDICT_SYMBOLS)].sort_values(["symbol", "date"]).copy()
    p["realized"] = p.groupby("symbol")["monthly_return"].shift(-1)
    p["z_target"] = (p["realized"] - p["prev_mean"]) / p["ewma_vol"]
    p[FEATURES] = p[FEATURES].fillna(0.0)                 # z chưa đủ lịch sử -> trung lập
    return p.dropna(subset=["prev_mean", "ewma_vol"]).reset_index(drop=True)


def train_rows(df, d):
    m = (df["date"] <= d - pd.DateOffset(months=1)) & df["z_target"].notna() & df["symbol"].isin(common.ML_SYMBOLS)
    return df[m]


def forecast_dates(df):
    months = sorted(df["date"].unique())
    first_train = df.loc[df["z_target"].notna(), "date"].min()
    return [pd.Timestamp(d) for d in months if pd.Timestamp(d) >= first_train + pd.DateOffset(months=MIN_TRAIN_MONTHS)]


# ============================================
# MÔ HÌNH (fit trên z_target, predict ẑ)
# ============================================
class HistMean:
    name = "hist_mean"

    def fit(self, tr, d):
        return self

    def predict(self, X):
        return np.zeros(len(X))


class ENet:
    name = "enet"

    def __init__(self):
        self.log = []

    def fit(self, tr, d):
        from sklearn.linear_model import ElasticNetCV
        splits = cvmod.time_splits(tr["date"])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.m = ElasticNetCV(l1_ratio=[0.1, 0.5, 0.9, 1.0], alphas=100, max_iter=50000, tol=1e-6,
                                  cv=splits if len(splits) >= 2 else 3).fit(tr[FEATURES], tr["z_target"])
        n_conv = sum(1 for w in caught if "Convergence" in type(w.message).__name__)
        self.log.append({"date": d, "alpha": self.m.alpha_, "l1_ratio": self.m.l1_ratio_, "n_convergence_warnings": n_conv,
                         "n_nonzero": int((np.abs(self.m.coef_) > 1e-12).sum()),
                         **{f: c for f, c in zip(FEATURES, self.m.coef_)}})
        return self

    def predict(self, X):
        return self.m.predict(X[FEATURES])


class LGBM:
    name = "lgbm"

    def __init__(self):
        self.params, self.tuned_at, self.log = None, None, []

    def tune(self, tr, d):
        import lightgbm as lgb
        splits = cvmod.time_splits(tr["date"], n_splits=3, val_months=6)
        if len(splits) < 2:
            splits = cvmod.time_splits(tr["date"], n_splits=3, val_months=3)
        if len(splits) < 2:                                   # quá ít dữ liệu: cấu hình nông nhất của lưới
            self.params = dict(max_depth=1, num_leaves=2, learning_rate=0.05, min_child_samples=40,
                               reg_lambda=10.0, n_estimators=100)
            self.tuned_at = d
            self.log.append({"tune_date": d, **self.params, "note": "mặc định - chưa đủ dữ liệu cho CV"})
            return
        X, y = tr[FEATURES], tr["z_target"].values
        res = []
        for cfg in LGBM_GRID:
            losses, iters = [], []
            for a, b in splits:
                m = lgb.LGBMRegressor(**LGBM_FIXED, **cfg)
                m.fit(X.iloc[a], y[a], eval_X=X.iloc[b], eval_y=y[b], callbacks=[lgb.early_stopping(50, verbose=False)])
                it = m.best_iteration_ or LGBM_FIXED["n_estimators"]
                losses.append(float(np.mean((y[b] - m.predict(X.iloc[b], num_iteration=it)) ** 2)))
                iters.append(it)
            res.append({**cfg, "cv_mse": np.mean(losses), "cv_se": np.std(losses, ddof=1) / np.sqrt(len(losses)),
                        "n_estimators_sel": int(np.median(iters))})
        res = pd.DataFrame(res)
        best = res.loc[res["cv_mse"].idxmin()]
        ok = res[res["cv_mse"] <= best["cv_mse"] + best["cv_se"]]            # quy tắc 1-SE
        ok = ok.assign(neg_mc=-ok["min_child_samples"], neg_rl=-ok["reg_lambda"]).sort_values(
            ["max_depth", "num_leaves", "neg_mc", "neg_rl", "n_estimators_sel", "learning_rate"])
        sel = ok.iloc[0]
        self.params = {k: (int(sel[k]) if k in ("max_depth", "num_leaves", "min_child_samples") else float(sel[k]))
                       for k in ("max_depth", "num_leaves", "learning_rate", "min_child_samples", "reg_lambda")}
        self.params["n_estimators"] = int(sel["n_estimators_sel"])
        self.tuned_at = d
        self.log.append({"tune_date": d, **self.params, "cv_mse_selected": sel["cv_mse"], "cv_mse_min": best["cv_mse"],
                         "cv_se_min": best["cv_se"], "n_candidates_1se": len(ok), "n_grid": len(res),
                         "cv_min_params": str({k: best[k] for k in ("max_depth", "num_leaves", "learning_rate",
                                                                    "min_child_samples", "reg_lambda")}),
                         # cấu hình cực trị (chính quy hóa mạnh nhất) của lưới: nếu CHÍNH điểm CV nhỏ nhất
                         # nằm ở đây thì lưới có thể còn hẹp; 1-SE chọn ở đây là chủ đích (mô hình đơn giản nhất)
                         "cv_min_at_strongest_corner": bool(best["max_depth"] == 1 and best["min_child_samples"] == 80
                                                            and best["reg_lambda"] == 10.0),
                         "selected_at_strongest_corner": bool(self.params["max_depth"] == 1 and
                                                              self.params["min_child_samples"] == 80 and
                                                              self.params["reg_lambda"] == 10.0)})

    def fit(self, tr, d):
        import lightgbm as lgb
        if self.tuned_at is None or d >= self.tuned_at + pd.DateOffset(months=RETUNE_EVERY):
            self.tune(tr, d)
        self.m = lgb.LGBMRegressor(**{**LGBM_FIXED, **self.params}).fit(tr[FEATURES], tr["z_target"])
        return self

    def predict(self, X):
        return self.m.predict(X[FEATURES])


class TabPFN:
    name = "tabpfn"

    def fit(self, tr, d):
        from tabpfn import TabPFNRegressor
        self.m = TabPFNRegressor(random_state=SEED).fit(tr[FEATURES].values, tr["z_target"].values)
        return self

    def predict(self, X):
        return self.m.predict(X[FEATURES].values)


def generate(model, df, dates=None):
    rows = []
    for d in (dates or forecast_dates(df)):
        tr = train_rows(df, d)
        te = df[df["date"] == d]
        model.fit(tr, d)
        # chỉ giữ phần lệch DO TÍN HIỆU: trừ mức dự báo trung bình trong mẫu train (hằng số
        # chung cho mọi tài sản như ENet ở bản cũ -> ẑ = 0 -> dự báo trùng trung bình lịch sử)
        z = model.predict(te) - float(np.mean(model.predict(tr)))
        rows.append(pd.DataFrame({"model": model.name, "date": d, "symbol": te["symbol"].values,
                                  "forecast": te["prev_mean"].values + te["ewma_vol"].values * z,
                                  "bench": te["prev_mean"].values, "sigma": te["ewma_vol"].values,
                                  "z_hat": z, "realized": te["realized"].values}))
    return pd.concat(rows, ignore_index=True)


# ============================================
# ĐÁNH GIÁ KỸ NĂNG
# ============================================
def newey_west_se(x, lag=2):
    x = np.asarray(x, float) - np.mean(x)
    n = len(x)
    v = x @ x / n
    for k in range(1, lag + 1):
        v += 2 * (1 - k / (lag + 1)) * (x[k:] @ x[:-k]) / n
    return np.sqrt(max(v, 0) / n)


def clark_west(r, f, m):
    """Clark & West (2007): H0 benchmark lồng (m) không kém mô hình (f). p một phía."""
    adj = (r - m) ** 2 - ((r - f) ** 2 - (f - m) ** 2)
    se = newey_west_se(adj)
    t = adj.mean() / se if se > 0 else np.nan
    return t, (1 - stats.norm.cdf(t)) if not np.isnan(t) else np.nan


def class_level(fc: pd.DataFrame, universe="main") -> pd.DataFrame:
    """Gộp dự báo mã -> lớp theo universe (BĐS = bình quân đều 4 mã)."""
    sym2cls = {s: c for c, syms in common.estimation_universe(universe).items() for s in syms}
    x = fc[fc["symbol"].isin(sym2cls)].assign(asset_class=lambda t: t["symbol"].map(sym2cls))
    return x.groupby(["model", "date", "asset_class"])[["forecast", "bench", "realized"]].mean().reset_index()


def evaluate(fc: pd.DataFrame, test_start=None):
    cl = class_level(fc).dropna(subset=["realized"])
    cl = cl[cl["asset_class"] != common.CASH]
    if test_start is not None:
        cl = cl[cl["date"] >= test_start]
    by_class = []
    for (mdl, c), g in cl.groupby(["model", "asset_class"]):
        r, f, m = g["realized"].values, g["forecast"].values, g["bench"].values
        r2 = 1 - ((r - f) ** 2).sum() / ((r - m) ** 2).sum()
        t, p = clark_west(r, f, m) if mdl != "hist_mean" else (np.nan, np.nan)
        by_class.append({"model": mdl, "asset_class": c, "n_months": len(g), "r2_os": r2, "cw_stat": t, "cw_pvalue": p,
                         "dir_acc_vs_mean": float((np.sign(f - m) == np.sign(r - m)).mean()) if mdl != "hist_mean" else np.nan,
                         "rmse": float(np.sqrt(np.mean((r - f) ** 2)))})
    by_class = pd.DataFrame(by_class)
    summ = []
    for mdl, g in cl.groupby("model"):
        r, f, m = g["realized"].values, g["forecast"].values, g["bench"].values
        ic = g.groupby("date").apply(lambda x: stats.spearmanr(x["forecast"], x["realized"])[0]
                                     if x["forecast"].nunique() > 1 else np.nan, include_groups=False).dropna()
        t, p = clark_west(r, f, m) if mdl != "hist_mean" else (np.nan, np.nan)
        summ.append({"model": mdl, "n_obs": len(g), "n_months": g["date"].nunique(),
                     "r2_os_pooled": 1 - ((r - f) ** 2).sum() / ((r - m) ** 2).sum(),
                     "cw_stat": t, "cw_pvalue": p,
                     "rank_ic_mean": ic.mean(), "rank_ic_t": ic.mean() / (ic.std(ddof=1) / np.sqrt(len(ic))) if len(ic) > 2 else np.nan,
                     "dir_acc_vs_mean": float((np.sign(f - m) == np.sign(r - m)).mean()) if mdl != "hist_mean" else np.nan,
                     "n_classes_r2_pos": int((by_class[(by_class.model == mdl)]["r2_os"] > 0).sum())})
    return by_class, pd.DataFrame(summ)


def momentum_rank_ic(panel_path=PANEL_PATH):
    """Đối chiếu QC: rank IC của momentum 3 tháng giữa các lớp."""
    p = pd.read_csv(panel_path, parse_dates=["date"])
    sym2cls = {s: c for c, syms in common.estimation_universe("main").items() for s in syms if c != common.CASH}
    p = p[p["symbol"].isin(sym2cls)].assign(asset_class=lambda t: t["symbol"].map(sym2cls))
    p["realized"] = p.groupby("symbol")["monthly_return"].shift(-1)
    g = p.groupby(["date", "asset_class"])[["mom_3m", "realized"]].mean().dropna().reset_index()
    ic = g.groupby("date").apply(lambda x: stats.spearmanr(x["mom_3m"], x["realized"])[0], include_groups=False).dropna()
    return float(ic.mean()), float(ic.mean() / (ic.std(ddof=1) / np.sqrt(len(ic))))


def write_skill_tables(fc: pd.DataFrame, test_start):
    """Bảng kỹ năng (toàn bộ OOS + giai đoạn kiểm tra) + file tương thích app."""
    out = []
    for label, ts in (("toan_bo_oos", None), ("giai_doan_kiem_tra", test_start)):
        bc, sm = evaluate(fc, ts)
        out.append((label, bc.assign(period=label), sm.assign(period=label)))
    by_class = pd.concat([o[1] for o in out], ignore_index=True)
    summary = pd.concat([o[2] for o in out], ignore_index=True)
    ic_m, ic_t = momentum_rank_ic()
    summary = pd.concat([summary, pd.DataFrame([{"model": "mom_3m_rank (đối chiếu)", "period": "toan_bo_oos",
                                                  "rank_ic_mean": ic_m, "rank_ic_t": ic_t}])], ignore_index=True)
    common.write_csv(by_class, f"{OUT_DIR}/forecast_skill_by_class.csv", index=False)
    common.write_csv(summary, f"{OUT_DIR}/forecast_skill_summary.csv", index=False)
    # file tương thích app (cột cũ giữ lại; 'n_folds' = số tháng ngoài mẫu)
    s = summary[summary["period"] == "toan_bo_oos"].dropna(subset=["n_obs"])
    bc = by_class[by_class["period"] == "toan_bo_oos"]
    compat = pd.DataFrame({
        "model": s["model"].values,
        "avg_rmse": [bc[bc.model == m]["rmse"].mean() for m in s["model"]],
        "std_rmse": [bc[bc.model == m]["rmse"].std() for m in s["model"]],
        "avg_directional_acc": s["dir_acc_vs_mean"].values,
        "avg_directional_acc_ex_deposit": s["dir_acc_vs_mean"].values,
        "n_folds": s["n_months"].values.astype(int),
        "r2_os_pooled": s["r2_os_pooled"].values, "cw_pvalue": s["cw_pvalue"].values,
        "rank_ic_mean": s["rank_ic_mean"].values, "n_classes_r2_pos": s["n_classes_r2_pos"].values,
    }).sort_values("r2_os_pooled", ascending=False)
    common.write_csv(compat, f"{OUT_DIR}/model_comparison_summary_with_mlp.csv", index=False)
    return by_class, summary


def test_start_decision():
    """Tháng quyết định đầu tiên của backtest (xem backtest_engine) - để báo kỹ năng cùng giai đoạn."""
    eng = import_module("backtest_engine")
    return eng.first_decision_month(PANEL_PATH)


def main():
    df = prepare()
    dates = forecast_dates(df)
    print(f"Dự báo ngoài mẫu: {dates[0]:%Y-%m} -> {dates[-1]:%Y-%m} ({len(dates)} tháng), "
          f"{df['symbol'].nunique()} mã, {len(FEATURES)} feature")
    parts = []
    for model in (HistMean(), ENet(), LGBM()):
        print(f"  {model.name} ...", flush=True)
        parts.append(generate(model, df, dates))
        if model.name == "enet":
            log = pd.DataFrame(model.log)
            common.write_csv(log, f"{OUT_DIR}/enet_coefficients.csv", index=False)
        if model.name == "lgbm":
            common.write_csv(pd.DataFrame(model.log), f"{OUT_DIR}/lgbm_tuning_log.csv", index=False)
    try:
        parts.append(generate(TabPFN(), df, dates))
        print("  tabpfn: xong")
    except Exception as e:                       # thư viện/trọng số không có -> bỏ qua
        print(f"  [BỎ QUA TabPFN] {type(e).__name__}: {str(e)[:100]}")
    fc = pd.concat(parts, ignore_index=True)
    old = common.FORECAST_PATH
    if os.path.exists(old):                      # giữ dự báo MLP (bước 07) nếu đã có
        prev = pd.read_csv(old, parse_dates=["date"])
        fc = pd.concat([fc, prev[prev["model"] == "mlp"]], ignore_index=True)
    common.write_csv(fc, common.FORECAST_PATH, index=False)
    by_class, summary = write_skill_tables(fc, test_start_decision())

    log = pd.read_csv(f"{OUT_DIR}/enet_coefficients.csv")
    signs = {f: float(((np.sign(log[f]) == EXPECTED_SIGN[f]) | (log[f] == 0)).mean()) for f in FEATURES}
    print(f"\nElasticNet: {int((log['n_nonzero'] == 0).sum())}/{len(log)} tháng có 0 hệ số khác 0; "
          f"cảnh báo hội tụ: {int(log['n_convergence_warnings'].sum())}")
    print("Tỷ lệ tháng hệ số ENet đúng dấu kỳ vọng (hoặc = 0):", {k: round(v, 2) for k, v in signs.items()})
    print("\nKỸ NĂNG NGOÀI MẪU theo lớp (toàn bộ OOS):")
    print(by_class[by_class.period == "toan_bo_oos"].pivot(index="asset_class", columns="model", values="r2_os").round(4))
    print("\nTỔNG HỢP:")
    print(summary.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
