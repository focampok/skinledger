"""Guards: cookies, invite code, attestation and unit caps (P04, reused by P06)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import sqlite3
from contextlib import asynccontextmanager

from fastapi import Request, Response

from skinledger import copy, usage
from skinledger.config import Settings, get_settings

OWNER_COOKIE = "sl_owner"
INVITE_COOKIE = "sl_invite"
OWNER_COOKIE_MAX_AGE = 365 * 24 * 3600
INVITE_COOKIE_MAX_AGE = 30 * 24 * 3600

COUNTED_STATUSES = ("queued", "uploading", "running", "success", "timeout")
IN_FLIGHT_STATUSES = ("queued", "uploading", "running")

_OWNER_CONTEXT = b"skinledger-owner-v1"
_INVITE_CONTEXT = b"skinledger-invite-v1"
_ADMIN_OWNER_HASH = hashlib.sha256(b"skinledger-admin-session").hexdigest()

_cap_lock = asyncio.Lock()


class CapExceeded(Exception):
    """A visitor analysis would exceed a per-person, per-browser, daily or total cap."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@asynccontextmanager
async def cap_lock():
    """Serialize the cap check and the capture reservation in this process."""
    async with _cap_lock:
        yield


# -- cookies -----------------------------------------------------------------


def new_owner_token() -> str:
    return secrets.token_urlsafe(32)


def owner_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def admin_owner_hash() -> str:
    return _ADMIN_OWNER_HASH


def _owner_signature(token: str) -> str:
    # The 256-bit token is the bearer credential; the HMAC binds the cookie to it
    # and makes accidental or partial tampering detectable.
    return hmac.new(token.encode("utf-8"), _OWNER_CONTEXT, hashlib.sha256).hexdigest()


def encode_owner_cookie(token: str) -> str:
    return f"{token}.{_owner_signature(token)}"


def decode_owner_cookie(raw: str | None) -> str | None:
    if not raw or "." not in raw:
        return None
    token, signature = raw.rsplit(".", 1)
    if not token or not hmac.compare_digest(signature, _owner_signature(token)):
        return None
    return token


def owner_token_from_request(request: Request) -> str | None:
    return decode_owner_cookie(request.cookies.get(OWNER_COOKIE))


def set_owner_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        OWNER_COOKIE,
        encode_owner_cookie(token),
        max_age=OWNER_COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def _invite_signature(code: str) -> str:
    return hmac.new(code.encode("utf-8"), _INVITE_CONTEXT, hashlib.sha256).hexdigest()


def encode_invite_cookie(code: str) -> str:
    return f"{code}.{_invite_signature(code)}"


def invite_cookie_is_valid(raw: str | None, current_code: str) -> bool:
    if not raw or not current_code or "." not in raw:
        return False
    code, signature = raw.rsplit(".", 1)
    if not hmac.compare_digest(code, current_code):
        return False
    return hmac.compare_digest(signature, _invite_signature(code))


def set_invite_cookie(response: Response, code: str) -> None:
    response.set_cookie(
        INVITE_COOKIE,
        encode_invite_cookie(code),
        max_age=INVITE_COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def has_valid_invite(request: Request, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    current_code = settings.invite_code.get_secret_value()
    return invite_cookie_is_valid(request.cookies.get(INVITE_COOKIE), current_code)


def is_admin_request(request: Request, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    token = settings.admin_token.get_secret_value()
    provided = request.headers.get("X-Admin-Token")
    if not token or not provided:
        return False
    return hmac.compare_digest(provided, token)


# -- authorization -----------------------------------------------------------


def authorize_person(
    conn: sqlite3.Connection, request: Request, person_id: int
) -> sqlite3.Row | None:
    """Return the person when this browser owns it, or when the request is admin."""
    person = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
    if person is None:
        return None
    if is_admin_request(request):
        return person
    token = owner_token_from_request(request)
    if not token:
        return None
    if not hmac.compare_digest(person["owner_token_hash"], owner_token_hash(token)):
        return None
    return person


def authorize_person_read(
    conn: sqlite3.Connection, request: Request, person_id: int
) -> sqlite3.Row | None:
    """The person for a read page: owner, admin, or any visitor for the public demo."""
    person = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
    if person is None:
        return None
    if person["is_demo_public"]:
        return person
    return authorize_person(conn, request, person_id)


def demo_person(
    conn: sqlite3.Connection, person_id: int
) -> sqlite3.Row | None:
    """The person when it is the public demo, so write routes can answer 403."""
    person = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
    if person is not None and person["is_demo_public"]:
        return person
    return None


def authorize_capture(
    conn: sqlite3.Connection, request: Request, capture_id: int
) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT c.*, p.owner_token_hash AS person_owner_hash "
        "FROM captures c JOIN persons p ON p.id = c.person_id WHERE c.id = ?",
        (capture_id,),
    ).fetchone()
    if row is None:
        return None
    if is_admin_request(request):
        return row
    token = owner_token_from_request(request)
    if not token:
        return None
    if not hmac.compare_digest(row["person_owner_hash"], owner_token_hash(token)):
        return None
    return row


def has_current_consent(conn: sqlite3.Connection, person_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM consents WHERE person_id = ? AND adult_confirmed = 1 "
        "AND revoked_at IS NULL ORDER BY id DESC LIMIT 1",
        (person_id,),
    ).fetchone()
    return row is not None


# -- caps --------------------------------------------------------------------


def count_person_analyses(conn: sqlite3.Connection, person_id: int) -> int:
    placeholders = ", ".join("?" for _ in COUNTED_STATUSES)
    row = conn.execute(
        "SELECT COUNT(*) FROM captures WHERE person_id = ? AND is_admin = 0 "
        f"AND data_label IN ('REAL', 'SAMPLE') AND status IN ({placeholders})",
        (person_id, *COUNTED_STATUSES),
    ).fetchone()
    return int(row[0])


def count_browser_analyses(conn: sqlite3.Connection, owner_hash: str) -> int:
    placeholders = ", ".join("?" for _ in IN_FLIGHT_STATUSES)
    used = conn.execute(
        "SELECT COUNT(*) FROM api_usage WHERE owner_token_hash = ? AND is_admin = 0",
        (owner_hash,),
    ).fetchone()[0]
    in_flight = conn.execute(
        "SELECT COUNT(*) FROM captures WHERE owner_token_hash = ? AND is_admin = 0 "
        f"AND status IN ({placeholders})",
        (owner_hash, *IN_FLIGHT_STATUSES),
    ).fetchone()[0]
    return int(used) + int(in_flight)


def count_in_flight_captures(conn: sqlite3.Connection) -> int:
    placeholders = ", ".join("?" for _ in IN_FLIGHT_STATUSES)
    row = conn.execute(
        f"SELECT COUNT(*) FROM captures WHERE is_admin = 0 "
        f"AND status IN ({placeholders})",
        IN_FLIGHT_STATUSES,
    ).fetchone()
    return int(row[0])


def person_analyses_left(conn: sqlite3.Connection, person_id: int, limit: int) -> int:
    return max(0, limit - count_person_analyses(conn, person_id))


def check_caps(
    conn: sqlite3.Connection,
    person_id: int,
    owner_hash: str,
    settings: Settings | None = None,
) -> None:
    """Raise CapExceeded when a visitor analysis would exceed any cap."""
    settings = settings or get_settings()
    limit = settings.max_real_analyses_per_person
    units = settings.units_per_analysis

    if count_person_analyses(conn, person_id) >= limit:
        raise CapExceeded(f"{copy.LIMIT_REACHED} You've used your {limit} analyses.")
    if count_browser_analyses(conn, owner_hash) >= limit:
        raise CapExceeded(f"{copy.LIMIT_REACHED} You've used your {limit} analyses.")

    in_flight_units = count_in_flight_captures(conn) * units
    used_today = usage.visitor_units_for_day(conn, usage.guatemala_today(), units)
    if used_today + in_flight_units + units > settings.daily_unit_cap:
        raise CapExceeded(copy.LIMIT_REACHED)

    used_total = usage.visitor_units_total(conn, units)
    if used_total + in_flight_units + units > settings.total_unit_cap:
        raise CapExceeded(copy.LIMIT_REACHED)
