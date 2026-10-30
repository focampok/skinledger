"""P04 acceptance tests: in-memory pipeline, guards, caps, masks and resume."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import tempfile
import time
from datetime import UTC, date, datetime

import httpx
import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from skinledger import config, copy, guards, pipeline, usage
from skinledger.aspects import NUMERIC_ASPECTS
from skinledger.db import connect, db_path, init_db
from skinledger.web.app import app
from skinledger.youcam import (
    FRIENDLY_ERRORS,
    TaskResult,
    YouCamClient,
    YouCamTaskError,
)

OWNER_TOKEN = "owner-token"
INVITE = "invite-ok"


# -- helpers -----------------------------------------------------------------


async def _no_sleep(_seconds: float) -> None:
    return None


def jpeg_bytes(size=(800, 1000)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (180, 140, 120)).save(buffer, format="JPEG")
    return buffer.getvalue()


def grey_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("L", (32, 24), color=200).save(buffer, format="PNG")
    return buffer.getvalue()


def rgb_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 24), color=(180, 140, 120)).save(buffer, format="PNG")
    return buffer.getvalue()


def sample_result() -> TaskResult:
    return TaskResult(
        status="success",
        scores={aspect: 50.0 for aspect in NUMERIC_ASPECTS},
        categorical={
            "skin_type_whole": "Combination",
            "skin_type_t_zone": "Oily",
            "skin_type_u_zone": "Dry",
        },
        mask_urls={
            **{
                aspect: [f"https://example.invalid/mask/{aspect}_0.png?signature=stub"]
                for aspect in NUMERIC_ASPECTS
            },
            **{
                f"skin_type_{region}": [
                    f"https://example.invalid/mask/skin_type_{region}_0.png?signature=stub"
                ]
                for region in ("whole", "t_zone", "u_zone")
            },
        },
        raw={"data": {"task_status": "success", "results": {"output": []}}},
    )


class StubClient:
    """Deterministic YouCam double; records every call."""

    def __init__(self) -> None:
        self.calls: list[object] = []
        self.poll_result = sample_result()
        self.poll_error: Exception | None = None
        self.mask_bytes: bytes | None = None

    async def upload_file(self, img, file_name="capture.jpg") -> str:
        self.calls.append(("upload_file", file_name))
        return "file-stub"

    async def create_task(self, file_id, actions=None, mask_overlay=False) -> str:
        self.calls.append(("create_task", file_id))
        return "task-stub"

    async def poll(self, task_id, interval=None, timeout=None) -> TaskResult:
        self.calls.append(("poll", task_id))
        if self.poll_error is not None:
            raise self.poll_error
        return self.poll_result

    async def download(self, url: str, task_id: str | None = None) -> bytes:
        self.calls.append(("download", url))
        return self.mask_bytes if self.mask_bytes is not None else grey_png()


@pytest.fixture
def stub() -> StubClient:
    return StubClient()


@pytest.fixture
def env(tmp_path, monkeypatch, stub):
    settings = config.settings
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "youcam_mock", True)
    monkeypatch.setattr(settings, "invite_code", SecretStr(INVITE))
    monkeypatch.setattr(settings, "admin_token", SecretStr("admin-ok"))
    monkeypatch.setattr(settings, "allow_upload", True)
    monkeypatch.setattr(settings, "store_masks", True)
    monkeypatch.setattr(settings, "max_real_analyses_per_person", 2)
    monkeypatch.setattr(settings, "daily_unit_cap", 96)
    monkeypatch.setattr(settings, "total_unit_cap", 480)
    monkeypatch.setattr(settings, "units_per_analysis", 16)
    monkeypatch.setattr(pipeline, "get_client", lambda: stub)
    init_db()
    return settings


@pytest.fixture
def web(env):
    with TestClient(app, base_url="https://testserver") as client:
        yield client


def seed_person(token: str = OWNER_TOKEN, *, consent: bool = True) -> int:
    conn = connect(db_path())
    try:
        person_id = conn.execute(
            "INSERT INTO persons (display_name, owner_token_hash) VALUES (?, ?)",
            ("Self", guards.owner_token_hash(token)),
        ).lastrowid
        if consent:
            conn.execute(
                "INSERT INTO consents "
                "(person_id, consent_version, adult_confirmed, accepted_at) "
                "VALUES (?, ?, 1, ?)",
                (person_id, "consent-v2", usage.utc_now_iso()),
            )
        conn.commit()
        return int(person_id or 0)
    finally:
        conn.close()


def insert_capture(
    person_id: int,
    *,
    status: str,
    task_id: str | None = None,
    owner_token: str = OWNER_TOKEN,
) -> int:
    now = usage.utc_now_iso()
    conn = connect(db_path())
    try:
        capture_id = conn.execute(
            "INSERT INTO captures (person_id, owner_token_hash, captured_at, data_label, "
            "source, status, task_id, created_at) VALUES (?, ?, ?, 'SAMPLE', "
            "'camera_kit', ?, ?, ?)",
            (person_id, guards.owner_token_hash(owner_token), now, status, task_id, now),
        ).lastrowid
        conn.commit()
        return int(capture_id or 0)
    finally:
        conn.close()


def login(client: TestClient, *, token: str = OWNER_TOKEN, invite: str | None = INVITE):
    client.cookies.set(guards.OWNER_COOKIE, guards.encode_owner_cookie(token))
    if invite is not None:
        client.cookies.set(guards.INVITE_COOKIE, guards.encode_invite_cookie(invite))


def post_capture(
    client,
    person_id: int,
    *,
    source: str = "camera_kit",
    attested: int = 1,
    baseline: int = 0,
    image: bytes | None = None,
    headers: dict[str, str] | None = None,
):
    return client.post(
        "/api/captures",
        params={
            "person_id": person_id,
            "source": source,
            "is_baseline_pair": baseline,
            "attested": attested,
        },
        content=image if image is not None else jpeg_bytes(),
        headers={"Content-Type": "image/jpeg", **(headers or {})},
    )


def latest_capture() -> dict:
    conn = connect(db_path())
    try:
        row = conn.execute("SELECT * FROM captures ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row is not None else {}
    finally:
        conn.close()


def get_capture(capture_id: int) -> dict:
    conn = connect(db_path())
    try:
        row = conn.execute("SELECT * FROM captures WHERE id = ?", (capture_id,)).fetchone()
        return dict(row) if row is not None else {}
    finally:
        conn.close()


def wait_final(
    client,
    capture_id: int,
    timeout: float = 5.0,
    headers: dict[str, str] | None = None,
) -> str:
    deadline = time.monotonic() + timeout
    text = ""
    while time.monotonic() < deadline:
        response = client.get(
            f"/api/captures/{capture_id}/status", headers=headers
        )
        assert response.status_code == 200
        text = response.text
        if 'data-status="success"' in text or 'data-status="error"' in text:
            return text
        time.sleep(0.02)
    raise AssertionError(f"capture did not finish: {text}")


def run_analysis(client, person_id: int) -> int:
    response = post_capture(client, person_id)
    assert response.status_code == 202, response.text
    capture_id = latest_capture()["id"]
    wait_final(client, capture_id)
    return capture_id


# -- happy flow --------------------------------------------------------------


def test_happy_flow_stores_scores_masks_and_sanitized_raw(env, web, monkeypatch):
    mock_client = YouCamClient(mock=True, poll_interval=0, sleep=_no_sleep)
    monkeypatch.setattr(pipeline, "get_client", lambda: mock_client)
    temp_dir = env.data_dir.parent / "temp"
    temp_dir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp_dir))
    image = jpeg_bytes()
    person_id = seed_person()
    login(web)

    response = post_capture(web, person_id, image=image)
    assert response.status_code == 202
    assert 'data-status="running"' in response.text
    capture_id = latest_capture()["id"]
    final = wait_final(web, capture_id)

    capture = get_capture(capture_id)
    assert capture["status"] == "success"
    assert capture["data_label"] == "SAMPLE"
    assert capture["units_charged"] == 0
    assert capture["attested_at"]

    raw_text = capture["raw_result_json"]
    raw = json.loads(raw_text)
    output = raw["data"]["results"]["output"]
    assert all(item.get("type") != "resize_image" for item in output)
    assert "ui_score" not in json.dumps(raw)
    assert "signature=" not in raw_text
    assert "resized/photo_0" not in raw_text

    conn = connect(db_path())
    try:
        rows = conn.execute(
            "SELECT aspect, raw_score, value_text FROM aspect_scores WHERE capture_id = ?",
            (capture_id,),
        ).fetchall()
        numeric = [row for row in rows if row["aspect"] in NUMERIC_ASPECTS]
        skin = [row for row in rows if row["aspect"].startswith("skin_type_")]
        assert len(numeric) == 15
        assert all(row["raw_score"] is not None and row["value_text"] is None for row in numeric)
        assert {row["aspect"] for row in skin} == {
            "skin_type_whole",
            "skin_type_t_zone",
            "skin_type_u_zone",
        }
        assert all(row["raw_score"] is None and row["value_text"] for row in skin)

        masks = conn.execute(
            "SELECT aspect, file_path FROM masks WHERE capture_id = ?", (capture_id,)
        ).fetchall()
        assert len(masks) == 18
        for mask in masks:
            path = env.data_dir / mask["file_path"]
            assert path.is_file()
            with Image.open(path) as mask_image:
                assert mask_image.mode != "RGB"

        usage_rows = conn.execute(
            "SELECT units, mode, is_admin, day FROM api_usage WHERE capture_id = ?",
            (capture_id,),
        ).fetchall()
        assert len(usage_rows) == 1
        assert usage_rows[0]["units"] == 0
        assert usage_rows[0]["mode"] == "mock"
        assert usage_rows[0]["is_admin"] == 0
        assert usage_rows[0]["day"] == usage.guatemala_today()
    finally:
        conn.close()

    for path in env.data_dir.rglob("*"):
        if path.is_file():
            relative = path.relative_to(env.data_dir)
            assert str(relative).startswith("masks/") or path.name in {
                "skinledger.sqlite",
                "skinledger.sqlite-wal",
                "skinledger.sqlite-shm",
            }
            if not str(relative).startswith("masks/"):
                assert not path.read_bytes().startswith(image[:8])
    assert list(temp_dir.iterdir()) == []

    assert "Moisture" in final
    assert "Skin type (whole)" in final
    assert "Combination" in final
    assert "You have 1 analysis left" in final


def test_store_masks_false_keeps_scores_only(env, web, stub):
    env.store_masks = False
    person_id = seed_person()
    login(web)

    capture_id = run_analysis(web, person_id)

    assert get_capture(capture_id)["status"] == "success"
    conn = connect(db_path())
    try:
        assert conn.execute("SELECT COUNT(*) FROM masks").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM aspect_scores").fetchone()[0] == 18
    finally:
        conn.close()
    assert not (env.data_dir / "masks").exists()


def test_rgb_mask_is_refused_and_logged_without_url(env, web, stub, caplog):
    stub.mask_bytes = rgb_png()
    caplog.set_level(logging.WARNING)
    person_id = seed_person()
    login(web)

    capture_id = run_analysis(web, person_id)

    assert get_capture(capture_id)["status"] == "success"
    conn = connect(db_path())
    try:
        assert conn.execute("SELECT COUNT(*) FROM masks").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM aspect_scores").fetchone()[0] == 18
    finally:
        conn.close()
    assert not (env.data_dir / "masks").exists()
    assert "acne" in caplog.text
    assert "https://" not in caplog.text
    assert "signature=" not in caplog.text


# -- ordering checks ---------------------------------------------------------


def test_owner_cookie_is_required_and_tampering_is_rejected(env, web, stub):
    person_id = seed_person()

    assert post_capture(web, person_id).status_code == 404

    web.cookies.set(guards.OWNER_COOKIE, "tampered")
    web.cookies.set(guards.INVITE_COOKIE, guards.encode_invite_cookie(INVITE))
    assert post_capture(web, person_id).status_code == 404
    assert stub.calls == []
    assert latest_capture() == {}


def test_consent_is_required(env, web, stub):
    person_id = seed_person(consent=False)
    login(web)

    response = post_capture(web, person_id)

    assert response.status_code == 403
    assert response.json()["detail"] == copy.CONSENT_REQUIRED
    assert stub.calls == []


def test_attestation_is_required(env, web, stub):
    person_id = seed_person()
    login(web)

    response = post_capture(web, person_id, attested=0)

    assert response.status_code == 400
    assert response.json()["detail"] == copy.ATTESTATION_REQUIRED
    assert stub.calls == []


def test_invite_is_required_and_rotation_invalidates_the_cookie(env, web, stub):
    person_id = seed_person()

    login(web, invite=None)
    response = post_capture(web, person_id)
    assert response.status_code == 403
    assert response.json()["detail"] == copy.INVITE_REQUIRED

    login(web, invite="old-code")
    env.invite_code = SecretStr("new-code")
    response = post_capture(web, person_id)
    assert response.status_code == 403
    assert stub.calls == []
    assert latest_capture() == {}


def test_upload_can_be_disabled_while_camera_kit_works(env, web, stub):
    env.allow_upload = False
    person_id = seed_person()
    login(web)

    response = post_capture(web, person_id, source="upload")
    assert response.status_code == 403
    assert response.json()["detail"] == copy.UPLOAD_DISABLED

    response = post_capture(web, person_id, source="camera_kit")
    assert response.status_code == 202
    wait_final(web, latest_capture()["id"])


def test_body_over_ten_megabytes_is_rejected(env, web, stub):
    person_id = seed_person()
    login(web)

    response = post_capture(web, person_id, image=b"\x00" * (10 * 1024 * 1024 + 1))

    assert response.status_code == 413
    assert copy.ATTEMPT_FREE in response.json()["detail"]
    assert stub.calls == []
    assert latest_capture() == {}


def test_rejected_small_image_costs_nothing(env, web, stub):
    person_id = seed_person()
    login(web)

    response = post_capture(web, person_id, image=jpeg_bytes(size=(300, 800)))

    assert response.status_code == 422
    assert "error_below_min_image_size" not in response.text
    assert copy.ATTEMPT_FREE in response.json()["detail"]
    assert stub.calls == []
    assert latest_capture() == {}


# -- errors and caps ---------------------------------------------------------


@pytest.mark.parametrize(
    "code", ["error_no_face", "error_multiple_people", "error_lighting_dark"]
)
def test_task_errors_are_free_and_do_not_count_toward_caps(env, web, stub, code):
    env.max_real_analyses_per_person = 1
    stub.poll_error = YouCamTaskError(code)
    person_id = seed_person()
    login(web)

    capture_id = run_analysis(web, person_id)
    capture = get_capture(capture_id)

    assert capture["status"] == "error"
    assert capture["error_code"] == code
    assert capture["error_message"] == FRIENDLY_ERRORS[code]
    assert capture["units_charged"] == 0
    conn = connect(db_path())
    try:
        assert conn.execute("SELECT COUNT(*) FROM api_usage").fetchone()[0] == 0
    finally:
        conn.close()

    stub.poll_error = None
    second_id = run_analysis(web, person_id)
    assert get_capture(second_id)["status"] == "success"


def test_third_analysis_for_the_same_person_is_rejected(env, web, stub):
    person_id = seed_person()
    login(web)
    for _ in range(2):
        run_analysis(web, person_id)

    response = post_capture(web, person_id)

    assert response.status_code == 429
    detail = response.json()["detail"]
    assert copy.LIMIT_REACHED in detail
    assert "You've used your 2 analyses." in detail


def test_second_profile_in_the_same_browser_cannot_exceed_the_cap(env, web, stub):
    person_id = seed_person()
    login(web)
    for _ in range(2):
        run_analysis(web, person_id)

    other_person = seed_person(token=OWNER_TOKEN)
    response = post_capture(web, other_person)

    assert response.status_code == 429


def test_daily_unit_cap_blocks_the_third_analysis(env, web, stub):
    env.daily_unit_cap = 32
    env.max_real_analyses_per_person = 10
    person_id = seed_person()
    login(web)
    for _ in range(2):
        run_analysis(web, person_id)

    response = post_capture(web, person_id)

    assert response.status_code == 429
    assert response.json()["detail"] == copy.LIMIT_REACHED


def test_total_unit_cap_blocks_the_third_analysis(env, web, stub):
    env.total_unit_cap = 32
    env.max_real_analyses_per_person = 10
    person_id = seed_person()
    login(web)
    for _ in range(2):
        run_analysis(web, person_id)

    response = post_capture(web, person_id)

    assert response.status_code == 429
    assert response.json()["detail"] == copy.LIMIT_REACHED


def test_admin_token_bypasses_caps_and_is_recorded(env, web, stub):
    env.max_real_analyses_per_person = 1
    person_id = seed_person()
    login(web)
    run_analysis(web, person_id)

    web.cookies.clear()
    response = post_capture(web, person_id, headers={"X-Admin-Token": "admin-ok"})

    assert response.status_code == 202
    capture_id = latest_capture()["id"]
    wait_final(web, capture_id, headers={"X-Admin-Token": "admin-ok"})
    capture = get_capture(capture_id)
    assert capture["is_admin"] == 1
    conn = connect(db_path())
    try:
        row = conn.execute(
            "SELECT is_admin FROM api_usage WHERE capture_id = ?", (capture_id,)
        ).fetchone()
        assert row["is_admin"] == 1
    finally:
        conn.close()


# -- resume ------------------------------------------------------------------


async def _await_db_status(capture_id: int, status: str, attempts: int = 300) -> dict:
    for _ in range(attempts):
        capture = get_capture(capture_id)
        if capture.get("status") == status:
            return capture
        await asyncio.sleep(0.01)
    raise AssertionError(f"capture never reached {status}: {get_capture(capture_id)}")


@pytest.mark.asyncio
async def test_resume_running_capture_completes(env, stub):
    person_id = seed_person()
    capture_id = insert_capture(person_id, status="running", task_id="task-resume")

    await pipeline.resume_pending()

    capture = await _await_db_status(capture_id, "success")
    assert capture["raw_result_json"]
    conn = connect(db_path())
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM aspect_scores WHERE capture_id = ?", (capture_id,)
        ).fetchone()[0] == 18
        assert conn.execute("SELECT COUNT(*) FROM api_usage").fetchone()[0] == 1
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_resume_uploading_capture_becomes_error_without_units(env, stub):
    person_id = seed_person()
    capture_id = insert_capture(person_id, status="uploading", task_id=None)

    await pipeline.resume_pending()

    capture = await _await_db_status(capture_id, "error")
    assert capture["error_message"] == copy.TRY_AGAIN_NO_UNITS
    assert capture["units_charged"] == 0
    conn = connect(db_path())
    try:
        assert conn.execute("SELECT COUNT(*) FROM api_usage").fetchone()[0] == 0
    finally:
        conn.close()


# -- concurrency and time zone ----------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_requests_at_the_cap_boundary_only_one_passes(env, stub):
    env.max_real_analyses_per_person = 1
    person_id = seed_person()
    cookie = (
        f"{guards.OWNER_COOKIE}={guards.encode_owner_cookie(OWNER_TOKEN)}; "
        f"{guards.INVITE_COOKIE}={guards.encode_invite_cookie(INVITE)}"
    )
    headers = {"Content-Type": "image/jpeg", "Cookie": cookie}
    params = {
        "person_id": person_id,
        "source": "camera_kit",
        "is_baseline_pair": 0,
        "attested": 1,
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as ac:
        first, second = await asyncio.gather(
            ac.post("/api/captures", params=params, content=jpeg_bytes(), headers=headers),
            ac.post("/api/captures", params=params, content=jpeg_bytes(), headers=headers),
        )

    assert sorted([first.status_code, second.status_code]) == [202, 429]
    await asyncio.sleep(0.05)


def test_guatemala_day_never_uses_the_utc_day():
    # 23:30 GT on 28 Oct is 05:30 UTC on 29 Oct and still counts as 28 Oct.
    assert usage.guatemala_day(datetime(2026, 10, 29, 5, 30, tzinfo=UTC)) == date(
        2026, 10, 28
    )
    assert usage.guatemala_day(datetime(2026, 10, 29, 6, 0, tzinfo=UTC)) == date(
        2026, 10, 29
    )


def test_cookie_helpers_round_trip_and_reject_tampering():
    owner_value = guards.encode_owner_cookie(OWNER_TOKEN)
    assert guards.decode_owner_cookie(owner_value) == OWNER_TOKEN
    assert guards.decode_owner_cookie(owner_value + "x") is None
    assert guards.decode_owner_cookie("no-dot") is None

    invite_value = guards.encode_invite_cookie("code-1")
    assert guards.invite_cookie_is_valid(invite_value, "code-1")
    assert not guards.invite_cookie_is_valid(invite_value, "code-2")
    assert not guards.invite_cookie_is_valid(invite_value + "x", "code-1")


def test_cookie_setters_are_httponly_secure_and_lax():
    response = Response()
    guards.set_owner_cookie(response, OWNER_TOKEN)
    guards.set_invite_cookie(response, INVITE)

    for header in response.headers.getlist("set-cookie"):
        assert "HttpOnly" in header
        assert "Secure" in header
        assert "samesite=lax" in header.lower()


# -- P16a: the upload source enforces the same guards as the guided camera ----


def test_upload_source_requires_consent(env, web, stub):
    person_id = seed_person(consent=False)
    login(web)

    response = post_capture(web, person_id, source="upload")

    assert response.status_code == 403
    assert response.json()["detail"] == copy.CONSENT_REQUIRED
    assert stub.calls == []


def test_upload_source_requires_the_invite_code(env, web, stub):
    person_id = seed_person()
    login(web, invite=None)

    response = post_capture(web, person_id, source="upload")

    assert response.status_code == 403
    assert response.json()["detail"] == copy.INVITE_REQUIRED
    assert stub.calls == []


def test_upload_source_counts_against_the_daily_unit_cap(env, web, stub):
    env.daily_unit_cap = 32
    env.max_real_analyses_per_person = 10
    person_id = seed_person()
    login(web)
    for _ in range(2):
        accepted = post_capture(web, person_id, source="upload")
        assert accepted.status_code == 202
        wait_final(web, latest_capture()["id"])

    response = post_capture(web, person_id, source="upload")

    assert response.status_code == 429


def test_upload_source_requires_attestation(env, web, stub):
    person_id = seed_person()
    login(web)

    response = post_capture(web, person_id, source="upload", attested=0)

    assert response.status_code == 400
    assert response.json()["detail"] == copy.ATTESTATION_REQUIRED
