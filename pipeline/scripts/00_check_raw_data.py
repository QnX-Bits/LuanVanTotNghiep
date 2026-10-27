"""
00_check_raw_data.py - kiểm tra data/raw/ TRƯỚC khi chạy lại pipeline; cho biết mỗi cờ QC còn
lại sẽ đóng hay chưa và vì sao.   python scripts/00_check_raw_data.py
"""
import sys
from importlib import import_module

import pandas as pd

common = import_module("common")
RAW = common.RAW
TARGET_MONTHS = 120


def rng(s):
    s = pd.to_datetime(pd.Series(s)).dropna()
    return f"{s.min():%Y-%m} -> {s.max():%Y-%m}" if len(s) else "trống"


def main():
    ok = True
    print("=== File thô ===")
    try:
        m03 = import_module("03_merge_panel")
    except Exception as e:                                       # file sai định dạng
        print(f"[LỖI] Không đọc được dữ liệu thô: {type(e).__name__}: {e}")
        return 1
    stock = pd.read_csv(RAW / "all_stock_based_raw.csv")
    first = stock.groupby("symbol")["time"].min()
    print("Giá ngày - phiên đầu tiên theo mã:", {s: first.get(s, "THIẾU") for s in ["VNINDEX", "E1VFVN30", *common.RE_TICKERS]})
    bond = m03.load_bond_yield()
    print(f"TPCP 5 năm (tháng): {rng(bond.dropna().index)}")
    gold = m03.load_gold_points()
    real_m = gold.loc[gold["data_quality"] == "real_monthly", "date"]
    print(f"Vàng SJC: {len(gold)} điểm thật, {rng(gold['date'])}; giá THÁNG thật từ {real_m.min():%Y-%m}")
    dep = m03.load_deposit_points()
    print(f"Tiền gửi 12T: {rng(dep.index)}")

    start = m03.PANEL_START
    end = pd.Timestamp(m03.PANEL_END)
    n = (end.year - start.year) * 12 + end.month - start.month + 1
    print(f"\n=== Panel dự kiến: {start:%Y-%m} -> {end:%Y-%m} = {n} tháng (mục tiêu >= {TARGET_MONTHS}) ===")
    print("Mốc từng lớp (tháng return sớm nhất):", m03.PANEL_START_DETAIL)
    a = start + pd.DateOffset(months=common.MIN_HISTORY - 1)
    test0 = a if common.GOLD_VINTAGE else max(a, real_m.min())
    nt = (end.year - test0.year) * 12 + end.month - test0.month
    print(f"Giai đoạn kiểm tra dự kiến: return từ {test0 + pd.DateOffset(months=1):%Y-%m} ({nt} tháng)"
          f"{' [vàng point-in-time BẬT]' if common.GOLD_VINTAGE else ''}")
    if not common.GOLD_VINTAGE and real_m.min() > a + pd.DateOffset(months=12):
        print(f"  -> Giai đoạn kiểm tra đang bị chặn bởi tháng có giá vàng thật ({real_m.min():%Y-%m}). "
              f"Đặt \"gold_vintage\": 1 trong settings.json để bắt đầu từ {a + pd.DateOffset(months=1):%Y-%m}.")

    print("\n=== Trạng thái dự kiến các cờ QC ===")
    rows = []
    det = m03.PANEL_START_DETAIL or {}
    binding = [k for k, v in det.items() if v == max(det.values())] if det else []
    rows.append(("1  mẫu >= 120 tháng", n >= TARGET_MONTHS, f"{n} tháng" + (f"; lớp quyết định mốc: {', '.join(binding)}" if binding else "")))
    fx = RAW / "usd_vnd_monthly.csv"
    if fx.exists():
        f = pd.read_csv(fx, parse_dates=["date"])
        cover = f["date"].min() <= start - pd.DateOffset(months=7)
        rows.append(("2c USD/VND", cover, f"{rng(f['date'])}" + ("" if cover else " - chưa phủ đầu panel")))
    else:
        rows.append(("2c USD/VND", False, "thiếu usd_vnd_monthly.csv"))
    if common.RE_INDEX_FILE.exists():
        rows.append(("4  cổ phiếu BĐS point-in-time", True, f"chỉ số ngành {rng(pd.read_csv(common.RE_INDEX_FILE)['date'])}"))
    elif common.RE_MEMBERSHIP_FILE.exists():
        mem = pd.read_csv(common.RE_MEMBERSHIP_FILE)
        miss = sorted(set(mem["symbol"]) - set(first.index))
        yrs = sorted(mem["year"].unique())
        gap = [y for y in range(start.year, end.year + 1) if y not in yrs]
        good = not miss and not gap
        rows.append(("4  cổ phiếu BĐS point-in-time", good, f"thành viên {yrs[0]}-{yrs[-1]}"
                     + (f"; thiếu giá: {miss}" if miss else "") + (f"; thiếu năm: {gap}" if gap else "")))
    else:
        rows.append(("4  cổ phiếu BĐS point-in-time", False, "thiếu realestate_index.csv hoặc re_basket_membership.csv"))
    cited = common.source_cited("deposit_rate_12m")
    if common.DEPOSIT_TERM_FILE.exists():
        t = pd.read_csv(common.DEPOSIT_TERM_FILE, parse_dates=["date"])
        cov = {c: rng(t.loc[t[c].notna(), "date"]) for c in ("rate_1m", "rate_3m")}
        rows.append(("5b lãi kỳ hạn + trích dẫn", cited, f"kỳ hạn: {cov}; trích dẫn nguồn trong SOURCES.md: {'có' if cited else 'CHƯA'}"))
    else:
        rows.append(("5b lãi kỳ hạn + trích dẫn", False, "thiếu deposit_rate_1m_3m.csv" + ("" if cited else "; chưa điền SOURCES.md")))
    nav = RAW / "bond_fund_nav.csv"
    if nav.exists():
        nv = pd.read_csv(nav, parse_dates=["date"])
        cover = nv["date"].min() <= start
        rows.append(("6  NAV quỹ trái phiếu", True, f"{rng(nv['date'])}" + ("" if cover else
                     f" - trước {nv['date'].min():%Y-%m} vẫn dùng chuỗi tổng hợp (ghi rõ trong luận văn)")))
    else:
        rows.append(("6  NAV quỹ trái phiếu", False, "thiếu bond_fund_nav.csv"))
    for name, good, note in rows:
        ok &= good
        print(f"[{'OK' if good else 'FLAG'}] {name}: {note}")
    print("\nSau khi đủ: python run.py --stage all --no-open  rồi  python scripts/19_qc_checks.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
