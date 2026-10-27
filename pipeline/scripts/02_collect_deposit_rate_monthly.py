"""
02_collect_deposit_rate_monthly.py
Thu thập lãi suất tiền gửi 12 tháng của Vietcombank theo TỪNG THÁNG THẬT
(không nội suy), bằng cách tìm và scrape các bài báo "Lãi suất Vietcombank
tháng X/20YY" đăng đều đặn trên các trang tài chính (vietnambiz.vn,
dnse.com.vn, cafef.vn, 24hmoney.vn...).

CÁCH HOẠT ĐỘNG:
1. Với mỗi tháng trong giai đoạn cần thu thập, dùng Google Custom Search API
   (hoặc search thủ công) để tìm URL bài viết "lãi suất vietcombank tháng
   X/20YY" -> lấy link bài mới nhất, uy tín nhất (ưu tiên vietnambiz.vn,
   cafef.vn, dnse.com.vn).
2. Fetch nội dung bài viết, dùng regex tìm số liệu lãi suất kỳ hạn 12 tháng
   (ví dụ pattern "12 tháng ... X,X%/năm" hoặc "kỳ hạn 12 tháng: X,X%").
3. Lưu kết quả vào CSV theo tháng.

LƯU Ý QUAN TRỌNG:
- Cần Google Custom Search API key + Search Engine ID (miễn phí, nhưng giới
  hạn 100 query/ngày). Với ~75 tháng cần thu thập (2020-2026), cần chạy script
  qua ít nhất 1 ngày, hoặc chia làm 2 lần chạy nếu vượt 100 tháng x 1 query/tháng.
  Đăng ký tại: https://programmablesearchengine.google.com/
  và lấy API key tại: https://console.cloud.google.com/apis/credentials
- Regex trích số liệu CẦN KIỂM TRA THỦ CÔNG một phần (ví dụ 10-20% số tháng)
  vì cách viết số liệu trong bài báo không đồng nhất 100% giữa các nguồn.
- Đây là phương án bán tự động (semi-automation), không chạy 1 lần là xong
  như vnstock -- cần review kết quả sau khi chạy.
"""
import pandas as pd
import requests
import re
import time
import os
from bs4 import BeautifulSoup  # pip install beautifulsoup4

OUTPUT_DIR = "data/raw"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==== CẦN ĐIỀN: đăng ký miễn phí tại https://programmablesearchengine.google.com/ ====
GOOGLE_API_KEY = "DIỀN_API_KEY_CỦA_BẠN"
GOOGLE_CSE_ID = "DIỀN_SEARCH_ENGINE_ID_CỦA_BẠN"
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

# Ưu tiên các nguồn uy tín, có pattern bài viết đều đặn theo tháng
PREFERRED_DOMAINS = ["vietnambiz.vn", "dnse.com.vn", "cafef.vn", "24hmoney.vn"]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Regex tìm lãi suất kỳ hạn 12 tháng - có thể cần điều chỉnh tùy cách viết
# của từng bài (vd: "12 tháng: 5,2%/năm" hoặc "kỳ hạn 12 tháng là 5,2%/năm")
RATE_12M_PATTERNS = [
    r"12\s*tháng[^0-9]{0,20}?(\d+[,.]\d+)\s*%",
    r"kỳ hạn 12 tháng[^0-9]{0,30}?(\d+[,.]\d+)\s*%",
]


def search_article(month: int, year: int) -> str | None:
    """Tìm URL bài viết lãi suất Vietcombank cho tháng/năm cụ thể."""
    query = f"lãi suất ngân hàng vietcombank tháng {month}/{year}"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": 5,
    }
    try:
        resp = requests.get(GOOGLE_SEARCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("items", [])
        # Ưu tiên domain uy tín
        for domain in PREFERRED_DOMAINS:
            for item in results:
                if domain in item.get("link", ""):
                    return item["link"]
        # Nếu không có domain ưu tiên, lấy kết quả đầu tiên
        return results[0]["link"] if results else None
    except Exception as e:
        print(f"  [LỖI SEARCH] {month}/{year}: {e}")
        return None


def extract_rate_12m(url: str) -> float | None:
    """Fetch bài viết, lấy text sạch (bỏ HTML/quảng cáo), rồi trích lãi suất 12 tháng."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # Bỏ script, style, nav, footer để giảm nhiễu khi regex
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        text = re.sub(r"\s+", " ", text)  # gộp khoảng trắng thừa

        for pattern in RATE_12M_PATTERNS:
            match = re.search(pattern, text)
            if match:
                rate_str = match.group(1).replace(",", ".")
                rate = float(rate_str)
                # Sanity check: lãi suất tiền gửi VN hợp lý trong khoảng 0-15%
                if 0 < rate < 15:
                    return rate
        return None
    except Exception as e:
        print(f"  [LỖI FETCH] {url}: {e}")
        return None


def collect_all(start_year=2020, end_year=2026):
    records = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            if year == end_year and month > 8:  # dừng ở tháng hiện tại
                break
            print(f"Đang xử lý {month}/{year}...")
            url = search_article(month, year)
            if url:
                rate = extract_rate_12m(url)
                records.append({
                    "year": year, "month": month,
                    "deposit_rate_12m": rate, "source_url": url,
                    "needs_review": rate is None,
                })
                status = f"{rate}%" if rate else "KHÔNG TRÍCH ĐƯỢC - cần xem thủ công"
                print(f"  -> {status} ({url})")
            else:
                records.append({
                    "year": year, "month": month,
                    "deposit_rate_12m": None, "source_url": None,
                    "needs_review": True,
                })
                print("  -> KHÔNG TÌM THẤY BÀI VIẾT")
            time.sleep(1.5)  # tránh rate limit

    df = pd.DataFrame(records)
    df.to_csv(f"{OUTPUT_DIR}/deposit_rate_monthly_raw.csv", index=False)
    n_missing = df["needs_review"].sum()
    print(f"\nHoàn tất: {len(df)} tháng, {n_missing} tháng cần kiểm tra thủ công")
    print(f"Đã lưu: {OUTPUT_DIR}/deposit_rate_monthly_raw.csv")
    return df


if __name__ == "__main__":
    if GOOGLE_API_KEY.startswith("DIỀN") or GOOGLE_CSE_ID.startswith("DIỀN"):
        print("CẦN ĐIỀN GOOGLE_API_KEY và GOOGLE_CSE_ID trước khi chạy.")
        print("Đăng ký miễn phí tại: https://programmablesearchengine.google.com/")
    else:
        collect_all(start_year=2020, end_year=2026)
