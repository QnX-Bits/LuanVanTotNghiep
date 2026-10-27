"""
09_portfolio_optimization.py (đợt 4) - bộ ước lượng + bộ tối ưu dùng chung.

Thay đổi theo QC:
- QC 9: tiền gửi là TIỀN MẶT nhận phần dư -> mọi ước lượng/tối ưu chỉ chạy trên
  các lớp PHI tiền mặt; bỏ hẳn tham số "sàn vol tiền gửi".
- QC 10: MỘT cách ước lượng hiệp phương sai cho mọi khung thời gian: EWMA
  (half-life 18 tháng) trên toàn bộ lịch sử tới thời điểm quyết định + co ngót
  Ledoit-Wolf các hệ số tương quan về 0 (target "D" của Schäfer & Strimmer 2005:
  giữ nguyên phương sai từng lớp). Trái phiếu được khử độ trơn (Geltner) trước khi
  ước lượng vì chuỗi lợi suất bị đứng giá (autocorrelation tháng ~0,34) - QC 6.
- QC 11: Markowitz giải bằng cvxpy (Clarabel, lồi, tất định) thay SLSQP; μ lịch sử
  được co về trung bình của danh mục phương sai nhỏ nhất (Bayes-Stein, Jorion
  1986); có phạt turnover theo vector phí từng lớp.
- QC 8: dải khẩu vị là RÀNG BUỘC trong bài toán MVO/BL (lo <= Σw_rủi ro <= hi).
  RP/HRP là thiết kế HAI TẦNG: tầng 1 co giãn danh mục phi tiền mặt về vol mục
  tiêu của khẩu vị (tiền mặt nhận phần dư) và ép tỷ trọng nhóm rủi ro vào dải;
  tầng 2 do RP/HRP quyết định tỷ lệ BÊN TRONG nhóm.
"""
import numpy as np
import pandas as pd
import cvxpy as cp
from importlib import import_module
from scipy.optimize import minimize
from scipy.cluster.hierarchy import linkage

common = import_module("common")

UNSMOOTH_CLASSES = ("trai_phieu",)
RHO_MAX = 0.6
SOLVER_TOL = 1e-9


# ============================================
# ƯỚC LƯỢNG
# ============================================
def geltner_unsmooth(r: pd.Series):
    """r*_t = (r_t - ρ r_{t-1}) / (1 - ρ), ρ = AR(1) ước lượng trong cửa sổ, chặn [0, 0,6]."""
    x = r.dropna()
    if len(x) < 12:
        return r, 0.0
    rho = x.autocorr(1)
    rho = float(np.clip(0.0 if np.isnan(rho) else rho, 0.0, RHO_MAX))
    return (r - rho * r.shift(1)) / (1 - rho), rho


def time_weights(n: int) -> np.ndarray:
    if common.ROLLING_WINDOW > 0:
        w = np.zeros(n)
        w[-min(common.ROLLING_WINDOW, n):] = 1.0
    else:
        lam = 0.5 ** (1.0 / common.EWMA_HALFLIFE)
        w = lam ** np.arange(n - 1, -1, -1, dtype=float)
    return w / w.sum()


def eligible_columns(R: pd.DataFrame, min_obs: int = common.MIN_HISTORY):
    return [c for c in R.columns if R[c].count() >= min_obs]


def estimate_cov(R: pd.DataFrame, return_info: bool = False):
    """Hiệp phương sai THÁNG cho các lớp phi tiền mặt (R: tháng x lớp, có thể NaN)."""
    R = R.copy()
    info = {}
    for c in UNSMOOTH_CLASSES:
        if c in R:
            R[c], info[f"rho_{c}"] = geltner_unsmooth(R[c])
    X = R.values.astype(float)
    n, p = X.shape
    w = time_weights(n)
    M = ~np.isnan(X)
    S = np.zeros((p, p))
    means = np.zeros(p)
    for i in range(p):
        wi = w[M[:, i]] / w[M[:, i]].sum()
        means[i] = wi @ X[M[:, i], i]
    for i in range(p):
        for j in range(i, p):
            m = M[:, i] & M[:, j]
            ww = w[m] / w[m].sum()
            xi = X[m, i] - ww @ X[m, i]
            xj = X[m, j] - ww @ X[m, j]
            S[i, j] = S[j, i] = (ww * xi * xj).sum() / max(1 - (ww ** 2).sum(), 1e-12)
    sd = np.sqrt(np.clip(np.diag(S), 1e-14, None))
    C = S / np.outer(sd, sd)
    ev, V = np.linalg.eigh((C + C.T) / 2)                      # chiếu PSD (ước lượng theo cặp)
    C = V @ np.diag(np.clip(ev, 1e-8, None)) @ V.T
    d = np.sqrt(np.diag(C))
    C = C / np.outer(d, d)

    # Ledoit-Wolf (trọng số EWMA) co các hệ số tương quan về 0
    Y = np.where(M, (X - means) / sd, 0.0)
    off = ~np.eye(p, dtype=bool)
    outer = Y[:, :, None] * Y[:, None, :]
    beta2 = float((w ** 2) @ (((outer - C[None]) ** 2)[:, off]).sum(axis=1))
    delta2 = float((C[off] ** 2).sum())
    shrink = float(np.clip(beta2 / delta2, 0, 1)) if delta2 > 0 else 1.0
    C_s = (1 - shrink) * C + shrink * np.eye(p)
    Sigma = pd.DataFrame(C_s * np.outer(sd, sd), index=R.columns, columns=R.columns)
    info.update({"lw_shrinkage": shrink, "n_eff": float(1 / (w ** 2).sum()), "n_obs": n})
    return (Sigma, info) if return_info else Sigma


def bayes_stein_mean(R_ex: pd.DataFrame, Sigma: np.ndarray):
    """Jorion (1986): μ_BS = (1-φ)μ̂ + φ μ_g 1, μ_g = trung bình của danh mục GMV."""
    mu_hat = R_ex.mean().values
    T = int(R_ex.count().min())
    N = len(mu_hat)
    Si = np.linalg.inv(Sigma)
    one = np.ones(N)
    mu_g = float(one @ Si @ mu_hat / (one @ Si @ one))
    dvec = mu_hat - mu_g
    phi = float(np.clip((N + 2) / ((N + 2) + T * dvec @ Si @ dvec), 0, 1))
    return (1 - phi) * mu_hat + phi * mu_g, phi


# ============================================
# TỐI ƯU MEAN-VARIANCE (cvxpy) - Markowitz / BL / MLP_MVO
# ============================================
def mvo(mu, Sigma, delta, risky_mask, band=None, has_cash=True, cap=1.0,
        w_prev=None, costs=None, hold_months=1):
    """max  k·(w'μ - δ/2 w'Σw) - Σ c_i|w_i - w_prev,i|  (k = số tháng giữ tới lần tái cân bằng sau)
    s.t. w >= 0, w <= cap, Σw <= 1 (có tiền mặt; tiền mặt = 1 - Σw) hoặc = 1 (không có),
         lo <= Σ w_rủi ro <= hi  (dải khẩu vị - ràng buộc cứng).
    μ là lợi nhuận VƯỢT TRỘI so với tiền mặt; trả về vector [phi tiền mặt..., tiền mặt]."""
    mu = np.asarray(mu, float)
    n = len(mu)
    risky_mask = np.asarray(risky_mask, bool)
    scale = 1e3                                                # đưa bài toán về độ lớn ~1
    w = cp.Variable(n)
    cons = [w >= 0]
    if cap < 1:
        cons.append(w <= cap)
    tot = cp.sum(w)
    cons.append(tot <= 1 if has_cash else tot == 1)
    if band is not None and risky_mask.any():
        lo, hi = band
        cons += [risky_mask.astype(float) @ w >= lo, risky_mask.astype(float) @ w <= hi]
    Sig = cp.psd_wrap((np.asarray(Sigma) + np.asarray(Sigma).T) / 2)
    obj = scale * hold_months * (mu @ w - delta / 2 * cp.quad_form(w, Sig))
    if w_prev is not None and costs is not None:
        c = np.asarray(costs, float)
        obj -= scale * (c[:n] @ cp.abs(w - w_prev[:n]))
        if has_cash:
            obj -= scale * c[n] * cp.abs(1 - tot - w_prev[n])
    prob = cp.Problem(cp.Maximize(obj), cons)
    try:
        prob.solve(solver=cp.CLARABEL, tol_gap_abs=SOLVER_TOL, tol_gap_rel=SOLVER_TOL, tol_feas=SOLVER_TOL)
    except cp.SolverError:
        prob.solve(solver=cp.OSQP, eps_abs=1e-10, eps_rel=1e-10, max_iter=200000, polish=True)
    if prob.status not in ("optimal", "optimal_inaccurate") or w.value is None:
        raise RuntimeError(f"MVO không giải được: {prob.status}")
    x = np.clip(np.asarray(w.value).ravel(), 0, None)
    x = np.round(x, 10)                                        # khử nhiễu số học -> kết quả tái lập
    if has_cash:
        if x.sum() > 1:
            x = x / x.sum()
        return np.append(x, 1 - x.sum())
    return x / x.sum()


# ============================================
# RISK PARITY / HRP (trên các lớp phi tiền mặt)
# ============================================
def risk_parity(Sigma) -> np.ndarray:
    """Equal Risk Contribution (Maillard, Roncalli & Teïletche 2010), bài toán lồi:
    min_y 0.5 y'Σy - (1/n) Σ log y_i, y > 0, w = y/Σy."""
    S = np.asarray(Sigma, float)
    n = S.shape[0]
    S = S / np.mean(np.diag(S))

    def f(y):
        return 0.5 * y @ S @ y - np.sum(np.log(y)) / n

    def g(y):
        return S @ y - 1.0 / (n * y)

    y0 = 1.0 / np.sqrt(np.diag(S))
    res = minimize(f, y0, jac=g, method="L-BFGS-B", bounds=[(1e-10, None)] * n,
                   options={"ftol": 1e-15, "gtol": 1e-12, "maxiter": 5000})
    return res.x / res.x.sum()


def hrp(Sigma) -> np.ndarray:
    """Hierarchical Risk Parity (López de Prado 2016): single linkage trên khoảng
    cách tương quan, quasi-diagonalization, chia đôi đệ quy theo phương sai cụm."""
    S = np.asarray(Sigma, float)
    n = S.shape[0]
    if n == 1:
        return np.ones(1)
    sd = np.sqrt(np.diag(S))
    corr = S / np.outer(sd, sd)
    dist = np.sqrt(np.clip(0.5 * (1 - np.clip(corr, -1, 1)), 0, None))
    link = linkage(dist[np.triu_indices(n, 1)], method="single")

    link_i = link[:, :2].astype(int)
    order = [link_i[-1, 0], link_i[-1, 1]]
    while max(order) >= n:
        new = []
        for i in order:
            new.extend(link_i[i - n].tolist() if i >= n else [i])
        order = new

    def cluster_var(idx):
        sub = S[np.ix_(idx, idx)]
        iv = 1 / np.diag(sub)
        w = iv / iv.sum()
        return w @ sub @ w

    w = pd.Series(1.0, index=order)
    clusters = [order]
    while clusters:
        clusters = [c[a:b] for c in clusters for a, b in ((0, len(c) // 2), (len(c) // 2, len(c))) if len(c) > 1]
        for i in range(0, len(clusters) - 1, 2):
            c0, c1 = clusters[i], clusters[i + 1]
            v0, v1 = cluster_var(c0), cluster_var(c1)
            alpha = 1 - v0 / (v0 + v1)
            w[c0] *= alpha
            w[c1] *= 1 - alpha
    out = w.sort_index().values
    return out / out.sum()


# ============================================
# TẦNG 1: vol mục tiêu + dải khẩu vị
# ============================================
def scale_to_vol(w_noncash, Sigma, target_ann):
    """Co danh mục phi tiền mặt (tổng 1) về vol mục tiêu, không đòn bẩy; tiền mặt = phần dư."""
    w = np.asarray(w_noncash, float)
    vol = float(np.sqrt(w @ np.asarray(Sigma) @ w * 12))
    s = min(1.0, target_ann / vol) if vol > 0 else 1.0
    return np.append(s * w, 1 - s)


def two_tier_band(w_full, risky_mask, lo, hi):
    """Đưa tổng nhóm rủi ro về [lo, hi], giữ tỷ lệ BÊN TRONG nhóm rủi ro và nhóm còn lại."""
    w = np.asarray(w_full, float).copy()
    risky_mask = np.asarray(risky_mask, bool)
    if not risky_mask.any() or risky_mask.all():
        return w / w.sum()
    r = w[risky_mask].sum()
    target = min(max(r, lo), hi)
    if np.isclose(target, r, atol=1e-12):
        return w / w.sum()
    for mask, total in ((risky_mask, target), (~risky_mask, 1 - target)):
        cur = w[mask].sum()
        w[mask] = w[mask] * (total / cur) if cur > 1e-12 else total / mask.sum()
    return w / w.sum()


def cap_classes(w_full, risky_mask, cash_mask, cap):
    """Trần `cap` cho mỗi lớp phi tiền mặt (giống ràng buộc của MVO/BL), giữ nguyên tổng nhóm rủi ro: phần vượt của
    lớp rủi ro chia cho lớp rủi ro còn chỗ; phần vượt của lớp phòng thủ (vàng, trái phiếu) chuyển về tiền mặt."""
    w = np.asarray(w_full, float).copy()
    risky_mask, cash_mask = np.asarray(risky_mask, bool), np.asarray(cash_mask, bool)
    if cap >= 1:
        return w
    for _ in range(10):
        over = (~cash_mask) & (w > cap + 1e-12)
        if not over.any():
            break
        for i in np.where(over)[0]:
            excess, w[i] = w[i] - cap, cap
            if risky_mask[i]:
                room = risky_mask & (w < cap - 1e-12)
                if room.any():
                    w[room] += excess * (cap - w[room]) / (cap - w[room]).sum()
                    continue
            if cash_mask.any():
                w[cash_mask] += excess / cash_mask.sum()
            else:
                room = (~risky_mask) & (w < cap - 1e-12)
                if room.any():
                    w[room] += excess * (cap - w[room]) / (cap - w[room]).sum()
                else:
                    w[i] += excess                       # không còn chỗ: giữ nguyên
    return w / w.sum()


if __name__ == "__main__":
    rng = np.random.RandomState(42)
    R = pd.DataFrame(rng.randn(60, 4) * [0.06, 0.09, 0.05, 0.01], columns=["etf", "bat_dong_san", "vang", "trai_phieu"])
    Sig, info = estimate_cov(R, return_info=True)
    print("Σ (năm hóa vol):", np.round(np.sqrt(np.diag(Sig) * 12), 3), info)
    print("RP :", np.round(risk_parity(Sig.values), 4))
    print("HRP:", np.round(hrp(Sig.values), 4))
    mu, phi = bayes_stein_mean(R, Sig.values)
    print("MVO:", np.round(mvo(mu, Sig.values, 2.5, [1, 1, 0, 0], band=(0.4, 0.6), cap=0.5), 4), "phi", round(phi, 3))
