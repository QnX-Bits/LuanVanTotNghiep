"""
common.py - hằng số và hàm DÙNG CHUNG cho toàn pipeline (đợt 4, sau QC).

QUY ƯỚC THỜI GIAN (giữ từ đợt 1):
- Panel gắn nhãn tháng t; monthly_return(t) là return CỦA tháng t (giá cuối t /
  giá cuối t-1). Feature đo tại CUỐI tháng t.
- Quyết định tại cuối tháng t (thông tin <= t) chỉ áp cho return tháng t+1.
- Lãi tiền gửi/carry trái phiếu của tháng t dùng lãi suất CUỐI tháng t-1 (đã
  biết khi vào tháng) - đợt 4 sửa tiền gửi cho nhất quán với trái phiếu (QC 5).

CẤU TRÚC LỚP TÀI SẢN (QC 3, 9):
- Bản chính 5 lớp: cổ phiếu (thực hiện qua ETF E1VFVN30, khóa "etf"), cổ phiếu
  BĐS, vàng SJC, trái phiếu, tiền gửi. VN-Index chỉ còn là chuỗi tham chiếu
  (không đầu tư trực tiếp được, chỉ số giá không gồm cổ tức, tương quan 0,95
  với ETF).
- Tiền gửi = phần TIỀN MẶT nhận phần dư: lợi nhuận đã biết trước, không có
  phương sai, không vào ML, không cần "sàn vol".
- Bản 6 lớp gốc (VN-Index + ETF tách riêng) chạy lại làm kiểm tra độ vững.
"""
import json
import os
import pathlib

import numpy as np
import pandas as pd
from scipy import stats


ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
# settings.json: lựa chọn CỐ ĐỊNH của nghiên cứu (đi theo bản sao pipeline khi Admin chạy lại);
# biến môi trường PVN_* cùng tên vẫn ghi đè khi chạy độ nhạy.
_SETTINGS_FILE = ROOT / "settings.json"
SETTINGS = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8")) if _SETTINGS_FILE.exists() else {}


def _env(name, default, cast=float):
    v = os.getenv(name)
    if v not in (None, ""):
        return cast(v)
    key = name.removeprefix("PVN_").lower()
    return cast(SETTINGS[key]) if key in SETTINGS else default

# ---------- dữ liệu bổ sung để đóng các mục QC còn cờ (docs/data_request_qc.md) ----------
# Mỗi file có mặt trong data/raw/ thì nhánh tương ứng TỰ BẬT; không có thì giữ cách cũ.
RE_INDEX_FILE = RAW / "realestate_index.csv"           # QC 4: chỉ số ngành BĐS (date,close)
RE_MEMBERSHIP_FILE = RAW / "re_basket_membership.csv"  # QC 4: rổ point-in-time (year,symbol)
DEPOSIT_TERM_FILE = RAW / "deposit_rate_1m_3m.csv"     # QC 5: lãi kỳ hạn 1/3 tháng (date,rate_1m,rate_3m)
RE_BASKET_MODE = RE_INDEX_FILE.exists() or RE_MEMBERSHIP_FILE.exists()
# QC 1-2: vàng POINT-IN-TIME. Bật khi panel kéo dài về trước giai đoạn có giá SJC tháng thật:
# mỗi tháng t chỉ dùng các neo giá SJC <= t (basis giữ nguyên sau neo gần nhất) để ước lượng
# rủi ro và làm feature ML; lợi nhuận thực hiện (P&L) vẫn dùng chuỗi dựng lại cuối cùng.
# Nhờ vậy giai đoạn kiểm tra không còn phải chờ tới tháng có giá vàng thật.
GOLD_VINTAGE = _env("PVN_GOLD_VINTAGE", 0, int)
SOURCES_FILE = RAW / "SOURCES.md"                       # QC 5: trích dẫn nguồn từng file thô


def source_cited(file_key: str) -> bool:
    """True nếu dòng của file_key trong data/raw/SOURCES.md đã điền cột Nguồn (không còn 'ĐIỀN')."""
    if not SOURCES_FILE.exists():
        return False
    for line in SOURCES_FILE.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and file_key in cells[0]:
            return bool(cells[1]) and "ĐIỀN" not in cells[1].upper()
    return False

# ---------- lớp tài sản & universe ----------
CASH = "tien_gui"
RISKY_CLASSES = {"co_phieu", "etf", "bat_dong_san"}
CLASS_LABELS = {
    "etf": "Cổ phiếu (ETF E1VFVN30)", "co_phieu": "VN-Index", "bat_dong_san": "Cổ phiếu BĐS",
    "vang": "Vàng SJC", "trai_phieu": "Trái phiếu (NAV quỹ DCBF)", "tien_gui": "Tiền gửi (tiền mặt)",
}
RE_TICKERS = ["VHM", "NVL", "KDH", "DXG"]                # rổ cố định cũ (thiên lệch chọn mã - QC 4)
RE_SYMBOLS = ["RE_BASKET"] if RE_BASKET_MODE else RE_TICKERS
_BASE = {"bat_dong_san": RE_SYMBOLS, "vang": ["GOLD_SJC"], "trai_phieu": ["VN_BOND_5Y"], "tien_gui": ["DEPOSIT_12M"]}
UNIVERSES = {
    # bản chính (QC 3): 1 lớp cổ phiếu, thực hiện qua ETF
    "main": {"etf": ["E1VFVN30"], **_BASE},
    # bản 6 lớp như đề cương gốc - kiểm tra độ vững
    "split6": {"co_phieu": ["VNINDEX"], "etf": ["E1VFVN30"], **_BASE},
    # H3: chỉ cổ phiếu - trái phiếu (không có tiền mặt)
    "h3_2": {"etf": ["E1VFVN30"], "trai_phieu": ["VN_BOND_5Y"]},
    # H3 mở rộng (QC 17): thêm TỪNG lớp vào cổ phiếu - trái phiếu
    "h3_plus_vang": {"etf": ["E1VFVN30"], "trai_phieu": ["VN_BOND_5Y"], "vang": ["GOLD_SJC"]},
    "h3_plus_bds": {"etf": ["E1VFVN30"], "trai_phieu": ["VN_BOND_5Y"], "bat_dong_san": RE_SYMBOLS},
    "h3_plus_tien_gui": {"etf": ["E1VFVN30"], "trai_phieu": ["VN_BOND_5Y"], "tien_gui": ["DEPOSIT_12M"]},
}
ASSET_CLASSES = list(UNIVERSES["main"])                    # thứ tự lớp bản chính
OUTPUT_CLASSES = ["co_phieu", "bat_dong_san", "etf", "vang", "tien_gui", "trai_phieu"]  # schema CSV cho app
GOLD_EST_SYMBOL = "GOLD_SJC_RT" if GOLD_VINTAGE else "GOLD_SJC"   # chuỗi vàng dùng để ƯỚC LƯỢNG / ML


def estimation_universe(name):
    """Universe dùng cho ước lượng & ML: như UNIVERSES nhưng vàng = chuỗi point-in-time khi bật."""
    return {c: ([GOLD_EST_SYMBOL] if c == "vang" else syms) for c, syms in UNIVERSES[name].items()}


ML_SYMBOLS = ["E1VFVN30", *RE_SYMBOLS, GOLD_EST_SYMBOL, "VN_BOND_5Y"]   # tiền gửi bị loại khỏi ML (QC 7)

PANEL_PATH = "data/processed/asset_panel_standardized.csv"
FORECAST_PATH = "data/processed/forecasts_oos.csv"

# ---------- khẩu vị rủi ro (ràng buộc CỨNG) & khung thời gian ----------
RISK_BANDS = {"than_trong": (0.10, 0.30), "can_bang": (0.40, 0.60), "tang_truong": (0.70, 0.90)}
# vol mục tiêu năm hóa dùng để co giãn RP/HRP về từng khẩu vị (tiền mặt nhận phần dư)
VOL_TARGETS = {"than_trong": 0.05, "can_bang": 0.10, "tang_truong": 0.16}
# QC 10: khung thời gian chỉ quyết định tần suất tái cân bằng và kỳ hạn/thanh khoản
# của phần tiền mặt; cách ước lượng dùng chung cho mọi khung.
HORIZONS = {"ngan_han": {"rebalance": 1}, "trung_han": {"rebalance": 3}, "dai_han": {"rebalance": 12}}

# ---------- tham số ước lượng / tối ưu (đọc env để chạy độ nhạy) ----------
DELTA = _env("PVN_DELTA", 2.5)                    # QC 12: δ cố định, độ nhạy 1,5 / 4
TAU = 0.05
EWMA_HALFLIFE = _env("PVN_EWMA_HALFLIFE", 18.0)   # QC 10: EWMA half-life (tháng)
ROLLING_WINDOW = _env("PVN_ROLLING_WINDOW", 0, int)  # >0: thay EWMA bằng cửa sổ trượt (độ nhạy)
MIN_HISTORY = 24                                   # số tháng tối thiểu để một lớp được ước lượng/đầu tư
MAX_WEIGHT = 0.5                                   # trần 1 lớp phi tiền mặt (khi universe >= 4 lớp phi tiền mặt)
GOLD_RECON = _env("PVN_GOLD_RECON", 1, int)       # 0: không dùng giá vàng dựng lại (độ vững QC 2)

# QC 18: phí theo lớp (tỷ lệ trên giá trị giao dịch). PVN_TRANSACTION_COST -> phí đồng nhất.
CLASS_COSTS = {"co_phieu": 0.002, "etf": 0.002, "bat_dong_san": 0.002, "vang": 0.010,
               "tien_gui": 0.003, "trai_phieu": 0.003}
_uniform = os.getenv("PVN_TRANSACTION_COST")
if _uniform not in (None, ""):
    CLASS_COSTS = {k: float(_uniform) for k in CLASS_COSTS}

# QC 5: tái cân bằng hàng tháng/quý không hưởng được lãi kỳ hạn 12T nếu không chịu
# phạt rút trước hạn -> phần tiền mặt hưởng lãi kỳ hạn khớp tần suất tái cân bằng,
# xấp xỉ = lãi 12T - chênh lệch kỳ hạn (năm hóa). GIẢ ĐỊNH (nhóm NHTM lớn
# 2021-2026: 12T cao hơn 1T khoảng 2,4-3,0 điểm %, hơn 3T khoảng 2,0-2,7 điểm %);
# Có data/raw/deposit_rate_1m_3m.csv thì engine dùng LÃI SUẤT THỰC kỳ hạn 1/3 tháng thay
# cho giả định này (tháng nào thiếu mới dùng lại giả định). PVN_CASH_HAIRCUT=0 -> tắt.
CASH_TERM_SPREAD = {1: 0.025, 3: 0.022, 12: 0.0}
TERM_RATE_COLUMN = {1: "rate_1m", 3: "rate_3m"}
if _env("PVN_CASH_HAIRCUT", 1, int) == 0:
    CASH_TERM_SPREAD = {k: 0.0 for k in CASH_TERM_SPREAD}
# QC 5: độ nhạy lãi suất tiền gửi (chuỗi gốc ~ nhóm Big4). Cộng thêm (điểm %/năm)
# cho CẢ rf lẫn lợi nhuận tiền mặt, xấp xỉ lãi suất bình quân các NHTM.
RF_SHIFT = _env("PVN_RF_SHIFT", 0.0)


# Lớp KHÔNG nhận view ML trong BL / tín hiệu ML trong MLP_MVO: tiền gửi (lợi nhuận đã
# biết trước) và trái phiếu - chuỗi lợi suất tổng hợp bị đứng giá (autocorrelation tháng
# ~0,34), dự báo được nhưng KHÔNG giao dịch được; nhất quán với việc khử độ trơn khi ước
# lượng rủi ro. PVN_BOND_VIEWS=1 -> cho phép view trái phiếu (phân tích độ nhạy).
NO_VIEW_CLASSES = {"tien_gui"} | (set() if _env("PVN_BOND_VIEWS", 0, int) else {"trai_phieu"})


# ---------- tiện ích thời gian ----------
def forward_returns(returns_wide: pd.DataFrame) -> pd.DataFrame:
    """fwd.loc[t] = return tháng t+1. Index phải là chuỗi tháng liên tục."""
    idx = pd.DatetimeIndex(returns_wide.index)
    assert all(idx[i + 1] == idx[i] + pd.DateOffset(months=1) for i in range(len(idx) - 1)), \
        "Index tháng không liên tục - shift(-1) sẽ sai"
    return returns_wide.shift(-1)


def next_month(d):
    return pd.Timestamp(d) + pd.DateOffset(months=1)


# ---------- lãi suất phi rủi ro ----------
def load_rf(panel_path: str = PANEL_PATH) -> pd.Series:
    """rf theo THÁNG PHÁT SINH return = lãi tiền gửi 12T cuối tháng trước / 12
    (+ RF_SHIFT). Dùng cho Sharpe vượt trội."""
    p = pd.read_csv(panel_path, parse_dates=["date"])
    rf = p[p["symbol"] == "DEPOSIT_12M"].set_index("date")["monthly_return"].sort_index()
    return (rf + RF_SHIFT / 12).rename("rf")


def excess(returns, rf: pd.Series) -> pd.Series:
    r = pd.Series(returns)
    out = r - rf.reindex(pd.DatetimeIndex(r.index)).values
    if out.isna().any():
        raise ValueError("Thiếu lãi suất phi rủi ro cho một số tháng")
    return out


def sharpe(returns, rf: pd.Series = None) -> float:
    """Sharpe năm hóa (ddof=1); có rf -> trên return vượt trội (mục 6.2)."""
    r = pd.Series(returns)
    if rf is not None:
        r = excess(r, rf)
    sd = r.std(ddof=1)
    return float(r.mean() / sd * np.sqrt(12)) if sd > 0 else np.nan


def max_drawdown(returns) -> float:
    """QC 22: tính cả điểm vốn ban đầu 1,0 (tháng đầu âm cũng là drawdown)."""
    r = np.asarray(returns, float)
    wealth = np.concatenate([[1.0], np.cumprod(1 + r)])
    peak = np.maximum.accumulate(wealth)
    return float((wealth / peak - 1).min())


def annualised_return(returns) -> float:
    r = np.asarray(returns, float)
    return float(np.prod(1 + r) ** (12 / len(r)) - 1) if len(r) else np.nan


def jobson_korkie_memmel(returns_a, returns_b):
    """Jobson-Korkie (1981) hiệu chỉnh Memmel (2003) - giả định iid chuẩn; chỉ để
    đối chiếu với đề cương, kiểm định chính là Ledoit-Wolf (2008) ở bước 12."""
    a, b = np.asarray(returns_a, float), np.asarray(returns_b, float)
    n = len(a)
    mean_a, mean_b = a.mean(), b.mean()
    var_a, var_b = a.var(ddof=1), b.var(ddof=1)
    sd_a, sd_b = np.sqrt(var_a), np.sqrt(var_b)
    cov_ab = np.cov(a, b, ddof=1)[0, 1]
    theta = (1 / n) * (
        2 * var_a * var_b - 2 * sd_a * sd_b * cov_ab
        + 0.5 * mean_a ** 2 * var_b + 0.5 * mean_b ** 2 * var_a
        - (mean_a * mean_b / (sd_a * sd_b)) * cov_ab ** 2
    )
    if theta <= 0 or np.isnan(theta):
        return np.nan, np.nan
    z = (sd_b * mean_a - sd_a * mean_b) / np.sqrt(theta)
    return z, 2 * (1 - stats.norm.cdf(abs(z)))


def to_output_weights(weights: dict) -> dict:
    """Map tỷ trọng theo lớp nghiên cứu -> 6 cột w_* cố định của app (lớp không có = 0)."""
    return {f"w_{c}": float(weights.get(c, 0.0)) for c in OUTPUT_CLASSES}


def write_csv(df: pd.DataFrame, path: str, **kw):
    """Ghi CSV với định dạng số cố định -> checksum ổn định giữa các lần chạy (QC 19)."""
    df.to_csv(path, float_format="%.10g", **kw)
