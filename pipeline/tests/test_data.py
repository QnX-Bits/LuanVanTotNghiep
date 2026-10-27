"""Kiểm tra dữ liệu panel sau QC (mục 1-7)."""
from importlib import import_module

import numpy as np
import pandas as pd

common = import_module("common")


def panel():
    return pd.read_csv(common.PANEL_PATH, parse_dates=["date"])


def test_panel_continuous_and_complete():
    p = panel()
    months = pd.date_range(p["date"].min(), p["date"].max(), freq="MS")
    required = {"VNINDEX", "E1VFVN30", "VHM", "NVL", "KDH", "DXG", "GOLD_SJC", "VN_BOND_5Y", "DEPOSIT_12M"}
    assert required <= set(p["symbol"]) <= required | {"RE_BASKET", "GOLD_SJC_RT"}
    for _, g in p.groupby("symbol"):
        assert list(g.sort_values("date")["date"]) == list(months)
    assert p["date"].min() <= pd.Timestamp("2020-03-01")          # có COVID 03/2020
    assert p["date"].max() == pd.Timestamp("2026-07-01")          # 08/2026 chưa trọn -> loại


def test_gold_has_no_gaps_and_flags_reconstruction():
    g = panel().query("symbol == 'GOLD_SJC'")
    assert g["monthly_return"].notna().all()
    assert g["data_quality"].str.startswith("reconstructed").any()
    assert (g.loc[g["date"] >= "2022-08-01", "data_quality"] == "real_monthly").all()


def test_deposit_return_uses_previous_month_rate():
    d = panel().query("symbol == 'DEPOSIT_12M'").sort_values("date")
    assert np.allclose(d["monthly_return"].iloc[1:].values, d["price"].shift(1).iloc[1:].values / 1200)


def test_features_winsorized_and_no_deposit_features():
    p = panel()
    z = [c for c in p.columns if c.endswith("_z")]
    assert p[z].abs().max().max() <= 3 + 1e-12
    assert p.loc[p["symbol"] == "DEPOSIT_12M", z].isna().all().all()


def test_bond_momentum_has_price_sign():
    b = panel().query("symbol == 'VN_BOND_5Y'").sort_values("date")
    # momentum 1 tháng = return giá+carry (không phải thay đổi lợi suất, vốn ngược dấu)
    assert np.allclose(b["mom_1m"].dropna(), b["monthly_return"].dropna())
