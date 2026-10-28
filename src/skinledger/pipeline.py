"""Analysis pipeline: in-memory bytes to YouCam, then store raw scores and masks (P04)."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image

from skinledger import copy, usage
from skinledger.aspects import NUMERIC_ASPECTS
from skinledger.config import Settings, get_settings
from skinledger.db import connect, db_path
from skinledger.youcam import (
    SKIN_TYPE_REGIONS,
    TaskResult,
    YouCamClient,
    YouCamError,
    YouCamTaskError,
    get_client,
)

logger = logging.getLogger(__name__)

TASK_RETENTION_DAYS = 30

_background_tasks: set[asyncio.Task[None]] = set()


def spawn_finish(capture_id: int) -> None:
    """Start the background analysis and keep a strong reference to the task."""
    task = asyncio.create_task(finish_analysis(capture_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def create_capture(
    conn: sqlite3.Connection,
    *,
    person_id: int,
    owner_token_hash: str,
    source: str,
    width: int,
    height: int,
    attested_at: str,
    is_admin: bool,
    is_baseline_pair: bool,
    data_label: str,
) -> int:
    """Reserve an analysis row before any YouCam call so caps see it in flight."""
    now = usage.utc_now_iso()
    cursor = conn.execute(
        "INSERT INTO captures (person_id, owner_token_hash, captured_at, data_label, source, "
        "attested_at, is_admin, width, height, status, is_baseline_pair, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploading', ?, ?)",
        (
            person_id,
            owner_token_hash,
            now,
            data_label,
            source,
            attested_at,
            int(is_admin),
            width,
            height,
            int(is_baseline_pair),
            now,
        ),
    )
    return int(cursor.lastrowid or 0)


def set_capture_running(
    conn: sqlite3.Connection, capture_id: int, file_id: str, task_id: str
) -> None:
    conn.execute(
        "UPDATE captures SET file_id = ?, task_id = ?, status = 'running' WHERE id = ?",
        (file_id, task_id, capture_id),
    )


def mark_capture_error(
    conn: sqlite3.Connection, capture_id: int, error_code: str, error_message: str
) -> None:
    conn.execute(
        "UPDATE captures SET status = 'error', error_code = ?, error_message = ?, "
        "units_charged = 0 WHERE id = ? AND status IN "
        "('queued', 'uploading', 'running', 'timeout')",
        (error_code, error_message, capture_id),
    )


async def finish_analysis(capture_id: int) -> None:
    """Poll the YouCam task, then store scores, masks, the raw JSON and the usage row."""
    settings = get_settings()
    conn = connect(db_path())
    try:
        capture = conn.execute(
            "SELECT * FROM captures WHERE id = ?", (capture_id,)
        ).fetchone()
        if capture is None or capture["status"] not in ("running", "timeout"):
            return
        task_id = capture["task_id"]
        if not task_id:
            mark_capture_error(conn, capture_id, "interrupted_upload", copy.TRY_AGAIN_NO_UNITS)
            conn.commit()
            return

        client = get_client()
        try:
            result = await client.poll(task_id)
        except YouCamTaskError as exc:
            mark_capture_error(conn, capture_id, exc.error_code, exc.user_message)
            conn.commit()
            return
        except YouCamError as exc:
            code = getattr(exc, "code", None) or "unknown_internal_error"
            mark_capture_error(conn, capture_id, code, exc.user_message)
            conn.commit()
            return

        if result.status == "timeout":
            conn.execute(
                "UPDATE captures SET status = 'timeout' WHERE id = ? "
                "AND status IN ('running', 'timeout')",
                (capture_id,),
            )
            conn.commit()
            return

        await _store_success(conn, capture, result, client, settings)
    except Exception:
        logger.exception("Analysis capture %s failed unexpectedly", capture_id)
        try:
            mark_capture_error(
                conn, capture_id, "unknown_internal_error", copy.TRY_AGAIN_NO_UNITS
            )
            conn.commit()
        except sqlite3.Error:
            logger.warning("Could not mark capture %s as failed", capture_id)
    finally:
        conn.close()


async def _store_success(
    conn: sqlite3.Connection,
    capture: sqlite3.Row,
    result: TaskResult,
    client: YouCamClient,
    settings: Settings,
) -> None:
    mask_rows = await _download_masks(capture, result, client, settings)
    charged = 0 if settings.youcam_mock else settings.units_per_analysis
    mode = "mock" if settings.youcam_mock else "real"

    current = conn.execute(
        "SELECT status FROM captures WHERE id = ?", (capture["id"],)
    ).fetchone()
    if current is None or current["status"] not in ("running", "timeout"):
        return

    try:
        for aspect, raw_score, value_text in _score_rows(result):
            conn.execute(
                "INSERT INTO aspect_scores (capture_id, aspect, raw_score, value_text) "
                "VALUES (?, ?, ?, ?)",
                (capture["id"], aspect, raw_score, value_text),
            )
        for aspect, relative_path in mask_rows:
            conn.execute(
                "INSERT INTO masks (capture_id, aspect, file_path) VALUES (?, ?, ?)",
                (capture["id"], aspect, relative_path),
            )
        conn.execute(
            "UPDATE captures SET status = 'success', raw_result_json = ?, "
            "units_charged = ? WHERE id = ?",
            (json.dumps(result.raw), charged, capture["id"]),
        )
        conn.execute(
            "INSERT INTO api_usage "
            "(capture_id, owner_token_hash, day, units, mode, is_admin) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                capture["id"],
                capture["owner_token_hash"],
                usage.guatemala_today(),
                charged,
                mode,
                int(capture["is_admin"]),
            ),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise


def _score_rows(result: TaskResult) -> list[tuple[str, float | None, str | None]]:
    """15 numeric aspects as raw_score; the three skin-type regions as value_text."""
    rows: list[tuple[str, float | None, str | None]] = []
    for aspect in NUMERIC_ASPECTS:
        if aspect in result.scores:
            rows.append((aspect, result.scores[aspect], None))
    for region in SKIN_TYPE_REGIONS:
        key = f"skin_type_{region}"
        value = result.categorical.get(key)
        if value is not None:
            rows.append((key, None, value))
    return rows


async def _download_masks(
    capture: sqlite3.Row,
    result: TaskResult,
    client: YouCamClient,
    settings: Settings,
) -> list[tuple[str, str]]:
    """Download only the mask keys the parser exposes; never resize_image."""
    if not settings.store_masks:
        return []
    written: list[tuple[str, str]] = []
    for aspect, urls in result.mask_urls.items():
        for index, url in enumerate(urls):
            try:
                data = await client.download(url, task_id=capture["task_id"])
            except YouCamError:
                logger.warning("Could not download the mask for aspect %s", aspect)
                continue
            refusal = _mask_refusal_reason(data)
            if refusal:
                logger.warning(
                    "Refusing to store the mask for aspect %s: %s", aspect, refusal
                )
                continue
            safe_aspect = re.sub(r"[^A-Za-z0-9_.-]", "_", aspect)
            relative = (
                Path("masks")
                / str(capture["person_id"])
                / str(capture["id"])
                / f"{safe_aspect}_{index}.png"
            )
            target = settings.data_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            written.append((aspect, str(relative)))
    return written


def _mask_refusal_reason(data: bytes) -> str | None:
    """Masks may never be the face photo; refuse opaque RGB and unreadable bytes."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.mode == "RGB":
                return "RGB without alpha"
    except Exception:
        return "unreadable image"
    return None


async def resume_pending() -> None:
    """Resume recent running tasks and fail tasks whose photo was already discarded."""
    conn = connect(db_path())
    resume_ids: list[int] = []
    try:
        for row in conn.execute(
            "SELECT id FROM captures WHERE status = 'uploading'"
        ).fetchall():
            mark_capture_error(conn, row["id"], "interrupted_upload", copy.TRY_AGAIN_NO_UNITS)
        for row in conn.execute(
            "SELECT id, task_id, created_at FROM captures "
            "WHERE status IN ('running', 'timeout')"
        ).fetchall():
            if not row["task_id"]:
                mark_capture_error(
                    conn, row["id"], "interrupted_upload", copy.TRY_AGAIN_NO_UNITS
                )
            elif _older_than_days(row["created_at"], TASK_RETENTION_DAYS):
                mark_capture_error(conn, row["id"], "task_expired", copy.TASK_EXPIRED)
            else:
                resume_ids.append(row["id"])
        conn.commit()
    finally:
        conn.close()

    for capture_id in resume_ids:
        spawn_finish(capture_id)


def _older_than_days(created_at: str, days: int) -> bool:
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return usage.utc_now() - created > timedelta(days=days)
