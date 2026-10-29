"""Admin usage page: counts, units and balance only (P15)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from skinledger import copy, guards, usage
from skinledger.config import get_settings
from skinledger.db import connect, db_path
from skinledger.web.templating import templates
from skinledger.youcam import get_client

router = APIRouter()
logger = logging.getLogger(__name__)

SQLITE_FILES = ("skinledger.sqlite", "skinledger.sqlite-wal", "skinledger.sqlite-shm")


def files_outside_masks(data_dir: Path) -> int:
    """Files in DATA_DIR that are neither the SQLite database nor a mask."""
    count = 0
    for path in data_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(data_dir)
        if relative.parts and relative.parts[0] == "masks":
            continue
        if relative.name in SQLITE_FILES:
            continue
        count += 1
    return count


def _count(conn, sql: str, params: tuple[object, ...] = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def _balance_text(balance: float | None) -> str:
    if balance is None:
        return copy.ADMIN_UNAVAILABLE
    return f"{balance:.0f}"


@router.get("/admin/usage", response_class=HTMLResponse)
async def admin_usage(request: Request) -> HTMLResponse:
    """Header-only admin page; a missing or wrong X-Admin-Token looks like 404."""
    if not guards.is_admin_request(request):
        raise HTTPException(status_code=404, detail="Not found.")

    settings = get_settings()
    today = usage.guatemala_today()
    conn = connect(db_path())
    try:
        visitor_units_today = usage.visitor_units_for_day(
            conn, today, settings.units_per_analysis
        )
        visitor_units_total = usage.visitor_units_total(
            conn, settings.units_per_analysis
        )
        visitor_analyses_today = _count(
            conn,
            "SELECT COUNT(*) FROM api_usage WHERE day = ? AND is_admin = 0",
            (today,),
        )
        visitor_analyses_total = _count(
            conn, "SELECT COUNT(*) FROM api_usage WHERE is_admin = 0"
        )
        admin_units = _count(
            conn,
            "SELECT COALESCE(SUM(units), 0) FROM api_usage "
            "WHERE is_admin = 1 AND mode = 'real'",
        )
        admin_analyses = _count(
            conn, "SELECT COUNT(*) FROM api_usage WHERE is_admin = 1"
        )
        rejected = [
            {"error_code": row["error_code"] or "unknown", "count": int(row["count"])}
            for row in conn.execute(
                "SELECT error_code, COUNT(*) AS count FROM captures "
                "WHERE status IN ('error', 'timeout') AND units_charged = 0 "
                "GROUP BY error_code ORDER BY count DESC"
            ).fetchall()
        ]
    finally:
        conn.close()

    balance: float | None = None
    try:
        balance = await get_client().get_credit_balance()
    except Exception:  # balance is informational; never break the page
        logger.info("YouCam balance unavailable")
        balance = None

    analyses_left = max(
        0, settings.total_unit_cap - visitor_units_total
    ) // settings.units_per_analysis
    return templates.TemplateResponse(
        request,
        "admin_usage.html",
        {
            "visitor_analyses_today": visitor_analyses_today,
            "visitor_analyses_total": visitor_analyses_total,
            "visitor_units_today": visitor_units_today,
            "visitor_units_total": visitor_units_total,
            "admin_units": admin_units,
            "admin_analyses": admin_analyses,
            "analyses_left": analyses_left,
            "daily_cap": settings.daily_unit_cap,
            "total_cap": settings.total_unit_cap,
            "per_person_cap": settings.max_real_analyses_per_person,
            "allow_upload": settings.allow_upload,
            "balance": _balance_text(balance),
            "files_outside": files_outside_masks(settings.data_dir),
            "rejected": rejected,
        },
    )
