from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd

SOURCE_LINE = "Nguồn số liệu: giá cổ phiếu, ETF và VN-Index (Vietcap), giá vàng SJC và lãi suất tiền gửi Vietcombank (pricedancing.com và biểu lãi suất công bố trên báo chí), NAV quỹ trái phiếu DCBF (Fmarket), lợi suất TPCP 5 năm (Investing.com)."
SOURCE_LINE_EN = "Source: stock, ETF and VN-Index prices (Vietcap), SJC gold and Vietcombank deposit rates (pricedancing.com and published rate sheets), DCBF bond-fund NAV (Fmarket), 5-year government bond yield (Investing.com)."
ASSET_ORDER = ("co_phieu", "bat_dong_san", "etf", "vang", "tien_gui", "trai_phieu")
ASSET_NAMES = {
    "co_phieu": {"vi": "Cổ phiếu", "en": "Stocks"},
    "bat_dong_san": {"vi": "Cổ phiếu BĐS", "en": "Real-estate stocks"},
    "etf": {"vi": "ETF", "en": "ETF"},
    "vang": {"vi": "Vàng SJC", "en": "SJC gold"},
    "tien_gui": {"vi": "Tiền gửi 12 tháng", "en": "12-month deposits"},
    "trai_phieu": {"vi": "Trái phiếu Chính phủ 5 năm", "en": "5-year government bonds"},
}


def slugify(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text)
    plain = "".join(char for char in raw if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:180]


def _fmt_pct(value: float, locale: str = "vi", signed: bool = False) -> str:
    text = f"{abs(value) * 100:.2f}" if locale == "vi" else f"{abs(value) * 100:.2f}"
    if locale == "vi":
        text = text.replace(".", ",")
    sign = ("+" if value > 0 else "−" if value < 0 else "") if signed else ("−" if value < 0 else "")
    return f"{sign}{text}%"


def _fmt_number(value: float, locale: str = "vi", decimals: int = 2) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".") if locale == "vi" else text


def _fmt_vnd(value: float, locale: str = "vi") -> str:
    n = int(round(value))
    return f"{n:,}".replace(",", ".") if locale == "vi" else f"{n:,}"


def _period(date: pd.Timestamp) -> str:
    return date.strftime("%Y-%m")


def _date_label(date: pd.Timestamp, locale: str) -> str:
    return date.strftime("%m/%Y")


def _fact(series: str, month: pd.Timestamp, raw: float | None, displayed: str, asset_class: str) -> dict[str, Any]:
    return {"series": series, "month": _period(month), "raw_value": raw, "display_value": displayed, "asset_class": asset_class}


def _date_panel(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    p["date"] = pd.to_datetime(p["date"])
    return p.sort_values(["date", "symbol"])


def _series_by_symbol(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    p = _date_panel(panel)
    return {str(symbol): group.set_index("date").sort_index() for symbol, group in p.groupby("symbol")}


LEGACY_RE = ["VHM", "NVL", "KDH", "DXG"]


def re_basket_returns(p: pd.DataFrame) -> pd.Series:
    """Lớp cổ phiếu BĐS: chuỗi RE_BASKET (rổ point-in-time của nghiên cứu) nếu có, nếu không là bình quân 4 mã cũ."""
    if (p.symbol == "RE_BASKET").any():
        return p[p.symbol == "RE_BASKET"].set_index("date")["monthly_return"].astype(float).sort_index()
    return p[p.symbol.isin(LEGACY_RE)].groupby("date")["monthly_return"].mean()


def _return_series(panel: pd.DataFrame) -> dict[str, pd.Series]:
    p = _date_panel(panel)
    out: dict[str, pd.Series] = {}
    out["co_phieu"] = p[p.symbol == "VNINDEX"].set_index("date")["monthly_return"].astype(float)
    out["bat_dong_san"] = re_basket_returns(p)
    out["etf"] = p[p.symbol == "E1VFVN30"].set_index("date")["monthly_return"].astype(float)
    out["vang"] = p[p.symbol == "GOLD_SJC"].set_index("date")["monthly_return"].astype(float)
    # Rates are interpreted as percentage-point changes, not monthly return decimals.
    for key, symbol in (("tien_gui", "DEPOSIT_12M"), ("trai_phieu", "VN_BOND_5Y")):
        g = p[p.symbol == symbol].set_index("date").sort_index()
        out[key] = g["price"].astype(float).diff()
    return {key: series.sort_index() for key, series in out.items()}


def generate_auto_articles(panel: pd.DataFrame, version_label: str, provisional_month: str | None = None) -> list[dict[str, Any]]:
    p = _date_panel(panel)
    symbols = _series_by_symbol(p)
    returns = _return_series(p)
    months = sorted(pd.to_datetime(p.date.unique()))
    if not months:
        return []
    recent = months[-36:]
    articles: list[dict[str, Any]] = []

    for month in recent:
        facts: list[dict[str, Any]] = []
        return_movers = []
        for key in ("co_phieu", "bat_dong_san", "etf", "vang"):
            series = returns[key]
            value = series.get(month)
            if pd.notna(value):
                return_movers.append((abs(float(value)), key, float(value)))
        if return_movers:
            _, top_class, top_value = max(return_movers, key=lambda row: (row[0], -ASSET_ORDER.index(row[1])))
            sign_word = ("tăng" if top_value >= 0 else "giảm")
            title_vi = f"Thị trường tháng {month:%m/%Y}: {ASSET_NAMES[top_class]['vi']} {sign_word} {_fmt_pct(top_value, 'vi')}"
            title_en = f"Markets in {month:%m/%Y}: {ASSET_NAMES[top_class]['en']} {'rose' if top_value >= 0 else 'fell'} {_fmt_pct(top_value, 'en')}"
        else:
            title_vi = f"Thị trường tháng {month:%m/%Y}: cập nhật dữ liệu tháng"
            title_en = f"Markets in {month:%m/%Y}: monthly data update"

        v = symbols.get("VNINDEX")
        vn_level = float(v.loc[month, "price"]) if v is not None and month in v.index and pd.notna(v.loc[month, "price"]) else None
        vn_change = returns["co_phieu"].get(month)
        facts.append(_fact("VNINDEX", month, vn_level, f"{_fmt_number(vn_level, 'vi')} điểm" if vn_level is not None else "—", "co_phieu"))
        if pd.notna(vn_change):
            facts.append(_fact("VNINDEX.monthly_return", month, float(vn_change), _fmt_pct(float(vn_change), 'vi', True), "co_phieu"))

        re_rows = p[(p.date == month) & p.symbol.isin(LEGACY_RE)].set_index("symbol")
        re_change = returns["bat_dong_san"].get(month)
        has_basket = (p.symbol == "RE_BASKET").any()
        if has_basket and re_change is not None and pd.notna(re_change):
            re_sentence_vi = f"Rổ cổ phiếu bất động sản (4 doanh nghiệp vốn hóa lớn nhất, cập nhật đầu mỗi năm) {_direction_vi(float(re_change))} {_fmt_pct(float(re_change), 'vi')}."
            re_sentence_en = f"The real-estate basket (four largest developers, reset each January) {_direction_en(float(re_change))} {_fmt_pct(float(re_change), 'en')}."
            facts.append(_fact("RE_BASKET.monthly_return", month, float(re_change), _fmt_pct(float(re_change), 'vi', True), "bat_dong_san"))
        elif len(re_rows) and re_rows.monthly_return.notna().any():
            sorted_re = re_rows.dropna(subset=["monthly_return"])["monthly_return"].sort_values()
            best_sym, worst_sym = sorted_re.index[-1], sorted_re.index[0]
            best_value, worst_value = float(sorted_re.iloc[-1]), float(sorted_re.iloc[0])
            re_sentence_vi = f"Rổ cổ phiếu bất động sản {_direction_vi(float(re_change))} {_fmt_pct(float(re_change), 'vi')} khi mạnh nhất {best_sym} {_fmt_pct(best_value, 'vi', True)}, yếu nhất {worst_sym} {_fmt_pct(worst_value, 'vi', True)}."
            re_sentence_en = f"The equal-weight real-estate basket {_direction_en(float(re_change))} {_fmt_pct(float(re_change), 'en')}; strongest {best_sym} {_fmt_pct(best_value, 'en', True)}, weakest {worst_sym} {_fmt_pct(worst_value, 'en', True)}."
            for sym, val in ((best_sym, best_value), (worst_sym, worst_value)):
                facts.append(_fact(sym + ".monthly_return", month, val, _fmt_pct(val, 'vi', True), "bat_dong_san"))
        else:
            re_sentence_vi = "Rổ cổ phiếu bất động sản chưa có đủ số liệu tháng."
            re_sentence_en = "The real-estate basket does not have a complete monthly observation."
        if vn_level is None or pd.isna(vn_change):
            vn_sentence_vi = "VN-Index chưa có số liệu tháng."
            vn_sentence_en = "VN-Index has no monthly observation."
        else:
            vn_sentence_vi = f"VN-Index đóng tháng ở {_fmt_number(vn_level, 'vi')} điểm, {_direction_vi(float(vn_change))} {_fmt_pct(float(vn_change), 'vi')} so với tháng trước."
            vn_sentence_en = f"VN-Index closed at {_fmt_number(vn_level, 'en')} points, {_direction_en(float(vn_change))} {_fmt_pct(float(vn_change), 'en')} month over month."

        etf = symbols.get("E1VFVN30")
        etf_level = float(etf.loc[month, "price"]) * 1000 if etf is not None and month in etf.index and pd.notna(etf.loc[month, "price"]) else None
        etf_change = returns["etf"].get(month)
        if etf_level is not None and pd.notna(etf_change):
            etf_sentence_vi = f"Chứng chỉ quỹ E1VFVN30 {_direction_vi(float(etf_change))} {_fmt_pct(float(etf_change), 'vi')}, đóng ở {_fmt_vnd(etf_level, 'vi')} ₫."
            etf_sentence_en = f"E1VFVN30 {_direction_en(float(etf_change))} {_fmt_pct(float(etf_change), 'en')}, closing at VND {_fmt_vnd(etf_level, 'en')}."
            facts.extend([_fact("E1VFVN30", month, etf_level, f"{_fmt_vnd(etf_level)} ₫", "etf"), _fact("E1VFVN30.monthly_return", month, float(etf_change), _fmt_pct(float(etf_change), 'vi', True), "etf")])
        else:
            etf_sentence_vi, etf_sentence_en = "Chứng chỉ quỹ E1VFVN30 chưa có số liệu tháng.", "E1VFVN30 has no monthly observation."

        gold = symbols.get("GOLD_SJC")
        gold_level = float(gold.loc[month, "price"]) if gold is not None and month in gold.index and pd.notna(gold.loc[month, "price"]) else None
        gold_change = returns["vang"].get(month)
        if gold_level is not None and pd.notna(gold_change):
            gold_sentence_vi = f"Giá vàng SJC {_direction_vi(float(gold_change))} {_fmt_pct(float(gold_change), 'vi')} {'lên' if gold_change >= 0 else 'xuống'} {_fmt_vnd(gold_level)} ₫/lượng."
            gold_sentence_en = f"SJC gold {_direction_en(float(gold_change))} {_fmt_pct(float(gold_change), 'en')} to VND {_fmt_vnd(gold_level, 'en')} per tael."
            facts.extend([_fact("GOLD_SJC", month, gold_level, f"{_fmt_vnd(gold_level)} ₫/lượng", "vang"), _fact("GOLD_SJC.monthly_return", month, float(gold_change), _fmt_pct(float(gold_change), 'vi', True), "vang")])
        else:
            gold_sentence_vi, gold_sentence_en = "Không có số liệu tháng cho vàng SJC.", "No monthly SJC gold observation is available."

        dep = symbols.get("DEPOSIT_12M")
        dep_level = float(dep.loc[month, "price"]) if dep is not None and month in dep.index and pd.notna(dep.loc[month, "price"]) else None
        dep_change = returns["tien_gui"].get(month)
        if dep_level is not None and pd.notna(dep_change):
            if abs(float(dep_change)) < 0.005:
                dep_verb = f"giữ nguyên ở {_fmt_number(dep_level, 'vi')}%/năm"
            else:
                dep_verb = f"{'tăng lên' if dep_change > 0 else 'giảm xuống'} {_fmt_number(dep_level, 'vi')}%/năm"
            dep_sentence_vi = f"Lãi suất tiền gửi 12 tháng {dep_verb} ({_fmt_number(float(dep_change), 'vi')} điểm %)."
            dep_sentence_en = f"The 12-month deposit rate {'held at' if abs(float(dep_change)) < 0.005 else ('rose to' if dep_change > 0 else 'fell to')} {_fmt_number(dep_level, 'en')}% a year ({_fmt_number(float(dep_change), 'en')} percentage points)."
            facts.extend([_fact("DEPOSIT_12M", month, dep_level, f"{_fmt_number(dep_level, 'vi')}%/năm", "tien_gui"), _fact("DEPOSIT_12M.change_pp", month, float(dep_change), f"{_fmt_number(float(dep_change), 'vi')} điểm %", "tien_gui")])
        else:
            dep_sentence_vi, dep_sentence_en = "Lãi suất tiền gửi 12 tháng chưa có số liệu tháng.", "The 12-month deposit rate is not available for this month."

        bond = symbols.get("VN_BOND_5Y")
        bond_level = float(bond.loc[month, "price"]) if bond is not None and month in bond.index and pd.notna(bond.loc[month, "price"]) else None
        bond_change = returns["trai_phieu"].get(month)
        if bond_level is not None and pd.notna(bond_change):
            bond_sentence_vi = f"Lợi suất TPCP kỳ hạn 5 năm {_direction_vi(float(bond_change))} {_fmt_number(float(bond_change), 'vi')} điểm %, ở mức {_fmt_number(bond_level, 'vi')}%."
            bond_sentence_en = f"The 5-year government bond yield {_direction_en(float(bond_change))} {_fmt_number(float(bond_change), 'en')} percentage points, at {_fmt_number(bond_level, 'en')}%."
            facts.extend([_fact("VN_BOND_5Y", month, bond_level, f"{_fmt_number(bond_level, 'vi')}%", "trai_phieu"), _fact("VN_BOND_5Y.change_pp", month, float(bond_change), f"{_fmt_number(float(bond_change), 'vi')} điểm %", "trai_phieu")])
        else:
            bond_sentence_vi, bond_sentence_en = "Lợi suất TPCP 5 năm chưa có số liệu tháng.", "The 5-year bond yield is not available for this month."

        is_provisional = provisional_month == month.strftime("%Y-%m")
        provisional_vi = f"Tháng {month:%m/%Y} là tạm tính; dữ liệu nguồn chưa đủ cả tháng." if is_provisional else ""
        provisional_en = f"{month:%m/%Y} is provisional; source data does not yet cover the full month." if is_provisional else ""
        body_vi = "\n\n".join(filter(None, [vn_sentence_vi, re_sentence_vi, etf_sentence_vi, gold_sentence_vi, dep_sentence_vi, bond_sentence_vi, provisional_vi, f"{SOURCE_LINE} Bài viết được tạo tự động từ dữ liệu phiên bản {version_label}."]))
        body_en = "\n\n".join(filter(None, [vn_sentence_en, re_sentence_en, etf_sentence_en, gold_sentence_en, dep_sentence_en, bond_sentence_en, provisional_en, f"{SOURCE_LINE_EN} Automatically generated from result version {version_label}."]))
        slug = f"ban-tin-thang-{month:%m}-{month:%Y}"
        articles.append({"kind": "monthly_brief", "slug": slug, "period": _period(month), "asset_tags": list(ASSET_ORDER), "title": {"vi": title_vi, "en": title_en}, "summary": {"vi": f"Điểm lại sáu lớp tài sản trong tháng {month:%m/%Y}.", "en": f"Six-asset monthly review for {month:%m/%Y}."}, "body": {"vi": body_vi, "en": body_en}, "facts": facts, "source_name": "Pipeline dataset", "source_url": None, "is_provisional": is_provisional, "status": "published", "version_id": version_label})

    # Deterministic notable-move articles; use the previous 24 monthly observations only.
    for asset in ASSET_ORDER:
        series = returns[asset].dropna().sort_index()
        is_rate = asset in ("tien_gui", "trai_phieu")
        for month in recent:
            if month not in series.index:
                continue
            previous = series.loc[series.index < month].tail(24).dropna()
            value = float(series.loc[month])
            if is_rate:
                threshold = 0.25
                notable = abs(value) >= threshold
                threshold_text = f"{_fmt_number(threshold, 'vi')} điểm %"
            else:
                if len(previous) < 12:
                    continue
                threshold = 2 * float(previous.std(ddof=1))
                notable = abs(value) >= threshold
                threshold_text = _fmt_pct(threshold, 'vi')
            if not notable:
                continue
            month_text = f"{month:%m/%Y}"
            if asset == "co_phieu":
                series_name = "VN-Index"
            elif asset == "bat_dong_san":
                series_name = "Rổ cổ phiếu bất động sản"
            elif asset == "etf":
                series_name = "E1VFVN30"
            elif asset == "vang":
                series_name = "Vàng SJC"
            elif asset == "tien_gui":
                series_name = "Lãi suất tiền gửi 12 tháng"
            else:
                series_name = "Lợi suất TPCP kỳ hạn 5 năm"
            if is_rate:
                title_vi = f"{series_name} {'tăng' if value >= 0 else 'giảm'} {abs(value):.2f} điểm % trong tháng {month_text} — biến động mạnh"
                title_vi = title_vi.replace(".", ",")
                value_text_vi = f"{abs(value):.2f}".replace(".", ",")
                body_vi = f"{series_name} {'tăng' if value >= 0 else 'giảm'} {value_text_vi} điểm % trong tháng {month_text}, vượt ngưỡng thay đổi 0,25 điểm %."
            else:
                title_vi = f"{series_name} {'tăng' if value >= 0 else 'giảm'} {_fmt_pct(value, 'vi')} trong tháng {month_text} — biến động mạnh"
                body_vi = f"{series_name} {_direction_vi(value)} {_fmt_pct(value, 'vi')} trong tháng {month_text}, vượt ngưỡng 2 lần độ lệch chuẩn 24 tháng trước đó ({threshold_text})."
            title_en = f"{series_name} {'rose' if value >= 0 else 'fell'} {_fmt_number(abs(value), 'en') + ' percentage points' if is_rate else _fmt_pct(value, 'en')} in {month_text} — notable move"
            body_en = f"{series_name} changed by {abs(value):.2f} percentage points in {month_text}, exceeding the 0.25 percentage-point threshold." if is_rate else f"{series_name} {_direction_en(value)} {_fmt_pct(value, 'en')} in {month_text}, exceeding twice the standard deviation of the prior 24 months ({threshold_text})."
            raw_level = None
            symbol = {"co_phieu": "VNINDEX", "bat_dong_san": "RE_BASKET", "etf": "E1VFVN30", "vang": "GOLD_SJC", "tien_gui": "DEPOSIT_12M", "trai_phieu": "VN_BOND_5Y"}[asset]
            if asset == "bat_dong_san":
                raw_level = float(returns["bat_dong_san"].get(month)) if returns["bat_dong_san"].get(month) is not None else float("nan")
            else:
                raw_level = value
            facts = [_fact(symbol + (".change_pp" if is_rate else ".monthly_return"), month, raw_level, (f"{_fmt_number(value, 'vi')} điểm %" if is_rate else _fmt_pct(value, 'vi', True)), asset), _fact(symbol + ".threshold", month, threshold, threshold_text, asset)]
            slug = f"bien-dong-{asset}-{month:%m}-{month:%Y}"
            articles.append({"kind": "notable_move", "slug": slug, "period": _period(month), "asset_tags": [asset], "title": {"vi": title_vi, "en": title_en}, "summary": {"vi": body_vi, "en": body_en}, "body": {"vi": body_vi + "\n\n" + SOURCE_LINE + f" Bài viết được tạo tự động từ dữ liệu phiên bản {version_label}.", "en": body_en + f"\n\nSource: thesis research dataset. Automatically generated from version {version_label}."}, "facts": facts, "source_name": "Pipeline dataset", "source_url": None, "is_provisional": provisional_month == _period(month), "status": "published", "version_id": version_label})
    return articles


def _direction_vi(value: float) -> str:
    if abs(value) < 0.00005:
        return "đi ngang"
    return "tăng" if value > 0 else "giảm"


def _direction_en(value: float) -> str:
    if abs(value) < 0.00005:
        return "was unchanged"
    return "rose" if value > 0 else "fell"
