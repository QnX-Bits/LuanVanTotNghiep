from __future__ import annotations

import base64
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import USERS
from .data.repository import PROCESSED_DIR, ensure_v1, panel_month_label, version_label, get_active_version, import_result_version, load_frames
from .domain.news import generate_auto_articles
from .models import AuditLog, DemoUser, NewsArticle, PipelineRun, Plan, PlanSequence, ResultVersion, ShareLink
from .services.plan_service import build_plan_snapshot, ensure_default_rules

ROOT = Path(__file__).resolve().parents[2]
V2_OUTPUT = ROOT / "results" / "v2-delta4"      # bản chạy cô lập --stage backtest với PVN_DELTA=4


def _facts_key(article: dict, checksum: str) -> str:
    tags = ",".join(article.get("asset_tags", []))
    digest = hashlib.sha256(f"{tags}:{checksum}".encode("utf-8")).hexdigest()
    return f"{article['kind']}:{article['period']}:{digest}"


def _store_generated_news(db: Session, version: ResultVersion) -> None:
    frames = load_frames(db, version.id)
    articles = generate_auto_articles(frames["asset_panel_standardized.csv"], version.label, version.manifest.get("provisional_month"))
    for article in articles:
        key = _facts_key(article, version.panel_checksum)
        existing = db.execute(select(NewsArticle).where(NewsArticle.auto_key == key)).scalars().first()
        if existing:
            continue
        article["version_id"] = version.id
        db.add(NewsArticle(slug=article["slug"], kind=article["kind"], period=article["period"], status="published", article=article, auto_key=key, panel_checksum=version.panel_checksum, version_id=version.id, published_at=datetime.now(timezone.utc)))
    db.flush()


def _manual_article(slug: str, kind: str, title: str, summary: str, body: str, status: str, published: bool) -> NewsArticle:
    return NewsArticle(slug=slug, kind=kind, period=None, status=status, article={"kind": kind, "slug": slug, "title": {"vi": title, "en": title}, "summary": {"vi": summary, "en": summary}, "body": {"vi": body, "en": body}, "asset_tags": [], "facts": [], "source_name": "PortfolioVN research demo", "source_url": None, "is_provisional": False, "status": status, "version_id": None}, auto_key=None, panel_checksum=None, version_id=None, published_at=datetime.now(timezone.utc) if published else None)


def _seed_users(db: Session) -> None:
    for key, user in USERS.items():
        if db.get(DemoUser, key) is None:
            db.add(DemoUser(id=key, display_name=user["name"], role=user["role"], locale=user["locale"]))
    db.flush()


def _import_v2_if_available(db: Session) -> ResultVersion | None:
    existing = db.get(ResultVersion, "v20261012-v2")
    if existing:
        return existing
    if not (V2_OUTPUT / "performance_summary.csv").is_file():
        return None
    params = {"delta": 4.0, "transaction_cost": "class_vector", "source": "isolated PVN_DELTA=4 run.py --stage backtest --no-open"}
    version = import_result_version(db, V2_OUTPUT, version_label(V2_OUTPUT, 4.0, None), params, status="draft", version_id="v20261012-v2")
    if version.status == "invalid":
        return version
    db.flush()
    return version


def _create_sample_plan(db: Session, code: str, user_key: str, answers: dict, profile: str, amount: int, locale: str) -> None:
    if db.get(Plan, code):
        return
    user = {"key": user_key, **USERS[user_key]}
    snapshot = build_plan_snapshot(db, user, {"answers": answers, "chosen_profile": profile, "acknowledged": False, "amount_vnd": amount, "locale": locale})
    snapshot["created_at"] = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    db.add(Plan(code=code, user_id=user_key, version_id=snapshot["result_version_id"], execution_rules_id=snapshot["execution_rules_id"], snapshot=snapshot, created_at=datetime.now(timezone.utc) - timedelta(days=3)))
    db.flush()


def seed_demo(db: Session) -> None:
    _seed_users(db)
    v1 = ensure_v1(db)
    ensure_default_rules(db)
    v2 = _import_v2_if_available(db)
    if v1.status == "active":
        _store_generated_news(db, v1)
    if v2 and v2.status == "active":
        _store_generated_news(db, v2)

    manual = [
        ("pvn-announcement-ueh-2026", "announcement", "Thông báo: phạm vi demo PortfolioVN", "Cổng dữ liệu nghiên cứu cho buổi trình diễn tại UEH.", "Demo sử dụng dữ liệu tháng trong bộ pipeline đã cung cấp. Đây không phải dịch vụ môi giới, dữ liệu thời gian thực hay lời khuyên đầu tư.", "published", True),
        ("pvn-announcement-provisional", "announcement", f"Dữ liệu nghiên cứu kết thúc ở tháng {panel_month_label()}", "Tháng 08/2026 chưa trọn nên không đưa vào nghiên cứu.", f"Bộ dữ liệu thô có giá cổ phiếu đến 17/08/2026 và lợi suất trái phiếu đến 21/08/2026. Vì tháng 08/2026 chưa đủ dữ liệu, return tháng này không so sánh được với các tháng khác; toàn bộ backtest và tỷ trọng dừng ở tháng {panel_month_label()}. Các kết quả nghiên cứu không phải dự báo.", "published", True),
        ("pvn-draft-demo-note", "announcement", "Bản nháp: ghi chú nội bộ", "Bản nháp chỉ hiển thị cho Admin.", "Bài nháp dùng để minh họa quyền xuất bản nội dung; không hiển thị cho Investor/Reviewer.", "draft", False),
    ]
    for values in manual:
        slug = values[0]
        if db.get(NewsArticle, slug) is None:
            db.add(_manual_article(*values))

    now = datetime.now(timezone.utc)
    if not db.get(PipelineRun, "run-seed-v1"):
        n_tests = len(load_frames(db, v1.id)["holm_bonferroni_results.csv"])
        db.add(PipelineRun(id="run-seed-v1", status="succeeded", stage="backtest", params={"delta": 2.5, "transaction_cost": None, "note": "Source V1 provided"}, started_by="admin", started_at=now-timedelta(days=2), finished_at=now-timedelta(days=2)+timedelta(minutes=7), log_tail=f"V1 imported and validated: 63 performance rows, 63 allocations, {n_tests} hypothesis rows."))
    if v2 and v2.status == "draft" and not db.get(PipelineRun, "run-seed-v2"):
        db.add(PipelineRun(id="run-seed-v2", status="succeeded", stage="backtest", params={"delta": 4.0, "transaction_cost": None, "note": "V2 draft demo"}, started_by="admin", started_at=now-timedelta(days=1), finished_at=now-timedelta(days=1)+timedelta(minutes=9), result_version_id=v2.id, log_tail="Isolated --stage backtest run completed; V2 saved as draft."))
    if not db.get(PipelineRun, "run-seed-failed"):
        db.add(PipelineRun(id="run-seed-failed", status="failed", stage="backtest", params={"delta": 1.5, "transaction_cost": 0.0015, "note": "Validation failure demo"}, started_by="admin", started_at=now-timedelta(hours=8), finished_at=now-timedelta(hours=8)+timedelta(minutes=2), log_tail="Sample failed run: validation rejected an incomplete CSV snapshot; active version was unchanged."))

    answers_balanced = {"T1": 1, "T2": 2, "T3": 2, "T4": 2, "C1": 2, "C2": 2, "C3": 1, "H": "trung_han"}
    answers_conservative = {"T1": 3, "T2": 3, "T3": 3, "T4": 3, "C1": 1, "C2": 1, "C3": 1, "H": "ngan_han"}
    answers_growth = {"T1": 3, "T2": 3, "T3": 2, "T4": 2, "C1": 3, "C2": 3, "C3": 2, "H": "dai_han"}
    _create_sample_plan(db, "PVN-2026-00001", "an", answers_balanced, "can_bang", 100_000_000, "vi")
    _create_sample_plan(db, "PVN-2026-00002", "an", answers_conservative, "than_trong", 50_000_000, "vi")
    _create_sample_plan(db, "PVN-2026-00003", "binh", answers_growth, "tang_truong", 200_000_000, "en")
    sequence = db.get(PlanSequence, 2026)
    if sequence is None:
        db.add(PlanSequence(year=2026, last_number=3))
    else:
        sequence.last_number = max(sequence.last_number, 3)

    first = db.get(Plan, "PVN-2026-00001")
    if first and not db.execute(select(ShareLink).where(ShareLink.plan_code == first.code)).scalars().first():
        token = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
        db.add(ShareLink(token=token, plan_code=first.code, created_at=now))
    if not db.execute(select(AuditLog).where(AuditLog.action == "demo_seeded")).scalars().first():
        db.add(AuditLog(id=uuid.uuid4().hex, actor_id="admin", action="demo_seeded", entity="Demo", entity_id="seed-v1", after={"result_version": v1.id, "plans": 3, "news_seed": True}))
    db.commit()
