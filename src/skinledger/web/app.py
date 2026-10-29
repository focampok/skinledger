"""FastAPI application: health check, static shell, security headers and PWA entry points."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from skinledger import copy, seed, usage
from skinledger.config import get_settings
from skinledger.db import connect, db_path, init_db
from skinledger.logs import configure_logging
from skinledger.pipeline import resume_pending
from skinledger.web.home import home_context
from skinledger.web.routes.admin import router as admin_router
from skinledger.web.routes.captures import router as captures_router
from skinledger.web.routes.client_log import router as client_log_router
from skinledger.web.routes.csp import router as csp_router
from skinledger.web.routes.demo import router as demo_router
from skinledger.web.routes.persons import router as persons_router
from skinledger.web.routes.products import router as products_router
from skinledger.web.routes.routine import router as routine_router
from skinledger.web.routes.timeline import router as timeline_router
from skinledger.web.routes.try_ import router as try_router
from skinledger.web.routes.verdicts import router as verdicts_router
from skinledger.web.security import REPORT_PATH, is_capture_path, security_headers
from skinledger.web.templating import WEB_DIR, templates

configure_logging()
logger = logging.getLogger(__name__)

STATIC_DIR = WEB_DIR / "static"


def _validate_production_settings() -> None:
    """Refuse a production start with mock mode or empty secrets; log names only."""
    settings = get_settings()
    if not settings.railway_environment:
        return
    missing: list[str] = []
    if settings.youcam_mock:
        missing.append("YOUCAM_MOCK")
    if not settings.invite_code.get_secret_value():
        missing.append("INVITE_CODE")
    if not settings.admin_token.get_secret_value():
        missing.append("ADMIN_TOKEN")
    if not missing:
        return
    for name in missing:
        logger.error("Production startup refused: %s is missing or invalid", name)
    raise RuntimeError(
        "Refusing to start in production; missing or invalid: " + ", ".join(missing)
    )


def _seed_sample_on_start() -> None:
    settings = get_settings()
    if not settings.seed_sample_on_start:
        return
    conn = connect(db_path())
    try:
        seed.ensure_sample_person(conn, usage.guatemala_day())
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Check production config, create the schema, resume tasks and seed the sample."""
    _validate_production_settings()
    init_db()
    await resume_pending()
    _seed_sample_on_start()
    yield


app = FastAPI(title="SkinLedger", lifespan=lifespan)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    settings = get_settings()
    origin = str(request.base_url).rstrip("/")
    headers = security_headers(
        report_only=settings.csp_report_only,
        report_url=f"{origin}{REPORT_PATH}",
        capture=is_capture_path(request.url.path),
    )
    for name, value in headers.items():
        response.headers.setdefault(name, value)
    return response


@app.middleware("http")
async def head_answers_like_get(request: Request, call_next):
    """Answer HEAD with GET's status and headers but no body.

    Registered after the security middleware so it wraps it and the headers survive.
    Every page route is declared GET-only, so without this a HEAD probe gets 405.
    """
    if request.method != "HEAD":
        return await call_next(request)
    request.scope["method"] = "GET"
    response = await call_next(request)
    body = b"".join([chunk async for chunk in response.body_iterator])
    headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
    out = Response(status_code=response.status_code, headers=headers)
    # HEAD must advertise the length GET would return, but send no body.
    out.headers["content-length"] = str(len(body))
    return out


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(admin_router)
app.include_router(captures_router)
app.include_router(client_log_router)
app.include_router(csp_router)
app.include_router(demo_router)
app.include_router(persons_router)
app.include_router(products_router)
app.include_router(routine_router)
app.include_router(timeline_router)
app.include_router(try_router)
app.include_router(verdicts_router)


@app.get("/healthz")
async def healthz() -> dict[str, bool]:
    """Liveness probe used by Railway."""
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", home_context(request))


@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request) -> HTMLResponse:
    """Privacy page; the capture page links here."""
    return templates.TemplateResponse(
        request,
        "privacy.html",
        {"privacy_title": copy.PRIVACY_TITLE, "privacy_text": copy.PRIVACY_TEXT},
    )


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
