"""
05_purged_walkforward_cv.py (đợt 4) - chia CV theo thời gian cho vòng tune ML.

QC 14: purge 6 tháng là hiểu sai khái niệm. Purging loại các quan sát train có
NHÃN chồng lấp thời gian với tập validation; nhãn ở đây là return 1 tháng nên
chỉ cần bỏ 1 tháng ngay trước validation. Embargo không cần trong walk-forward
một chiều (train luôn nằm TRƯỚC validation).

Mỗi fold: validation là một khối `val_months` tháng liên tiếp ở cuối dữ liệu,
train = toàn bộ các tháng trước đó (cửa sổ mở rộng) trừ `purge_months` tháng
sát validation.
"""
import numpy as np
import pandas as pd


def time_splits(dates, n_splits=3, val_months=6, purge_months=1, min_train_months=12):
    """Trả về list (train_idx, val_idx) dạng vị trí - dùng được cho sklearn cv=."""
    dates = pd.Series(pd.DatetimeIndex(dates))
    months = np.array(sorted(dates.unique()))
    splits = []
    for k in range(n_splits, 0, -1):
        v0 = len(months) - k * val_months
        v1 = v0 + val_months
        t1 = v0 - purge_months
        if t1 < min_train_months or v0 < 0:
            continue
        tr_m, va_m = months[:t1], months[v0:v1]
        splits.append((np.where(dates.isin(tr_m))[0], np.where(dates.isin(va_m))[0]))
    return splits


def check_no_overlap(dates, splits, purge_months=1):
    """Kiểm tra: tháng train cuối cùng <= tháng validation đầu tiên - (purge + 1)."""
    dates = pd.Series(pd.DatetimeIndex(dates))
    for tr, va in splits:
        assert dates.iloc[tr].max() <= dates.iloc[va].min() - pd.DateOffset(months=purge_months + 1)
    return True


if __name__ == "__main__":
    d = pd.Series(np.repeat(pd.date_range("2020-01-01", periods=48, freq="MS"), 7))
    sp = time_splits(d)
    for tr, va in sp:
        print(f"train {d.iloc[tr].min():%Y-%m}..{d.iloc[tr].max():%Y-%m}  val {d.iloc[va].min():%Y-%m}..{d.iloc[va].max():%Y-%m}")
    print("Không chồng lấp:", check_no_overlap(d, sp))
