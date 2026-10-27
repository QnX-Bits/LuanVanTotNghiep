"""QC 21: kiểm tra đúng đắn của các bộ tối ưu / ước lượng."""
from importlib import import_module

import numpy as np
import pandas as pd
import pytest

common = import_module("common")
opt = import_module("09_portfolio_optimization")
bl = import_module("10_black_litterman")
cvmod = import_module("05_purged_walkforward_cv")


def random_cov(n, seed=0):
    rng = np.random.RandomState(seed)
    A = rng.randn(n, n)
    vol = rng.uniform(0.01, 0.12, n)
    M = A @ A.T + n * np.eye(n)
    C = M / np.sqrt(np.outer(np.diag(M), np.diag(M)))
    return C * np.outer(vol, vol)


def test_bl_without_views_returns_prior_and_ew():
    S = random_cov(4)
    w_ew = np.full(4, 1 / 5)                     # 4 lớp phi tiền mặt + tiền mặt
    pi = common.DELTA * S @ w_ew
    mu = bl.black_litterman_posterior_partial(pi, S, [], [], [])
    assert np.allclose(mu, pi)
    w = opt.mvo(mu, S, common.DELTA, [True, True, False, False], band=None, has_cash=True, cap=1.0)
    assert np.allclose(w, np.full(5, 0.2), atol=1e-6)


def test_bl_single_view_confidence_is_tilt_share():
    S = np.diag([0.004, 0.009, 0.002])
    pi = 2.5 * S @ np.full(3, 0.25)
    for c in (0.2, 0.5, 0.8):
        mu = bl.black_litterman_posterior_partial(pi, S, [1], [pi[1] + 0.01], [bl.omega_from_confidence(c, S[1, 1])])
        assert np.isclose((mu[1] - pi[1]) / 0.01, c)


def test_bl_skill_gate():
    rng = np.random.RandomState(1)
    m = np.zeros(40)
    r = rng.randn(40) * 0.05
    noise = rng.randn(40) * 0.05                 # dự báo vô nghĩa -> R²_OS < 0 -> không view
    r2, lam, _ = bl.skill(r, noise, m)
    assert bl.confidence_from_skill(r2, lam) == 0.0
    good = r * 0.5                                # dự báo có tín hiệu -> có view
    r2, lam, _ = bl.skill(r, good, m)
    assert r2 > 0 and bl.confidence_from_skill(r2, lam) > 0


def test_risk_parity_equal_risk_contributions():
    S = random_cov(5, 3)
    w = opt.risk_parity(S)
    rc = w * (S @ w)
    assert np.allclose(rc, rc.mean(), rtol=1e-5)
    assert np.isclose(w.sum(), 1) and (w > 0).all()


def _hrp_reference(cov: pd.DataFrame) -> pd.Series:
    """Cài đặt tham chiếu theo mã gốc López de Prado (2016), Advances in Financial ML, ch.16."""
    import scipy.cluster.hierarchy as sch
    corr = cov / np.outer(np.sqrt(np.diag(cov)), np.sqrt(np.diag(cov)))
    dist = ((1 - corr) / 2.0) ** 0.5
    link = sch.linkage(dist.values[np.triu_indices(len(cov), 1)], "single")

    def get_quasi_diag(link):
        link = link.astype(int)
        sort_ix = pd.Series([link[-1, 0], link[-1, 1]])
        num_items = link[-1, 3]
        while sort_ix.max() >= num_items:
            sort_ix.index = range(0, sort_ix.shape[0] * 2, 2)
            df0 = sort_ix[sort_ix >= num_items]
            i, j = df0.index, df0.values - num_items
            sort_ix[i] = link[j, 0]
            df0 = pd.Series(link[j, 1], index=i + 1)
            sort_ix = pd.concat([sort_ix, df0]).sort_index()
            sort_ix.index = range(sort_ix.shape[0])
        return sort_ix.tolist()

    def cluster_var(cov, items):
        c = cov.iloc[items, items]
        ivp = 1 / np.diag(c)
        ivp /= ivp.sum()
        return float(ivp @ c.values @ ivp)

    sort_ix = get_quasi_diag(link)
    w = pd.Series(1.0, index=sort_ix)
    c_items = [sort_ix]
    while len(c_items) > 0:
        c_items = [i[j:k] for i in c_items for j, k in ((0, len(i) // 2), (len(i) // 2, len(i))) if len(i) > 1]
        for i in range(0, len(c_items), 2):
            c0, c1 = c_items[i], c_items[i + 1]
            v0, v1 = cluster_var(cov, c0), cluster_var(cov, c1)
            a = 1 - v0 / (v0 + v1)
            w[c0] *= a
            w[c1] *= 1 - a
    return w.sort_index()


@pytest.mark.parametrize("n,seed", [(4, 0), (5, 1), (6, 2), (8, 3)])
def test_hrp_matches_reference(n, seed):
    S = random_cov(n, seed)
    ref = _hrp_reference(pd.DataFrame(S)).values
    assert np.allclose(opt.hrp(S), ref, atol=1e-12)


@pytest.mark.parametrize("band", [(0.10, 0.30), (0.40, 0.60), (0.70, 0.90)])
def test_mvo_respects_band_and_caps(band):
    rng = np.random.RandomState(7)
    S = random_cov(4, 5)
    for _ in range(10):
        mu = rng.randn(4) * 0.01
        w = opt.mvo(mu, S, 2.5, [True, True, False, False], band=band, has_cash=True, cap=0.5)
        assert np.isclose(w.sum(), 1) and (w >= -1e-12).all() and (w[:4] <= 0.5 + 1e-8).all()
        assert band[0] - 1e-7 <= w[:2].sum() <= band[1] + 1e-7


def test_mvo_turnover_penalty_reduces_trading():
    S = random_cov(4, 2)
    mu = np.array([0.006, 0.004, 0.005, 0.001])
    prev = np.array([0.1, 0.4, 0.1, 0.2, 0.2])
    w0 = opt.mvo(mu, S, 2.5, [1, 1, 0, 0], band=(0.4, 0.6), cap=0.5)
    w1 = opt.mvo(mu, S, 2.5, [1, 1, 0, 0], band=(0.4, 0.6), cap=0.5, w_prev=prev, costs=np.full(5, 0.01))
    assert np.abs(w1 - prev).sum() <= np.abs(w0 - prev).sum() + 1e-9


def test_two_tier_band_keeps_within_group_ratios():
    w = np.array([0.05, 0.05, 0.3, 0.4, 0.2])
    out = opt.two_tier_band(w, [True, True, False, False, False], 0.4, 0.6)
    assert np.isclose(out[:2].sum(), 0.4) and np.isclose(out[0] / out[1], 1.0)
    assert np.allclose(out[2:] / out[2:].sum(), w[2:] / w[2:].sum())


def test_scale_to_vol_hits_target_without_leverage():
    S = random_cov(4, 9)
    w = np.full(4, 0.25)
    out = opt.scale_to_vol(w, S, 0.02)
    vol = np.sqrt(out[:4] @ S @ out[:4] * 12)
    assert np.isclose(vol, 0.02) or np.isclose(out[4], 0)
    assert np.isclose(out.sum(), 1) and out[4] >= 0


def test_covariance_is_psd_and_shrinkage_bounded():
    rng = np.random.RandomState(4)
    R = pd.DataFrame(rng.randn(50, 4) * 0.05, columns=["etf", "bat_dong_san", "vang", "trai_phieu"])
    R.iloc[:20, 2] = np.nan                       # thiếu dữ liệu theo cặp
    S, info = opt.estimate_cov(R, return_info=True)
    assert np.linalg.eigvalsh(S.values).min() > 0
    assert 0 <= info["lw_shrinkage"] <= 1


def test_max_drawdown_counts_initial_capital():
    assert np.isclose(common.max_drawdown([-0.10, 0.05, 0.02]), -0.10)
    assert np.isclose(common.max_drawdown([0.1, -0.2]), -0.2)


def test_time_splits_purge_one_month():
    d = pd.Series(np.repeat(pd.date_range("2020-01-01", periods=40, freq="MS"), 3))
    sp = cvmod.time_splits(d)
    assert len(sp) >= 2 and cvmod.check_no_overlap(d, sp, purge_months=1)


def test_cap_classes_moves_defensive_excess_to_cash():
    opt = import_module("09_portfolio_optimization")
    w = opt.cap_classes([0.06, 0.04, 0.05, 0.85, 0.0], [1, 1, 0, 0, 0], [0, 0, 0, 0, 1], 0.5)
    assert np.allclose(w, [0.06, 0.04, 0.05, 0.5, 0.35])
    w = opt.cap_classes([0.6, 0.3, 0.02, 0.08, 0.0], [1, 1, 0, 0, 0], [0, 0, 0, 0, 1], 0.5)
    assert np.isclose(w[:2].sum(), 0.9) and w.max() <= 0.5 + 1e-12   # tổng nhóm rủi ro giữ nguyên
