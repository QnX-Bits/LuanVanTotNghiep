"""
collect_all.py - MỘT lệnh thu thập toàn bộ dữ liệu thô còn thiếu (đóng cờ QC 1, 2c, 4, 6). Chạy trên MÁY CỦA BẠN
(có mạng), trong thư mục PortfolioVN/pipeline, sau khi đã kích hoạt môi trường ảo:

    python scripts/collect_all.py
    python scripts/collect_all.py --fund DCBF                          # chọn quỹ trái phiếu (mặc định: quỹ lâu đời nhất)
    python scripts/collect_all.py --bond-csv "Vietnam 5-Year Bond Yield Historical Data.csv"
    python scripts/collect_all.py --skip stock,fmarket                 # bỏ bước đã làm

Các bước (bước nào lỗi thì bỏ qua, chạy tiếp, cuối cùng in tổng kết):
  stock    giá ngày cổ phiếu/ETF/VN-Index + ứng viên rổ BĐS từ 2014 (API VCI/VNDirect/TCBS) -> 00_collect_stock_data.py
  fx       tỷ giá USD/VND bình quân tháng (IMF IFS)                                -> 01d_collect_imf_usdvnd.py
  gold     JSON pricedancing (vàng SJC, lãi 12T/3T) -> file thô -> bổ sung lãi VCB  -> 02b, 02d
  fmarket  NAV quỹ trái phiếu mở                                                   -> 01c_collect_fmarket_nav.py
  bond     lợi suất TPCP 5 năm: investing.com KHÔNG tải tự động được -> tải tay CSV rồi truyền --bond-csv
  check    kiểm tra trạng thái các cờ                                              -> 00_check_raw_data.py

Cần cài: pip install requests beautifulsoup4   (KHÔNG cần vnstock)
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PD_DIR = os.path.join(ROOT, "data", "raw", "pricedancing")
PD_BASE = "https://www.pricedancing.com/api/chart/{cid}?style=line&period={period}&with_price=true"
PD_CHARTS = {"gold": "rAAvxj", "deposit_12m": "btQhHe", "deposit_3m": "VjbhHe"}
PD_PERIODS = {"4y": "4y", "alltime": "all-time"}
PD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}
ENV = dict(os.environ, PYTHONPATH=HERE, PYTHONIOENCODING="utf-8")


def run(script, *args):
    """Chạy một script của pipeline; trả True nếu thành công."""
    cmd = [sys.executable, os.path.join(HERE, script), *args]
    print(f"\n$ python scripts/{script} {' '.join(args)}", flush=True)
    return subprocess.run(cmd, cwd=ROOT, env=ENV).returncode == 0


def download_pricedancing():
    """Tải JSON pricedancing; trả (số file OK, danh sách (file, link) lỗi để lấy tay)."""
    import requests
    os.makedirs(PD_DIR, exist_ok=True)
    ok, failed = 0, []
    for name, cid in PD_CHARTS.items():
        for tag, period in PD_PERIODS.items():
            path = os.path.join(PD_DIR, f"{name}_{tag}.json")
            url = PD_BASE.format(cid=cid, period=period)
            try:
                r = requests.get(url, headers={**PD_HEADERS, "Referer": f"https://www.pricedancing.com/vi/chart-{cid}"},
                                 timeout=30)
                r.raise_for_status()
                payload = r.json()
                if payload.get("status") != "ok":
                    raise ValueError(str(payload)[:120])
                pts = payload["data"]["data"]
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
                print(f"  [OK] {os.path.relpath(path, ROOT)}: {len(pts)} điểm, {pts[0]['t'][:7]} -> {pts[-1]['t'][:7]}, "
                      f"nến {payload['data']['interval']}")
                ok += 1
            except Exception as e:
                failed.append((os.path.relpath(path, ROOT), url))
                print(f"  [LỖI] {name} {period}: {type(e).__name__}: {str(e)[:100]}")
            time.sleep(1)
    return ok, failed


def pick_fund():
    """Quỹ trái phiếu có ngày phát hành sớm nhất trên Fmarket."""
    sys.path.insert(0, HERE)
    from importlib import import_module
    funds = import_module("01c_collect_fmarket_nav").list_bond_funds()
    print(funds.to_string(index=False))
    first = funds.dropna(subset=["inception"]).iloc[0]
    print(f"  -> chọn quỹ phát hành sớm nhất: {first['short_name']} ({first['inception']:%m/%Y}). "
          f"Muốn quỹ khác: chạy lại với --fund <MÃ> --skip stock,fx,gold")
    return first["short_name"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fund", help="mã quỹ trái phiếu Fmarket (mặc định: quỹ lâu đời nhất)")
    ap.add_argument("--bond-csv", help="CSV 'Vietnam 5-Year Bond Yield Historical Data' tải từ investing.com")
    ap.add_argument("--skip", default="", help="bỏ bước: stock,fx,gold,fmarket,bond")
    a = ap.parse_args()
    skip = {s.strip() for s in a.skip.split(",") if s.strip()}
    status, manual = {}, []

    if "stock" not in skip:
        status["stock"] = run("00_collect_stock_data.py")

    if "fx" not in skip:
        status["fx"] = run("01d_collect_imf_usdvnd.py")

    if "gold" not in skip:
        print("\n== pricedancing JSON ==")
        ok, failed = download_pricedancing()
        if failed:
            manual.append("Lưu tay bằng trình duyệt (mở link -> Ctrl+S -> 'All files' -> đúng tên):\n"
                          + "\n".join(f"      {p}  <-  {u}" for p, u in failed)
                          + "\n    rồi chạy lại: python scripts/collect_all.py --skip stock,fx,fmarket")
        have_gold = os.path.exists(os.path.join(PD_DIR, "gold_alltime.json"))
        status["gold"] = have_gold and run("02b_build_raw_from_pricedancing.py") and run("02d_build_vcb_term_rates.py")

    if "fmarket" not in skip:
        try:
            fund = a.fund or pick_fund()
            status["fmarket"] = run("01c_collect_fmarket_nav.py", "--fund", fund)
        except Exception as e:
            status["fmarket"] = False
            manual.append(f"Fmarket lỗi ({type(e).__name__}: {str(e)[:80]}): làm theo hướng dẫn --from-json trong "
                          "scripts/01c_collect_fmarket_nav.py")

    if "bond" not in skip:
        if a.bond_csv:
            status["bond"] = run("02c_convert_investing_csv.py", "bond", "VN5Y", a.bond_csv)
        else:
            status["bond"] = False
            manual.append("TPCP 5 năm: investing.com -> 'Vietnam 5-Year Bond Yield Historical Data' -> chọn từ 01/01/2014 "
                          "-> Download, rồi: python scripts/collect_all.py --skip stock,fx,gold,fmarket --bond-csv \"<file>.csv\"")

    run("00_check_raw_data.py")
    print("\n=== Tổng kết ===")
    for k, v in status.items():
        print(f"  [{'OK' if v else 'CHƯA'}] {k}")
    if manual:
        print("\nCòn phải làm tay:")
        for m in manual:
            print("  - " + m)
    print("\nCờ 4 (rổ BĐS): nếu chưa có realestate_index.csv, lập data/raw/re_basket_membership.csv theo "
          "docs/data_request_qc.md.\nKhi đủ: python run.py --stage all --no-open")


if __name__ == "__main__":
    main()
