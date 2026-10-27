from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..data.repository import load_frames
from ..domain.news import generate_auto_articles
from ..models import AuditLog, NewsArticle, Plan, ResultVersion


def activate_version(db: Session, version_id: str, actor: str) -> ResultVersion:
    candidate = db.get(ResultVersion, version_id)
    if candidate is None:
        raise LookupError("Version not found")
    if candidate.status not in ("draft", "archived"):
        raise ValueError("Only a valid draft or archived version may be activated")
    if not candidate.manifest.get("validation", {}).get("valid"):
        raise ValueError("Version validation did not pass")
    if candidate.manifest.get("row_counts", {}).get("performance_summary.csv") != 63 or candidate.manifest.get("row_counts", {}).get("allocation_current.csv") != 63:
        raise ValueError("Version does not contain the required 63-row outputs")

    previous = db.execute(select(ResultVersion).where(ResultVersion.status == "active").with_for_update()).scalars().all()
    if len(previous) > 1:
        raise RuntimeError("More than one active result version exists")
    old_id = previous[0].id if previous else None
    now = datetime.now(timezone.utc)
    for row in previous:
        row.status = "archived"
    candidate.status = "active"
    candidate.activated_at = now

    # If market panel checksum changes, supersede old generated articles and publish the new deterministic set.
    if old_id is None or db.get(ResultVersion, old_id).panel_checksum != candidate.panel_checksum:
        if old_id:
            old_articles = db.execute(select(NewsArticle).where(NewsArticle.version_id == old_id, NewsArticle.auto_key.is_not(None))).scalars().all()
            for article in old_articles:
                article.status = "superseded"
                if article.article:
                    article.article = {**article.article, "status": "superseded"}
        panel = load_frames(db, candidate.id)["asset_panel_standardized.csv"]
        for article in generate_auto_articles(panel, candidate.label, candidate.manifest.get("provisional_month")):
            key = f"{article['kind']}:{article['period']}:{','.join(article.get('asset_tags', []))}:{candidate.panel_checksum}"
            exists = db.execute(select(NewsArticle).where(NewsArticle.auto_key == key)).scalars().first()
            if exists:
                exists.status = "published"
                exists.version_id = candidate.id
                exists.published_at = now
                continue
            article["version_id"] = candidate.id
            db.add(NewsArticle(slug=article["slug"], kind=article["kind"], period=article["period"], status="published", article=article, auto_key=key, panel_checksum=candidate.panel_checksum, version_id=candidate.id, published_at=now))
    db.add(AuditLog(id=uuid.uuid4().hex, actor_id=actor, action="activate_version", entity="ResultVersion", entity_id=candidate.id, before={"active_version_id": old_id}, after={"active_version_id": candidate.id, "label": candidate.label}))
    db.flush()
    return candidate
