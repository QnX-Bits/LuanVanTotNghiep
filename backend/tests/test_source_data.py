from pathlib import Path

import pandas as pd

from app.data.versioning import load_result_files, validate_result_files
from app.domain.news import generate_auto_articles
from app.seed import _facts_key

ROOT = Path(__file__).resolve().parents[2]


def test_uploaded_v1_result_files_match_required_schema_and_counts():
    files = load_result_files(ROOT / "pipeline" / "data" / "processed")
    result = validate_result_files(files)
    assert result["valid"] is True, result["reasons"]
    assert result["rows"]["performance_summary.csv"] == 63
    assert result["rows"]["allocation_current.csv"] == 63
    assert result["rows"]["holm_bonferroni_results.csv"] == 17   # H1 3 + H2 3 + H3 5 + H4 5 + mở rộng 1 (QC đợt 4)


def test_panel_excludes_incomplete_august_2026():
    panel = pd.read_csv(ROOT / "pipeline" / "data" / "processed" / "asset_panel_standardized.csv", parse_dates=["date"])
    assert panel["date"].max() == pd.Timestamp("2026-07-01")
    perf = pd.read_csv(ROOT / "pipeline" / "data" / "processed" / "performance_summary.csv")
    assert set(perf["end"]) == {"2026-07"} and set(perf["n_months"]) == {102}   # kiểm tra 02/2018-07/2026 (panel 02/2016-07/2026)


def test_published_news_seed_has_expected_counts_and_no_provisional_period():
    panel = pd.read_csv(ROOT / "pipeline" / "data" / "processed" / "asset_panel_standardized.csv")
    articles = generate_auto_articles(panel, "07/2026 · δ 2,5 · phí theo lớp", None)
    monthly = [row for row in articles if row["kind"] == "monthly_brief"]
    notable = [row for row in articles if row["kind"] == "notable_move"]
    assert len(monthly) == 36
    assert len(notable) == 30
    assert not any(row["period"] == "2026-08" for row in articles)
    assert not any(row["is_provisional"] for row in articles)
    july = next(row for row in monthly if row["period"] == "2026-07")
    assert "Cổ phiếu giảm −6,68%" in july["title"]["vi"]
    keys = [_facts_key(article, "8e411c18af51497c5b8f4cf46b6b16381c0d2560bb04b2bf013f0c11c66889f5") for article in articles]
    assert len(keys) == len(set(keys))
    assert max(map(len, keys)) <= 128


def test_research_metrics_are_not_recomputed():
    frame = pd.read_csv(ROOT / "pipeline" / "data" / "processed" / "performance_summary.csv")
    row = frame[(frame.method == "RiskParity") & (frame.risk_profile == "can_bang") & (frame.horizon == "trung_han")].iloc[0]
    assert round(float(row.annualised_return) * 100, 2) == 8.46
    assert round(float(row.volatility) * 100, 2) == 9.36
    assert round(float(row.max_drawdown) * 100, 2) == -22.02
