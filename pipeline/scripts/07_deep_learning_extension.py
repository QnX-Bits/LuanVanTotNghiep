"""
07_deep_learning_extension.py (đợt 4) - HƯỚNG MỞ RỘNG: MLP dự báo return (dùng cho
MLP_MVO). Không thuộc kiểm định chính.

Sửa theo QC 14:
- early_stopping của sklearn chia validation NGẪU NHIÊN -> rò rỉ thời gian. Thay bằng
  dừng sớm THEO THỜI GIAN: 20% số tháng cuối của mẫu train làm validation, chọn số
  epoch tốt nhất (patience 20), rồi train lại trên toàn bộ mẫu đúng số epoch đó.
- Lấy trung bình 5 seed; số luồng BLAS cố định = 1 (run.py) -> kết quả tái lập.
- Cùng target chuẩn hóa / feature / cửa sổ mở rộng / cách trừ mức trung bình như 06.
Kết quả ghi thêm vào forecasts_oos.csv (model = "mlp") và cập nhật bảng kỹ năng.
"""
import warnings

import numpy as np
import pandas as pd
from importlib import import_module

common = import_module("common")
m06 = import_module("06_train_models")
FEATURES = m06.FEATURES
SEEDS = [0, 1, 2, 3, 4]
HIDDEN = (8,)
ALPHA = 1.0
MAX_EPOCHS = 300
PATIENCE = 20


class MLP:
    name = "mlp"

    def __init__(self):
        self.epochs_log = []

    def _net(self, seed):
        from sklearn.neural_network import MLPRegressor
        return MLPRegressor(hidden_layer_sizes=HIDDEN, alpha=ALPHA, learning_rate_init=1e-3,
                            batch_size=32, random_state=seed, max_iter=1)

    def fit(self, tr, d):
        from sklearn.exceptions import ConvergenceWarning
        X, y = tr[FEATURES].values, tr["z_target"].values
        months = np.sort(tr["date"].unique())
        cut = months[int(np.floor(len(months) * 0.8))]
        is_val = (tr["date"] >= cut).values
        self.nets = []
        for seed in SEEDS:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ConvergenceWarning)   # 1 epoch/lần gọi là có chủ đích
                net, best, best_ep, bad = self._net(seed), np.inf, 1, 0
                for ep in range(1, MAX_EPOCHS + 1):
                    net.partial_fit(X[~is_val], y[~is_val])
                    loss = float(np.mean((net.predict(X[is_val]) - y[is_val]) ** 2))
                    if loss < best - 1e-9:
                        best, best_ep, bad = loss, ep, 0
                    else:
                        bad += 1
                        if bad >= PATIENCE:
                            break
                final = self._net(seed)
                for _ in range(best_ep):
                    final.partial_fit(X, y)
            self.nets.append(final)
            self.epochs_log.append({"date": d, "seed": seed, "best_epoch": best_ep, "val_mse": best})
        return self

    def predict(self, X):
        return np.mean([n.predict(X[FEATURES].values) for n in self.nets], axis=0)


def main():
    df = m06.prepare()
    dates = m06.forecast_dates(df)
    print(f"MLP: {len(dates)} tháng ngoài mẫu, {len(SEEDS)} seed, dừng sớm theo thời gian")
    model = MLP()
    fc_mlp = m06.generate(model, df, dates)
    common.write_csv(pd.DataFrame(model.epochs_log), "data/processed/mlp_epochs_log.csv", index=False)
    fc = pd.read_csv(common.FORECAST_PATH, parse_dates=["date"])
    fc = pd.concat([fc[fc["model"] != "mlp"], fc_mlp], ignore_index=True)
    common.write_csv(fc, common.FORECAST_PATH, index=False)
    by_class, summary = m06.write_skill_tables(fc, m06.test_start_decision())
    print(summary[summary.period == "toan_bo_oos"].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
