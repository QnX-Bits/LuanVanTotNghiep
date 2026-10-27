"""
03_merge_panel.py (đợt 4)
Gộp chuỗi THÁNG cho 9 mã (VNINDEX tham chiếu, E1VFVN30, 4 mã BĐS, vàng SJC,
TPCP 5 năm, tiền gửi 12T) thành 1 panel dài + feature thô cho ML.

Thay đổi so với đợt 3 (theo QC):
- QC 1: panel bắt đầu 02/2020 (trước là 07/2020) -> mẫu có cú sập COVID 03/2020.
  Mốc này là giới hạn của dữ liệu thô hiện có (TPCP từ 24/01/2020, vàng SJC từ
  01/2020); thả chuỗi dài hơn vào data/raw/ (cùng định dạng) là panel tự kéo dài.
- QC 2: vàng SJC các tháng không có giá thật được DỰNG LẠI:
      SJC_t = vàng thế giới_t (USD/oz) x 1,20565 oz/lượng x FX_t x basis_t
  basis_t = SJC/(thế giới x 1,20565 x FX) tại các điểm neo thật, nội suy log-tuyến
  tính theo thời gian GIỮA các neo (nội suy chênh lệch, không nội suy giá). Không
  có file USD/VND thì FX = 1 và basis = (VND/USD) x (1 + chênh lệch SJC). Tháng
  trước neo đầu tiên giữ basis của neo đầu (cờ reconstructed_extrapolated).
  PVN_GOLD_RECON=0 -> bỏ phần dựng lại (để chạy so sánh độ vững).
- QC 5: return tiền gửi tháng t = lãi suất cuối tháng t-1 / 12 (trước dùng lãi
  suất của chính tháng t, lệch thời điểm với carry trái phiếu).
- QC 6: trái phiếu vẫn là chuỗi tổng hợp từ lợi suất (chưa có NAV quỹ trái phiếu);
  nếu có data/raw/bond_fund_nav.csv (date,nav) thì dùng NAV làm chuỗi đầu tư được.
  Thống kê giá đứng ghi vào data_quality_report.csv; độ trơn (autocorrelation)
  được khử khi ước lượng rủi ro (09.estimate_cov, Geltner unsmoothing).
- QC 7: momentum mọi lớp tính trên CHỈ SỐ TỔNG LỢI NHUẬN tháng (trái phiếu: từ
  chuỗi return giá+carry, đúng dấu với lợi nhuận) thay cho thay đổi lợi suất.
- QC 14: thêm biến kinh tế có dấu kỳ vọng định trước (xem 06): term_spread
  (TPCP 5 năm - tiền gửi 12T), d_rate_3m (thay đổi lãi tiền gửi 3 tháng),
  gold_basis (log basis SJC, chỉ cho vàng).

Nhánh tự bật khi có dữ liệu bổ sung (docs/data_request_qc.md):
- PANEL_START tự xác định = tháng return sớm nhất mà cả 5 lớp đều có (PVN_PANEL_START để ép).
- realestate_index.csv / re_basket_membership.csv -> mã RE_BASKET (cổ phiếu BĐS point-in-time).
- deposit_rate_1m_3m.csv -> cột rate_1m, rate_3m trên dòng DEPOSIT_12M (lãi kỳ hạn thực).
- PVN_GOLD_VINTAGE=1 -> mã GOLD_SJC_RT: vàng point-in-time (tháng t chỉ dùng neo <= t).
"""
import os

import numpy as np
import pandas as pd
from importlib import import_module

common = import_module("common")

RAW_DIR = "data/raw"
OUT_DIR = "data/processed"
os.makedirs(OUT_DIR, exist_ok=True)

PANEL_END = "2026-07-01"     # 08/2026 chưa trọn tháng -> loại (đợt 3)
OZ_PER_LUONG = 1.20565
GOLD_RECON = int(os.getenv("PVN_GOLD_RECON", "1"))
MAX_DEPOSIT_BACKFILL = 6     # số tháng tối đa được lùi lãi suất về trước điểm biết đầu tiên (cờ bfill_assumption)
MAX_GOLD_EXTRAP = 2          # số tháng return vàng tối đa trước neo SJC đầu tiên (cờ reconstructed_extrapolated)
STOCK_SYMBOLS = {"VNINDEX": "co_phieu", "E1VFVN30": "etf", "VHM": "bat_dong_san",
                 "NVL": "bat_dong_san", "KDH": "bat_dong_san", "DXG": "bat_dong_san"}
GOLD_RAW = f"{RAW_DIR}/gold_sjc_2020_2026_final.csv"
DEPOSIT_RAW = f"{RAW_DIR}/deposit_rate_12m_2020_2026_final.csv"
BOND_RAW = f"{RAW_DIR}/Vietnam_5-Year_Bond_Yield_Historical_Data.csv"
STOCK_RAW = f"{RAW_DIR}/all_stock_based_raw.csv"


def month_label(idx):
    return pd.DatetimeIndex(idx).to_period("M").to_timestamp()


def monthly_close(daily: pd.DataFrame, time_col="time", value_col="close") -> pd.Series:
    s = daily.set_index(pd.to_datetime(daily[time_col]))[value_col].astype(float).sort_index().resample("ME").last()
    s.index = month_label(s.index)
    return s


def add_index_features(df: pd.DataFrame) -> pd.DataFrame:
    """Feature từ chỉ số tổng lợi nhuận THÁNG (đồng nhất cho mọi lớp)."""
    df = df.sort_values("date").copy()
    r = df["monthly_return"]
    df["tr_index"] = (1 + r.fillna(0)).cumprod()
    df["mom_1m"] = r
    df["mom_3m"] = (1 + r).rolling(3, min_periods=3).apply(np.prod, raw=True) - 1
    df["mom_6m"] = (1 + r).rolling(6, min_periods=6).apply(np.prod, raw=True) - 1
    df["vol_6m"] = r.rolling(6, min_periods=3).std() * np.sqrt(12)
    return df


# ============================================
# 1. CỔ PHIẾU / ETF / BĐS
# ============================================
def process_stock_based(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"])
    df = df[df["symbol"].isin(STOCK_SYMBOLS)]
    out = []
    for sym, sub in df.groupby("symbol"):
        close = monthly_close(sub)
        # đủ mọi tháng của panel (mã niêm yết muộn -> NaN, cờ not_listed) để panel liên tục
        full = pd.date_range(min(close.index.min(), pd.Timestamp(PANEL_START)), max(close.index.max(), pd.Timestamp(PANEL_END)), freq="MS")
        listed = full >= close.index.min()
        close = close.reindex(full)
        m = pd.DataFrame({"date": close.index, "price": close.values})
        m["monthly_return"] = m["price"].pct_change(fill_method=None)
        m["symbol"], m["asset_class"] = sym, STOCK_SYMBOLS[sym]
        m["data_quality"] = np.where(listed, "real_daily_resampled", "not_listed")
        out.append(add_index_features(m))
    return pd.concat(out, ignore_index=True)


def monthly_returns_all_symbols(path: str) -> pd.DataFrame:
    """Return tháng của MỌI mã trong file giá ngày (cột = mã)."""
    df = pd.read_csv(path)
    closes = {sym: monthly_close(sub) for sym, sub in df.groupby("symbol")}
    return pd.DataFrame(closes).sort_index().pct_change(fill_method=None)


def re_basket_current(panel_end) -> pd.DataFrame | None:
    """App: thành viên rổ cổ phiếu BĐS của năm chứa tháng cuối panel + giá đóng cửa tháng đó (nghìn đồng), để
    luồng 'thực hiện kế hoạch' mua đúng các mã nghiên cứu đang dùng (thay 4 mã cố định)."""
    if not common.RE_MEMBERSHIP_FILE.exists():
        return None
    mem = pd.read_csv(common.RE_MEMBERSHIP_FILE)
    end = pd.Timestamp(panel_end)
    year = int(end.year) if (mem["year"] == end.year).any() else int(mem["year"].max())
    syms = mem.loc[mem["year"] == year, "symbol"].tolist()
    df = pd.read_csv(STOCK_RAW)
    rows = []
    for s in syms:
        close = monthly_close(df[df["symbol"] == s])
        close = close[close.index <= end]
        rows.append({"year": year, "symbol": s, "as_of": f"{close.index.max():%Y-%m}", "price": float(close.iloc[-1]),
                     "weight_in_class": 1 / len(syms)})
    return pd.DataFrame(rows)


def process_re_basket() -> pd.DataFrame | None:
    """QC 4: cổ phiếu BĐS không còn là 4 mã chọn bằng hiểu biết năm 2026.
    - realestate_index.csv (date,close): chỉ số ngành BĐS (VD VNREAL) -> dùng trực tiếp.
    - re_basket_membership.csv (year,symbol): thành viên rổ quyết định ĐẦU mỗi năm bằng thông tin
      lúc đó (VD 4 doanh nghiệp BĐS dân dụng vốn hóa lớn nhất HOSE cuối năm trước, loại VIC);
      return tháng t = bình quân đều các thành viên của năm(t) có giá; giá ngày lấy từ
      all_stock_based_raw.csv."""
    if common.RE_INDEX_FILE.exists():
        idx = pd.read_csv(common.RE_INDEX_FILE)
        close = monthly_close(idx, "date", "close")
        r = close.pct_change(fill_method=None)
        quality = "re_index"
    elif common.RE_MEMBERSHIP_FILE.exists():
        mem = pd.read_csv(common.RE_MEMBERSHIP_FILE)
        rets = monthly_returns_all_symbols(STOCK_RAW)
        missing = sorted(set(mem["symbol"]) - set(rets.columns))
        if missing:
            raise ValueError(f"re_basket_membership.csv có mã chưa có giá trong {STOCK_RAW}: {missing}")
        years = mem.groupby("year")["symbol"].apply(list).to_dict()
        r = pd.Series({t: rets.loc[t, years[t.year]].mean() if t.year in years else np.nan for t in rets.index})
        r = r.where(r.index.year >= min(years))
        quality = "re_basket_point_in_time"
    else:
        return None
    r = r.loc[r.first_valid_index() - pd.DateOffset(months=1):]
    m = pd.DataFrame({"date": r.index, "monthly_return": r.values})
    m["price"] = 100 * (1 + m["monthly_return"].fillna(0)).cumprod()
    m["symbol"], m["asset_class"], m["data_quality"] = "RE_BASKET", "bat_dong_san_ro", quality
    return add_index_features(m)


# ============================================
# 2. TRÁI PHIẾU
# ============================================
MOD_DURATION, CONVEXITY = 4.3, 24


def load_bond_yield(path: str = BOND_RAW) -> pd.Series:
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
    y = df.set_index("Date")["Price"].astype(float).sort_index().resample("ME").last()
    y.index = month_label(y.index)
    return y


def bond_staleness(path: str) -> dict:
    df = pd.read_csv(path)
    for c in ["Price", "Open", "High", "Low"]:
        df[c] = pd.to_numeric(df[c])
    flat = (df["Open"] == df["High"]) & (df["High"] == df["Low"]) & (df["Low"] == df["Price"])
    return {"bond_days_open_eq_high_eq_low_eq_close": float(flat.mean())}


def process_bond(path: str) -> pd.DataFrame:
    yld = load_bond_yield(path)
    m = pd.DataFrame({"date": yld.index, "price": yld.values})
    dy = m["price"].diff() / 100
    carry = m["price"].shift(1) / 100 / 12                 # lợi suất cuối tháng t-1
    m["monthly_return"] = carry - MOD_DURATION * dy + 0.5 * CONVEXITY * dy ** 2
    m["data_quality"] = "synthetic_cmt_5y"
    nav_path = f"{RAW_DIR}/bond_fund_nav.csv"
    if os.path.exists(nav_path):                           # QC 6: chuỗi đầu tư được nếu có
        nav = pd.read_csv(nav_path, parse_dates=["date"]).set_index("date")["nav"].sort_index()
        nav = nav.resample("ME").last()
        nav.index = month_label(nav.index)
        r_nav = nav.pct_change().reindex(m["date"]).values
        m["monthly_return"] = np.where(~np.isnan(r_nav), r_nav, m["monthly_return"])
        m.loc[~np.isnan(r_nav), "data_quality"] = "bond_fund_nav"
    m["symbol"], m["asset_class"] = "VN_BOND_5Y", "trai_phieu"
    return add_index_features(m)


# ============================================
# 3. VÀNG SJC (QC 2: dựng lại từ vàng thế giới + basis)
# ============================================
def redate_anchors(df: pd.DataFrame, anchor_label: str, months_ahead: int) -> pd.DataFrame:
    """Nến pricedancing gắn nhãn NGÀY BẮT ĐẦU nến, giá là giá ĐÓNG CỬA cuối nến
    (bằng chứng ở đợt 2) -> dời neo về đúng tháng của giá; bỏ điểm nội suy."""
    df = df.copy()
    is_anchor = df["data_quality"] == anchor_label
    df.loc[is_anchor, "date"] = df.loc[is_anchor, "date"] + pd.DateOffset(months=months_ahead)
    df = df[~df["is_interpolated"].astype(bool)]
    first_monthly = df.loc[df["data_quality"] == "real_monthly", "date"].min()
    df = df[~(is_anchor.reindex(df.index) & (df["date"] >= first_monthly))]
    return df.sort_values("date").drop_duplicates("date", keep="last")


def load_world_gold_vnd_base() -> pd.Series:
    """vàng thế giới (USD/oz, bình quân tháng World Bank) x 1,20565 x FX (nếu có)."""
    w = pd.read_csv(f"{RAW_DIR}/world_gold_usd_monthly_wb.csv", parse_dates=["date"]).set_index("date")
    base = w["gold_usd_oz_avg"] * OZ_PER_LUONG
    fx_path = f"{RAW_DIR}/usd_vnd_monthly.csv"
    if os.path.exists(fx_path):
        fx = pd.read_csv(fx_path, parse_dates=["date"]).set_index("date")["usd_vnd"]
        base = base * fx.reindex(base.index).interpolate(limit_area="inside")
    return base


def reconstruct_sjc(real: pd.Series, base: pd.Series, idx: pd.DatetimeIndex):
    """real: giá SJC thật (NaN ở tháng thiếu) trên idx. Trả về (giá, cờ chất lượng)."""
    base = base.reindex(idx)
    log_basis = np.log(real / base)
    lb = log_basis.interpolate(method="index", limit_area="inside")
    first = log_basis.first_valid_index()
    extrap = idx < first
    lb = lb.bfill()
    price = real.copy()
    fill = real.isna() & base.notna()
    price[fill] = (base * np.exp(lb))[fill]
    quality = pd.Series("real", index=idx, dtype=object)
    quality[fill] = "reconstructed_wb_basis"
    quality[fill & extrap] = "reconstructed_extrapolated"
    return price, quality, np.exp(lb)


def validate_reconstruction(real_monthly: pd.Series, base: pd.Series) -> pd.DataFrame:
    """Kiểm chứng trên giai đoạn CÓ giá tháng thật: giữ 1/4 số tháng làm neo, dựng
    lại phần còn lại rồi so return với giá thật (4 cách chọn neo)."""
    rows = []
    rt = real_monthly.pct_change()
    for off in range(4):
        keep = real_monthly.copy()
        mask = np.ones(len(keep), bool)
        mask[off::4] = False
        keep[mask] = np.nan
        rec, _, _ = reconstruct_sjc(keep, base, real_monthly.index)
        rr = rec.pct_change()
        li = np.exp(np.log(keep).interpolate(method="index", limit_area="inside").ffill().bfill())
        rows.append({"anchor_offset": off, "n_months": int(rt.count()),
                     "corr_return_reconstructed": rr.corr(rt), "corr_return_price_interp": li.pct_change().corr(rt),
                     "vol_real": rt.std() * np.sqrt(12), "vol_reconstructed": rr.std() * np.sqrt(12),
                     "vol_price_interp": li.pct_change().std() * np.sqrt(12),
                     "price_rmse_pct_reconstructed": float(np.sqrt(np.mean((rec[mask] / real_monthly[mask] - 1) ** 2)))})
    return pd.DataFrame(rows)


def load_gold_points(path: str = GOLD_RAW) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = redate_anchors(df, "real_6month_anchor", 5)        # nến 6 tháng ("Tất cả", trước 2020)
    return redate_anchors(df, "real_4month_anchor", 3).rename(columns={"gold_sjc_price": "price"})


def gold_realtime(real: pd.Series, base: pd.Series, idx: pd.DatetimeIndex) -> pd.DataFrame:
    """QC 1-2, chế độ PVN_GOLD_VINTAGE: chuỗi vàng POINT-IN-TIME. Với mỗi tháng t chỉ dùng
    các giá SJC thật đã biết (<= t): basis nội suy giữa các neo <= t, giữ nguyên sau neo gần
    nhất. Return, momentum, vol và basis của tháng t tính trên chuỗi 'vintage t' đó."""
    base = base.reindex(idx)
    lb_all = np.log(real / base)
    rows = []
    for k, t in enumerate(idx):
        known = lb_all.iloc[: k + 1]
        if known.notna().sum() == 0:
            rows.append({"date": t})
            continue
        lb = known.interpolate(method="index", limit_area="inside").ffill().bfill()
        P = base.iloc[: k + 1] * np.exp(lb)
        r = P.pct_change(fill_method=None)
        rows.append({"date": t, "price": P.iloc[-1], "monthly_return": r.iloc[-1], "mom_1m": r.iloc[-1],
                     "mom_3m": P.iloc[-1] / P.iloc[-4] - 1 if k >= 3 else np.nan,
                     "mom_6m": P.iloc[-1] / P.iloc[-7] - 1 if k >= 6 else np.nan,
                     "vol_6m": r.iloc[-6:].std() * np.sqrt(12) if r.iloc[-6:].count() >= 3 else np.nan,
                     "gold_basis": lb.iloc[-1]})
    m = pd.DataFrame(rows)
    m["tr_index"] = (1 + m["monthly_return"].fillna(0)).cumprod()
    m["symbol"], m["asset_class"], m["data_quality"] = "GOLD_SJC_RT", "vang_rt", "realtime_vintage"
    return m


def process_gold(path: str = GOLD_RAW, gold_recon: int = GOLD_RECON, write_aux: bool = True):
    df = load_gold_points(path)
    start = pd.Timestamp(PANEL_START) - pd.DateOffset(months=7)   # đủ 6 tháng cho momentum
    idx = pd.date_range(min(start, df["date"].min()), PANEL_END, freq="MS")
    real = df.set_index("date")["price"].reindex(idx)
    raw_quality = df.set_index("date")["data_quality"].reindex(idx)
    base = load_world_gold_vnd_base()

    real_monthly = real[raw_quality == "real_monthly"]
    if write_aux:
        validate_reconstruction(real_monthly, base).to_csv(f"{OUT_DIR}/gold_reconstruction_validation.csv",
                                                           index=False, float_format="%.10g")

    price, quality, basis = reconstruct_sjc(real, base, idx)
    quality[raw_quality.notna()] = raw_quality[raw_quality.notna()]
    if not gold_recon:
        price = real
        quality = raw_quality.fillna("missing")
    m = pd.DataFrame({"date": idx, "price": price.values, "data_quality": quality.values})
    m["monthly_return"] = m["price"].pct_change(fill_method=None)
    m["gold_basis"] = np.log(basis.values)
    m["symbol"], m["asset_class"] = "GOLD_SJC", "vang"
    m = add_index_features(m)
    if common.GOLD_VINTAGE and gold_recon:
        return pd.concat([m, gold_realtime(real, base, idx)], ignore_index=True)
    return m


# ============================================
# 4. TIỀN GỬI (tiền mặt; QC 5: dùng lãi suất cuối tháng trước)
# ============================================
def load_deposit_points(path: str = DEPOSIT_RAW) -> pd.Series:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = redate_anchors(df.dropna(subset=["deposit_rate_12m"]), "real_2month_anchor", 1)
    return df.set_index("date")["deposit_rate_12m"]


def load_term_rates(idx: pd.DatetimeIndex) -> pd.DataFrame | None:
    """QC 5: lãi suất kỳ hạn 1/3 tháng thực (cùng ngân hàng/nguồn với chuỗi 12 tháng), hàm bậc
    thang theo tháng: giá trị tháng t = lãi suất hiệu lực cuối tháng t; không lùi về trước."""
    if not common.DEPOSIT_TERM_FILE.exists():
        return None
    t = pd.read_csv(common.DEPOSIT_TERM_FILE, parse_dates=["date"])
    t["date"] = month_label(t["date"])
    t = t.groupby("date")[["rate_1m", "rate_3m"]].last()
    return t.reindex(idx.union(t.index)).sort_index().ffill().reindex(idx)


def process_deposit(path: str = DEPOSIT_RAW) -> pd.DataFrame:
    rate = load_deposit_points(path)
    start = pd.Timestamp(PANEL_START) - pd.DateOffset(months=6)
    idx = pd.date_range(start, PANEL_END, freq="MS")
    full = rate.reindex(idx.union(rate.index)).sort_index()
    known = full.notna()
    ffilled = full.ffill()
    quality = np.where(known, "real", np.where(ffilled.notna(), "ffill_step", "bfill_assumption"))
    full = ffilled.bfill()
    m = pd.DataFrame({"date": full.index, "price": full.values, "data_quality": quality}).set_index("date").loc[idx]
    m = m.reset_index().rename(columns={"index": "date"})
    m["monthly_return"] = m["price"].shift(1) / 100 / 12
    m["symbol"], m["asset_class"] = "DEPOSIT_12M", "tien_gui"
    for c in ["tr_index", "mom_1m", "mom_3m", "mom_6m", "vol_6m"]:
        m[c] = np.nan                          # tiền gửi không vào ML (QC 7)
    term = load_term_rates(pd.DatetimeIndex(m["date"]))
    if term is not None:
        m["rate_1m"], m["rate_3m"] = term["rate_1m"].values, term["rate_3m"].values
    return m


# ============================================
# 4b. MỐC BẮT ĐẦU PANEL (tự xác định từ dữ liệu thô - QC 1)
# ============================================
def infer_panel_start():
    """Tháng return sớm nhất mà CẢ 5 lớp bản chính đều có dữ liệu."""
    def first_return(series):
        return series.dropna().index.min() + pd.DateOffset(months=1)
    stock = pd.read_csv(STOCK_RAW)
    by_sym = {s: monthly_close(g) for s, g in stock.groupby("symbol")}
    starts = {"etf": first_return(by_sym["E1VFVN30"])}
    if common.RE_INDEX_FILE.exists():
        starts["bat_dong_san"] = first_return(monthly_close(pd.read_csv(common.RE_INDEX_FILE), "date", "close"))
    elif common.RE_MEMBERSHIP_FILE.exists():
        mem = pd.read_csv(common.RE_MEMBERSHIP_FILE)
        y0 = int(mem["year"].min())
        firsts = [first_return(by_sym[s]) for s in mem.loc[mem["year"] == y0, "symbol"] if s in by_sym]
        starts["bat_dong_san"] = max(pd.Timestamp(f"{y0}-01-01"), min(firsts))
    else:
        starts["bat_dong_san"] = max(first_return(by_sym[s]) for s in common.RE_TICKERS)
    starts["trai_phieu"] = first_return(load_bond_yield())
    starts["vang"] = load_gold_points()["date"].min() - pd.DateOffset(months=MAX_GOLD_EXTRAP)
    starts["tien_gui"] = load_deposit_points().index.min() - pd.DateOffset(months=MAX_DEPOSIT_BACKFILL)
    return max(starts.values()), {k: f"{v:%Y-%m}" for k, v in starts.items()}


if os.getenv("PVN_PANEL_START"):
    PANEL_START, PANEL_START_DETAIL = pd.Timestamp(os.environ["PVN_PANEL_START"]), None
else:
    PANEL_START, PANEL_START_DETAIL = infer_panel_start()


# ============================================
# 5. GỘP + BIẾN KINH TẾ
# ============================================
def build_panel(gold_recon: int = GOLD_RECON, write_aux: bool = True):
    """Trả về (panel đã cắt, lịch sử đầy đủ). write_aux=False: không ghi file phụ
    (dùng khi dựng panel biến thể cho phân tích độ nhạy)."""
    stock = process_stock_based(STOCK_RAW)
    bond = process_bond(BOND_RAW)
    gold = process_gold(GOLD_RAW, gold_recon, write_aux)
    dep = process_deposit(DEPOSIT_RAW)
    re_basket = process_re_basket()
    if re_basket is not None:
        stock = pd.concat([stock, re_basket], ignore_index=True)

    rate = dep.set_index("date")["price"]
    yld = bond.set_index("date")["price"]
    macro = pd.DataFrame({"term_spread": yld - rate.reindex(yld.index),
                          "d_rate_3m": rate.diff(3)})
    panel = pd.concat([stock, bond, gold, dep], ignore_index=True)
    panel = panel.merge(macro, left_on="date", right_index=True, how="left")
    panel.loc[~panel["symbol"].isin(["GOLD_SJC", "GOLD_SJC_RT"]), "gold_basis"] = np.nan
    # lịch sử TRƯỚC panel (cổ phiếu có từ 08/2018) chỉ dùng để khởi động z-score,
    # trung bình/vol trượt ở bước 04 - không vào backtest
    hist = panel[panel["date"] <= PANEL_END].sort_values(["symbol", "date"]).reset_index(drop=True)
    panel = panel[(panel["date"] >= PANEL_START) & (panel["date"] <= PANEL_END)]
    panel["is_interpolated"] = ~panel["data_quality"].isin(
        ["real", "real_monthly", "real_daily_resampled", "synthetic_cmt_5y", "bond_fund_nav", "real_4month_anchor", "real_6month_anchor",
         "re_index", "re_basket_point_in_time"])
    cols = ["date", "symbol", "asset_class", "price", "monthly_return", "tr_index", "data_quality", "is_interpolated",
            "mom_1m", "mom_3m", "mom_6m", "vol_6m", "term_spread", "d_rate_3m", "gold_basis"]
    cols += [c for c in ("rate_1m", "rate_3m") if c in panel.columns]
    panel = panel[cols].sort_values(["asset_class", "symbol", "date"]).reset_index(drop=True)

    months = pd.date_range(PANEL_START, PANEL_END, freq="MS")
    for sym, g in panel.groupby("symbol"):
        assert list(g["date"]) == list(months), f"{sym}: tháng không liên tục / thiếu"
    return panel, hist


def quality_report(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sym, g in panel.groupby("symbol"):
        r = g["monthly_return"]
        rows.append({"symbol": sym, "first_month": g["date"].min().strftime("%Y-%m"),
                     "last_month": g["date"].max().strftime("%Y-%m"), "n_months": len(g),
                     "n_returns": int(r.count()), "share_flagged": float(g["is_interpolated"].mean()),
                     "vol_ann": float(r.std() * np.sqrt(12)), "ac1_monthly": float(r.autocorr(1)) if r.count() > 3 else np.nan,
                     "quality_counts": "; ".join(f"{k}={v}" for k, v in g["data_quality"].value_counts().items())})
    rep = pd.DataFrame(rows)
    rep["note"] = ""
    st = bond_staleness(BOND_RAW)
    rep.loc[rep.symbol == "VN_BOND_5Y", "note"] = f"tỷ lệ ngày O=H=L=C: {st['bond_days_open_eq_high_eq_low_eq_close']:.1%}"
    return rep


if __name__ == "__main__":
    print(f"PANEL_START = {PANEL_START:%Y-%m} ({'ép bằng PVN_PANEL_START' if os.getenv('PVN_PANEL_START') else 'tự xác định từ dữ liệu thô'})"
          + (f"; mốc từng lớp: {PANEL_START_DETAIL}" if PANEL_START_DETAIL else ""))
    panel, hist = build_panel()
    panel.to_csv(f"{OUT_DIR}/asset_panel.csv", index=False, float_format="%.10g")
    hist.to_csv(f"{OUT_DIR}/asset_panel_history.csv", index=False, float_format="%.10g")
    cur = re_basket_current(panel["date"].max())
    if cur is not None:
        cur.to_csv(f"{OUT_DIR}/re_basket_current.csv", index=False)
        print(f"Rổ BĐS hiện hành ({int(cur['year'].iloc[0])}): {', '.join(cur['symbol'])}")
    rep = quality_report(panel)
    rep.to_csv(f"{OUT_DIR}/data_quality_report.csv", index=False, float_format="%.10g")
    val = pd.read_csv(f"{OUT_DIR}/gold_reconstruction_validation.csv")
    print(f"Panel: {len(panel)} dòng, {panel['symbol'].nunique()} mã, "
          f"{panel['date'].min():%Y-%m} -> {panel['date'].max():%Y-%m} ({panel['date'].nunique()} tháng)")
    print(rep[["symbol", "n_returns", "share_flagged", "vol_ann", "ac1_monthly", "note"]].round(3).to_string(index=False))
    print("\nKiểm chứng dựng lại vàng (trung bình 4 cách chọn neo):")
    print(val.drop(columns="anchor_offset").mean().round(3).to_string())
