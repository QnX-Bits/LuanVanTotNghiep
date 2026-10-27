"""
01c_collect_fmarket_nav.py - QC 6: NAV lịch sử của một quỹ trái phiếu mở (chuỗi ĐẦU TƯ ĐƯỢC thay
cho chuỗi TPCP 5 năm tổng hợp). Nguồn: API công khai mà trang fmarket.vn dùng (cùng endpoint với
thư viện vnstock: vnstock/explorer/fmarket). Chạy trên MÁY CỦA BẠN (sandbox bị chặn).

    python scripts/01c_collect_fmarket_nav.py --list          # liệt kê quỹ trái phiếu + ngày phát hành
    python scripts/01c_collect_fmarket_nav.py --fund DCBF     # tải NAV quỹ chọn -> data/raw/bond_fund_nav.csv

Chọn quỹ: ưu tiên quỹ có NGÀY PHÁT HÀNH sớm nhất (cần phủ cả panel) và danh mục chủ yếu trái phiếu
CHÍNH PHỦ/ngân hàng (quỹ nặng trái phiếu doanh nghiệp chịu cú sốc 2022 riêng - ghi rõ trong luận văn).
Nếu API đổi/bị chặn: mở trang quỹ trên fmarket.vn -> DevTools -> Network -> request
"get-nav-history" -> copy Response, lưu thành data/raw/fmarket_nav.json rồi chạy với --from-json.
"""
import argparse
import json
from datetime import datetime

import pandas as pd

BASE = "https://api.fmarket.vn/res/products"
HEADERS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "Origin": "https://fmarket.vn",
           "Referer": "https://fmarket.vn/"}
OUT = "data/raw/bond_fund_nav.csv"


def list_bond_funds():
    import requests
    payload = {"types": ["NEW_FUND", "TRADING_FUND"], "issuerIds": [], "sortOrder": "DESC",
               "sortField": "navTo6Months", "page": 1, "pageSize": 100, "isIpo": False,
               "fundAssetTypes": ["BOND"], "bondRemainPeriods": [], "searchField": "",
               "isBuyByReward": False, "thirdAppIds": []}
    r = requests.post(f"{BASE}/filter", json=payload, headers=HEADERS, timeout=30)
    r.raise_for_status()
    rows = r.json()["data"]["rows"]
    df = pd.DataFrame([{"short_name": x.get("shortName"), "id": x.get("id"), "name": x.get("name"),
                        "owner": (x.get("owner") or {}).get("name"),
                        "inception": pd.to_datetime(x.get("firstIssueAt"), unit="ms", errors="coerce")} for x in rows])
    return df.sort_values("inception")


def nav_history(fund_id):
    import requests
    payload = {"isAllData": 1, "productId": int(fund_id), "fromDate": None, "toDate": datetime.now().strftime("%Y%m%d")}
    r = requests.post(f"{BASE[:-1]}/get-nav-history", json=payload, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()["data"]


def to_csv(records, label):
    df = pd.DataFrame(records)[["navDate", "nav"]].rename(columns={"navDate": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.drop_duplicates("date").sort_values("date")
    df.to_csv(OUT, index=False)
    with open(OUT.replace(".csv", "_source.txt"), "w", encoding="utf-8") as f:
        f.write(f"{label}\nNguồn: fmarket.vn (API get-nav-history), tải ngày {datetime.now():%Y-%m-%d}\n")
    print(f"Đã ghi {OUT}: {len(df)} điểm NAV, {df['date'].min()} -> {df['date'].max()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--fund", help="mã ngắn của quỹ (short_name), VD DCBF, TCBF, SSIBF")
    ap.add_argument("--from-json", help="file JSON copy từ DevTools (response get-nav-history)")
    a = ap.parse_args()
    if a.from_json:
        payload = json.load(open(a.from_json, encoding="utf-8"))
        to_csv(payload["data"], f"Quỹ: (từ {a.from_json})")
        return
    funds = list_bond_funds()
    if a.list or not a.fund:
        print(funds.to_string(index=False))
        return
    row = funds[funds["short_name"].str.upper() == a.fund.upper()]
    if row.empty:
        raise SystemExit(f"Không thấy quỹ {a.fund}. Chạy --list để xem mã.")
    to_csv(nav_history(row["id"].iloc[0]), f"Quỹ: {row['short_name'].iloc[0]} - {row['name'].iloc[0]} ({row['owner'].iloc[0]})")


if __name__ == "__main__":
    main()
