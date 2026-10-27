"""
01d_collect_imf_usdvnd.py - tỷ giá VND/USD bình quân tháng từ IMF IFS (QC 2c).

    python scripts/01d_collect_imf_usdvnd.py            # tải từ GitHub (bản chép IMF IFS của codeforIATI)
    python scripts/01d_collect_imf_usdvnd.py --from-dir <thư mục có 2 file csv đã tải>

Nguồn: IMF International Financial Statistics, bộ Exchange Rates (data.imf.org, IMF.STA:ER), qua bản chép
hằng đêm github.com/codeforIATI/imf-exchangerates (nhánh gh-pages):
- imf_exchangerates_M_ENSA_XDR.csv : đơn vị tiền tệ / SDR, bình quân tháng
- imf_exchangerates.csv            : đơn vị tiền tệ / USD, cuối tháng (chỉ dùng để đối chiếu)
VND/USD bình quân tháng = (VND/SDR bình quân) / (USD/SDR bình quân). Sai khác so với bình quân trực tiếp rất nhỏ
(đối chiếu với tỷ giá cuối tháng: lệch trung vị 0,06%, lớn nhất 1,7%).

Lưu ý khi viết luận văn: IMF ghi tỷ giá CHÍNH THỨC của Việt Nam (tỷ giá trung tâm/tham chiếu NHNN), không phải giá
bán ra của ngân hàng thương mại. Trong giai đoạn tỷ giá thị trường chạm biên ±5% (2022-2025), phần chênh lệch
thị trường - trung tâm nằm trong "chênh lệch SJC" của basis vàng.

Ghi data/raw/usd_vnd_monthly.csv (date,usd_vnd,usd_vnd_eom), date = ngày 1 của tháng.
"""
import argparse
import io
import os
import urllib.request

import pandas as pd

BASE = "https://raw.githubusercontent.com/codeforIATI/imf-exchangerates/gh-pages/"
FILES = {"avg_xdr": "imf_exchangerates_M_ENSA_XDR.csv", "eom_usd": "imf_exchangerates.csv"}
OUT = "data/raw/usd_vnd_monthly.csv"


def read(name, src_dir):
    if src_dir:
        return pd.read_csv(os.path.join(src_dir, name), parse_dates=["Date"])
    with urllib.request.urlopen(BASE + name, timeout=120) as r:
        return pd.read_csv(io.BytesIO(r.read()), parse_dates=["Date"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-dir")
    a = ap.parse_args()
    x = read(FILES["avg_xdr"], a.from_dir)
    e = read(FILES["eom_usd"], a.from_dir)
    usd = x[(x["Currency"] == "USD") & (x["Country code"] == "US")].set_index("Date")["Rate"]
    vnd = x[(x["Currency"] == "VND") & (x["Country code"] == "VN")].set_index("Date")["Rate"]
    eom = e[(e["Currency"] == "VND") & (e["Country code"] == "VN")].set_index("Date")["Rate"]
    df = pd.DataFrame({"usd_vnd": vnd / usd, "usd_vnd_eom": eom}).dropna(subset=["usd_vnd"])
    df = df.loc["2010-01-01":]
    df.index = df.index.to_period("M").to_timestamp()
    df.index.name = "date"
    out = df.round(2).reset_index()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.to_csv(OUT, index=False)
    rel = (df["usd_vnd"] / df["usd_vnd_eom"] - 1).abs()
    print(f"Đã ghi {OUT}: {len(out)} tháng {out['date'].iloc[0]} -> {out['date'].iloc[-1]}; "
          f"lệch bình quân/cuối tháng: trung vị {rel.median():.2%}, lớn nhất {rel.max():.2%}")


if __name__ == "__main__":
    main()
