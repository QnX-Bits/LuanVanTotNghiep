"""
02b_build_raw_from_pricedancing.py - dựng lại các file thô vàng SJC / lãi tiền gửi từ JSON đã lưu
của pricedancing.com (cách lấy JSON: xem 01_collect_gold_and_deposit.py, mục PHƯƠNG ÁN DỰ PHÒNG -
DevTools -> request /api/chart/{id}?period=... -> copy Response).

Đặt các file JSON vào data/raw/pricedancing/ (tên dưới đây; thiếu file nào bỏ qua file đó):
    gold_4y.json, gold_alltime.json             chart rAAvxj  (vàng SJC)
    deposit_12m_4y.json, deposit_12m_alltime.json  chart btQhHe (tiền gửi 12 tháng)
    deposit_3m_4y.json, deposit_3m_alltime.json    chart VjbhHe (tiền gửi 3 tháng)
    deposit_1m_4y.json, deposit_1m_alltime.json    tiền gửi 1 tháng (tìm chart id trong DevTools; nếu
                                                    trang không có kỳ hạn 1 tháng thì bỏ qua)
rồi chạy:  python scripts/02b_build_raw_from_pricedancing.py

Đầu ra (ghi đè, giữ đúng tên file pipeline đang đọc):
- gold_sjc_2020_2026_final.csv    (tên cũ, nội dung = TOÀN BỘ lịch sử, từ 2009) - QC 1, 2
- deposit_rate_12m_2020_2026_final.csv (toàn bộ lịch sử) - QC 1
- deposit_rate_1m_3m.csv          (date,rate_1m,rate_3m) - QC 5
Quy ước: điểm nến gắn nhãn NGÀY BẮT ĐẦU nến, giá trị là giá ĐÓNG CỬA cuối nến. Hai file đầu giữ
nhãn gốc + cờ real_4month_anchor / real_2month_anchor / real_monthly (03 tự dời về đúng tháng);
file lãi kỳ hạn được dời ngay ở đây về tháng cuối nến.
"""
import json
import os

import pandas as pd

SRC = "data/raw/pricedancing"
RAW = "data/raw"
QUALITY = {"1M": "real_monthly", "2M": "real_2month_anchor", "4M": "real_4month_anchor", "6M": "real_6month_anchor"}
MONTHS = {"1M": 1, "2M": 2, "4M": 4, "6M": 6}


def load(name):
    path = os.path.join(SRC, name)
    if not os.path.exists(path):
        return pd.DataFrame()
    payload = json.load(open(path, encoding="utf-8"))
    if payload.get("status") != "ok":
        raise ValueError(f"{name}: JSON không hợp lệ ({str(payload)[:120]})")
    df = pd.DataFrame(payload["data"]["data"])
    df["date"] = pd.to_datetime(df["t"]).dt.to_period("M").dt.to_timestamp()
    df["interval"] = payload["data"]["interval"]
    return df[["date", "c", "interval"]]


def merged(prefix):
    f4, fa = load(f"{prefix}_4y.json"), load(f"{prefix}_alltime.json")
    if f4.empty and fa.empty:
        return pd.DataFrame()
    if not f4.empty and not fa.empty:
        fa = fa[fa["date"] < f4["date"].min()]
    df = pd.concat([fa, f4], ignore_index=True).sort_values("date").drop_duplicates("date", keep="last")
    unknown = set(df["interval"]) - set(QUALITY)
    if unknown:
        raise ValueError(f"{prefix}: interval lạ {unknown} - cần bổ sung vào QUALITY/MONTHS")
    return df


def main():
    os.makedirs(RAW, exist_ok=True)
    g = merged("gold")
    if not g.empty:
        out = pd.DataFrame({"date": g["date"], "gold_sjc_price": g["c"],
                            "is_interpolated": False, "data_quality": g["interval"].map(QUALITY)})
        gpath = f"{RAW}/gold_sjc_2020_2026_final.csv"
        if os.path.exists(gpath):
            # giữ điểm cũ (nến mịn hơn, VD 4 tháng 2020-2022 và giá tháng 08-09/2022); JSON chỉ thêm phần trước điểm
            # cũ đầu tiên (pricedancing nay trả nến 6 tháng cho "Tất cả") và các tháng mới hơn điểm cũ cuối cùng
            old = pd.read_csv(gpath, parse_dates=["date"])
            old = old[~old["is_interpolated"].astype(bool)]
            first, last = old["date"].min(), old["date"].max()
            span = out["data_quality"].map({v: MONTHS[k] for k, v in QUALITY.items()})
            end_month = [d + pd.DateOffset(months=int(m) - 1) for d, m in zip(out["date"], span)]
            before = out[pd.Series(end_month, index=out.index) < first]
            after = out[(out["date"] > last) & (out["data_quality"] == "real_monthly")]
            same = out[(out["date"] >= first) & (out["date"] <= last) & (out["data_quality"] == "real_monthly")]
            old = old.set_index("date")
            for d, row in same.set_index("date").iterrows():        # cập nhật tháng cuối còn dở
                if d in old.index and old.loc[d, "data_quality"] == "real_monthly":
                    old.loc[d, "gold_sjc_price"] = row["gold_sjc_price"]
            out = pd.concat([before, old.reset_index(), after], ignore_index=True).sort_values("date")
            print(f"Vàng SJC: thêm {len(before)} điểm trước {first:%Y-%m}, {len(after)} tháng sau {last:%Y-%m}")
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
        out.to_csv(gpath, index=False)
        print(f"Vàng SJC: {len(out)} điểm, {out['date'].min()} -> {out['date'].max()}")
    d = merged("deposit_12m")
    if not d.empty:
        out = pd.DataFrame({"date": d["date"].dt.strftime("%Y-%m-%d"), "deposit_rate_12m": d["c"],
                            "is_interpolated": False, "data_quality": d["interval"].map(QUALITY)})
        out.to_csv(f"{RAW}/deposit_rate_12m_2020_2026_final.csv", index=False)
        print(f"Tiền gửi 12T: {len(out)} điểm, {out['date'].min()} -> {out['date'].max()}")
    terms = {}
    for col, prefix in (("rate_1m", "deposit_1m"), ("rate_3m", "deposit_3m")):
        t = merged(prefix)
        if t.empty:
            continue
        end = [dt + pd.DateOffset(months=MONTHS[iv] - 1) for dt, iv in zip(t["date"], t["interval"])]
        terms[col] = pd.Series(t["c"].values, index=pd.DatetimeIndex(end)).groupby(level=0).last()
        print(f"{col}: {len(terms[col])} điểm, {min(end):%Y-%m} -> {max(end):%Y-%m}")
    if terms:
        out = pd.DataFrame(terms).sort_index()
        for col in ("rate_1m", "rate_3m"):
            if col not in out:
                out[col] = float("nan")
        out["data_quality"] = "pricedancing"
        prev_path = f"{RAW}/deposit_rate_1m_3m.csv"
        if os.path.exists(prev_path):            # file Vietcombank từ 02d: giữ lại, chỉ thay tháng pricedancing có
            prev = pd.read_csv(prev_path, parse_dates=["date"]).set_index("date")
            if "data_quality" not in prev:
                prev["data_quality"] = "previous_file"
            idx = prev.index.union(out.index)
            merged_t = prev.reindex(idx)
            for col in ("rate_1m", "rate_3m"):
                have = out[col].reindex(idx).notna()
                merged_t.loc[have, col] = out[col].reindex(idx)[have]
                merged_t.loc[have, "data_quality"] = "pricedancing"
            out = merged_t
        out.index.name = "date"
        out[["rate_1m", "rate_3m", "data_quality"]].reset_index() \
            .assign(date=lambda x: x["date"].dt.strftime("%Y-%m-%d")).to_csv(prev_path, index=False)
        print(f"Đã ghi {prev_path}")
    print("Chạy tiếp: python scripts/02d_build_vcb_term_rates.py  (bổ sung lại lãi 12T Vietcombank trước điểm pricedancing đầu tiên)\n"
          "          python scripts/00_check_raw_data.py")


if __name__ == "__main__":
    main()
