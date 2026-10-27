from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from ..data.repository import import_result_version, version_label
from ..models import PipelineRun, SessionLocal

ROOT = Path(__file__).resolve().parents[3]
_PIPELINE_LOCK = threading.Lock()


def create_run(db, user: dict[str, Any], params: dict[str, Any]) -> PipelineRun:
    with _PIPELINE_LOCK:
        active = db.execute(select(PipelineRun).where(PipelineRun.status.in_(["queued", "running"]))).scalars().first()
        if active:
            raise RuntimeError("A pipeline run is already queued or running")
        row = PipelineRun(id=f"run-{uuid.uuid4().hex[:16]}", status="queued", stage="backtest", params=params, started_by=user["key"], started_at=datetime.now(timezone.utc), log_tail="Queued: isolated backtest run.")
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


def _append_log(run_id: str, text: str, status: str | None = None, finished: datetime | None = None, version_id: str | None = None) -> None:
    db = SessionLocal()
    try:
        row = db.get(PipelineRun, run_id)
        if not row:
            return
        row.log_tail = (row.log_tail + text)[-20_000:]
        if status:
            row.status = status
        if finished:
            row.finished_at = finished
        if version_id:
            row.result_version_id = version_id
        db.commit()
    finally:
        db.close()


def run_backtest_job(run_id: str, params: dict[str, Any]) -> None:
    root = ROOT / ".temp_pipeline_runs"
    root.mkdir(parents=True, exist_ok=True)
    work = root / f"{run_id}-{uuid.uuid4().hex[:6]}"
    started = time.monotonic()
    logs: list[str] = []
    try:
        _append_log(run_id, "\nPreparing a private working copy of pipeline source…\n", "running")
        shutil.copytree(ROOT / "pipeline", work)
        env = dict(os.environ)
        env.pop("PVN_TRANSACTION_COST", None)
        if params.get("transaction_cost") is not None:
            env["PVN_TRANSACTION_COST"] = str(params["transaction_cost"])
        env.update({
            "PVN_DELTA": str(params.get("delta", 2.5)),
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONPATH": str(work / "scripts"),
        })
        process = subprocess.Popen([sys.executable, str(work / "run.py"), "--stage", "backtest", "--no-open"], cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        lines: queue.Queue[str | None] = queue.Queue()

        def collect() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                lines.put(line)
            lines.put(None)

        reader = threading.Thread(target=collect, daemon=True)
        reader.start()
        last_update = time.monotonic()
        stream_closed = False
        while process.poll() is None or not stream_closed:
            try:
                line = lines.get(timeout=1)
                if line is None:
                    stream_closed = True
                else:
                    logs.append(line)
            except queue.Empty:
                pass
            now = time.monotonic()
            if now - last_update >= 3:
                _append_log(run_id, "".join(logs)[-2000:])
                logs.clear()
                last_update = now
            if now - started > 900 and process.poll() is None:
                process.kill()
                logs.append("\nTimeout: backtest exceeded 15 minutes.\n")
                break
        return_code = process.wait(timeout=5)
        logs.append(f"\nProcess exited with code {return_code}.\n")
        _append_log(run_id, "".join(logs))
        if return_code != 0:
            _append_log(run_id, "Backtest failed; active version was not changed.\n", "failed", datetime.now(timezone.utc))
            return

        cost = params.get("transaction_cost")
        params_label = version_label(work / "data" / "processed", float(params.get("delta", 2.5)), None if cost is None else float(cost))
        db = SessionLocal()
        try:
            version = import_result_version(
                db,
                work / "data" / "processed",
                params_label,
                {"delta": float(params.get("delta", 2.5)), "transaction_cost": "class_vector" if cost is None else float(cost), "note": params.get("note", ""), "stage": "backtest"},
                status="draft",
                data_through=None,
            )
            if version.status == "invalid":
                reasons = "; ".join(version.manifest.get("validation", {}).get("reasons", []))
                db.commit()
                _append_log(run_id, f"\nValidation rejected output: {reasons}\n", "failed", datetime.now(timezone.utc), version.id)
            else:
                db.commit()
                _append_log(run_id, f"\nVersion saved as draft: {version.id}\n", "succeeded", datetime.now(timezone.utc), version.id)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as exc:
        _append_log(run_id, f"\nRunner error: {type(exc).__name__}: {exc}\nActive version was not changed.\n", "failed", datetime.now(timezone.utc))
    finally:
        # The durable result CSV snapshot is in the database. Remove only this run's temporary copy.
        shutil.rmtree(work, ignore_errors=True)
