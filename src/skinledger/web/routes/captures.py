"""Capture route: raw image body in, analysis reserved and started (P04)."""

from __future__ import annotations

import sqlite3
from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from skinledger import copy, guards, imaging, pipeline, usage
from skinledger.aspects import ASPECT_LABELS, NUMERIC_ASPECTS
from skinledger.config import Settings, get_settings
from skinledger.db import connect, db_path
from skinledger.web.templating import templates
from skinledger.youcam import (
    YouCamConfigError,
    YouCamError,
    analysis_slot,
    friendly_message,
)

router = APIRouter()

STATUS_LABELS = {
    "queued": "Queued",
    "uploading": "Uploading…",
    "running": "Analyzing…",
    "success": "Done",
    "error": "Could not analyze",
    "timeout": "Still analyzing…",
}


def _image_error_message(code: str) -> str:
    return f"{friendly_message(code)} {copy.ATTEMPT_FREE}"


async def _read_body(request: Request) -> bytes:
    """Read the raw image body in memory, aborting as soon as it passes 10 MB."""
    limit = imaging.MAX_IMAGE_BYTES
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            too_large = int(content_length) > limit
        except ValueError:
            too_large = False
        if too_large:
            raise HTTPException(413, _image_error_message("error_exceed_max_image_size"))

    buffer = bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer) > limit:
            raise HTTPException(413, _image_error_message("error_exceed_max_image_size"))
    return bytes(buffer)


@router.post("/api/captures", response_class=HTMLResponse, status_code=202)
async def create_capture(
    request: Request,
    person_id: int,
    source: str,
    is_baseline_pair: int = 0,
    attested: int = 0,
) -> HTMLResponse:
    settings = get_settings()
    conn = connect(db_path())
    capture_id: int | None = None
    prepared: imaging.PreparedImage | None = None
    body = b""
    try:
        person = guards.authorize_person(conn, request, person_id)
        if person is None:
            raise HTTPException(status_code=404, detail="Person not found.")
        admin = guards.is_admin_request(request, settings)

        if not guards.has_current_consent(conn, person_id):
            raise HTTPException(status_code=403, detail=copy.CONSENT_REQUIRED)
        if attested != 1:
            raise HTTPException(status_code=400, detail=copy.ATTESTATION_REQUIRED)
        if source not in ("camera_kit", "upload"):
            raise HTTPException(status_code=400, detail="Unknown capture source.")
        if not admin and not guards.has_valid_invite(request, settings):
            raise HTTPException(status_code=403, detail=copy.INVITE_REQUIRED)
        if source == "upload" and not settings.allow_upload:
            raise HTTPException(status_code=403, detail=copy.UPLOAD_DISABLED)

        body = await _read_body(request)
        token = guards.owner_token_from_request(request)
        owner_hash = (
            guards.owner_token_hash(token) if token else guards.admin_owner_hash()
        )

        try:
            async with guards.cap_lock():
                if not admin:
                    guards.check_caps(conn, person_id, owner_hash, settings)
                prepared = imaging.prepare(body)
                capture_id = pipeline.create_capture(
                    conn,
                    person_id=person_id,
                    owner_token_hash=owner_hash,
                    source=source,
                    width=prepared.width,
                    height=prepared.height,
                    attested_at=usage.utc_now_iso(),
                    is_admin=admin,
                    is_baseline_pair=is_baseline_pair == 1,
                    data_label="SAMPLE" if settings.youcam_mock else "REAL",
                )
                conn.commit()
        except guards.CapExceeded as exc:
            raise HTTPException(status_code=429, detail=exc.message) from None
        except imaging.ImageRejected as exc:
            raise HTTPException(
                status_code=422, detail=_image_error_message(exc.code)
            ) from None
        finally:
            body = b""

        client = pipeline.get_client()
        try:
            async with analysis_slot():
                file_id = await client.upload_file(prepared)
                task_id = await client.create_task(file_id)
        except YouCamConfigError:
            _mark_failed(conn, capture_id, "config_error", copy.TRY_AGAIN_NO_UNITS)
            raise HTTPException(
                status_code=500, detail="Analysis is temporarily unavailable."
            ) from None
        except YouCamError as exc:
            code = getattr(exc, "code", None) or "unknown_internal_error"
            _mark_failed(conn, capture_id, code, exc.user_message)
            raise HTTPException(status_code=502, detail=exc.user_message) from None

        pipeline.set_capture_running(conn, capture_id, file_id, task_id)
        conn.commit()
        pipeline.spawn_finish(capture_id)
        return _render_status(
            conn, capture_id, request, settings, admin, status_code=202
        )
    finally:
        prepared = None
        body = b""
        conn.close()


@router.get("/people/{person_id}/capture", response_class=HTMLResponse)
async def capture_page(request: Request, person_id: int) -> HTMLResponse:
    settings = get_settings()
    conn = connect(db_path())
    try:
        person = guards.authorize_person(conn, request, person_id)
        if person is None:
            raise HTTPException(status_code=404, detail="Person not found.")
        admin = guards.is_admin_request(request, settings)
        if person["is_demo_public"] and not admin:
            raise HTTPException(status_code=403, detail=copy.DEMO_READ_ONLY)
        if not guards.has_current_consent(conn, person_id):
            return RedirectResponse(f"/people/{person_id}/consent", status_code=303)

        successes = conn.execute(
            "SELECT COUNT(*) FROM captures WHERE person_id = ? AND status = 'success' "
            "AND data_label IN ('REAL', 'SAMPLE')",
            (person_id,),
        ).fetchone()[0]
        has_band = conn.execute(
            "SELECT 1 FROM noise_bands WHERE person_id = ? LIMIT 1", (person_id,)
        ).fetchone() is not None
        baseline_step = None
        if not has_band and successes < 2:
            baseline_step = int(successes) + 1
        analyses_left = (
            None
            if admin
            else guards.person_analyses_left(
                conn, person_id, settings.max_real_analyses_per_person
            )
        )
    finally:
        conn.close()

    return templates.TemplateResponse(
        request,
        "capture.html",
        {
            "person": dict(person),
            "allow_upload": settings.allow_upload,
            "analyses_left": analyses_left,
            "max_analyses": settings.max_real_analyses_per_person,
            "baseline_step": baseline_step,
            "camera_language": settings.camera_kit_language,
        },
    )


@router.get("/media/{capture_id}/{file_name}")
async def mask_media(request: Request, capture_id: int, file_name: str) -> FileResponse:
    """Serve one stored mask to its owner, an admin or the public demo; never a photo."""
    if "/" in file_name or "\\" in file_name or file_name in (".", ".."):
        raise HTTPException(status_code=404, detail="File not found.")

    settings = get_settings()
    conn = connect(db_path())
    try:
        visibility = conn.execute(
            "SELECT p.is_demo_public FROM captures c JOIN persons p ON p.id = c.person_id "
            "WHERE c.id = ?",
            (capture_id,),
        ).fetchone()
        if visibility is None:
            raise HTTPException(status_code=404, detail="File not found.")
        allowed = visibility["is_demo_public"] == 1 or (
            guards.authorize_capture(conn, request, capture_id) is not None
        )
        if not allowed:
            raise HTTPException(status_code=404, detail="File not found.")
        rows = conn.execute(
            "SELECT file_path FROM masks WHERE capture_id = ?", (capture_id,)
        ).fetchall()
        target = next(
            (
                row["file_path"]
                for row in rows
                if PurePosixPath(row["file_path"]).name == file_name
            ),
            None,
        )
    finally:
        conn.close()

    if target is None:
        raise HTTPException(status_code=404, detail="File not found.")
    path = settings.data_dir / target
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(
        path, media_type="image/png", headers={"Cache-Control": "no-store"}
    )


@router.get("/api/captures/{capture_id}/status", response_class=HTMLResponse)
async def capture_status(request: Request, capture_id: int) -> HTMLResponse:
    settings = get_settings()
    conn = connect(db_path())
    try:
        row = guards.authorize_capture(conn, request, capture_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Capture not found.")
        admin = guards.is_admin_request(request, settings)
        return _render_status(conn, capture_id, request, settings, admin)
    finally:
        conn.close()


def _mark_failed(
    conn: sqlite3.Connection,
    capture_id: int | None,
    error_code: str,
    error_message: str,
) -> None:
    if capture_id is None:
        return
    pipeline.mark_capture_error(conn, capture_id, error_code, error_message)
    conn.commit()


def _render_status(
    conn: sqlite3.Connection,
    capture_id: int,
    request: Request,
    settings: Settings,
    admin: bool,
    status_code: int = 200,
) -> HTMLResponse:
    capture = conn.execute(
        "SELECT * FROM captures WHERE id = ?", (capture_id,)
    ).fetchone()
    analyses_left = (
        None
        if admin
        else guards.person_analyses_left(
            conn, capture["person_id"], settings.max_real_analyses_per_person
        )
    )
    mask_rows = conn.execute(
        "SELECT aspect, file_path FROM masks WHERE capture_id = ? ORDER BY id",
        (capture_id,),
    ).fetchall()
    masks = [
        {
            "aspect": row["aspect"],
            "file_name": PurePosixPath(row["file_path"]).name,
        }
        for row in mask_rows
    ]
    return templates.TemplateResponse(
        request,
        "capture_status.html",
        {
            "capture": dict(capture),
            "status_label": STATUS_LABELS.get(capture["status"], capture["status"]),
            "scores": _score_rows(conn, capture_id),
            "analyses_left": analyses_left,
            "masks": masks,
        },
        status_code=status_code,
    )


def _score_rows(conn: sqlite3.Connection, capture_id: int) -> list[dict[str, str | float]]:
    """The 16 headline scores: 15 numeric aspects plus the whole-face skin type."""
    rows = conn.execute(
        "SELECT aspect, raw_score, value_text FROM aspect_scores WHERE capture_id = ?",
        (capture_id,),
    ).fetchall()
    stored = {row["aspect"]: row for row in rows}
    result: list[dict[str, str | float]] = []
    for aspect in NUMERIC_ASPECTS:
        row = stored.get(aspect)
        value = row["raw_score"] if row is not None and row["raw_score"] is not None else "—"
        result.append({"label": ASPECT_LABELS[aspect], "value": value})
    whole = stored.get("skin_type_whole")
    value = whole["value_text"] if whole is not None and whole["value_text"] else "—"
    result.append({"label": "Skin type (whole)", "value": value})
    return result
