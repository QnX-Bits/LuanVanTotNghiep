from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .api.admin_routes import router as admin_router
from .api.analysis_routes import router as analysis_router
from .api.auth_routes import router as auth_router
from .api.data_routes import router as data_router
from .api.plan_routes import router as plan_router
from .models import SessionLocal
from .seed import seed_demo

app = FastAPI(title="PortfolioVN API", version="1.0.0", docs_url="/api/docs", redoc_url=None)


class PrivateNoStoreMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "private, no-store"
        return response


app.add_middleware(PrivateNoStoreMiddleware)
app.include_router(auth_router)
app.include_router(data_router)
app.include_router(plan_router)
app.include_router(analysis_router)
app.include_router(admin_router)


@app.on_event("startup")
def startup() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    command.upgrade(Config(str(backend_dir / "alembic.ini")), "head")
    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "PortfolioVN"}


DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
ASSET_DIR = DIST / "assets"
if ASSET_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=ASSET_DIR), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith(("api/", "manus-oauth/", "manus-storage/", "__manus/", "__system__/")):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    candidate = (DIST / path).resolve()
    try:
        candidate.relative_to(DIST.resolve())
    except ValueError:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    if candidate.is_file():
        return FileResponse(candidate)
    index = DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    return JSONResponse({"detail": "Frontend build is not available"}, status_code=503)
