"""QC 1-2: chế độ vàng POINT-IN-TIME (gold_vintage). Đổi giá một neo SJC nằm SAU thời điểm quyết
định d: chuỗi dùng để ước lượng và tỷ trọng tại d phải giữ nguyên (chuỗi dựng lại cuối cùng thì đổi -
chứng tỏ test có tác dụng)."""
from importlib import import_module

import numpy as np
import pandas as pd
import pytest

common = import_module("common")
m03 = import_module("03_merge_panel")
m04 = import_module("04_standardize_panel")
engine_mod = import_module("backtest_engine")


@pytest.fixture
def vintage(monkeypatch):
    monkeypatch.setattr(common, "GOLD_VINTAGE", 1)
    monkeypatch.setattr(common, "GOLD_EST_SYMBOL", "GOLD_SJC_RT")
    return monkeypatch


def build(monkeypatch, bump=None):
    pts = m03.load_gold_points()
    if bump is not None:
        pts = pts.copy()
        pts.loc[pts["date"] == bump, "price"] *= 1.10
        monkeypatch.setattr(m03, "load_gold_points", lambda path=None: pts)
    panel, hist = m03.build_panel(write_aux=False)
    return m04.standardize(hist, panel)


def test_future_gold_anchor_does_not_change_decision(vintage):
    base = build(vintage)
    eng0 = engine_mod.Engine(panel_df=base, forecast_df=pd.DataFrame(columns=["model", "date", "symbol", "forecast", "bench", "realized"]))
    d = eng0.oos_decisions[0]
    future = m03.load_gold_points()
    is_anchor = future["data_quality"].str.endswith("month_anchor")           # neo 4 hoặc 6 tháng
    anchor = future.loc[(future["date"] > d) & is_anchor, "date"].min()       # neo gần nhất SAU d
    assert pd.notna(anchor), "cần một neo sau tháng quyết định đầu tiên"
    alt = build(vintage, bump=anchor)
    eng1 = engine_mod.Engine(panel_df=alt, forecast_df=pd.DataFrame(columns=["model", "date", "symbol", "forecast", "bench", "realized"]))
    # chuỗi dựng lại CUỐI CÙNG có đổi trước d (nội suy dùng neo tương lai) ...
    assert not np.isclose(eng0.R.loc[d, "vang"], eng1.R.loc[d, "vang"])
    # ... nhưng chuỗi point-in-time và tỷ trọng tại d thì không
    pd.testing.assert_series_equal(eng0.R_est.loc[:d, "vang"], eng1.R_est.loc[:d, "vang"])
    for m in ("EqualWeight", "Markowitz", "RiskParity", "HRP", "RL"):
        for prof in common.RISK_BANDS:
            assert np.allclose(eng0.weights(m, d, prof, 3), eng1.weights(m, d, prof, 3), atol=1e-12), m
