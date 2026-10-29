"""CSP violation reports: always 204, log only directive/blocked/page (P15a)."""

from __future__ import annotations

import json
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, Request, Response

from skinledger import logs
from skinledger.web.security import REPORT_PATH

router = APIRouter()

MAX_BODY_BYTES = 8 * 1024
MAX_REPORTS_PER_WINDOW = 20
WINDOW_SECONDS = 60
_SAFE_TOKENS = frozenset({"inline", "eval"})

_reports: dict[str, list[float]] = {}


def reset_rate_limit() -> None:
    """Clear the in-memory per-IP bucket (tests start clean)."""
    _reports.clear()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _within_limit(ip: str, now: float | None = None) -> bool:
    moment = time.monotonic() if now is None else now
    recent = [stamp for stamp in _reports.get(ip, []) if moment - stamp < WINDOW_SECONDS]
    _reports[ip] = recent
    if len(recent) >= MAX_REPORTS_PER_WINDOW:
        return False
    recent.append(moment)
    return True


async def _read_body(request: Request) -> bytes | None:
    size = 0
    chunks: list[bytes] = []
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BODY_BYTES:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def _directive(value: object) -> str:
    text = str(value or "").split(";")[0].strip()
    token = text.split()[0] if text else ""
    return token[:50] or "unknown"


def _blocked(value: object) -> str:
    text = str(value or "")
    if text in _SAFE_TOKENS:
        return text
    if text.startswith("blob:"):
        return "blob"
    if text.startswith("data:"):
        return "data"
    split = urlsplit(text)
    if split.scheme and split.netloc:
        return f"{split.scheme}://{split.netloc}"
    return "unknown"


def _page(value: object) -> str:
    text = str(value or "")
    if not text:
        return "unknown"
    path = urlsplit(text).path
    return (path or "/")[:200]


def _reports_from_body(content_type: str, body: bytes) -> list[dict[str, object]]:
    try:
        data = json.loads(body)
    except (TypeError, ValueError):
        return []
    if "application/csp-report" in content_type:
        if isinstance(data, dict) and isinstance(data.get("csp-report"), dict):
            return [data["csp-report"]]
        return []
    if "application/reports+json" in content_type:
        if not isinstance(data, list):
            return []
        return [
            item["body"]
            for item in data
            if isinstance(item, dict)
            and item.get("type") == "csp-violation"
            and isinstance(item.get("body"), dict)
        ]
    return []


def _normalise(report: dict[str, object], legacy: bool) -> dict[str, str]:
    if legacy:
        directive = report.get("effective-directive") or report.get("violated-directive")
        blocked = report.get("blocked-uri")
        page = report.get("document-uri")
    else:
        directive = report.get("effectiveDirective") or report.get("violatedDirective")
        blocked = report.get("blockedURL")
        page = report.get("documentURL")
    return {
        "directive": _directive(directive),
        "blocked": _blocked(blocked),
        "page": _page(page),
    }


@router.post(REPORT_PATH, include_in_schema=False)
async def csp_report(request: Request) -> Response:
    """Accept a CSP report, log safe fields only and always answer 204."""
    ip = _client_ip(request)
    if not _within_limit(ip):
        return Response(status_code=204)

    content_type = request.headers.get("content-type", "")
    legacy = "application/csp-report" in content_type
    if not legacy and "application/reports+json" not in content_type:
        return Response(status_code=204)

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_BYTES:
                return Response(status_code=204)
        except ValueError:
            pass

    body = await _read_body(request)
    if body is None:
        return Response(status_code=204)
    for report in _reports_from_body(content_type, body):
        logs.log_event("csp.violation", **_normalise(report, legacy))
    return Response(status_code=204)
