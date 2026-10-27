"""
01b_collect_world_gold.py
Tải giá vàng thế giới theo tháng (USD/oz) dùng để DỰNG LẠI giá SJC các tháng
không có giá thật (trước 08/2022 pricedancing chỉ có nến 4 tháng).

Nguồn: World Bank Commodity Markets ("Pink Sheet"), bản đóng gói công khai
datasets/gold-prices (ODC-PDDL). Lưu ý: Pink Sheet là giá BÌNH QUÂN THÁNG, không
phải giá cuối tháng; 03_merge_panel.py xấp xỉ giá cuối tháng bằng trung bình
của bình quân tháng t và t+1 (đã kiểm chứng trên giai đoạn có giá SJC thật, xem
data/processed/gold_reconstruction_validation.csv).

Chạy tay (cần mạng):  python scripts/01b_collect_world_gold.py
"""
import io
import urllib.request

import pandas as pd

URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"
OUT = "data/raw/world_gold_usd_monthly_wb.csv"


def main():
    raw = urllib.request.urlopen(URL, timeout=60).read().decode("utf-8")
    df = pd.read_csv(io.StringIO(raw))
    df["date"] = pd.to_datetime(df["Date"]).dt.to_period("M").dt.to_timestamp()
    df = df[df["date"] >= "2000-01-01"][["date", "Price"]].rename(columns={"Price": "gold_usd_oz_avg"})
    df.to_csv(OUT, index=False)
    print(f"Đã lưu {OUT}: {len(df)} tháng, {df['date'].min():%Y-%m} -> {df['date'].max():%Y-%m}")


if __name__ == "__main__":
    main()
