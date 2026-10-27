"""
00_collect_stock_data.py - giá NGÀY (đã điều chỉnh) cho VN-Index, ETF, cổ phiếu BĐS và ứng viên rổ BĐS, từ 2014.
Chạy trên MÁY CỦA BẠN (có mạng), trong thư mục pipeline:   python scripts/00_collect_stock_data.py

KHÔNG cần vnstock: từ 10/2026 gói vnstock và phụ thuộc vnai bị PyPI đưa vào trạng thái "quarantined" (cách ly), nên
script gọi thẳng các API công khai mà vnstock vẫn dùng, chỉ cần `requests`:
  1. VCI (Vietcap)   trading.vietcap.com.vn  - cùng nguồn với file hiện có (08/2018-2026)
  2. VNDirect dchart dchart-api.vndirect.com.vn
  3. TCBS            apipubaws.tcbs.com.vn
Nguồn đầu tiên trả đủ dữ liệu thì dùng. Nếu cả ba đều lỗi: tải CSV từ investing.com rồi
`python scripts/02c_convert_investing_csv.py stock <MÃ> "<file>.csv"`.

Ghép dữ liệu an toàn: mỗi mã lấy CẢ chuỗi 2014-nay từ MỘT nguồn (không nối hai nguồn có cách điều chỉnh cổ tức
khác nhau). Đơn vị đưa về đúng file cũ (nghìn đồng; chỉ số = điểm) bằng hệ số lũy thừa 10, và in độ lệch so với file
cũ trên các phiên trùng để kiểm tra. Mã nào lệch > 2% (khác cách điều chỉnh) thì báo, vẫn thay bằng chuỗi mới
(một nguồn thống nhất) và lưu bản cũ ở data/raw/all_stock_based_raw.prev.csv.
QC 4: tải thêm ứng viên rổ BĐS (RE_CANDIDATES) và thử chỉ số ngành VNREAL -> realestate_index_candidate.csv.
"""
import math
import os
import shutil
import time
from datetime import datetime, timezone

import pandas as pd
import requests

START, END = "2014-01-01", "2026-07-31"
RAW = "data/raw"
PATH = f"{RAW}/all_stock_based_raw.csv"
CORE = ["VNINDEX", "E1VFVN30", "VHM", "NVL", "KDH", "DXG"]
# Ứng viên rổ cổ phiếu BĐS dân dụng niêm yết HOSE (dùng cho quy tắc chọn theo vốn hóa từng năm).
RE_CANDIDATES = ["NLG", "PDR", "DIG", "HDG", "DXS", "NTL", "SCR", "TCH", "HQC", "QCG", "VPI", "CRE", "KHG", "ITA", "FLC"]
SECTOR_INDEX = "VNREAL"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36", "Accept": "application/json, text/plain, */*"}
INDICES = {"VNINDEX", "VN30", "HNXINDEX", "VNREAL"}


def ts(d):
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def frame(t, o, h, l, c, v, unit_s=True):
    df = pd.DataFrame({"time": pd.to_datetime(pd.Series(t).astype(float), unit="s" if unit_s else "ms"),
                       "open": o, "high": h, "low": l, "close": c, "volume": v})
    df["time"] = df["time"].dt.tz_localize(None).dt.strftime("%Y-%m-%d")
    return df.dropna(subset=["close"]).drop_duplicates("time").sort_values("time")


def vci(sym):
    n = (datetime.strptime(END, "%Y-%m-%d") - datetime.strptime(START, "%Y-%m-%d")).days + 10
    r = requests.post("https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart",
                      json={"timeFrame": "ONE_DAY", "symbols": [sym], "to": ts(END) + 86400, "countBack": n},
                      headers={**UA, "Content-Type": "application/json", "Referer": "https://trading.vietcap.com.vn/",
                               "Origin": "https://trading.vietcap.com.vn"}, timeout=60)
    r.raise_for_status()
    d = r.json()[0]
    return frame(d["t"], d["o"], d["h"], d["l"], d["c"], d["v"])


def vndirect(sym):
    r = requests.get("https://dchart-api.vndirect.com.vn/dchart/history",
                     params={"resolution": "D", "symbol": sym, "from": ts(START), "to": ts(END) + 86400},
                     headers={**UA, "Referer": "https://dchart.vndirect.com.vn/"}, timeout=60)
    r.raise_for_status()
    d = r.json()
    if d.get("s") != "ok":
        raise ValueError(str(d)[:100])
    return frame(d["t"], d["o"], d["h"], d["l"], d["c"], d["v"])


def tcbs(sym):
    kind = "index" if sym in INDICES else "stock"
    r = requests.get("https://apipubaws.tcbs.com.vn/stock-insight/v2/stock/bars-long-term",
                     params={"ticker": sym, "type": kind, "resolution": "D", "from": ts(START), "to": ts(END) + 86400},
                     headers=UA, timeout=60)
    r.raise_for_status()
    d = pd.DataFrame(r.json()["data"])
    d["tradingDate"] = pd.to_datetime(d["tradingDate"]).astype("int64") // 10**9
    return frame(d["tradingDate"], d["open"], d["high"], d["low"], d["close"], d["volume"])


SOURCES = {"VCI": vci, "VNDirect": vndirect, "TCBS": tcbs}


def fetch(sym):
    for name, fn in SOURCES.items():
        try:
            df = fn(sym)
            df = df[(df["time"] >= START) & (df["time"] <= END)]
            if len(df) > 20:
                return df.assign(symbol=sym), name
        except Exception as e:
            print(f"    {sym} @ {name}: {type(e).__name__}: {str(e)[:80]}")
        time.sleep(0.5)
    return pd.DataFrame(), None


def align_units(new, old_sym):
    """Đưa đơn vị chuỗi mới về đơn vị file cũ (hệ số 10^k) và đo độ lệch trên phiên trùng."""
    if old_sym is None or old_sym.empty:
        scale = 1000.0 if new["close"].median() > 1000 and new["symbol"].iloc[0] not in INDICES else 1.0
        return new.assign(**{c: new[c] / scale for c in ("open", "high", "low", "close")}), None
    m = new.merge(old_sym[["time", "close"]], on="time", suffixes=("", "_old"))
    if m.empty:
        return new, None
    ratio = (m["close_old"] / m["close"]).median()
    scale = 10 ** round(math.log10(ratio))
    new = new.assign(**{c: new[c] * scale for c in ("open", "high", "low", "close")})
    m["close"] *= scale
    dev = (m["close"] / m["close_old"] - 1).abs()
    return new, (dev.median(), dev.max(), len(m))


def main():
    os.makedirs(RAW, exist_ok=True)
    old = pd.read_csv(PATH) if os.path.exists(PATH) else pd.DataFrame(columns=["time", "symbol", "close"])
    if os.path.exists(PATH):
        shutil.copy(PATH, f"{RAW}/all_stock_based_raw.prev.csv")
    keep = {s: g for s, g in old.groupby("symbol")}
    for sym in CORE + RE_CANDIDATES:
        df, src = fetch(sym)
        if df.empty:
            print(f"{sym}: KHÔNG LẤY ĐƯỢC từ {', '.join(SOURCES)} - giữ dữ liệu cũ" if sym in keep
                  else f"{sym}: KHÔNG LẤY ĐƯỢC")
            continue
        df, chk = align_units(df, keep.get(sym))
        msg = f"{sym}: {len(df)} phiên {df['time'].min()} -> {df['time'].max()} [{src}]"
        if chk:
            med, mx, n = chk
            msg += f"; so với file cũ ({n} phiên trùng): lệch trung vị {med:.2%}, lớn nhất {mx:.2%}"
            if med > 0.02:
                msg += "  <- CẢNH BÁO: khác cách điều chỉnh giá; đã thay cả chuỗi bằng nguồn mới"
        print(msg)
        keep[sym] = df[["time", "open", "high", "low", "close", "volume", "symbol"]]
    out = pd.concat(keep.values(), ignore_index=True).sort_values(["symbol", "time"])
    out.to_csv(PATH, index=False)
    print(f"Đã ghi {PATH}: {out['symbol'].nunique()} mã, {len(out)} dòng (bản cũ: all_stock_based_raw.prev.csv)")

    idx, src = fetch(SECTOR_INDEX)
    if len(idx):
        p = f"{RAW}/realestate_index_candidate.csv"
        idx[["time", "close"]].rename(columns={"time": "date"}).to_csv(p, index=False)
        print(f"{SECTOR_INDEX}: {idx['time'].min()} -> {idx['time'].max()} [{src}] -> {p}. Nếu có từ 2014, đổi tên thành "
              f"realestate_index.csv (QC 4).")
    else:
        print(f"{SECTOR_INDEX}: không lấy được - dùng re_basket_membership.csv (docs/data_request_qc.md)")


if __name__ == "__main__":
    main()
