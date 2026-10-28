"""P06 acceptance tests: /try, profiles, consent, delete and in-flight deletion."""

from __future__ import annotations

import asyncio
import html
import io

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from skinledger import config, copy, guards, pipeline, usage
from skinledger.aspects import NUMERIC_ASPECTS
from skinledger.db import connect, db_path, init_db
from skinledger.web.app import app
from skinledger.web.routes import try_ as try_routes
from skinledger.youcam import TaskResult

OWNER_TOKEN = "owner-token"
OTHER_TOKEN = "other-token"
INVITE = "invite-ok"


def jpeg_bytes(size=(800, 1000)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (180, 140, 120)).save(buffer, format="JPEG")
    return buffer.getvalue()


def grey_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("L", (16, 16), color=200).save(buffer, format="PNG")
    return buffer.getvalue()


def sample_result() -> TaskResult:
    return TaskResult(
        status="success",
        scores={aspect: 50.0 for aspect in NUMERIC_ASPECTS},
        categorical={"skin_type_whole": "Combination"},
        mask_urls={"acne": ["mock://mask/acne/0.png"]},
        raw={"data": {"task_status": "success", "results": {"output": []}}},
    )


class StubClient:
    async def upload_file(self, img, file_name="capture.jpg") -> str:
        return "file-stub"

    async def create_task(self, file_id, actions=None, mask_overlay=False) -> str:
        return "task-stub"

    async def poll(self, task_id, interval=None, timeout=None) -> TaskResult:
        return sample_result()

    async def download(self, url: str, task_id: str | None = None) -> bytes:
        return grey_png()


class GatedClient(StubClient):
    """Blocks in poll until the test releases it."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def poll(self, task_id, interval=None, timeout=None) -> TaskResult:
        self.started.set()
        await self.release.wait()
        return sample_result()


class GatedDownloadClient(StubClient):
    """Blocks while a mask is downloading, after the initial capture check."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def download(self, url: str, task_id: str | None = None) -> bytes:
        self.started.set()
        await self.release.wait()
        return grey_png()


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = config.settings
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "youcam_mock", True)
    monkeypatch.setattr(settings, "invite_code", SecretStr(INVITE))
    monkeypatch.setattr(settings, "admin_token", SecretStr("admin-ok"))
    monkeypatch.setattr(settings, "max_real_analyses_per_person", 2)
    monkeypatch.setattr(settings, "daily_unit_cap", 96)
    monkeypatch.setattr(settings, "total_unit_cap", 480)
    monkeypatch.setattr(settings, "units_per_analysis", 16)
    monkeypatch.setattr(pipeline, "get_client", lambda: StubClient())
    try_routes.reset_invite_attempts()
    init_db()
    return settings


@pytest.fixture
def web(env):
    with TestClient(app, base_url="https://testserver") as client:
        yield client


def seed_person(
    *,
    token: str = OWNER_TOKEN,
    name: str = "Self",
    consent: bool = False,
    demo: bool = False,
) -> int:
    conn = connect(db_path())
    try:
        person_id = conn.execute(
            "INSERT INTO persons (display_name, owner_token_hash, is_demo_public) "
            "VALUES (?, ?, ?)",
            (name, guards.owner_token_hash(token), int(demo)),
        ).lastrowid
        if consent:
            conn.execute(
                "INSERT INTO consents "
                "(person_id, consent_version, adult_confirmed, accepted_at) "
                "VALUES (?, ?, 1, ?)",
                (person_id, copy.CONSENT_VERSION, usage.utc_now_iso()),
            )
        conn.commit()
        return int(person_id or 0)
    finally:
        conn.close()


def login(client: TestClient, *, token: str = OWNER_TOKEN, invite: str | None = None):
    client.cookies.set(guards.OWNER_COOKIE, guards.encode_owner_cookie(token))
    if invite is not None:
        client.cookies.set(guards.INVITE_COOKIE, guards.encode_invite_cookie(invite))


def add_consent(person_id: int) -> None:
    conn = connect(db_path())
    try:
        conn.execute(
            "INSERT INTO consents (person_id, consent_version, adult_confirmed, accepted_at) "
            "VALUES (?, ?, 1, ?)",
            (person_id, copy.CONSENT_VERSION, usage.utc_now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


def person_row(person_id: int) -> dict | None:
    conn = connect(db_path())
    try:
        row = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def count_rows(table: str, person_id: int | None = None) -> int:
    conn = connect(db_path())
    try:
        if person_id is None:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return int(
            conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE person_id = ?", (person_id,)
            ).fetchone()[0]
        )
    finally:
        conn.close()


def create_profile(client, name: str = "Self") -> int:
    response = client.post(
        "/people/new", data={"display_name": name}, follow_redirects=False
    )
    assert response.status_code == 303
    return int(response.headers["location"].split("/")[2])


def post_consent(client, person_id: int, *, adult: bool = True, agree: bool = True):
    data: dict[str, str] = {}
    if adult:
        data["adult_confirmed"] = "1"
    if agree:
        data["agree"] = "1"
    return client.post(
        f"/people/{person_id}/consent", data=data, follow_redirects=False
    )


# -- /try --------------------------------------------------------------------


def test_try_page_and_correct_invite_sets_the_cookie(env, web):
    page = web.get("/try")
    assert page.status_code == 200
    assert "Invite code" in page.text
    assert copy.POWERED_BY in page.text

    response = web.post(
        "/try", data={"invite_code": INVITE}, follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/people/new"
    cookie = web.cookies.get(guards.INVITE_COOKIE)
    assert cookie is not None
    assert guards.invite_cookie_is_valid(cookie, INVITE)


def test_wrong_invite_shows_message_and_sets_no_cookie(env, web):
    response = web.post("/try", data={"invite_code": "wrong"})

    assert response.status_code == 400
    assert copy.INVALID_INVITE in html.unescape(response.text)
    assert web.cookies.get(guards.INVITE_COOKIE) is None


def test_eleventh_wrong_invite_in_an_hour_is_rate_limited(env, web):
    for _ in range(10):
        assert web.post("/try", data={"invite_code": "wrong"}).status_code == 400

    response = web.post("/try", data={"invite_code": "wrong"})

    assert response.status_code == 429
    assert response.json()["detail"] == copy.TOO_MANY_INVITE_ATTEMPTS


# -- profiles and consent ----------------------------------------------------


def test_create_profile_sets_owner_cookie_and_redirects_to_consent(env, web):
    response = web.post(
        "/people/new", data={"display_name": "Ana"}, follow_redirects=False
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/people/") and location.endswith("/consent")
    person_id = int(location.split("/")[2])

    cookie = web.cookies.get(guards.OWNER_COOKIE)
    assert cookie is not None
    token = guards.decode_owner_cookie(cookie)
    assert token is not None
    person = person_row(person_id)
    assert person is not None
    assert person["owner_token_hash"] == guards.owner_token_hash(token)
    assert person["is_demo_public"] == 0

    consent = web.get(location)
    assert consent.status_code == 200
    assert "Ana" in consent.text
    assert copy.DISCLAIMER in consent.text


def test_consent_requires_adult_and_agreement(env, web):
    person_id = create_profile(web)

    response = post_consent(web, person_id, adult=False, agree=True)

    assert response.status_code == 400
    assert copy.CONSENT_BOXES_REQUIRED in response.text
    assert count_rows("consents", person_id) == 0

    response = post_consent(web, person_id)

    assert response.status_code == 303
    assert response.headers["location"] == "/people"
    conn = connect(db_path())
    try:
        row = conn.execute(
            "SELECT consent_version, adult_confirmed, accepted_at FROM consents "
            "WHERE person_id = ?",
            (person_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row["consent_version"] == copy.CONSENT_VERSION
    assert row["adult_confirmed"] == 1
    assert row["accepted_at"]


def test_people_page_shows_own_profiles_and_the_public_demo(env, web):
    own_id = seed_person(name="Mine")
    other_id = seed_person(token=OTHER_TOKEN, name="Someone else")
    demo_id = seed_person(token=OTHER_TOKEN, name="Sample user", demo=True)
    login(web)

    page = web.get("/people")

    assert page.status_code == 200
    assert "Mine" in page.text
    assert "Someone else" not in page.text
    assert "Sample user" in page.text
    assert "read-only" in page.text
    assert f"/people/{own_id}/delete" in page.text
    assert f"/people/{demo_id}/delete" not in page.text
    assert other_id != demo_id


def test_another_browser_cannot_see_or_delete_the_person(env, web):
    person_id = seed_person(consent=True)
    login(web, token=OTHER_TOKEN)

    assert "Self" not in web.get("/people").text
    assert web.get(f"/people/{person_id}/consent").status_code == 404
    assert web.get(f"/people/{person_id}/delete").status_code == 404
    response = web.post(
        f"/people/{person_id}/delete", data={"confirm_name": "Self"}
    )
    assert response.status_code == 404
    assert person_row(person_id) is not None


# -- delete ------------------------------------------------------------------


def _seed_full_person(env):
    person_id = seed_person(consent=True)
    conn = connect(db_path())
    try:
        capture_a = conn.execute(
            "INSERT INTO captures (person_id, owner_token_hash, captured_at, data_label, "
            "source, status) VALUES (?, ?, ?, 'REAL', 'camera_kit', 'success')",
            (person_id, guards.owner_token_hash(OWNER_TOKEN), usage.utc_now_iso()),
        ).lastrowid
        capture_b = conn.execute(
            "INSERT INTO captures (person_id, owner_token_hash, captured_at, data_label, "
            "source, status) VALUES (?, ?, ?, 'REAL', 'camera_kit', 'success')",
            (person_id, guards.owner_token_hash(OWNER_TOKEN), usage.utc_now_iso()),
        ).lastrowid
        conn.execute(
            "INSERT INTO aspect_scores (capture_id, aspect, raw_score) VALUES (?, 'moisture', 55)",
            (capture_a,),
        )
        mask_relative = f"masks/{person_id}/{capture_a}/acne_0.png"
        mask_file = env.data_dir / mask_relative
        mask_file.parent.mkdir(parents=True)
        mask_file.write_bytes(grey_png())
        conn.execute(
            "INSERT INTO masks (capture_id, aspect, file_path) VALUES (?, 'acne', ?)",
            (capture_a, mask_relative),
        )
        conn.execute(
            "INSERT INTO noise_bands (person_id, aspect, band, a_capture_id, b_capture_id, "
            "floor_applied, computed_at) VALUES (?, 'moisture', 3.0, ?, ?, 1, ?)",
            (person_id, capture_a, capture_b, usage.utc_now_iso()),
        )
        product_id = conn.execute(
            "INSERT INTO products (person_id, name, category, started_on, target_aspects, "
            "data_label) VALUES (?, 'Serum (SAMPLE)', 'serum', '2026-10-28', '[]', 'SAMPLE')",
            (person_id,),
        ).lastrowid
        conn.execute(
            "INSERT INTO verdicts (product_id, check_window, outcome, payload_json, computed_at) "
            "VALUES (?, 'd14', 'keep', '{}', ?)",
            (product_id, usage.utc_now_iso()),
        )
        conn.execute(
            "INSERT INTO api_usage (capture_id, owner_token_hash, day, units, mode, is_admin) "
            "VALUES (?, ?, ?, 16, 'real', 0)",
            (capture_a, guards.owner_token_hash(OWNER_TOKEN), usage.guatemala_today()),
        )
        conn.commit()
    finally:
        conn.close()
    return person_id


def test_delete_removes_rows_and_masks_but_keeps_usage(env, web):
    person_id = _seed_full_person(env)
    login(web)

    response = web.post(
        f"/people/{person_id}/delete", data={"confirm_name": "Self"}
    )

    assert response.status_code == 200
    assert copy.DELETED_MESSAGE in response.text
    assert person_row(person_id) is None
    for table in ("consents", "captures", "noise_bands", "products"):
        assert count_rows(table, person_id) == 0, table
    for table in ("aspect_scores", "masks", "verdicts"):
        assert count_rows(table) == 0, table
    assert not (env.data_dir / "masks" / str(person_id)).exists()

    conn = connect(db_path())
    try:
        usage_row = conn.execute(
            "SELECT capture_id, units FROM api_usage"
        ).fetchone()
    finally:
        conn.close()
    assert usage_row["capture_id"] is None
    assert usage_row["units"] == 16


def test_delete_requires_the_exact_display_name(env, web):
    person_id = seed_person(consent=True)
    login(web)

    response = web.post(
        f"/people/{person_id}/delete", data={"confirm_name": "Not self"}
    )

    assert response.status_code == 400
    assert copy.DELETE_CONFIRM_MISMATCH in response.text
    assert person_row(person_id) is not None


def test_demo_profile_cannot_be_deleted_without_admin_token(env, web):
    person_id = seed_person(token=OWNER_TOKEN, name="Sample user", demo=True)
    login(web)

    response = web.post(
        f"/people/{person_id}/delete", data={"confirm_name": "Sample user"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == copy.DEMO_READ_ONLY
    assert person_row(person_id) is not None

    response = web.post(
        f"/people/{person_id}/delete",
        data={"confirm_name": "Sample user"},
        headers={"X-Admin-Token": "admin-ok"},
    )
    assert response.status_code == 200
    assert person_row(person_id) is None


def test_deleting_and_recreating_does_not_reset_the_browser_cap(env, web):
    person_id = seed_person(consent=True)
    conn = connect(db_path())
    try:
        for _ in range(2):
            conn.execute(
                "INSERT INTO api_usage (capture_id, owner_token_hash, day, units, mode, "
                "is_admin) VALUES (NULL, ?, ?, 16, 'real', 0)",
                (guards.owner_token_hash(OWNER_TOKEN), usage.guatemala_today()),
            )
        conn.commit()
    finally:
        conn.close()

    login(web, invite=INVITE)
    assert web.post(
        f"/people/{person_id}/delete", data={"confirm_name": "Self"}
    ).status_code == 200

    new_person_id = create_profile(web, "New self")
    assert post_consent(web, new_person_id).status_code == 303

    response = web.post(
        "/api/captures",
        params={
            "person_id": new_person_id,
            "source": "camera_kit",
            "is_baseline_pair": 0,
            "attested": 1,
        },
        content=jpeg_bytes(),
        headers={"Content-Type": "image/jpeg"},
    )

    assert response.status_code == 429
    assert "You've used your 2 analyses." in response.json()["detail"]


# -- in-flight deletion ------------------------------------------------------


@pytest.mark.asyncio
async def test_finishing_capture_after_delete_does_not_recreate_rows_or_masks(env, monkeypatch):
    gated = GatedClient()
    monkeypatch.setattr(pipeline, "get_client", lambda: gated)
    person_id = seed_person(consent=True)
    cookie = (
        f"{guards.OWNER_COOKIE}={guards.encode_owner_cookie(OWNER_TOKEN)}; "
        f"{guards.INVITE_COOKIE}={guards.encode_invite_cookie(INVITE)}"
    )
    headers = {"Cookie": cookie, "Content-Type": "image/jpeg"}
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as ac:
        response = await ac.post(
            "/api/captures",
            params={
                "person_id": person_id,
                "source": "camera_kit",
                "is_baseline_pair": 0,
                "attested": 1,
            },
            content=jpeg_bytes(),
            headers=headers,
        )
        assert response.status_code == 202
        await asyncio.wait_for(gated.started.wait(), timeout=2)

        deleted = await ac.post(
            f"/people/{person_id}/delete",
            data={"confirm_name": "Self"},
            headers={"Cookie": cookie},
        )
        assert deleted.status_code == 200
        assert person_row(person_id) is None

        gated.release.set()
        await asyncio.sleep(0.1)

    for table in ("captures", "aspect_scores", "masks", "api_usage"):
        assert count_rows(table) == 0, table
    assert not (env.data_dir / "masks" / str(person_id)).exists()


@pytest.mark.asyncio
async def test_delete_during_mask_download_writes_nothing(env, monkeypatch):
    gated = GatedDownloadClient()
    monkeypatch.setattr(pipeline, "get_client", lambda: gated)
    person_id = seed_person(consent=True)
    cookie = (
        f"{guards.OWNER_COOKIE}={guards.encode_owner_cookie(OWNER_TOKEN)}; "
        f"{guards.INVITE_COOKIE}={guards.encode_invite_cookie(INVITE)}"
    )
    headers = {"Cookie": cookie, "Content-Type": "image/jpeg"}
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as ac:
        response = await ac.post(
            "/api/captures",
            params={
                "person_id": person_id,
                "source": "camera_kit",
                "is_baseline_pair": 0,
                "attested": 1,
            },
            content=jpeg_bytes(),
            headers=headers,
        )
        assert response.status_code == 202
        await asyncio.wait_for(gated.started.wait(), timeout=2)

        deleted = await ac.post(
            f"/people/{person_id}/delete",
            data={"confirm_name": "Self"},
            headers={"Cookie": cookie},
        )
        assert deleted.status_code == 200

        gated.release.set()
        await asyncio.sleep(0.1)

    for table in ("captures", "aspect_scores", "masks", "api_usage"):
        assert count_rows(table) == 0, table
    assert not (env.data_dir / "masks" / str(person_id)).exists()
