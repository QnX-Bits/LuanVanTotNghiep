"""
04_standardize_panel.py (đợt 4)
Chuẩn hóa feature theo TIME-SERIES expanding z-score (mục 6.1.1), chỉ dùng quá
khứ:  z_t = (x_t - mean(x_1..x_{t-1})) / std(x_1..x_{t-1}).

Thay đổi theo QC 7:
- Winsorize z-score ở ±3 (trước có |z| tới 13,1 ở tiền gửi, 11,2 ở NVL).
- Tối thiểu 12 quan sát quá khứ (trước 6) mới tính z.
- Momentum/vol tính trên chỉ số tổng lợi nhuận (03) -> trái phiếu cùng dấu với
  các lớp khác; tiền gửi KHÔNG có feature (bị loại khỏi ML).
- Biến kinh tế cấp thị trường (term_spread, d_rate_3m) chuẩn hóa trên chính chuỗi
  tháng của nó; gold_basis chỉ cho vàng.
Thêm 2 cột dùng cho ML (06): prev_mean = trung bình lịch sử (expanding) của return
tới t - chính là benchmark "historical mean" của R²_OS; ewma_vol = độ lệch chuẩn
EWMA (half-life 12 tháng) của return tới t - dùng chuẩn hóa target (QC 14).
Lịch sử trước panel (cổ phiếu từ 08/2018) dùng để khởi động các thống kê này.
"""
import numpy as np
import pandas as pd

HIST_PATH = "data/processed/asset_panel_history.csv"
INPUT_PATH = "data/processed/asset_panel.csv"
OUTPUT_PATH = "data/processed/asset_panel_standardized.csv"

SYMBOL_FEATURES = ["mom_1m", "mom_3m", "mom_6m", "vol_6m"]
MARKET_FEATURES = ["term_spread", "d_rate_3m"]
MIN_PERIODS = 12
WINSOR = 3.0
VOL_HALFLIFE = 12


def expanding_zscore(series: pd.Series, min_periods: int = MIN_PERIODS) -> pd.Series:
    past = series.shift(1)
    mu = past.expanding(min_periods=min_periods).mean()
    sd = past.expanding(min_periods=min_periods).std()
    return ((series - mu) / sd).clip(-WINSOR, WINSOR)


def standardize(hist: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    hist = hist.sort_values(["symbol", "date"])
    out = []
    for sym, g in hist.groupby("symbol"):
        g = g.copy()
        for f in SYMBOL_FEATURES:
            g[f + "_z"] = expanding_zscore(g[f]) if sym != "DEPOSIT_12M" else np.nan
        g["gold_basis_z"] = expanding_zscore(g["gold_basis"]) if sym in ("GOLD_SJC", "GOLD_SJC_RT") else np.nan
        r = g["monthly_return"]
        g["prev_mean"] = r.expanding(min_periods=6).mean()
        g["ewma_vol"] = r.ewm(halflife=VOL_HALFLIFE, min_periods=6).std()
        out.append(g)
    hist = pd.concat(out)
    macro = hist[hist["symbol"] == "DEPOSIT_12M"].set_index("date")[MARKET_FEATURES]
    macro_z = pd.DataFrame({f + "_z": expanding_zscore(macro[f]) for f in MARKET_FEATURES})
    hist = hist.merge(macro_z, left_on="date", right_index=True, how="left")
    hist.loc[hist["symbol"] == "DEPOSIT_12M", [f + "_z" for f in MARKET_FEATURES]] = np.nan
    keep = [c for c in hist.columns if c not in panel.columns or c in ("date", "symbol")]
    panel = panel.merge(hist[keep], on=["date", "symbol"], how="left")
    return panel.sort_values(["asset_class", "symbol", "date"]).reset_index(drop=True)


def main():
    hist = pd.read_csv(HIST_PATH, parse_dates=["date"])
    panel = pd.read_csv(INPUT_PATH, parse_dates=["date"])
    panel = standardize(hist, panel)
    panel.to_csv(OUTPUT_PATH, index=False, float_format="%.10g")
    zc = [c for c in panel.columns if c.endswith("_z")]
    print(f"Đã lưu: {OUTPUT_PATH}  shape={panel.shape}")
    print("|z| lớn nhất theo cột:", panel[zc].abs().max().round(2).to_dict())
    print("Số giá trị z hợp lệ theo mã:")
    print(panel.groupby("symbol")[zc].count().to_string())


if __name__ == "__main__":
    main()
