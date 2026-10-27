"""
20_test_size_check.py - kiểm tra KÍCH THƯỚC thực nghiệm của kiểm định Sharpe (không nằm trong run.py).

Mô phỏng N cặp chuỗi 47 tháng có CÙNG Sharpe (tương quan 0,8 như các danh mục thực tế),
đếm tỷ lệ bác bỏ ở α = 0,10. Kết quả lần chạy 24/10/2026 (N = 300): Ledoit-Wolf 2008
(khối 4, SE HAC) ~11%, JK-Memmel ~18% -> JK-Memmel bác bỏ quá nhiều với mẫu nhỏ; kết luận
"không có cặp nào có ý nghĩa" không bị ảnh hưởng theo hướng bất lợi.
    python scripts/20_test_size_check.py      (~3 phút)
"""
import numpy as np
from importlib import import_module

m12 = import_module("12_holm_bonferroni_comparison")
common = import_module("common")
N, T, ALPHA = 300, 47, 0.10


def main():
    rng = np.random.RandomState(7)
    lw = jk = 0
    for i in range(N):
        z = rng.multivariate_normal([0, 0], [[1, 0.8], [0.8, 1]], T)
        a, b = 0.005 + 0.03 * z[:, 0], 0.005 + 0.03 * z[:, 1]
        lw += m12.lw2008(a, b, n_boot=499, seed=i)[2] <= ALPHA
        jk += common.jobson_korkie_memmel(a, b)[1] <= ALPHA
    print(f"Kích thước thực nghiệm ở α = {ALPHA}: Ledoit-Wolf 2008 = {lw / N:.3f}, JK-Memmel = {jk / N:.3f} (N = {N}, T = {T})")


if __name__ == "__main__":
    main()
