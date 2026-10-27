"""
02c_convert_investing_csv.py - chuyển file CSV "Historical Data" tải từ investing.com (hoặc
file cùng cấu trúc Date/Price/Open/High/Low) sang đúng định dạng data/raw/ của pipeline.

Cách tải trên investing.com: mở trang lịch sử (VD "Vietnam 5-Year Bond Yield Historical Data",
"USD VND Historical Data", "VN Index Historical Data", "E1VFVN30 ..."), chọn khoảng ngày từ
01/01/2014, tần suất Daily (USD/VND có thể chọn Monthly), bấm Download.

    python scripts/02c_convert_investing_csv.py stock  VNINDEX  "VN Index Historical Data.csv"
    python scripts/02c_convert_investing_csv.py stock  E1VFVN30 "E1VFVN30 Historical Data.csv"
    python scripts/02c_convert_investing_csv.py bond   VN5Y     "Vietnam 5-Year Bond Yield Historical Data.csv"
    python scripts/02c_convert_investing_csv.py usdvnd USDVND   "USD_VND Historical Data.csv"
    python scripts/02c_convert_investing_csv.py reindex VNREAL  "VNREAL Historical Data.csv"

- stock  : nối vào all_stock_based_raw.csv; ngày đã có (từ vnstock) được GIỮ, chỉ thêm ngày mới.
- bond   : hợp với Vietnam_5-Year_Bond_Yield_Historical_Data.csv (giữ ngày đã có).
- usdvnd : bình quân tháng -> usd_vnd_monthly.csv (date = ngày đầu tháng) - QC 2.
- reindex: chỉ số ngành BĐS -> realestate_index.csv (date,close) - QC 4. File này BẬT rổ BĐS
           theo chỉ số khi chạy lại pipeline.
Ngày dạng DD/MM/YYYY (bản tiếng Việt) được tự nhận; ép bằng --dayfirst nếu cần.
"""
import argparse
import os
import re

import numpy as np
import pandas as pd

RAW = "data/raw"


def parse_number(x):
    if pd.isna(x):
        return np.nan
    s = str(x).strip().replace('"', "")
    if s in ("", "-"):
        return np.nan
    mult = 1.0
    if s[-1] in "KMB":
        mult = {"K": 1e3, "M": 1e6, "B": 1e9}[s[-1]]
        s = s[:-1]
    s = s.replace("%", "")
    if re.match(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$", s):          # kiểu VN: 1.234,56
        s = s.replace(".", "").replace(",", ".")
    else:                                                      # kiểu EN: 1,234.56
        s = s.replace(",", "")
    return float(s) * mult


def read_investing(path, dayfirst=None):
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [c.strip().strip('"') for c in df.columns]
    rename = {"Ngày": "Date", "Lần cuối": "Price", "Mở": "Open", "Cao": "High", "Thấp": "Low", "KL": "Vol.",
              "% Thay đổi": "Change %", "Close": "Price"}
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    raw_dates = df["Date"].astype(str)
    if dayfirst is None:
        first = raw_dates.str.extract(r"^(\d{1,2})[/\-.]")[0].astype(float)
        dayfirst = bool((first > 12).any())
    df["Date"] = pd.to_datetime(raw_dates, dayfirst=dayfirst)
    for c in ("Price", "Open", "High", "Low", "Vol."):
        if c in df.columns:
            df[c] = df[c].map(parse_number)
    return df.sort_values("Date").reset_index(drop=True)


def convert_stock(df, symbol):
    out = pd.DataFrame({"time": df["Date"].dt.strftime("%Y-%m-%d"), "open": df.get("Open", df["Price"]),
                        "high": df.get("High", df["Price"]), "low": df.get("Low", df["Price"]),
                        "close": df["Price"], "volume": df.get("Vol.", np.nan), "symbol": symbol})
    path = f"{RAW}/all_stock_based_raw.csv"
    old = pd.read_csv(path) if os.path.exists(path) else out.iloc[:0]
    have = set(zip(old["time"], old["symbol"]))
    add = out[[(t, symbol) not in have for t in out["time"]]]
    merged = pd.concat([old, add], ignore_index=True).sort_values(["symbol", "time"])
    merged.to_csv(path, index=False)
    return path, len(add), f"{out['time'].min()} -> {out['time'].max()}"


def convert_bond(df):
    path = f"{RAW}/Vietnam_5-Year_Bond_Yield_Historical_Data.csv"
    new = pd.DataFrame({"Date": df["Date"], "Price": df["Price"], "Open": df.get("Open", df["Price"]),
                        "High": df.get("High", df["Price"]), "Low": df.get("Low", df["Price"])})
    if os.path.exists(path):
        old = pd.read_csv(path)
        old["Date"] = pd.to_datetime(old["Date"], format="%m/%d/%Y")
        new = new[~new["Date"].isin(old["Date"])]
        for c in ("Price", "Open", "High", "Low"):
            old[c] = old[c].map(parse_number)
        new = pd.concat([old[["Date", "Price", "Open", "High", "Low"]], new], ignore_index=True)
    new = new.sort_values("Date", ascending=False)
    new["Change %"] = ""
    out = new.assign(Date=new["Date"].dt.strftime("%m/%d/%Y"))
    out.to_csv(path, index=False, float_format="%.3f")
    return path, len(out), f"{new['Date'].min():%Y-%m-%d} -> {new['Date'].max():%Y-%m-%d}"


def convert_usdvnd(df):
    m = df.set_index("Date")["Price"].resample("MS").mean()
    out = pd.DataFrame({"date": m.index.strftime("%Y-%m-%d"), "usd_vnd": m.values}).dropna()
    path = f"{RAW}/usd_vnd_monthly.csv"
    out.to_csv(path, index=False, float_format="%.2f")
    return path, len(out), f"{out['date'].min()} -> {out['date'].max()}"


def convert_reindex(df):
    out = pd.DataFrame({"date": df["Date"].dt.strftime("%Y-%m-%d"), "close": df["Price"]})
    path = f"{RAW}/realestate_index.csv"
    out.to_csv(path, index=False)
    return path, len(out), f"{out['date'].min()} -> {out['date'].max()}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["stock", "bond", "usdvnd", "reindex"])
    ap.add_argument("symbol")
    ap.add_argument("file")
    ap.add_argument("--dayfirst", action="store_true", default=None)
    a = ap.parse_args()
    df = read_investing(a.file, a.dayfirst)
    fn = {"stock": lambda d: convert_stock(d, a.symbol), "bond": convert_bond,
          "usdvnd": convert_usdvnd, "reindex": convert_reindex}[a.kind]
    path, n, rng = fn(df)
    print(f"Đã ghi {path}: {n} dòng ({rng}). Chạy tiếp: python scripts/00_check_raw_data.py")


if __name__ == "__main__":
    main()
