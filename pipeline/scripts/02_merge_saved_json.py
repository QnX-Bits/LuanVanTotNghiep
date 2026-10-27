"""
02_merge_saved_json.py
Đọc các file JSON đã lưu thủ công (copy-paste từ trình duyệt, KHÔNG gọi
API trực tiếp - tránh hoàn toàn vấn đề bot detection), ghép 2 period lại
thành 1 chuỗi hoàn chỉnh cho từng tài sản.

CÁCH DÙNG:
1. Đặt các file JSON đã lưu vào cùng thư mục với script này, đúng tên:
   - gold_4y.json, gold_alltime.json
   - deposit_12m_4y.json, deposit_12m_alltime.json
   - (nếu có trái phiếu) bond_4y.json, bond_alltime.json
2. Chạy: python 02_merge_saved_json.py
3. Kết quả: mỗi tài sản 1 file CSV trong data/raw/, sẵn sàng cho bước
   chuẩn hóa panel (mục 6.1.1 đề cương)
"""
import json
import pandas as pd
import os

INPUT_DIR = "."  # đổi nếu file JSON để ở thư mục khác
OUTPUT_DIR = "data/raw"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Khai báo các tài sản cần ghép - thêm/bớt dòng tùy file bạn thực sự có
ASSETS = {
    "gold_sjc": ("gold_4y.json", "gold_alltime.json"),
    "deposit_12m": ("deposit_12m_4y.json", "deposit_12m_alltime.json"),
    # "bond_5y": ("bond_5y_4y.json", "bond_5y_alltime.json"),  # bỏ comment nếu có
}


def load_json_series(filepath: str, period_label: str) -> pd.DataFrame:
    full_path = os.path.join(INPUT_DIR, filepath)
    if not os.path.exists(full_path):
        print(f"  [BỎ QUA] Không tìm thấy file: {full_path}")
        return pd.DataFrame()

    with open(full_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if payload.get("status") != "ok":
        print(f"  [LỖI] File {filepath} không hợp lệ: {payload}")
        return pd.DataFrame()

    records = payload["data"]["data"]
    interval = payload["data"]["interval"]
    df = pd.DataFrame(records)
    df["t"] = pd.to_datetime(df["t"])
    df["interval_source"] = interval
    df["period_query"] = period_label
    return df


def merge_asset(name: str, file_4y: str, file_alltime: str) -> pd.DataFrame:
    print(f"\n=== {name} ===")
    df_4y = load_json_series(file_4y, "4y")
    df_all = load_json_series(file_alltime, "all-time")

    if df_4y.empty and df_all.empty:
        print(f"  -> KHÔNG có dữ liệu nào cho {name}, bỏ qua hoàn toàn")
        return pd.DataFrame()

    if df_4y.empty:
        combined = df_all
        print("  -> Chỉ có dữ liệu all-time (thô hơn), không có bản 4y")
    elif df_all.empty:
        combined = df_4y
        print("  -> Chỉ có dữ liệu 4y, không có bản all-time (lịch sử ngắn hơn)")
    else:
        cutoff = df_4y["t"].min()
        df_all_before = df_all[df_all["t"] < cutoff]
        combined = pd.concat([df_all_before, df_4y], ignore_index=True)

    combined = combined.sort_values("t").reset_index(drop=True)
    combined = combined.rename(columns={"t": "date", "c": "close_price", "a": "avg_price"})

    n_dup = combined["date"].duplicated().sum()
    if n_dup > 0:
        print(f"  [CẢNH BÁO] {n_dup} dòng trùng ngày - kiểm tra lại thủ công")

    print(f"  -> {len(combined)} điểm, {combined['date'].min().date()} đến {combined['date'].max().date()}")
    return combined


def main():
    for name, (file_4y, file_alltime) in ASSETS.items():
        df = merge_asset(name, file_4y, file_alltime)
        if not df.empty:
            out_path = f"{OUTPUT_DIR}/{name}.csv"
            df.to_csv(out_path, index=False)
            print(f"  -> Đã lưu: {out_path}")

    print("\n=== HOÀN TẤT ===")
    print("Kiểm tra thư mục data/raw/ để xem các file đã tạo.")
    print("Tiếp theo: dùng các file này làm input cho bước chuẩn hóa panel (mục 6.1.1).")


if __name__ == "__main__":
    main()
