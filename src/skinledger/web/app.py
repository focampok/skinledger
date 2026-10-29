"""FastAPI application: health check, static shell and the PWA entry points."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from skinledger.db import init_db
from skinledger.logs import configure_logging
from skinledger.pipeline import resume_pending
from skinledger.web.routes.captures import router as captures_router
from skinledger.web.routes.client_log import router as client_log_router
from skinledger.web.routes.persons import router as persons_router
from skinledger.web.routes.products import router as products_router
from skinledger.web.routes.timeline import router as timeline_router
from skinledger.web.routes.try_ import router as try_router
from skinledger.web.templating import WEB_DIR, templates

configure_logging()

STATIC_DIR = WEB_DIR / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Create the SQLite schema on startup and resume recent YouCam tasks."""
    init_db()
    await resume_pending()
    yield


app = FastAPI(title="SkinLedger", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(captures_router)
app.include_router(client_log_router)
app.include_router(persons_router)
app.include_router(products_router)
app.include_router(timeline_router)
app.include_router(try_router)


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
