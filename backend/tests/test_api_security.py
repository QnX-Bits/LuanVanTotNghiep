from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.auth import DEMO_PASSCODE
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app, base_url="https://testserver") as instance:
        yield instance


def login(client: TestClient, user_id: str) -> str:
    response = client.post("/api/auth/login", json={"user_id": user_id, "passcode": DEMO_PASSCODE})
    assert response.status_code == 200
    csrf = client.cookies.get("pvn_csrf")
    assert csrf
    return csrf


def test_dashboard_and_session_do_not_expose_internal_user_key(client: TestClient):
    login(client, "an")
    session = client.get("/api/auth/session")
    assert session.status_code == 200
    assert session.json()["name"] == "An Nguyễn"
    assert "key" not in session.json()

    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert len(payload["assets"]) == 6
    assert payload["data_confidence"]["provisional_month"] is None
    assert payload["balanced_medium"]["end"] == "2026-07"
    assert len(payload["latest_news"]) == 5


def test_draft_news_and_v2_draft_results_are_not_published_to_investors(client: TestClient):
    login(client, "an")
    investor_news = client.get("/api/news?limit=200")
    assert investor_news.status_code == 200
    assert investor_news.json()["count"] == 68  # 36 briefs + 30 moves + two published announcements.
    assert client.get("/api/news/pvn-draft-demo-note").status_code == 404

    login(client, "admin")
    admin_news = client.get("/api/news?limit=200")
    assert admin_news.status_code == 200
    assert admin_news.json()["count"] == 69  # + one admin-only draft
    assert any(row["slug"] == "pvn-draft-demo-note" and row["status"] == "draft" for row in admin_news.json()["items"])


def test_investor_cannot_enumerate_or_read_another_investors_plan(client: TestClient):
    login(client, "an")
    own = client.get("/api/plans/PVN-2026-00001")
    foreign = client.get("/api/plans/PVN-2026-00003")
    assert own.status_code == 200
    assert foreign.status_code == 404
    assert "owner_name" not in own.json()
    listed = client.get("/api/plans")
    assert listed.status_code == 200
    codes = {row["code"] for row in listed.json()["items"]}
    assert "PVN-2026-00001" in codes
    assert "PVN-2026-00003" not in codes


def test_reviewer_is_read_only_and_personal_plan_routes_are_not_found(client: TestClient):
    login(client, "reviewer")
    assert client.get("/api/plans").status_code == 403
    assert client.get("/api/plans/PVN-2026-00001").status_code == 404
    assert client.get("/api/admin/versions").status_code == 200
    assert client.get("/api/admin/runs").status_code == 200
    assert client.get("/api/admin/audit").status_code == 200


def test_advisor_assessment_uses_csrf_and_server_score(client: TestClient):
    csrf = login(client, "an")
    response = client.post(
        "/api/advisor/assess",
        headers={"x-csrf-token": csrf},
        json={
            "answers": {"T1": 1, "T2": 2, "T3": 2, "T4": 2, "C1": 2, "C2": 2, "C3": 1, "H": "trung_han"},
            "locale": "vi",
        },
    )
    assert response.status_code == 200
    profile = response.json()
    assert profile["scores"] == {"tolerance": 7, "capacity": 5}
    assert profile["system_profile"] == "can_bang"
    assert profile["warnings"] == []


def test_public_share_has_no_answers_owner_or_internal_user_ids(client: TestClient):
    csrf = login(client, "an")
    created = client.post("/api/plans/PVN-2026-00001/share", headers={"x-csrf-token": csrf})
    assert created.status_code == 200
    shared = client.get(created.json()["path"].replace("/share/", "/api/share/"))
    assert shared.status_code == 200
    data = shared.json()
    assert data["share_mode"] == "public"
    assert "answers" not in data
    assert "answer_text" not in data
    assert "acknowledgement" not in data
    assert "owner_name" not in data
    assert "user_id" not in data
    assert "result_version_id" not in data
    assert "execution_rules_id" not in data
    revoked = client.delete("/api/plans/PVN-2026-00001/share", headers={"x-csrf-token": csrf})
    assert revoked.status_code == 200
    assert client.get(created.json()["path"].replace("/share/", "/api/share/")).status_code == 404


def test_advisor_result_and_saved_plan_use_active_csv_snapshot(client: TestClient):
    csrf = login(client, "an")
    payload = {
        "answers": {"T1": 1, "T2": 2, "T3": 2, "T4": 2, "C1": 2, "C2": 2, "C3": 1, "H": "trung_han"},
        "chosen_profile": "can_bang",
        "acknowledged": False,
        "amount_vnd": 100_000_000,
        "locale": "vi",
    }
    preview = client.post("/api/advisor/result", headers={"x-csrf-token": csrf}, json=payload)
    assert preview.status_code == 200, preview.text
    result = preview.json()
    source = pd.read_csv(Path(__file__).resolve().parents[2] / "pipeline" / "data" / "processed" / "performance_summary.csv")
    source_row = source[(source.method == "RiskParity") & (source.risk_profile == "can_bang") & (source.horizon == "trung_han")].iloc[0]
    assert result["metrics"]["annualised_return"] == pytest.approx(float(source_row.annualised_return), abs=1e-15)
    assert result["metrics"]["volatility"] == pytest.approx(float(source_row.volatility), abs=1e-15)
    assert sum(result["targets_vnd"].values()) == 100_000_000
    assert result["execution"]["total_vnd"] == 100_000_000

    saved = client.post("/api/plans", headers={"x-csrf-token": csrf}, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["code"].startswith("PVN-2026-")
    stored = client.get(f"/api/plans/{saved.json()['code']}")
    assert stored.status_code == 200
    snapshot = stored.json()
    assert snapshot["metrics"]["annualised_return"] == pytest.approx(float(source_row.annualised_return), abs=1e-15)
    assert snapshot["amount_vnd"] == 100_000_000
    assert snapshot["answers"]["H"] == "trung_han"


def test_admin_reset_restores_seed_and_audits_reset_on_isolated_database(client: TestClient):
    csrf = login(client, "admin")
    denied = client.post("/api/admin/reset?confirm=wrong", headers={"x-csrf-token": csrf})
    assert denied.status_code == 422

    reset = client.post("/api/admin/reset?confirm=RESET%20PORTFOLIOVN%20DEMO", headers={"x-csrf-token": csrf})
    assert reset.status_code == 200
    plans = client.get("/api/plans")
    assert plans.status_code == 200
    assert {row["code"] for row in plans.json()["items"]} == {"PVN-2026-00001", "PVN-2026-00002", "PVN-2026-00003"}
    versions = client.get("/api/admin/versions").json()["items"]
    assert sum(row["status"] == "active" for row in versions) == 1
    audit = client.get("/api/admin/audit").json()["items"]
    assert any(row["action"] == "reset_demo" for row in audit)


def test_admin_run_accepts_delta_not_volatility_floor_and_v2_draft_is_valid(client: TestClient):
    """QC đợt 4: tham số 'sàn vol tiền gửi' đã bỏ; admin run nhận δ 1,5/2,5/4 và phí theo lớp (None) hoặc đồng nhất."""
    csrf = login(client, "admin")
    bad = client.post("/api/admin/runs", headers={"x-csrf-token": csrf}, json={"delta": 3.0})
    assert bad.status_code == 422
    bad_cost = client.post("/api/admin/runs", headers={"x-csrf-token": csrf}, json={"delta": 2.5, "transaction_cost": 0.02})
    assert bad_cost.status_code == 422
    versions = {row["id"]: row for row in client.get("/api/admin/versions").json()["items"]}
    assert versions["v20261012-v2"]["status"] == "draft"
    assert "δ 4" in versions["v20261012-v2"]["label"]
    assert "δ 2,5 · phí theo lớp" in versions["v20261012-v1"]["label"]


def test_methodology_reports_detectable_difference_and_families(client: TestClient):
    login(client, "reviewer")
    data = client.get("/api/analysis/methodology").json()
    families = {row["hypothesis"] for row in data["rows"]}
    assert {"H1", "H2", "H3"} <= families and "Khác" not in families
    assert data["row_count"] == 11
    assert all(row["minimum_detectable_difference"] is not None for row in data["rows"])
    sens = client.get("/api/analysis/sensitivity").json()["rows"]
    assert any(row["parameter"] == "gold_recon" for row in sens)
