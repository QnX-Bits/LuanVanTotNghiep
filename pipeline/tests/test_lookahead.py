"""QC 21: test look-ahead TỰ ĐỘNG - xáo trộn toàn bộ dữ liệu SAU thời điểm quyết định d,
tỷ trọng tại d của mọi phương pháp và feature/dự báo tại d phải KHÔNG đổi."""
from importlib import import_module

import numpy as np
import pandas as pd
import pytest

common = import_module("common")
engine_mod = import_module("backtest_engine")
m04 = import_module("04_standardize_panel")
m06 = import_module("06_train_models")

METHODS = ["EqualWeight", "Markowitz", "RiskParity", "HRP", "BlackLitterman", "MLP_MVO", "RL"]
FUTURE_COLS = ["monthly_return", "price", "tr_index", "mom_1m", "mom_3m", "mom_6m", "vol_6m", "term_spread",
               "d_rate_3m", "gold_basis", "mom_1m_z", "mom_3m_z", "mom_6m_z", "vol_6m_z", "gold_basis_z",
               "term_spread_z", "d_rate_3m_z", "prev_mean", "ewma_vol"]


def shuffle_after(panel, fc, d, seed=0):
    rng = np.random.RandomState(seed)
    p = panel.copy()
    months = np.array(sorted(p.loc[p["date"] > d, "date"].unique()))
    perm = dict(zip(months, rng.permutation(months)))
    cols = [c for c in FUTURE_COLS if c in p.columns]
    src = p.set_index(["date", "symbol"])[cols]
    fut = p["date"] > d
    for i in p.index[fut]:
        p.loc[i, cols] = src.loc[(perm[p.at[i, "date"]], p.at[i, "symbol"])].values * rng.uniform(0.5, 1.5)
    f = fc.copy()
    f.loc[f["date"] > d, ["forecast", "bench"]] = rng.randn((f["date"] > d).sum(), 2) * 0.05
    f.loc[f["date"] >= d, "realized"] = rng.randn((f["date"] >= d).sum()) * 0.05
    return p, f


@pytest.fixture(scope="module")
def data():
    panel = pd.read_csv(common.PANEL_PATH, parse_dates=["date"])
    fc = pd.read_csv(common.FORECAST_PATH, parse_dates=["date"])
    return panel, fc


@pytest.mark.parametrize("which", [0, 12, 30])
def test_weights_do_not_use_future(data, which):
    panel, fc = data
    base = engine_mod.Engine(panel_df=panel, forecast_df=fc)
    d = base.oos_decisions[which]
    p2, f2 = shuffle_after(panel, fc, d, seed=which)
    alt = engine_mod.Engine(panel_df=p2, forecast_df=f2)
    for m in METHODS:
        for prof in common.RISK_BANDS:
            w1 = base.weights(m, d, prof, 3)
            w2 = alt.weights(m, d, prof, 3)
            assert np.allclose(w1, w2, atol=1e-9), f"{m}/{prof} tại {d:%Y-%m} đổi khi xáo dữ liệu tương lai"


def test_standardized_features_are_point_in_time():
    hist = pd.read_csv("data/processed/asset_panel_history.csv", parse_dates=["date"])
    panel = pd.read_csv("data/processed/asset_panel.csv", parse_dates=["date"])
    full = m04.standardize(hist, panel)
    d = pd.Timestamp("2023-06-01")
    cut = m04.standardize(hist[hist["date"] <= d], panel[panel["date"] <= d])
    cols = [c for c in full.columns if c.endswith("_z")] + ["prev_mean", "ewma_vol"]
    a = full[full["date"] == d].set_index("symbol")[cols].sort_index()
    b = cut[cut["date"] == d].set_index("symbol")[cols].sort_index()
    pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-12)


def test_ml_forecast_at_d_uses_only_past_rows(data):
    panel, _ = data
    d = pd.Timestamp("2024-03-01")
    df_full = m06.prepare(common.PANEL_PATH)
    tr = m06.train_rows(df_full, d)
    assert tr["date"].max() <= d - pd.DateOffset(months=1)
    trunc = panel[panel["date"] <= d]
    a = m06.generate(m06.ENet(), df_full, [d])
    path = "data/processed/_tmp_trunc_panel.csv"
    trunc.to_csv(path, index=False)
    try:
        b = m06.generate(m06.ENet(), m06.prepare(path), [d])
    finally:
        import os
        os.remove(path)
    assert np.allclose(a.sort_values("symbol")["forecast"].values, b.sort_values("symbol")["forecast"].values, atol=1e-12)
