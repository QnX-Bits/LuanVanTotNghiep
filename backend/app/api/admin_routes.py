from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..auth import current_user, require_roles, verify_csrf
from ..data.repository import ROOT, get_active_version, import_result_version, version_public
from ..domain.news import slugify
from ..models import AuditLog, DemoUser, ExecutionRules, NewsArticle, PipelineRun, Plan, PlanSequence, ResultFile, ResultVersion, ShareLink, get_db
from ..schemas import ArticleRequest, ExecutionRulesRequest, RunRequest
from ..seed import seed_demo
from ..services.activation import activate_version
from ..services.pipeline_runner import run_backtest_job
from ..services.plan_service import DEFAULT_RULES

router = APIRouter(prefix="/api/admin", tags=["admin"])
ADMIN = require_roles("admin")


def _audit(db: Session, actor: str, action: str, entity: str, entity_id: str | None, before=None, after=None) -> None:
    db.add(AuditLog(id=uuid.uuid4().hex, actor_id=actor, action=action, entity=entity, entity_id=entity_id, before=before, after=after))


@router.get("/versions")
def versions(user: dict = Depends(require_roles("admin", "reviewer")), db: Session = Depends(get_db)):
    rows = db.execute(select(ResultVersion).order_by(ResultVersion.created_at.desc())).scalars().all()
    return {"items": [version_public(row, user["role"]) for row in rows]}


@router.post("/versions/{version_id}/activate")
def activate(version_id: str, request: Request, user: dict = Depends(ADMIN), db: Session = Depends(get_db)):
    verify_csrf(request)
    try:
        row = activate_version(db, version_id, user["key"])
        db.commit()
        db.refresh(row)
        return version_public(row, "admin")
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/versions/{version_id}")
def delete_version(version_id: str, request: Request, user: dict = Depends(ADMIN), db: Session = Depends(get_db)):
    verify_csrf(request)
    row = db.get(ResultVersion, version_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Version not found")
    if row.status not in ("draft", "archived", "invalid"):
        raise HTTPException(status_code=409, detail="Active version cannot be deleted")
    if db.execute(select(Plan).where(Plan.version_id == version_id)).scalars().first():
        raise HTTPException(status_code=409, detail="Version is referenced by a saved plan")
    _audit(db, user["key"], "delete_version", "ResultVersion", version_id, before={"status": row.status, "label": row.label})
    db.execute(delete(ResultFile).where(ResultFile.version_id == version_id))
    db.delete(row)
    db.commit()
    shutil.rmtree(ROOT / "results" / version_id, ignore_errors=True)
    return {"deleted": True}


@router.post("/runs")
def start_run(payload: RunRequest, background: BackgroundTasks, request: Request, user: dict = Depends(ADMIN), db: Session = Depends(get_db)):
    verify_csrf(request)
    if min(abs(payload.delta - x) for x in (1.5, 2.5, 4.0)) > 1e-9:
        raise HTTPException(status_code=422, detail="delta must be 1.5, 2.5 or 4")
    if payload.transaction_cost is not None and not (0 <= payload.transaction_cost <= 0.005):
        raise HTTPException(status_code=422, detail="transaction cost must be between 0% and 0.50%")
    params = {"delta": payload.delta, "transaction_cost": payload.transaction_cost, "note": payload.note}
    from ..services.pipeline_runner import create_run
    try:
        run = create_run(db, user, params)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background.add_task(run_backtest_job, run.id, params)
    _audit(db, user["key"], "start_pipeline_run", "PipelineRun", run.id, after=params)
    db.commit()
    return {"id": run.id, "status": run.status, "stage": run.stage, "params": run.params}


@router.get("/runs")
def runs(user: dict = Depends(require_roles("admin", "reviewer")), db: Session = Depends(get_db)):
    rows = db.execute(select(PipelineRun).order_by(PipelineRun.started_at.desc())).scalars().all()
    return {"items": [{"id": row.id, "status": row.status, "stage": row.stage, "params": row.params, "started_at": row.started_at.isoformat(), "finished_at": row.finished_at.isoformat() if row.finished_at else None, "result_version_id": row.result_version_id, "log_tail": row.log_tail if user["role"] == "admin" else None} for row in rows]}


@router.get("/runs/{run_id}")
def run_detail(run_id: str, user: dict = Depends(require_roles("admin", "reviewer")), db: Session = Depends(get_db)):
    row = db.get(PipelineRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    result = {"id": row.id, "status": row.status, "stage": row.stage, "params": row.params, "started_at": row.started_at.isoformat(), "finished_at": row.finished_at.isoformat() if row.finished_at else None, "result_version_id": row.result_version_id}
    if user["role"] == "admin":
        result["log_tail"] = row.log_tail
    return result


@router.get("/news")
def admin_news(user: dict = Depends(ADMIN), db: Session = Depends(get_db), status: str | None = None):
    query = select(NewsArticle).order_by(NewsArticle.updated_at.desc())
    if status:
        query = query.where(NewsArticle.status == status)
    rows = db.execute(query.limit(500)).scalars().all()
    return {"items": [{**row.article, "status": row.status, "slug": row.slug, "auto_key": row.auto_key, "panel_checksum": row.panel_checksum, "version_id": row.version_id, "updated_at": row.updated_at.isoformat()} for row in rows]}


def _sanitize_markdown(value: str) -> str:
    value = re.sub(r"<[^>]*>", "", value)
    value = re.sub(r"(?i)(javascript|data|vbscript)\s*:", "", value)
    value = re.sub(r"(?i)\bon\w+\s*=", "", value)
    return value.strip()


def _article_payload(payload: ArticleRequest) -> dict:
    if payload.kind not in ("announcement", "external_summary"):
        raise HTTPException(status_code=422, detail="Only announcement or external_summary can be edited manually")
    if payload.kind == "external_summary":
        if not payload.source_url or urlparse(payload.source_url).scheme != "https" or not urlparse(payload.source_url).netloc:
            raise HTTPException(status_code=422, detail="external_summary requires an HTTPS source URL")
        if len(payload.summary.get("vi", "")) > 600 or len(payload.summary.get("en", "")) > 600:
            raise HTTPException(status_code=422, detail="Source summary is limited to 600 characters per language")
        if not payload.source_name or not payload.source_published_at or not payload.tags:
            raise HTTPException(status_code=422, detail="Add source name, original date and at least one tag")
    title = {key: _sanitize_markdown(value) for key, value in payload.title.items()}
    summary = {key: _sanitize_markdown(value) for key, value in payload.summary.items()}
    body = {key: _sanitize_markdown(value) for key, value in payload.body.items()}
    if not title.get("vi") or not body.get("vi"):
        raise HTTPException(status_code=422, detail="Vietnamese title and body are required")
    return {"kind": payload.kind, "slug": "", "title": title, "summary": summary, "body": body, "asset_tags": payload.tags[:10], "facts": [], "source_name": payload.source_name, "source_url": payload.source_url, "source_published_at": payload.source_published_at, "is_provisional": False, "status": "draft"}


@router.post("/news")
def create_article(payload: ArticleRequest, request: Request, user: dict = Depends(ADMIN), db: Session = Depends(get_db)):
    verify_csrf(request)
    article = _article_payload(payload)
    slug = slugify(article["title"]["vi"])
    if db.get(NewsArticle, slug):
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"
    article["slug"] = slug
    row = NewsArticle(slug=slug, kind=article["kind"], period=None, status="draft", article=article, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
    db.add(row)
    _audit(db, user["key"], "create_news_draft", "NewsArticle", slug, after={"kind": row.kind, "status": "draft"})
    db.commit()
    return {"slug": slug, "status": "draft", "article": article}


@router.put("/news/{slug}")
def update_article(slug: str, payload: ArticleRequest, request: Request, user: dict = Depends(ADMIN), db: Session = Depends(get_db)):
    verify_csrf(request)
    row = db.get(NewsArticle, slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if row.auto_key or row.status == "published":
        raise HTTPException(status_code=409, detail="Unpublish a manual article before editing; generated articles are immutable")
    article = _article_payload(payload)
    article["slug"] = row.slug
    before = {"status": row.status, "title": row.article.get("title")}
    row.article = article
    row.updated_at = datetime.now(timezone.utc)
    _audit(db, user["key"], "update_news_draft", "NewsArticle", slug, before=before, after={"status": row.status, "title": article["title"]})
    db.commit()
    return {"slug": row.slug, "status": row.status, "article": row.article}


@router.post("/news/{slug}/publish")
def set_article_published(slug: str, request: Request, user: dict = Depends(ADMIN), db: Session = Depends(get_db)):
    verify_csrf(request)
    row = db.get(NewsArticle, slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if row.auto_key:
        raise HTTPException(status_code=409, detail="Automatic articles cannot be manually edited or published")
    row.status = "published"
    row.article = {**row.article, "status": "published"}
    row.published_at = datetime.now(timezone.utc)
    _audit(db, user["key"], "publish_news", "NewsArticle", slug, after={"status": "published"})
    db.commit()
    return {"slug": slug, "status": row.status}


@router.post("/news/{slug}/unpublish")
def unpublish_article(slug: str, request: Request, user: dict = Depends(ADMIN), db: Session = Depends(get_db)):
    verify_csrf(request)
    row = db.get(NewsArticle, slug)
    if row is None:
        raise HTTPException(status_code=404, detail="Article not found")
    row.status = "unpublished"
    row.article = {**row.article, "status": "unpublished"}
    _audit(db, user["key"], "unpublish_news", "NewsArticle", slug, after={"status": "unpublished"})
    db.commit()
    return {"slug": slug, "status": row.status}


@router.get("/execution-rules")
def get_rules(user: dict = Depends(ADMIN), db: Session = Depends(get_db)):
    row = db.execute(select(ExecutionRules).where(ExecutionRules.is_current.is_(True))).scalars().first()
    return {"id": row.id if row else "rules-v1", "rules": row.rules if row else DEFAULT_RULES}


@router.put("/execution-rules")
def update_rules(payload: ExecutionRulesRequest, request: Request, user: dict = Depends(ADMIN), db: Session = Depends(get_db)):
    verify_csrf(request)
    if set(payload.rules.keys()) - set(DEFAULT_RULES.keys()):
        raise HTTPException(status_code=422, detail="Unknown execution rule key")
    bounds = {"share_lot": (1, 10000), "etf_lot": (1, 10000), "fund_min_vnd": (0, 100_000_000), "fund_step_vnd": (1, 1_000_000), "re_deviation_threshold_pp": (0, 20), "early_rebalance_threshold_pp": (0, 50)}
    for key, (minimum, maximum) in bounds.items():
        value = payload.rules.get(key)
        if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or not minimum <= value <= maximum):
            raise HTTPException(status_code=422, detail=f"{key} must be between {minimum} and {maximum}")
    if "gold_unit" in payload.rules and payload.rules["gold_unit"] not in {"chi", "luong"}:
        raise HTTPException(status_code=422, detail="gold_unit must be chi or luong")
    old = db.execute(select(ExecutionRules).where(ExecutionRules.is_current.is_(True))).scalars().first()
    if old:
        old.is_current = False
        version_number = int(old.id.split("-v")[-1]) + 1 if "-v" in old.id else 2
    else:
        version_number = 2
    new_id = f"rules-v{version_number}"
    rules = {**DEFAULT_RULES, **(old.rules if old else {}), **payload.rules, "version": new_id}
    row = ExecutionRules(id=new_id, rules=rules, is_current=True)
    db.add(row)
    _audit(db, user["key"], "update_execution_rules", "ExecutionRules", new_id, before=old.rules if old else None, after=rules)
    db.commit()
    return {"id": row.id, "rules": row.rules}


@router.get("/audit")
def audit(user: dict = Depends(require_roles("admin", "reviewer")), db: Session = Depends(get_db)):
    rows = db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(500)).scalars().all()
    items = []
    for row in rows:
        item = {"action": row.action, "entity": row.entity, "entity_id": row.entity_id, "created_at": row.created_at.isoformat()}
        if user["role"] == "admin":
            item.update({"actor_id": row.actor_id, "before": row.before, "after": row.after})
        else:
            item["actor"] = "Administrator" if row.actor_id == "admin" else "Investor/reviewer"
        items.append(item)
    return {"items": items}


@router.post("/reset")
def reset_demo(request: Request, confirm: str, user: dict = Depends(ADMIN), db: Session = Depends(get_db)):
    verify_csrf(request)
    if confirm != "RESET PORTFOLIOVN DEMO":
        raise HTTPException(status_code=422, detail="Confirmation text does not match")
    # This only resets PortfolioVN demo-owned rows; the uploaded pipeline source remains intact.
    for model in (ShareLink, Plan, PlanSequence, NewsArticle, PipelineRun, ResultFile, ResultVersion, ExecutionRules, AuditLog, DemoUser):
        db.execute(delete(model))
    db.commit()
    seed_demo(db)
    _audit(db, user["key"], "reset_demo", "Demo", "portfolio", after={"restored": True})
    db.commit()
    return {"reset": True, "message": "Demo data restored from the uploaded V1 pipeline snapshot."}
