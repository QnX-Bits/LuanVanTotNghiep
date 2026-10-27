"""
02d_build_vcb_term_rates.py - lãi suất tiết kiệm kỳ hạn 1 và 3 tháng của Vietcombank (tại quầy, cá nhân,
lĩnh lãi cuối kỳ) từ bảng mốc điều chỉnh có trích nguồn data/raw/vcb_deposit_rate_events.csv (QC 5b).

    python scripts/02d_build_vcb_term_rates.py

- Mỗi dòng của bảng mốc = biểu lãi suất có hiệu lực từ `date` (date_basis: effective = ngày hiệu lực nêu trong
  bài; article = ngày đăng bài khi bài không nêu ngày hiệu lực; snapshot = ảnh chụp biểu tại ngày bài, không
  phải ngày đổi; inferred = suy ra từ mức "trước/sau" của bài khác, xem cột note).
- Chuỗi tháng: giá trị tháng t = lãi suất hiệu lực CUỐI tháng t (bậc thang, chỉ ffill tiến) - đúng quy ước
  03_merge_panel.load_term_rates.
- Ghi data/raw/deposit_rate_1m_3m.csv (date,rate_1m,rate_3m,data_quality). Nếu có JSON pricedancing kỳ hạn
  1/3 tháng, 02b sẽ ưu tiên chuỗi đó và chỉ dùng file này lấp tháng thiếu.
- Kiểm chứng nguồn chuỗi 12 tháng: so cột rate_12m của bảng mốc với deposit_rate_12m_2020_2026_final.csv
  (pricedancing chart btQhHe) ở các tháng giá thật -> xác định chuỗi 12 tháng là của Vietcombank.
"""
import pandas as pd

RAW = "data/raw"
EVENTS = f"{RAW}/vcb_deposit_rate_events.csv"
OUT = f"{RAW}/deposit_rate_1m_3m.csv"
DEP12 = f"{RAW}/deposit_rate_12m_2020_2026_final.csv"
START, END = "2014-06-01", "2026-07-01"
VCB_12M_START = "2014-03-01"
WEAK = {"snapshot", "inferred"}


def monthly(ev: pd.DataFrame, col: str, start: str = START) -> pd.DataFrame:
    e = ev.dropna(subset=[col]).sort_values("date")
    e = e.assign(month=e["date"].dt.to_period("M").dt.to_timestamp())
    last = e.groupby("month").last()
    idx = pd.date_range(start, END, freq="MS")
    val = last[col].reindex(idx.union(last.index)).sort_index().ffill().reindex(idx)
    basis = last["date_basis"].reindex(idx.union(last.index)).sort_index().ffill().reindex(idx)
    return pd.DataFrame({col: val, f"{col}_basis": basis}, index=idx)


def extend_12m(ev: pd.DataFrame, d: pd.DataFrame) -> None:
    """QC 1 (lớp tiền gửi): chuỗi 12T pricedancing bắt đầu 07/2020 -> bổ sung các tháng TRƯỚC điểm pricedancing
    đầu tiên bằng bảng mốc 12T của Vietcombank (cùng ngân hàng, đã đối chiếu ở trên). Không đụng vào tháng đã có
    số pricedancing; chạy lại nhiều lần cho cùng kết quả. 02b ghi lại file -> chạy lại 02d."""
    real = d[d["deposit_rate_12m"].notna() & ~d["is_interpolated"].astype(bool)
             & (~d["data_quality"].astype(str).str.startswith("vcb_news_step"))]
    first = real["date"].min()
    m = monthly(ev, "rate_12m", start=VCB_12M_START)["rate_12m"]
    m = m[m.index < first].dropna()
    if m.empty:
        return
    add = pd.DataFrame({"date": m.index, "deposit_rate_12m": m.values, "is_interpolated": False,
                        "data_quality": "vcb_news_step"})
    gap = (add["date"] >= "2015-01-01") & (add["date"] <= "2016-08-01")   # chưa tìm được mốc 12T 2015-08/2016
    add.loc[gap, "data_quality"] = "vcb_news_step_unverified"
    keep = d[(d["date"] >= first) & (~d["data_quality"].astype(str).str.startswith("vcb_news_step"))]
    out = pd.concat([add, keep], ignore_index=True).sort_values("date")
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.to_csv(DEP12, index=False)
    print(f"Chuỗi 12T: bổ sung {len(add)} tháng Vietcombank {m.index.min():%Y-%m} -> {m.index.max():%Y-%m} "
          f"(trước điểm pricedancing đầu tiên {first:%Y-%m})")


def main():
    ev = pd.read_csv(EVENTS, parse_dates=["date"])
    m1, m3 = monthly(ev, "rate_1m"), monthly(ev, "rate_3m")
    out = pd.concat([m1, m3], axis=1)
    weak = out["rate_1m_basis"].isin(WEAK) | out["rate_3m_basis"].isin(WEAK)
    out["data_quality"] = ["vcb_step_" + ("snapshot_or_inferred" if w else "dated_change") for w in weak]
    # tháng nằm trong khoảng "CHƯA XÁC MINH" ghi rõ
    unverified = [("2016-01-01", "2016-08-01")]   # lần tăng 2016 trước đợt giảm 26/9/2016: chưa tìm được
    for a, b in unverified:
        out.loc[a:b, "data_quality"] = "vcb_step_unverified_gap"
    out.index.name = "date"
    # giữ các tháng đã có số pricedancing (02b ghi data_quality = pricedancing): ưu tiên chuỗi tháng của nguồn đó
    try:
        prev = pd.read_csv(OUT, parse_dates=["date"]).set_index("date")
        pdm = prev[prev.get("data_quality", pd.Series(dtype=str)) == "pricedancing"]
        common = pdm.index.intersection(out.index)
        if len(common):
            for col in ("rate_1m", "rate_3m"):
                have = pdm.loc[common, col].notna()
                out.loc[common[have.values], col] = pdm.loc[common[have.values], col]
            out.loc[common, "data_quality"] = "pricedancing"
            diff = (prev.loc[common, ["rate_1m", "rate_3m"]] - pd.concat([m1, m3], axis=1).loc[common, ["rate_1m", "rate_3m"]]).abs()
            print(f"Giữ {len(common)} tháng pricedancing; lệch so với bảng mốc VCB: trung vị "
                  f"{diff.stack().median():.2f}, lớn nhất {diff.stack().max():.2f} điểm %")
    except (FileNotFoundError, KeyError):
        pass
    res = out[["rate_1m", "rate_3m", "data_quality"]].reset_index()
    res["date"] = res["date"].dt.strftime("%Y-%m-%d")
    res.to_csv(OUT, index=False)
    print(f"Đã ghi {OUT}: {len(res)} tháng {res['date'].iloc[0]} -> {res['date'].iloc[-1]}")
    print(res["data_quality"].value_counts().to_string())

    # kiểm chứng chuỗi 12 tháng đang dùng là của Vietcombank
    m12 = monthly(ev, "rate_12m")["rate_12m"]
    try:
        d = pd.read_csv(DEP12, parse_dates=["date"])
    except FileNotFoundError:
        return
    extend_12m(ev, d)
    d = d[d["data_quality"] == "real_monthly"].set_index("date")["deposit_rate_12m"]
    cmp = pd.DataFrame({"pricedancing": d, "vcb": m12.reindex(d.index)}).dropna()
    diff = (cmp["pricedancing"] - cmp["vcb"]).abs()
    print(f"\nĐối chiếu 12T (tháng giá thật): {len(cmp)} tháng, khớp tuyệt đối {int((diff < 1e-9).sum())}, "
          f"lệch <= 0.2 điểm {int((diff <= 0.2 + 1e-9).sum())}, lệch lớn nhất {diff.max():.2f}")
    bad = cmp[diff > 0.2 + 1e-9]
    if len(bad):
        print("Tháng lệch > 0.2 điểm:\n" + bad.to_string())


if __name__ == "__main__":
    main()
