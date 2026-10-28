"""FastAPI application: health check, static shell and the PWA entry points."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from skinledger import copy
from skinledger.db import init_db

WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"

templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
templates.env.globals.update(
    disclaimer=copy.DISCLAIMER,
    powered_by=copy.POWERED_BY,
)

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Create the SQLite schema on startup; the migration is idempotent."""
    init_db()
    yield


app = FastAPI(title="SkinLedger", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    """Liveness probe used by Railway."""
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@app.get("/offline", response_class=HTMLResponse)
async def offline(request: Request) -> HTMLResponse:
    """Shell shown by the service worker when a page cannot be fetched."""
    return templates.TemplateResponse(request, "offline.html")


@app.get("/sw.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    """Serve the service worker from the origin root so it can control the whole app."""
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )
