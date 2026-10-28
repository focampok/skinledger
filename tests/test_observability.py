"""P05b acceptance tests: structured server events, redaction and the client log bridge."""

from __future__ import annotations

import io
import json
import logging
import re
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from skinledger import config, guards, logs, pipeline, usage
from skinledger.db import connect, db_path, init_db
from skinledger.web.app import app
from skinledger.web.routes import try_ as try_routes
from skinledger.web.routes.client_log import reset_client_log_attempts
from skinledger.youcam import YouCamClient

OWNER_TOKEN = "owner-token-secret-value"
INVITE = "invite-secret-42"
ADMIN = "admin-secret-42"
API_KEY = "youcam-secret-42"
DISPLAY_NAME = "Hidden Person Name"
EVENT_LINE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}-06:00 "
    r"(DEBUG|INFO|WARNING|ERROR) [a-z][a-z0-9_.-]*( .*)?$"
)


async def _no_sleep(_seconds: float) -> None:
    return None


def jpeg_bytes(size=(800, 1000)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (180, 140, 120)).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = config.settings
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "youcam_mock", True)
    monkeypatch.setattr(settings, "youcam_api_key", SecretStr(API_KEY))
    monkeypatch.setattr(settings, "invite_code", SecretStr(INVITE))
    monkeypatch.setattr(settings, "admin_token", SecretStr(ADMIN))
    monkeypatch.setattr(settings, "allow_upload", True)
    monkeypatch.setattr(settings, "store_masks", True)
    monkeypatch.setattr(settings, "max_real_analyses_per_person", 2)
    monkeypatch.setattr(settings, "daily_unit_cap", 96)
    monkeypatch.setattr(settings, "total_unit_cap", 480)
    monkeypatch.setattr(settings, "units_per_analysis", 16)
    monkeypatch.setattr(
        pipeline, "get_client", lambda: YouCamClient(mock=True, poll_interval=0, sleep=_no_sleep)
    )
    init_db()
    return settings


@pytest.fixture
def web(env):
    with TestClient(app, base_url="https://testserver") as client:
        yield client


def event_lines(caplog) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == logs.EVENT_LOGGER
    ]


def wait_final(client: TestClient, capture_id: int, timeout: float = 8.0) -> str:
    deadline = time.monotonic() + timeout
    text = ""
    while time.monotonic() < deadline:
        response = client.get(f"/api/captures/{capture_id}/status")
        assert response.status_code == 200
        text = response.text
        if 'data-status="success"' in text or 'data-status="error"' in text:
            return text
        time.sleep(0.02)
    raise AssertionError(f"capture did not finish: {text}")


def latest_capture_id() -> int:
    conn = connect(db_path())
    try:
        row = conn.execute("SELECT id FROM captures ORDER BY id DESC LIMIT 1").fetchone()
        return int(row["id"])
    finally:
        conn.close()


def create_profile(client: TestClient) -> int:
    response = client.post(
        "/people/new", data={"display_name": DISPLAY_NAME}, follow_redirects=False
    )
    assert response.status_code == 303
    person_id = int(response.headers["location"].split("/")[2])
    consent = client.post(
        f"/people/{person_id}/consent",
        data={"adult_confirmed": "1", "agree": "1"},
        follow_redirects=False,
    )
    assert consent.status_code == 303
    return person_id


def test_full_mock_analysis_logs_events_without_secrets(env, web, caplog):
    caplog.set_level(logging.DEBUG, logger=logs.EVENT_LOGGER)
    person_id = create_profile(web)
    cookie_value = web.cookies.get(guards.OWNER_COOKIE)
    assert cookie_value is not None
    web.cookies.set(guards.INVITE_COOKIE, guards.encode_invite_cookie(INVITE))

    response = web.post(
        "/api/captures",
        params={
            "person_id": person_id,
            "source": "camera_kit",
            "is_baseline_pair": 0,
            "attested": 1,
        },
        content=jpeg_bytes(),
        headers={"Content-Type": "image/jpeg"},
    )
    assert response.status_code == 202
    capture_id = latest_capture_id()
    wait_final(web, capture_id)

    lines = event_lines(caplog)
    text = "\n".join(lines)
    assert lines and all(EVENT_LINE.match(line) for line in lines)
    for event in (
        "person.created",
        "consent.accepted",
        "image.prepared",
        "capture.reserved",
        "youcam.file_created",
        "youcam.put_done",
        "youcam.task_created",
        "youcam.poll",
        "youcam.success",
        "masks.saved",
        "usage.recorded",
    ):
        assert event in text, event
    assert f"capture_id={capture_id}" in text
    assert "task_status=running" in text
    assert "mode=mock" in text

    for secret in (
        DISPLAY_NAME,
        INVITE,
        ADMIN,
        API_KEY,
        OWNER_TOKEN,
        cookie_value,
        "Authorization",
        "Bearer",
        "signature=",
    ):
        assert secret not in text, secret
        assert secret not in caplog.text, secret


def test_log_event_redacts_blocked_fields_secrets_and_signed_urls(env, caplog):
    caplog.set_level(logging.DEBUG, logger=logs.EVENT_LOGGER)

    logs.log_event(
        "test.redaction",
        display_name="Ana",
        api_key="plain-key",
        authorization="Bearer nope",
        cookie="sl_owner=abc",
        signed_url="https://cdn.example/masks/acne_0.png?signature=abc123",
        detail=f"invite code was {INVITE}",
    )

    line = event_lines(caplog)[-1]
    assert "test.redaction" in line
    assert "Ana" not in line
    assert "plain-key" not in line
    assert "Bearer nope" not in line
    assert "sl_owner=abc" not in line
    assert "signature=abc123" not in line
    assert "?<signed>" in line
    assert INVITE not in line
    assert "<redacted>" in line


def test_capture_rejections_log_the_guard_and_http_status(env, web, caplog):
    caplog.set_level(logging.DEBUG, logger=logs.EVENT_LOGGER)
    person_id = create_profile(web)

    response = web.post(
        "/api/captures",
        params={
            "person_id": person_id,
            "source": "camera_kit",
            "is_baseline_pair": 0,
            "attested": 0,
        },
        content=jpeg_bytes(),
        headers={"Content-Type": "image/jpeg"},
    )
    assert response.status_code == 400

    # No invite cookie: the next check that fails must be the invite guard.
    response = web.post(
        "/api/captures",
        params={
            "person_id": person_id,
            "source": "camera_kit",
            "is_baseline_pair": 0,
            "attested": 1,
        },
        content=jpeg_bytes(),
        headers={"Content-Type": "image/jpeg"},
    )
    assert response.status_code == 403

    text = "\n".join(event_lines(caplog))
    assert "capture.rejected" in text
    assert "guard=attestation" in text
    assert "http_status=400" in text
    assert "guard=invite" in text
    assert "http_status=403" in text
    assert f"person_id={person_id}" in text


def test_invite_failures_log_a_count_but_never_the_code(env, web, caplog):
    try_routes.reset_invite_attempts()
    caplog.set_level(logging.DEBUG, logger=logs.EVENT_LOGGER)
    wrong = "totally-wrong-code-value"

    response = web.post("/try", data={"invite_code": wrong})

    assert response.status_code == 400
    text = "\n".join(event_lines(caplog))
    assert "invite.failed" in text
    assert "count=1" in text
    assert "http_status=400" in text
    assert wrong not in text
    assert INVITE not in text


# -- client log bridge -------------------------------------------------------


def _post_client_log(client, payload, **kwargs):
    return client.post("/api/client-log", json=payload, **kwargs)


def test_client_log_accepts_an_event_without_auth_and_hides_cookies(env, web, caplog):
    reset_client_log_attempts()
    caplog.set_level(logging.DEBUG, logger=logs.EVENT_LOGGER)
    cookie_value = guards.encode_owner_cookie(OWNER_TOKEN)
    web.cookies.set(guards.OWNER_COOKIE, cookie_value)

    response = _post_client_log(
        web,
        {"level": "info", "event": "page_load", "detail": "has_ymk=true"},
    )

    assert response.status_code == 204
    text = "\n".join(event_lines(caplog))
    assert "client.page_load" in text
    assert "has_ymk=true" in text
    assert cookie_value not in text
    assert OWNER_TOKEN not in text


def test_client_log_rejects_oversized_payloads(env, web):
    reset_client_log_attempts()

    response = web.post(
        "/api/client-log",
        content=b"x" * 2049,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413


@pytest.mark.parametrize(
    "payload",
    [
        {"level": "info", "event": "Has Spaces", "detail": ""},
        {"level": "loud", "event": "page_load", "detail": ""},
        {"level": "info", "event": "page_load", "detail": {"nested": "no"}},
        ["not", "a", "dict"],
    ],
)
def test_client_log_rejects_invalid_payloads(env, web, payload):
    reset_client_log_attempts()

    assert _post_client_log(web, payload).status_code == 400


def test_client_log_is_limited_to_thirty_events_per_minute(env, web):
    reset_client_log_attempts()
    payload = {"level": "info", "event": "throttled", "detail": ""}

    for _ in range(30):
        assert _post_client_log(web, payload).status_code == 204

    assert _post_client_log(web, payload).status_code == 429


def test_client_log_parses_json_and_keeps_the_event_name(env, web, caplog):
    reset_client_log_attempts()
    caplog.set_level(logging.DEBUG, logger=logs.EVENT_LOGGER)

    response = web.post(
        "/api/client-log",
        content=json.dumps(
            {"level": "warning", "event": "camera_failed", "detail": "code=error_permission_denied"}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 204
    line = event_lines(caplog)[-1]
    assert "WARNING client.camera_failed" in line
    assert "error_permission_denied" in line


def test_usage_day_helper_is_used_for_recorded_events(env, web, caplog):
    caplog.set_level(logging.DEBUG, logger=logs.EVENT_LOGGER)
    person_id = create_profile(web)
    web.cookies.set(guards.INVITE_COOKIE, guards.encode_invite_cookie(INVITE))
    web.post(
        "/api/captures",
        params={
            "person_id": person_id,
            "source": "camera_kit",
            "is_baseline_pair": 0,
            "attested": 1,
        },
        content=jpeg_bytes(),
        headers={"Content-Type": "image/jpeg"},
    )
    wait_final(web, latest_capture_id())

    text = "\n".join(event_lines(caplog))
    assert "usage.recorded" in text
    assert f"day={usage.guatemala_today()}" in text
    assert "units=0" in text
