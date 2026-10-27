from __future__ import annotations

import base64
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user, require_roles, verify_csrf
from ..data.repository import get_active_version, load_frames
from ..models import Plan, ShareLink, get_db
from ..schemas import ProfileRequest
from ..domain.profiling import ACK_TEXT, CAPACITY_TEXT, HORIZON_LABELS, PROFILE_LABELS, TOLERANCE_TEXT, WARNING_TEXT, allowed_choices, assess_profile
from ..services.plan_service import build_plan_snapshot, create_plan, public_plan, saved_drift

router = APIRouter(prefix="/api", tags=["plans"])


@router.get("/advisor/questions")
def advisor_questions(user: dict = Depends(current_user)):
    return {
        "tolerance": TOLERANCE_TEXT,
        "capacity": CAPACITY_TEXT,
        "horizons": HORIZON_LABELS,
        "profiles": PROFILE_LABELS,
    }


@router.post("/advisor/assess")
def advisor_assess(payload: ProfileRequest, request: Request, user: dict = Depends(current_user)):
    verify_csrf(request)
    try:
        assessment = assess_profile(payload.answers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    locale = "en" if payload.locale == "en" else ("en" if user["locale"] == "en" else "vi")
    warning_copy = {}
    for code in assessment.warnings:
        text = WARNING_TEXT[code][locale]
        if code == "W1":
            text = text.format(capacity=PROFILE_LABELS[assessment.capacity_profile][locale])
        warning_copy[code] = text
    return {
        "scores": {"tolerance": assessment.tolerance_score, "capacity": assessment.capacity_score},
        "tolerance_profile": assessment.tolerance_profile,
        "capacity_profile": assessment.capacity_profile,
        "horizon": assessment.horizon,
        "horizon_cap": assessment.horizon_cap,
        "system_profile": assessment.system_profile,
        "warnings": list(assessment.warnings),
        "warning_copy": warning_copy,
        "choices": allowed_choices(assessment),
        "acknowledgement": ACK_TEXT[locale],
    }


@router.post("/advisor/result")
def advisor_result(payload: ProfileRequest, request: Request, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    verify_csrf(request)
    if payload.amount_vnd is None:
        raise HTTPException(status_code=422, detail="Investment amount is required")
    try:
        snapshot = build_plan_snapshot(db, user, {**payload.model_dump(), "locale": payload.model_dump().get("locale") or user["locale"]})
        snapshot.pop("result_version_id", None)
        snapshot.pop("execution_rules_id", None)
        return snapshot
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/plans")
def save_plan(payload: ProfileRequest, request: Request, user: dict = Depends(require_roles("investor")), db: Session = Depends(get_db)):
    verify_csrf(request)
    if payload.amount_vnd is None:
        raise HTTPException(status_code=422, detail="Investment amount is required")
    try:
        plan = create_plan(db, user, {**payload.model_dump(), "locale": payload.model_dump().get("locale") or user["locale"]})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return public_plan(plan, user)


@router.get("/plans")
def list_plans(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    if user["role"] == "reviewer":
        raise HTTPException(status_code=403, detail="Reviewer does not access personal plans")
    stmt = select(Plan).order_by(Plan.created_at.desc())
    if user["role"] == "investor":
        stmt = stmt.where(Plan.user_id == user["key"])
    rows = db.execute(stmt).scalars().all()
    return {"items": [{"code": row.code, "created_at": row.created_at.isoformat(), "profile": row.snapshot["chosen_profile"], "horizon": row.snapshot["horizon"], "amount_vnd": row.snapshot["amount_vnd"], "version_label": row.snapshot["result_version_label"], "outdated": row.snapshot["result_version_id"] != get_active_version(db).id} for row in rows]}


@router.get("/plans/{code}")
def get_plan(code: str, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    plan = db.get(Plan, code)
    if plan is None or user["role"] == "reviewer" or (user["role"] == "investor" and plan.user_id != user["key"]):
        raise HTTPException(status_code=404, detail="Plan not found")
    result = public_plan(plan, user)
    result["outdated"] = plan.version_id != get_active_version(db).id
    active_panel = load_frames(db, get_active_version(db).id)["asset_panel_standardized.csv"]
    result["drift"] = saved_drift(plan, active_panel)
    return result


@router.post("/plans/{code}/refresh")
def refresh_plan(code: str, request: Request, user: dict = Depends(require_roles("investor")), db: Session = Depends(get_db)):
    verify_csrf(request)
    old = db.get(Plan, code)
    if old is None or old.user_id != user["key"]:
        raise HTTPException(status_code=404, detail="Plan not found")
    try:
        new = create_plan(db, user, {"answers": old.snapshot["answers"], "chosen_profile": old.snapshot["chosen_profile"], "acknowledged": bool(old.snapshot.get("acknowledgement", {}).get("version")), "amount_vnd": old.snapshot["amount_vnd"], "locale": user["locale"]})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return public_plan(new, user)


@router.post("/plans/{code}/share")
def create_share(code: str, request: Request, user: dict = Depends(require_roles("investor")), db: Session = Depends(get_db)):
    verify_csrf(request)
    plan = db.get(Plan, code)
    if plan is None or plan.user_id != user["key"]:
        raise HTTPException(status_code=404, detail="Plan not found")
    existing = db.execute(select(ShareLink).where(ShareLink.plan_code == code, ShareLink.revoked_at.is_(None))).scalars().first()
    if existing is None:
        token = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
        existing = ShareLink(token=token, plan_code=code)
        db.add(existing)
        db.commit()
    return {"token": existing.token, "path": f"/share/{existing.token}", "ips_path": f"/share/{existing.token}?print=1", "revoked": False}


@router.delete("/plans/{code}/share")
def revoke_share(code: str, request: Request, user: dict = Depends(require_roles("investor")), db: Session = Depends(get_db)):
    verify_csrf(request)
    plan = db.get(Plan, code)
    if plan is None or plan.user_id != user["key"]:
        raise HTTPException(status_code=404, detail="Plan not found")
    from datetime import datetime, timezone
    rows = db.execute(select(ShareLink).where(ShareLink.plan_code == code, ShareLink.revoked_at.is_(None))).scalars().all()
    for link in rows:
        link.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"revoked": True}


@router.get("/share/{token}")
def shared_plan(token: str, db: Session = Depends(get_db)):
    link = db.get(ShareLink, token)
    if link is None or link.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Shared plan not found")
    plan = db.get(Plan, link.plan_code)
    if plan is None:
        raise HTTPException(status_code=404, detail="Shared plan not found")
    data = public_plan(plan, {"role": "public"}, shared=True, ips=True)
    data["share_mode"] = "public"
    return data


@router.get("/print/plans/{code}")
def plan_for_print(code: str, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    plan = db.get(Plan, code)
    if plan is None or user["role"] == "reviewer" or (user["role"] == "investor" and plan.user_id != user["key"]):
        raise HTTPException(status_code=404, detail="Plan not found")
    return public_plan(plan, user, ips=True)
