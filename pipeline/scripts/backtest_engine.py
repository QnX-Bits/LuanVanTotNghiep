"""
backtest_engine.py (đợt 4) - walk-forward hàng tháng dùng chung cho mọi phương pháp.

QUY TRÌNH tại tháng quyết định d (chỉ dùng thông tin <= cuối tháng d):
  1. Lớp phi tiền mặt đủ điều kiện = có >= 24 return tháng tới d.
  2. Σ = EWMA (half-life 18) + co ngót Ledoit-Wolf trên TOÀN BỘ lịch sử tới d -
     CHUNG cho mọi khung thời gian (QC 10). Trái phiếu được khử độ trơn.
  3. Tỷ trọng theo phương pháp (tiền gửi = tiền mặt nhận phần dư, QC 9):
       EqualWeight    1/N mọi lớp (kể cả tiền mặt) -> dải khẩu vị (hai tầng)
       RiskParity/HRP ERC/HRP trên lớp phi tiền mặt -> co về vol mục tiêu -> dải (hai tầng)
       Markowitz      μ Bayes-Stein (Jorion) + cvxpy, dải là ràng buộc, phạt turnover
       BlackLitterman π = δΣw_EW + view ML có kỹ năng ngoài mẫu (10), cùng bộ MVO
       MLP_MVO        μ = dự báo MLP (mở rộng), cùng bộ MVO
       RL             contextual bandit chọn vị trí trong dải (phụ lục, 08)
  4. Tái cân bằng theo khung thời gian (1/3/12 tháng); giữa 2 lần tỷ trọng trôi theo
     giá; phí = Σ c_lớp |Δw| (QC 18). Phần tiền mặt hưởng lãi kỳ hạn khớp tần suất
     tái cân bằng (QC 5).
  5. Return ghi nhận = return tháng d+1 (cột "date" = d+1).

GIAI ĐOẠN KIỂM TRA: tháng quyết định đầu tiên = muộn hơn của (a) tháng thứ 24 của
panel và (b) tháng đầu tiên mà giá vàng SJC là giá thật hàng tháng (08/2022) - nhờ
vậy KHÔNG tháng quyết định nào dùng giá vàng nội suy giữa 2 neo tương lai, và mọi
return trong giai đoạn kiểm tra là giá thật. Kết quả: return 09/2022 -> 07/2026.
"""
import os

import numpy as np
import pandas as pd
from importlib import import_module

common = import_module("common")
opt = import_module("09_portfolio_optimization")
bl = import_module("10_black_litterman")
rl = import_module("08_rl_extension")

HORIZONS = common.HORIZONS
STATIC = ("EqualWeight", "RiskParity", "HRP")
MVO_FAMILY = ("Markowitz", "BlackLitterman", "MLP_MVO")


def first_decision_month(panel_path=common.PANEL_PATH, panel_df=None):
    p = panel_df if panel_df is not None else pd.read_csv(panel_path, parse_dates=["date"])
    months = sorted(p["date"].unique())
    a = pd.Timestamp(months[common.MIN_HISTORY - 1])
    if common.GOLD_VINTAGE and (p["symbol"] == "GOLD_SJC_RT").any():
        return a          # vàng point-in-time: không cần chờ tới tháng có giá SJC thật
    gold = p[p["symbol"] == "GOLD_SJC"].set_index("date")["data_quality"]
    not_final = gold.index[gold != "real_monthly"]
    b = (not_final.max() + pd.DateOffset(months=1)) if len(not_final) else a
    return max(a, b)


class Engine:
    def __init__(self, universe="main", panel_path=common.PANEL_PATH, forecast_path=common.FORECAST_PATH,
                 panel_df=None, forecast_df=None):
        self.universe = universe
        self.uni = common.UNIVERSES[universe]
        self.classes = list(self.uni)
        self.has_cash = common.CASH in self.classes
        self.noncash = [c for c in self.classes if c != common.CASH]
        self.costs = {c: common.CLASS_COSTS[c] for c in self.classes}

        p = panel_df if panel_df is not None else pd.read_csv(panel_path, parse_dates=["date"])
        ret = p.pivot(index="date", columns="symbol", values="monthly_return").sort_index()
        # R: return THỰC HIỆN (P&L). R_est: return dùng để ƯỚC LƯỢNG/ML - khác R chỉ ở vàng khi
        # bật PVN_GOLD_VINTAGE (chuỗi point-in-time GOLD_SJC_RT, không dùng neo SJC tương lai).
        est = common.estimation_universe(universe) if universe in common.UNIVERSES else self.uni
        self.uni_est = {c: [x if x in ret.columns else y for x, y in zip(est[c], self.uni[c])] for c in self.uni}
        self.R = pd.DataFrame({c: ret[s].mean(axis=1, skipna=False) for c, s in self.uni.items()})
        self.R_est = pd.DataFrame({c: ret[s].mean(axis=1, skipna=False) for c, s in self.uni_est.items()})
        self.months = self.R.index
        self.fwd = common.forward_returns(self.R)
        self.fwd_est = common.forward_returns(self.R_est)
        dep = p[p["symbol"] == "DEPOSIT_12M"].set_index("date")
        self.rf = (dep["monthly_return"] + common.RF_SHIFT / 12).reindex(self.months).rename("rf")
        rate = dep["price"].reindex(self.months)
        self.rf_next = rate / 1200 + common.RF_SHIFT / 12        # rf tháng d+1 = lãi 12T cuối tháng d (biết tại d)
        # QC 5: lãi kỳ hạn THỰC 1/3 tháng cho phần tiền mặt (nếu panel có cột rate_1m/rate_3m)
        self.term_next = {k: dep[col].reindex(self.months) / 1200 + common.RF_SHIFT / 12
                          for k, col in common.TERM_RATE_COLUMN.items() if col in dep.columns}
        self.first_decision = first_decision_month(panel_path, p)
        self.oos_decisions = [d for d in self.months if d >= self.first_decision
                              and not self.fwd.loc[d, self.noncash].isna().any()]
        self.current_date = self.months[-1]

        sym2cls = {s: c for c, syms in self.uni_est.items() for s in syms}
        q = p[p["symbol"].isin(sym2cls) & (p["symbol"] != "DEPOSIT_12M")].assign(cls=lambda t: t["symbol"].map(sym2cls))
        sig = q.groupby(["date", "cls"])[["mom_3m_z", "vol_6m_z"]].mean().groupby("date").mean()
        self.signal = sig.reindex(self.months).fillna(0.0)

        self.fc = {}
        if forecast_df is not None or os.path.exists(forecast_path):
            f = forecast_df if forecast_df is not None else pd.read_csv(forecast_path, parse_dates=["date"])
            f = f[f["symbol"].isin(sym2cls)].assign(cls=lambda t: t["symbol"].map(sym2cls))
            for m, g in f.groupby("model"):
                agg = g.groupby(["date", "cls"])[["forecast", "bench", "realized"]].mean()
                self.fc[m] = {k: agg[k].unstack("cls").reindex(columns=self.noncash) for k in agg.columns}
        self._cache = {}
        self.diag = []

    # ---------- tiện ích ----------
    def cash_next(self, d, k):
        """Lợi nhuận phần tiền mặt tháng d+1 khi tái cân bằng mỗi k tháng: lãi kỳ hạn thực nếu có,
        không thì lãi 12T trừ chênh lệch kỳ hạn giả định (common.CASH_TERM_SPREAD)."""
        if k in self.term_next and not np.isnan(self.term_next[k].loc[d]):
            return float(self.term_next[k].loc[d])
        return float(self.rf_next.loc[d] - common.CASH_TERM_SPREAD[k] / 12)

    def spread(self, k, d):
        """Chênh lệch (tháng) giữa lãi 12T và lợi nhuận tiền mặt của khung thời gian."""
        if k in self.term_next and not np.isnan(self.term_next[k].loc[d]):
            return float(self.rf_next.loc[d] - self.term_next[k].loc[d])
        return common.CASH_TERM_SPREAD[k] / 12

    def r_next(self, d, k, est=False):
        r = (self.fwd_est if est else self.fwd).loc[d].copy()
        if self.has_cash:
            r[common.CASH] = self.cash_next(d, k)
        return r[self.classes].values.astype(float)

    def eligible(self, d):
        return opt.eligible_columns(self.R_est.loc[:d, self.noncash])

    def sigma(self, d):
        key = ("sigma", d)
        if key not in self._cache:
            el = self.eligible(d)
            S, info = opt.estimate_cov(self.R_est.loc[:d, el], return_info=True)
            self._cache[key] = (el, S.values, info)
        return self._cache[key]

    def risky_mask(self, names):
        return np.array([c in common.RISKY_CLASSES for c in names])

    def to_full(self, names, w):
        full = pd.Series(0.0, index=self.classes)
        full[list(names)] = w
        return full.values

    def from_full(self, names, w_full):
        return pd.Series(w_full, index=self.classes)[list(names)].values

    def band_project(self, w_full, profile):
        lo, hi = common.RISK_BANDS[profile]
        w = opt.two_tier_band(w_full, self.risky_mask(self.classes), lo, hi)
        # trần 50%/lớp như MVO/BL (đợt 5: NAV quỹ trái phiếu biến động thấp khiến RP/HRP dồn > 80% vào trái phiếu)
        noncash = [c for c in self.classes if c != common.CASH]
        cash = np.array([c == common.CASH for c in self.classes])
        return opt.cap_classes(w, self.risky_mask(self.classes), cash, self.cap(noncash))

    def cap(self, el):
        return common.MAX_WEIGHT if len(el) >= 4 else 1.0

    # ---------- dự báo & kỹ năng ----------
    def skill(self, model, d):
        key = ("skill", model, d)
        if key not in self._cache:
            F = self.fc[model]
            past = F["forecast"].index[F["forecast"].index <= d - pd.DateOffset(months=1)]
            out = {}
            for c in self.noncash:
                r2, lam, n = bl.skill(F["realized"].loc[past, c], F["forecast"].loc[past, c], F["bench"].loc[past, c])
                out[c] = {"r2_os": r2, "lambda": lam, "n_oos": n, "conf": bl.confidence_from_skill(r2, lam)}
            self._cache[key] = out
        return self._cache[key]

    def forecast_at(self, model, d):
        F = self.fc[model]["forecast"]
        return F.loc[d] if d in F.index else pd.Series(np.nan, index=self.noncash)

    # ---------- tỷ trọng ----------
    def mvo_full(self, mu_opt, d, el, S, profile, k, w_prev, band):
        names = el + ([common.CASH] if self.has_cash else [])
        wp = None if w_prev is None else self.from_full(names, w_prev)
        costs = np.array([self.costs[c] for c in names])
        lo, hi = common.RISK_BANDS[profile]
        w = opt.mvo(mu_opt, S, common.DELTA, self.risky_mask(el), band=(lo, hi) if band else None,
                    has_cash=self.has_cash, cap=self.cap(el), w_prev=wp, costs=costs, hold_months=k)
        return self.to_full(names, w)

    def w_black_litterman(self, model, d, profile, k, w_prev, band, record=False):
        el, S, _ = self.sigma(d)
        n_all = len(el) + (1 if self.has_cash else 0)
        pi = common.DELTA * S @ np.full(len(el), 1.0 / n_all)
        sk = self.skill(model, d)
        F = self.forecast_at(model, d)
        r_cash = self.cash_next(d, k) if self.has_cash else self.rf_next.loc[d]
        idx, Q, Om = [], [], []
        for i, c in enumerate(el):
            conf = sk[c]["conf"]
            if c not in common.NO_VIEW_CLASSES and conf > 0 and not np.isnan(F.get(c, np.nan)):
                idx.append(i)
                Q.append(F[c] - r_cash)
                Om.append(bl.omega_from_confidence(conf, S[i, i]))
        mu = bl.black_litterman_posterior_partial(pi, S, idx, Q, Om)
        if record:
            self.diag.append({"model": model, "decision_date": d, "k": k, "n_views": len(idx),
                              **{f"r2_os_{c}": sk[c]["r2_os"] for c in el}, **{f"conf_{c}": sk[c]["conf"] for c in el},
                              **{f"Q_{el[i]}": Q[j] for j, i in enumerate(idx)},
                              **{f"pi_{c}": pi[i] for i, c in enumerate(el)},
                              "view_weight_mean": float(np.mean([sk[el[i]]["conf"] for i in idx])) if idx else 0.0})
        return self.mvo_full(mu, d, el, S, profile, k, w_prev, band)

    def w_rl(self, d, profile, k):
        el, _, _ = self.sigma(d)
        lo, hi = common.RISK_BANDS[profile]
        actions = rl.band_actions(lo, hi)
        risky = [c for c in el if c in common.RISKY_CLASSES]
        defensive = [c for c in el if c not in common.RISKY_CLASSES] + ([common.CASH] if self.has_cash else [])

        def alloc(share):
            w = pd.Series(0.0, index=self.classes)
            w[risky] = share / len(risky)
            w[defensive] = (1 - share) / len(defensive)
            return w.values

        i = self.months.get_loc(d)
        tr = self.months[:i]                                     # t <= d-1, reward tháng t+1 <= d
        tr = [t for t in tr if not self.fwd_est.loc[t, el].isna().any()]
        if len(tr) < 12:
            return alloc(actions[1])
        rewards = np.array([[alloc(a) @ self.r_next(t, k, est=True) for a in actions] for t in tr])
        st = self.signal.loc[tr]
        med = st.median()
        states = ((st["mom_3m_z"] >= med["mom_3m_z"]).astype(int) * 2 + (st["vol_6m_z"] >= med["vol_6m_z"]).astype(int)).values
        Qv = rl.train_bandit(states, rewards, delta=common.DELTA)
        now = self.signal.loc[d]
        s = int(now["mom_3m_z"] >= med["mom_3m_z"]) * 2 + int(now["vol_6m_z"] >= med["vol_6m_z"])
        return alloc(actions[int(np.argmax(Qv[s]))])

    def weights(self, method, d, profile, k, w_prev=None, band=True, record=False):
        if method.startswith("SleeveEW:"):                       # cùng tỷ lệ 3 nhóm, chia đều TRONG nhóm
            base = self.weights(method.split(":", 1)[1], d, profile, k, w_prev, band)
            return self.sleeve_ew(base, d)
        el, S, _ = self.sigma(d)
        if method == "EqualWeight":
            names = el + ([common.CASH] if self.has_cash else [])
            w = self.to_full(names, np.full(len(names), 1.0 / len(names)))
            return self.band_project(w, profile) if band else w
        if method in ("RiskParity", "HRP"):
            wn = opt.risk_parity(S) if method == "RiskParity" else opt.hrp(S)
            if self.has_cash:
                w = self.to_full(el + [common.CASH], opt.scale_to_vol(wn, S, common.VOL_TARGETS[profile]))
            else:
                w = self.to_full(el, wn)
            return self.band_project(w, profile) if band else w
        if method == "Markowitz":
            key = ("bs", d)
            if key not in self._cache:
                R_ex = self.R_est.loc[:d, el].sub(self.rf.loc[:d], axis=0)
                self._cache[key] = opt.bayes_stein_mean(R_ex, S)
            mu, _ = self._cache[key]
            # μ vượt trội so với lãi 12T -> so với tiền mặt của khung thời gian này
            return self.mvo_full(mu + (self.spread(k, d) if self.has_cash else 0.0), d, el, S, profile, k, w_prev, band)
        if method == "BlackLitterman":
            return self.w_black_litterman("enet", d, profile, k, w_prev, band, record)
        if method.startswith("BlackLitterman_"):
            return self.w_black_litterman(method.split("_", 1)[1].lower(), d, profile, k, w_prev, band, record)
        if method == "MLP_MVO":
            F = self.forecast_at("mlp", d).reindex(el)
            B = self.fc["mlp"]["bench"].loc[d].reindex(el) if d in self.fc["mlp"]["bench"].index else F
            F[[c for c in el if c in common.NO_VIEW_CLASSES]] = np.nan     # lớp không dùng tín hiệu ML
            r_cash = self.cash_next(d, k) if self.has_cash else self.rf_next.loc[d]
            mu = F.fillna(B).values - r_cash
            return self.mvo_full(mu, d, el, S, profile, k, w_prev, band)
        if method == "RL":
            return self.w_rl(d, profile, k)
        raise KeyError(method)

    def sleeve_ew(self, w_full, d):
        el, _, _ = self.sigma(d)
        w = pd.Series(w_full, index=self.classes)
        groups = [[c for c in el if c in common.RISKY_CLASSES], [c for c in el if c not in common.RISKY_CLASSES]]
        if self.has_cash:
            groups.append([common.CASH])
        out = pd.Series(0.0, index=self.classes)
        for g in groups:
            if g:
                out[g] = w[g].sum() / len(g)
        return out.values

    # ---------- mô phỏng ----------
    def run(self, methods, profiles=None, horizons=None, with_current=True, band=True, record_diag=False):
        profiles = profiles or list(common.RISK_BANDS)
        horizons = horizons or list(HORIZONS)
        rows, current = [], []
        for h in horizons:
            k = HORIZONS[h]["rebalance"]
            reb = set(self.oos_decisions[::k])
            for method in methods:
                for prof in profiles:
                    w_hold = None
                    for d in self.oos_decisions:
                        r = self.r_next(d, k)
                        if d in reb:
                            target = self.weights(method, d, prof, k, w_hold, band,
                                                  record=record_diag and prof == "can_bang")
                            dw = np.zeros_like(target) if w_hold is None else np.abs(target - w_hold)
                            cost = float(sum(dw[i] * self.costs[c] for i, c in enumerate(self.classes)))
                            turnover = float(dw.sum())
                            w = target
                        else:
                            w, cost, turnover = w_hold, 0.0, 0.0
                        gross = float(w @ r)
                        row = {"method": method, "risk_profile": prof, "horizon": h, "decision_date": d,
                               "date": common.next_month(d), "rebalanced": d in reb, "gross_return": gross,
                               "turnover": turnover, "transaction_cost": cost, "return": gross - cost,
                               "rf": float(self.rf_next.loc[d]),
                               "risky_share": float(sum(w[i] for i, c in enumerate(self.classes) if c in common.RISKY_CLASSES))}
                        row.update(common.to_output_weights(dict(zip(self.classes, w))))
                        row.update({f"r_{c}": r[i] for i, c in enumerate(self.classes)})
                        rows.append(row)
                        w_hold = w * (1 + r) / (1 + gross)
                    if with_current:
                        wc = self.weights(method, self.current_date, prof, k, None, band)
                        current.append({"method": method, "risk_profile": prof, "horizon": h,
                                        "as_of": self.current_date.strftime("%Y-%m"),
                                        **common.to_output_weights(dict(zip(self.classes, wc)))})
                print(f"  [{self.universe}/{h}] {method}: xong ({len(reb)} lần tái cân bằng)", flush=True)
        out = pd.DataFrame(rows)
        if with_current:
            out.attrs["current"] = pd.DataFrame(current)
        return out
