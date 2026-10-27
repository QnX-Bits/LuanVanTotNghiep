from __future__ import annotations

import unicodedata
from datetime import date
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user, require_roles
from ..data.repository import get_active_version, get_version, load_frames, version_public
from ..domain.allocation import ADVISOR_METHOD
from ..domain.news import re_basket_returns
from ..models import NewsArticle, get_db

router = APIRouter(prefix="/api", tags=["data"])
CLASS_TO_ASSET = {"co_phieu": "VNINDEX", "bat_dong_san": "RE_BASKET", "etf": "E1VFVN30", "vang": "GOLD_SJC", "tien_gui": "DEPOSIT_12M", "trai_phieu": "VN_BOND_5Y"}
ASSETS = (
    {"key": "co_phieu", "label": {"vi": "Cổ phiếu", "en": "Stocks"}, "unit": {"vi": "điểm", "en": "points"}, "source": "HOSE / VN-Index (giá Vietcap)"},
    {"key": "bat_dong_san", "label": {"vi": "Cổ phiếu BĐS", "en": "Real-estate stocks"}, "unit": {"vi": "chỉ số (đầu chuỗi = 100)", "en": "index (start = 100)"}, "source": "HOSE / rổ 4 DN BĐS vốn hóa lớn nhất, cập nhật đầu mỗi năm (giá Vietcap)"},
    {"key": "etf", "label": {"vi": "ETF", "en": "ETF"}, "unit": {"vi": "₫/chứng chỉ", "en": "VND/unit"}, "source": "HOSE / E1VFVN30 (giá Vietcap)"},
    {"key": "vang", "label": {"vi": "Vàng SJC", "en": "SJC gold"}, "unit": {"vi": "₫/lượng", "en": "VND/tael"}, "source": "pricedancing.com / SJC"},
    {"key": "tien_gui", "label": {"vi": "Tiền gửi 12 tháng", "en": "12-month deposit"}, "unit": {"vi": "%/năm", "en": "% p.a."}, "source": "Vietcombank (pricedancing.com; báo chí trước 07/2020)"},
    {"key": "trai_phieu", "label": {"vi": "Trái phiếu Chính phủ 5 năm", "en": "5-year government bonds"}, "unit": {"vi": "% lợi suất", "en": "% yield"}, "source": "Lợi suất: Investing.com Vietnam 5-Year Bond Yield; lợi nhuận lớp: NAV quỹ trái phiếu DCBF (Fmarket)"},
)


def _class_returns(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    p["date"] = pd.to_datetime(p.date)
    return p.groupby(["date", "asset_class"])["monthly_return"].mean().unstack().sort_index()


def _level_series(panel: pd.DataFrame, key: str) -> pd.Series:
    p = panel.copy()
    p["date"] = pd.to_datetime(p.date)
    if key == "bat_dong_san":
        group = re_basket_returns(p).sort_index()
        level = 100.0
        values = []
        for idx, value in group.items():
            if pd.notna(value):
                level *= 1 + float(value)
            values.append((idx, level if pd.notna(value) else None))
        return pd.Series({idx: val for idx, val in values}, name="value", dtype="float64").sort_index()
    symbol = CLASS_TO_ASSET[key]
    if symbol == "RE_BASKET":
        return pd.Series(dtype="float64")
    g = p[p.symbol == symbol].set_index("date").sort_index()
    if g.empty:
        return pd.Series(dtype="float64")
    return g.price.astype(float)


def _return_series(panel: pd.DataFrame, key: str) -> pd.Series:
    p = panel.copy()
    p["date"] = pd.to_datetime(p.date)
    if key == "bat_dong_san":
        return re_basket_returns(p).sort_index()
    g = p[p.symbol == CLASS_TO_ASSET[key]].set_index("date").sort_index()
    if key in ("tien_gui", "trai_phieu"):
        return g.price.astype(float).diff()
    return g.monthly_return.astype(float)


def _as_of(period: pd.Timestamp) -> str:
    return period.strftime("%Y-%m")


def _asset_record(meta: dict[str, Any], panel: pd.DataFrame, provisional_month: str | None, basket: pd.DataFrame | None = None) -> dict[str, Any]:
    key = meta["key"]
    levels = _level_series(panel, key).dropna()
    if levels.empty:
        raise ValueError(f"No price series for {key}")
    latest_date = pd.Timestamp(levels.index[-1])
    latest_level = float(levels.iloc[-1])
    returns = _return_series(panel, key).dropna().sort_index()
    is_rate = key in ("tien_gui", "trai_phieu")
    latest_return = (float(returns.loc[latest_date]) if latest_date in returns.index else None) if not is_rate else None
    year_start = pd.Timestamp(year=latest_date.year, month=1, day=1)
    ytd_returns = returns[returns.index >= year_start].tolist()
    twelve_start = latest_date - pd.DateOffset(months=11)
    twelve_returns = returns[(returns.index >= twelve_start) & (returns.index <= latest_date)].tolist()
    def compound(values: list[float]) -> float | None:
        if not values:
            return None
        product = 1.0
        for value in values:
            product *= 1 + float(value)
        return product - 1
    # ETF prices are stored in thousand VND; the UI displays whole VND per unit.
    if key == "etf":
        latest_level *= 1000
        levels = levels * 1000
    prior_month_level = float(levels.iloc[-2]) if len(levels) > 1 else None
    delta_pp = latest_level - prior_month_level if is_rate and prior_month_level is not None else None
    if is_rate:
        year_reference = levels[levels.index < year_start]
        ytd_change_pp = latest_level - float(year_reference.iloc[-1]) if len(year_reference) else None
        twelve_reference = levels[levels.index <= latest_date - pd.DateOffset(months=12)]
        change_12m_pp = latest_level - float(twelve_reference.iloc[-1]) if len(twelve_reference) else None
        ytd_result = None
        twelve_result = None
    else:
        ytd_change_pp = None
        change_12m_pp = None
        ytd_result = compound(ytd_returns)
        twelve_result = compound(twelve_returns)
    series_rows = []
    # Do not interpolate missing observations; retain missing points as nulls.
    if key == "bat_dong_san":
        series_values = _level_series(panel, key)
    else:
        series_values = _level_series(panel, key)
    for period, value in series_values.tail(38).items():
        r = returns.get(period)
        series_rows.append({"month": _as_of(pd.Timestamp(period)), "value": None if pd.isna(value) else float(value), "return": None if r is None or pd.isna(r) else float(r), "is_provisional": _as_of(pd.Timestamp(period)) == provisional_month})
    prices = panel.copy()
    prices["date"] = pd.to_datetime(prices.date)
    current_rows = prices[prices.date == latest_date]
    symbol_list = ["VHM", "NVL", "KDH", "DXG"] if key == "bat_dong_san" else [CLASS_TO_ASSET[key]]
    current = current_rows[current_rows.symbol.isin(symbol_list)]
    components = []
    if key == "bat_dong_san" and basket is not None and len(basket):
        cur_ret = current.set_index("symbol")["monthly_return"] if len(current) else pd.Series(dtype="float64")
        for row in basket.itertuples():
            r = cur_ret.get(str(row.symbol))
            components.append({"symbol": str(row.symbol), "price": float(row.price) * 1000, "monthly_return": float(r) if r is not None and pd.notna(r) else None})
    elif key == "bat_dong_san":
        for _, row in current.iterrows():
            components.append({"symbol": row["symbol"], "price": float(row["price"]) * 1000, "monthly_return": float(row["monthly_return"]) if pd.notna(row["monthly_return"]) else None})
    return {
        **meta,
        "as_of": _as_of(latest_date),
        "level": latest_level,
        "monthly_return": latest_return,
        "ytd_return": ytd_result,
        "return_12m": twelve_result,
        "ytd_change_pp": ytd_change_pp,
        "change_12m_pp": change_12m_pp,
        "monthly_change_pp": delta_pp,
        "is_provisional": _as_of(latest_date) == provisional_month,
        "series": series_rows,
        "components": components,
    }


@router.get("/dashboard")
def dashboard(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    version = get_active_version(db)
    frames = load_frames(db, version.id)
    panel = frames["asset_panel_standardized.csv"]
    assets = [_asset_record(meta, panel, version.manifest.get("provisional_month")) for meta in ASSETS]
    perf = frames["performance_summary.csv"]
    balanced = perf[(perf.method == ADVISOR_METHOD) & (perf.risk_profile == "can_bang") & (perf.horizon == "trung_han")]
    if balanced.empty:
        raise HTTPException(status_code=500, detail=f"Active version is missing the balanced/medium {ADVISOR_METHOD} result")
    one = balanced.iloc[0]
    method_rows = perf[(perf.risk_profile == "can_bang") & (perf.horizon == "trung_han")].sort_values("sharpe_ratio", ascending=False)
    articles = db.execute(select(NewsArticle).where(NewsArticle.status == "published").order_by(NewsArticle.published_at.desc().nullslast(), NewsArticle.period.desc().nullslast()).limit(10)).scalars().all()
    news = [_public_article(row.article, user["locale"]) for row in articles[:5]]
    return {"version": version_public(version, user["role"]), "assets": assets, "latest_news": news, "balanced_medium": {"annualised_return": float(one.annualised_return), "deposit_annualised_return": float(one.deposit_annualised_return), "volatility": float(one.volatility), "sharpe_ratio": float(one.sharpe_ratio), "max_drawdown": float(one.max_drawdown), "n_months": int(one.n_months), "start": str(one.start), "end": str(one.end)}, "methods": [{"method": row.method, "sharpe_ratio": float(row.sharpe_ratio), "annualised_return": float(row.annualised_return), "max_drawdown": float(row.max_drawdown)} for _, row in method_rows.iterrows()], "data_confidence": {"version": version.label, "data_through": version.manifest.get("data_through"), "provisional_month": version.manifest.get("provisional_month"), "validation": version.manifest.get("validation") if user["role"] in ("admin", "reviewer") else None}}


def _public_article(article: dict, locale: str) -> dict:
    out = {key: value for key, value in article.items() if key not in ("version_id", "panel_checksum", "source_path", "log")}
    return out


@router.get("/markets")
def markets(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    version = get_active_version(db)
    panel = load_frames(db, version.id)["asset_panel_standardized.csv"]
    assets = [_asset_record(meta, panel, version.manifest.get("provisional_month")) for meta in ASSETS]
    return {"version": version_public(version, user["role"]), "as_of": assets[0]["as_of"], "provisional_month": version.manifest.get("provisional_month"), "assets": assets}


@router.get("/markets/{asset}")
def market_asset(asset: str, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    meta = next((item for item in ASSETS if item["key"] == asset), None)
    if meta is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    version = get_active_version(db)
    frames = load_frames(db, version.id)
    result = _asset_record(meta, frames["asset_panel_standardized.csv"], version.manifest.get("provisional_month"), frames.get("re_basket_current.csv"))
    alloc = frames["allocation_current.csv"]
    if asset == "bat_dong_san":
        result["weights_by_profile"] = {}
        for profile in ("than_trong", "can_bang", "tang_truong"):
            row = alloc[(alloc.method == ADVISOR_METHOD) & (alloc.risk_profile == profile) & (alloc.horizon == "trung_han")]
            if len(row):
                result["weights_by_profile"][profile] = float(row.iloc[0]["w_bat_dong_san"])
    linked = db.execute(select(NewsArticle).where(NewsArticle.status == "published").order_by(NewsArticle.period.desc().nullslast()).limit(60)).scalars().all()
    result["related_news"] = [_public_article(row.article, user["locale"]) for row in linked if asset in row.article.get("asset_tags", [])][:5]
    result["source_notes"] = [{"vi": "Lợi suất tháng được lấy trực tiếp từ asset_panel_standardized.csv. Giá vàng SJC trước 08/2022 chỉ có điểm neo (6 tháng trước 2020, 4 tháng 2020–2022); các tháng giữa được dựng lại từ giá vàng thế giới × tỷ giá × chênh lệch SJC nội suy giữa các neo (cột data_quality ghi rõ). Lớp cổ phiếu BĐS là rổ 4 doanh nghiệp vốn hóa lớn nhất, xác định đầu mỗi năm; lớp trái phiếu dùng NAV quỹ DCBF.", "en": "Monthly returns are read from asset_panel_standardized.csv. Before Aug 2022 SJC gold has anchors only (6-month before 2020, 4-month in 2020–2022); months in between are reconstructed from world gold × FX × an SJC premium interpolated between anchors (flagged in data_quality). Real-estate stocks are a basket of the four largest developers reset each January; bonds use the DCBF bond-fund NAV."}]
    return result


@router.get("/news")
def news_list(user: dict = Depends(current_user), db: Session = Depends(get_db), kind: str | None = None, month: str | None = None, tag: str | None = None, q: str | None = None, limit: int = Query(default=100, ge=1, le=200)):
    query = select(NewsArticle).order_by(NewsArticle.period.desc().nullslast(), NewsArticle.created_at.desc())
    if user["role"] != "admin":
        query = query.where(NewsArticle.status == "published")
    if kind:
        query = query.where(NewsArticle.kind == kind)
    if month:
        query = query.where(NewsArticle.period == month)
    rows = db.execute(query.limit(500)).scalars().all()
    locale = user["locale"]
    if tag:
        rows = [row for row in rows if tag in row.article.get("asset_tags", [])]
    if q:
        needle = _fold(q)
        rows = [row for row in rows if needle in _fold(" ".join([str(row.article.get("title", {}).get(locale, "")), str(row.article.get("summary", {}).get(locale, "")), " ".join(row.article.get("asset_tags", []))]))]
    return {"items": [_public_article(row.article, locale) for row in rows[:limit]], "count": len(rows)}


@router.get("/news/{slug}")
def news_detail(slug: str, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(NewsArticle, slug)
    if row is None or (row.status != "published" and user["role"] != "admin"):
        raise HTTPException(status_code=404, detail="Article not found")
    return _public_article(row.article, user["locale"])


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", str(text).lower())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


@router.get("/versions/active")
def active_version(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    return version_public(get_active_version(db), user["role"])
