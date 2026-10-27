from __future__ import annotations

import gzip
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditLog, ResultFile, ResultVersion
from .versioning import create_manifest, load_result_files, validate_result_files

ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = ROOT / "pipeline" / "data" / "processed"
RAW_DIR = ROOT / "pipeline" / "data" / "raw"


def panel_end_month(processed_dir: Path = PROCESSED_DIR) -> pd.Timestamp:
    """Last month in the research panel (month-start timestamp)."""
    panel = pd.read_csv(processed_dir / "asset_panel_standardized.csv", usecols=["date"], parse_dates=["date"])
    return panel["date"].max().to_period("M").to_timestamp()


def panel_month_label(processed_dir: Path = PROCESSED_DIR) -> str:
    return panel_end_month(processed_dir).strftime("%m/%Y")


def version_label(processed_dir: Path, delta: float = 2.5, transaction_cost: float | None = None) -> str:
    """Nhãn phiên bản, ví dụ "07/2026 · δ 2,5 · phí theo lớp" hoặc "... · phí 0,15%"."""
    cost = "theo lớp" if transaction_cost is None else f"{transaction_cost:.2%}".replace(".", ",")
    return f"{panel_month_label(processed_dir)} · δ {f'{delta:g}'.replace('.', ',')} · phí {cost}"


def data_through_from_raw(raw_dir: Path = RAW_DIR, until: pd.Timestamp | None = None) -> dict[str, str]:
    """Latest raw observation per source, capped at `until` (the panel's last day).

    The panel deliberately stops at the last COMPLETE month, so raw rows after it
    (e.g. a partial month) are not part of the research data and are not reported.
    """
    def latest(dates: pd.Series) -> str | None:
        dates = pd.to_datetime(dates, errors="coerce").dropna()
        if until is not None:
            dates = dates[dates <= until]
        return dates.max().date().isoformat() if len(dates) else None

    through: dict[str, str] = {}
    stock_path = raw_dir / "all_stock_based_raw.csv"
    if stock_path.is_file():
        value = latest(pd.read_csv(stock_path)["time"])
        if value:
            through["stocks"] = value
    bond_path = raw_dir / "Vietnam_5-Year_Bond_Yield_Historical_Data.csv"
    if bond_path.is_file():
        bond = pd.read_csv(bond_path)
        value = latest(pd.to_datetime(bond["Date"], format="%m/%d/%Y", errors="coerce"))
        if value:
            through["bonds"] = value
    for source, filename, column in (
        ("gold_sjc", "gold_sjc_2020_2026_final.csv", "date"),
        ("deposit_12m", "deposit_rate_12m_2020_2026_final.csv", "date"),
    ):
        path = raw_dir / filename
        if path.is_file():
            value = latest(pd.read_csv(path)[column])
            if value:
                through[source] = value
    return through


def pipeline_source_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in sorted((ROOT / "pipeline").rglob("*.py")):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _decode_files(db: Session, version_id: str) -> dict[str, bytes]:
    result = db.execute(select(ResultFile).where(ResultFile.version_id == version_id)).scalars().all()
    if not result:
        raise FileNotFoundError(f"No immutable result files for version {version_id}")
    return {row.name: gzip.decompress(row.compressed_content) for row in result}


def load_frames(db: Session, version_id: str) -> dict[str, pd.DataFrame]:
    from .versioning import OPTIONAL_COLUMNS, REQUIRED_COLUMNS
    files = _decode_files(db, version_id)
    return {name: pd.read_csv(BytesIO(files[name])) for name in (*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS) if name in files}


def get_active_version(db: Session) -> ResultVersion:
    version = db.execute(select(ResultVersion).where(ResultVersion.status == "active")).scalars().first()
    if version is None:
        raise RuntimeError("No active result version has been imported")
    return version


def get_version(db: Session, version_id: str) -> ResultVersion | None:
    return db.get(ResultVersion, version_id)


def import_result_version(
    db: Session,
    processed_dir: Path,
    label: str,
    params: dict[str, Any],
    status: str = "draft",
    version_id: str | None = None,
    data_through: dict[str, str] | None = None,
) -> ResultVersion:
    files = load_result_files(processed_dir)
    validation = validate_result_files(files)
    if data_through is None:
        month_end = panel_end_month(processed_dir) + pd.offsets.MonthEnd(0)
        data_through = data_through_from_raw(until=month_end)
    manifest = create_manifest(files, label, params, data_through, None)
    manifest["validation"] = validation
    vid = version_id or f"v{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    checksum = manifest["panel_checksum"]
    manifest["source_origin"] = str(params.get("source", "project pipeline"))
    manifest["source_fingerprint"] = pipeline_source_fingerprint()
    row = ResultVersion(id=vid, label=label, status=(status if validation["valid"] else "invalid"), params=params, manifest=manifest, panel_checksum=checksum)
    for name, raw in files.items():
        row.result_files.append(ResultFile(version_id=vid, name=name, compressed_content=gzip.compress(raw, compresslevel=6), sha256=hashlib.sha256(raw).hexdigest()))
    db.add(row)
    db.flush()
    (ROOT / "results" / vid).mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        (ROOT / "results" / vid / name).write_bytes(raw)
    (ROOT / "results" / vid / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return row


def ensure_v1(db: Session) -> ResultVersion:
    v1 = db.get(ResultVersion, "v20261012-v1")
    if v1 is not None:
        return v1
    if db.execute(select(ResultVersion).where(ResultVersion.status == "active")).scalars().first():
        return get_active_version(db)
    params = {"delta": 2.5, "transaction_cost": "class_vector", "source": "pipeline QC round 4 (data/processed)"}
    v1 = import_result_version(db, PROCESSED_DIR, version_label(PROCESSED_DIR, 2.5, None), params, status="active", version_id="v20261012-v1")
    if v1.status == "invalid":
        raise RuntimeError("Uploaded V1 result files failed validation: " + "; ".join(v1.manifest["validation"]["reasons"]))
    v1.activated_at = datetime.now(timezone.utc)
    db.add(AuditLog(id=uuid.uuid4().hex, actor_id="admin", action="activate_version", entity="ResultVersion", entity_id=v1.id, after={"status": "active", "label": v1.label}))
    db.commit()
    db.refresh(v1)
    return v1


def version_public(version: ResultVersion, role: str) -> dict[str, Any]:
    base: dict[str, Any] = {"label": version.label, "status": version.status}
    if role in ("admin", "reviewer"):
        base.update({"id": version.id, "params": version.params, "created_at": version.created_at.isoformat(), "activated_at": version.activated_at.isoformat() if version.activated_at else None, "manifest": version.manifest})
    return base


def manifest_json(version: ResultVersion) -> str:
    return json.dumps(version.manifest, ensure_ascii=False, indent=2)
