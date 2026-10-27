"""
10_black_litterman.py (đợt 4) - ML-enhanced MVO qua Black-Litterman (mục 6.4.3).

    π = δ Σ w_EW                      prior; w_EW = 1/N trên MỌI lớp kể cả tiền mặt,
                                       π là lợi nhuận vượt trội so với tiền mặt
    Q = dự báo ML của lớp có kỹ năng  view tuyệt đối, không có view cho tiền gửi
    Ω_kk = (1 - c_k)/c_k · τ Σ_kk     mức tin cậy kiểu Idzorek (xấp xỉ Walters 2011)
    μ_BL = [(τΣ)^-1 + P'Ω^-1 P]^-1 [(τΣ)^-1 π + P'Ω^-1 Q]  -> MVO (cùng δ, cùng ràng buộc)

Thay đổi theo QC 12:
- Không có view cho tiền gửi (lợi nhuận đã biết trước; tiền gửi là tiền mặt).
- δ CỐ ĐỊNH = 2,5 (common.DELTA, độ nhạy 1,5 / 4) thay cho δ từ Sharpe EW vốn chạm
  biên [1, 10] ở 65% số lần.
- Ω lấy từ KỸ NĂNG NGOÀI MẪU tới thời điểm quyết định: với mỗi lớp, trên các dự báo
  ngoài mẫu đã có kết quả (>= 12 tháng):
      R²_OS = 1 - Σ(r - f)² / Σ(r - m)²       (m = trung bình lịch sử, Campbell-Thompson)
      λ*    = Σ(r - m)(f - m) / Σ(f - m)²      (trọng số kết hợp tối ưu giữa f và m)
  Lớp có R²_OS <= 0 hoặc λ* <= 0 -> KHÔNG đưa view. Còn lại mức tin cậy c = λ* (chặn
  tối đa 0,95). Không lớp nào có kỹ năng -> BL = EW (vẫn là một kết quả H2 hợp lệ).
"""
import numpy as np

TAU = 0.05
MIN_OOS = 12
MAX_CONF = 0.95


def black_litterman_posterior_partial(pi, Sigma, view_idx, Q, omega_diag, tau=TAU):
    """BL với P chọn một phần lớp (view tuyệt đối). Không có view -> trả về π."""
    pi = np.asarray(pi, float)
    if len(view_idx) == 0:
        return pi
    n = len(pi)
    P = np.zeros((len(view_idx), n))
    P[np.arange(len(view_idx)), view_idx] = 1.0
    ts_inv = np.linalg.inv(tau * np.asarray(Sigma))
    om_inv = np.diag(1.0 / np.asarray(omega_diag, float))
    A = ts_inv + P.T @ om_inv @ P
    b = ts_inv @ pi + P.T @ om_inv @ np.asarray(Q, float)
    return np.linalg.solve(A, b)


def skill(realized, forecast, bench, min_obs=MIN_OOS):
    """(R²_OS, λ*, n) trên các cặp dự báo ngoài mẫu đã có kết quả."""
    r, f, m = (np.asarray(x, float) for x in (realized, forecast, bench))
    ok = ~(np.isnan(r) | np.isnan(f) | np.isnan(m))
    r, f, m = r[ok], f[ok], m[ok]
    n = len(r)
    if n < min_obs:
        return np.nan, np.nan, n
    den = ((r - m) ** 2).sum()
    r2 = 1 - ((r - f) ** 2).sum() / den if den > 0 else np.nan
    dd = ((f - m) ** 2).sum()
    lam = ((r - m) * (f - m)).sum() / dd if dd > 1e-18 else 0.0
    return float(r2), float(lam), n


def confidence_from_skill(r2, lam):
    if np.isnan(r2) or r2 <= 0 or lam <= 0:
        return 0.0
    return float(min(lam, MAX_CONF))


def omega_from_confidence(conf, sigma_kk, tau=TAU):
    return (1 - conf) / conf * tau * sigma_kk


if __name__ == "__main__":
    S = np.diag([0.004, 0.009, 0.002, 0.0003])
    pi = 2.5 * S @ np.full(4, 0.2)
    print("Không view -> π:", np.allclose(black_litterman_posterior_partial(pi, S, [], [], []), pi))
    mu = black_litterman_posterior_partial(pi, S, [0], [pi[0] + 0.01], [omega_from_confidence(0.5, S[0, 0])])
    print("1 view tin cậy 50% -> dịch 50% về Q:", round((mu[0] - pi[0]) / 0.01, 3))
