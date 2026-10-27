"""
01_collect_gold_and_deposit.py
Thu thập giá vàng SJC (17 năm, 2009-2026) và lãi suất tiền gửi 5 kỳ hạn
từ pricedancing.com - đã XÁC MINH có dữ liệu thật qua DevTools (21/08/2026).

CHIẾN LƯỢC GHÉP DỮ LIỆU (xem giải thích chi tiết trong chat):
- period=4y  -> độ phân giải THÁNG (interval="1M"), cho 4 năm gần nhất
                (2022-08 -> hiện tại) - dùng cho giai đoạn out-of-sample chính.
- period=all-time -> độ phân giải 4 THÁNG/điểm (interval="4M"), cho toàn bộ
                lịch sử từ 2009 -> hiện tại - dùng để nối lịch sử xa hơn.
Script gọi cả 2, ưu tiên dùng "4y" (mịn hơn) khi trùng giai đoạn, chỉ lấy
"all-time" cho phần TRƯỚC khi "4y" bắt đầu.

CÁC CHART ID ĐÃ XÁC NHẬN (từ DevTools của bạn ngày 21/08/2026):
- Vàng SJC:          rAAvxj
- Tiền gửi 3 tháng:   VjbhHe
- Tiền gửi 9 tháng:   Zp9hHe
- Tiền gửi 12 tháng:  btQhHe
- Tiền gửi 24 tháng:  dwhiHe
- Tiền gửi 36 tháng:  fzyiHe
(Tiền gửi 6 tháng: URL bạn gửi trước đó là app.js, không phải API chart -
 cần vào lại DevTools tìm đúng request cho kỳ hạn 6 tháng nếu cần dùng)

LƯU Ý QUAN TRỌNG VỀ BOT DETECTION:
- pricedancing.com có cơ chế chặn bot (đã xác nhận qua web_fetch bị chặn).
- Script dưới đây THỬ vượt qua bằng cách giả lập header trình duyệt thật.
- Sandbox của Claude không test được vì domain bị chặn ở tầng mạng riêng
  (khác với bot detection) - CẦN CHẠY TRÊN MÁY LOCAL để biết có work không.
- NẾU SCRIPT VẪN BỊ CHẶN (403/lỗi khác sau khi chạy local), dùng phương án
  dự phòng: copy tay JSON response qua DevTools (đã làm thành công 2 lần
  trước đó) - xem hướng dẫn PHƯƠNG_ÁN_DỰ_PHÒNG bên dưới.
"""
import pandas as pd
import requests
import time
import os

OUTPUT_DIR = "data/raw"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://www.pricedancing.com/api/chart/{chart_id}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Referer": "https://www.pricedancing.com/vi/SJC-SJC.1L-VND-chart-rAAvxj",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

# Danh sách chuỗi cần lấy: (chart_id, tên_để_lưu_file)
SERIES = {
    "rAAvxj": "gold_sjc",
    "VjbhHe": "deposit_3m",
    "Zp9hHe": "deposit_9m",
    "btQhHe": "deposit_12m",
    "dwhiHe": "deposit_24m",
    "fzyiHe": "deposit_36m",
}


def fetch_period(chart_id: str, period: str) -> pd.DataFrame:
    """Gọi API cho 1 chart_id với 1 period cụ thể ('4y' hoặc 'all-time')."""
    url = BASE_URL.format(chart_id=chart_id)
    params = {"style": "line", "period": period, "with_price": "true"}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("status") != "ok":
        raise ValueError(f"API lỗi cho {chart_id} ({period}): {payload}")

    records = payload["data"]["data"]
    interval = payload["data"]["interval"]
    df = pd.DataFrame(records)
    df["t"] = pd.to_datetime(df["t"])
    df["interval_source"] = interval
    df["period_query"] = period
    return df


def fetch_series_combined(chart_id: str) -> pd.DataFrame:
    """
    Gọi cả 2 period, ghép lại: ưu tiên dữ liệu 'a4y' (mịn hơn, gần đây),
    chỉ lấy 'all-time' cho phần trước khi '4y' bắt đầu.
    """
    df_4y = fetch_period(chart_id, "4y")
    time.sleep(1)
    df_all = fetch_period(chart_id, "all-time")
    time.sleep(1)

    cutoff = df_4y["t"].min()
    df_all_before_cutoff = df_all[df_all["t"] < cutoff]

    combined = pd.concat([df_all_before_cutoff, df_4y], ignore_index=True)
    combined = combined.sort_values("t").reset_index(drop=True)
    return combined


def main():
    all_results = {}
    for chart_id, name in SERIES.items():
        print(f"\n=== Đang lấy {name} ({chart_id}) ===")
        try:
            df = fetch_series_combined(chart_id)
            out_path = f"{OUTPUT_DIR}/{name}.csv"
            df.to_csv(out_path, index=False)
            print(f"  -> {len(df)} điểm, từ {df['t'].min().date()} đến {df['t'].max().date()}")
            print(f"  -> Đã lưu {out_path}")
            all_results[name] = df
        except Exception as e:
            print(f"  -> LỖI: {e}")
            print(f"  -> Nếu đây là lỗi 403/bot detection, dùng phương án dự phòng bên dưới.")
        time.sleep(2)

    print("\n=== TÓM TẮT ===")
    for name, df in all_results.items():
        print(f"{name}: {len(df)} điểm ({df['t'].min().date()} -> {df['t'].max().date()})")


if __name__ == "__main__":
    main()


"""
============================================
PHƯƠNG ÁN DỰ PHÒNG: copy tay qua DevTools
============================================
Nếu script trên bị chặn (403 hoặc lỗi bot detection) khi chạy local, làm
thủ công theo quy trình ĐÃ THÀNH CÔNG 2 LẦN trước đó:

Với mỗi chart_id trong SERIES (6 cái ở trên):
1. Mở https://www.pricedancing.com/vi/SJC-SJC.1L-VND-chart-{chart_id}
   (thay {chart_id} tương ứng - với tiền gửi có thể cần tìm lại URL trang
   đúng, không nhất thiết giống định dạng URL vàng)
2. Mở DevTools -> Network -> bấm nút "4N" trên biểu đồ -> tìm request
   /api/chart/{chart_id}?...period=4y... -> tab Response -> copy toàn bộ
3. Lặp lại nhưng bấm "Tất Cả" thay vì "4N" -> lấy request period=all-time
4. Lưu 2 file JSON (vd gold_sjc_4y.json, gold_sjc_alltime.json)
5. Dùng đoạn code dưới đây để đọc file JSON đã lưu và merge, thay vì gọi
   API trực tiếp:

    import json
    with open('gold_sjc_4y.json') as f:
        data_4y = json.load(f)['data']['data']
    with open('gold_sjc_alltime.json') as f:
        data_all = json.load(f)['data']['data']
    # rồi áp dụng logic merge tương tự hàm fetch_series_combined() ở trên,
    # chỉ khác nguồn là đọc file thay vì gọi requests.get()

Đây là quy trình chậm hơn (6 chuỗi x 2 request = 12 lần copy tay) nhưng
CHẮC CHẮN hoạt động vì không phụ thuộc việc vượt bot detection.
"""
