"""P05 acceptance tests: capture page copy, upload gating, masks route and JS privacy."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from skinledger import config, copy, guards, pipeline, usage
from skinledger.db import connect, db_path, init_db
from skinledger.web.app import app

OWNER_TOKEN = "owner-token"
OTHER_TOKEN = "other-token"
ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/skinledger/web/static"
TEMPLATES = ROOT / "src/skinledger/web/templates"


def grey_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("L", (16, 16), color=200).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = config.settings
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "youcam_mock", True)
    monkeypatch.setattr(settings, "invite_code", SecretStr("invite-ok"))
    monkeypatch.setattr(settings, "admin_token", SecretStr("admin-ok"))
    monkeypatch.setattr(settings, "allow_upload", True)
    monkeypatch.setattr(settings, "max_real_analyses_per_person", 2)
    monkeypatch.setattr(settings, "daily_unit_cap", 96)
    monkeypatch.setattr(settings, "total_unit_cap", 480)
    monkeypatch.setattr(settings, "units_per_analysis", 16)
    monkeypatch.setattr(pipeline, "get_client", lambda: None)
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
    consent: bool = True,
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
                "INSERT INTO consents (person_id, consent_version, adult_confirmed, accepted_at) "
                "VALUES (?, ?, 1, ?)",
                (person_id, copy.CONSENT_VERSION, usage.utc_now_iso()),
            )
        conn.commit()
        return int(person_id or 0)
    finally:
        conn.close()


def login(client: TestClient, token: str = OWNER_TOKEN) -> None:
    client.cookies.set(guards.OWNER_COOKIE, guards.encode_owner_cookie(token))


def create_profile(client, name: str = "Self") -> int:
    response = client.post(
        "/people/new", data={"display_name": name}, follow_redirects=False
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


def insert_capture(
    person_id: int,
    *,
    token: str = OWNER_TOKEN,
    status: str = "success",
) -> int:
    conn = connect(db_path())
    try:
        capture_id = conn.execute(
            "INSERT INTO captures (person_id, owner_token_hash, captured_at, data_label, "
            "source, status) VALUES (?, ?, ?, 'REAL', 'camera_kit', ?)",
            (person_id, guards.owner_token_hash(token), usage.utc_now_iso(), status),
        ).lastrowid
        conn.commit()
        return int(capture_id or 0)
    finally:
        conn.close()


def add_mask(env, capture_id: int, aspect: str = "acne") -> tuple[str, bytes]:
    data = grey_png()
    conn = connect(db_path())
    try:
        person_id = conn.execute(
            "SELECT person_id FROM captures WHERE id = ?", (capture_id,)
        ).fetchone()["person_id"]
        file_name = f"{aspect}_0.png"
        relative = f"masks/{person_id}/{capture_id}/{file_name}"
        path = env.data_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        conn.execute(
            "INSERT INTO masks (capture_id, aspect, file_path) VALUES (?, ?, ?)",
            (capture_id, aspect, relative),
        )
        conn.commit()
    finally:
        conn.close()
    return file_name, data


# -- page --------------------------------------------------------------------


def test_capture_page_has_exact_copy_and_baseline_step(env, web):
    person_id = create_profile(web)

    response = web.get(f"/people/{person_id}/capture")

    assert response.status_code == 200
    assert 'id="attestation-hint"' in response.text
    assert "Tick the checkbox above to enable" in response.text
    assert copy.ATTESTATION in response.text
    assert copy.DISCLAIMER in response.text
    assert copy.PRIVACY_NOTE in response.text
    assert copy.UPLOAD_TIP in response.text
    assert "Guided capture (recommended for tracking)" in response.text
    assert "Quick try: upload a photo" in response.text
    assert 'data-tab-panel="upload"' in response.text
    assert "2 of 2 analyses left" in response.text
    assert "Baseline: analysis 1 of 2" in response.text
    assert 'id="YMK-module"' in response.text
    assert "plugins-media.makeupar.com/v2.5-camera-kit/sdk.js" in response.text


def test_upload_tab_is_hidden_when_upload_is_disabled(env, web):
    env.allow_upload = False
    person_id = create_profile(web)

    response = web.get(f"/people/{person_id}/capture")

    assert response.status_code == 200
    assert 'data-tab-panel="upload"' not in response.text
    assert "Quick try: upload a photo" not in response.text
    assert "Guided capture (recommended for tracking)" in response.text


def test_failed_attempt_keeps_baseline_step_one_and_counter(env, web):
    person_id = seed_person()
    insert_capture(person_id, status="error")
    login(web)

    response = web.get(f"/people/{person_id}/capture")

    assert response.status_code == 200
    assert "Baseline: analysis 1 of 2" in response.text
    assert "2 of 2 analyses left" in response.text


def test_one_success_moves_to_the_second_baseline_analysis(env, web):
    person_id = seed_person()
    insert_capture(person_id, status="success")
    login(web)

    response = web.get(f"/people/{person_id}/capture")

    assert response.status_code == 200
    assert "Analysis 2 of 2 (same place, same light)" in response.text
    assert "1 of 2 analyses left" in response.text


def test_capture_page_redirects_to_consent_when_missing(env, web):
    person_id = seed_person(consent=False)
    login(web)

    response = web.get(
        f"/people/{person_id}/capture", follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/people/{person_id}/consent"


def test_capture_page_is_hidden_from_another_browser(env, web):
    person_id = seed_person()
    login(web, OTHER_TOKEN)

    assert web.get(f"/people/{person_id}/capture").status_code == 404


def test_status_fragment_lists_mask_files_without_media_urls(env, web):
    person_id = seed_person()
    capture_id = insert_capture(person_id)
    add_mask(env, capture_id)
    login(web)

    response = web.get(f"/api/captures/{capture_id}/status")

    assert response.status_code == 200
    assert 'data-mask-file="acne_0.png"' in response.text
    assert 'data-mask-aspect="acne"' in response.text
    assert "/media/" not in response.text


# -- /media ------------------------------------------------------------------


def test_media_serves_mask_to_owner_with_no_store(env, web):
    person_id = seed_person()
    capture_id = insert_capture(person_id)
    file_name, data = add_mask(env, capture_id)
    login(web)

    response = web.get(f"/media/{capture_id}/{file_name}")

    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"


def test_media_returns_404_for_another_cookie(env, web):
    person_id = seed_person()
    capture_id = insert_capture(person_id)
    file_name, _ = add_mask(env, capture_id)
    login(web, OTHER_TOKEN)

    assert web.get(f"/media/{capture_id}/{file_name}").status_code == 404


def test_media_returns_404_for_a_name_not_in_the_masks_table(env, web):
    person_id = seed_person()
    capture_id = insert_capture(person_id)
    add_mask(env, capture_id)
    login(web)

    assert web.get(f"/media/{capture_id}/other.png").status_code == 404
    assert web.get(f"/media/{capture_id}/..%2Fsecret.png").status_code == 404


def test_media_serves_the_public_demo_without_a_cookie(env, web):
    person_id = seed_person(token=OTHER_TOKEN, name="Sample user", demo=True)
    capture_id = insert_capture(person_id, token=OTHER_TOKEN)
    file_name, data = add_mask(env, capture_id)

    response = web.get(f"/media/{capture_id}/{file_name}")

    assert response.status_code == 200
    assert response.content == data


# -- browser-side privacy ----------------------------------------------------


def test_capture_js_stores_only_the_camera_language_in_local_storage():
    source = (STATIC / "capture.js").read_text(encoding="utf-8")
    lowered = source.lower()
    storage_lines = [line for line in source.splitlines() if "localStorage" in line]

    assert storage_lines
    assert all("languageKey" in line for line in storage_lines)
    assert "indexeddb" not in lowered
    assert "caches" not in lowered
    assert "URL.createObjectURL" in source
    assert "URL.revokeObjectURL" in source
    assert "pagehide" in source


def test_capture_page_loads_the_camera_kit_after_the_ready_hook():
    template = (TEMPLATES / "capture.html").read_text(encoding="utf-8")

    hook = template.index("window.ymkAsyncInit = function")
    sdk = template.index("plugins-media.makeupar.com/v2.5-camera-kit/sdk.js")
    assert hook < sdk
    # The SDK looks for the lowercase name; the mixed-case spelling is only an alias.
    assert "window.YMKAsyncInit = window.ymkAsyncInit;" in template
    assert 'faceDetectionMode: "skincare"' in (STATIC / "capture.js").read_text(
        encoding="utf-8"
    )
    assert 'imageFormat: "blob"' in (STATIC / "capture.js").read_text(encoding="utf-8")


def test_guided_capture_never_gates_opening_on_is_loaded():
    source = (STATIC / "capture.js").read_text(encoding="utf-8")

    # isLoaded() means "something is drawn on the canvas", so it is not a readiness gate.
    assert "isLoaded" not in source
    assert "YMK.isLoaded" not in source
    assert "YMK.openCameraKit()" in source
    assert "YMK.init(" in source
    assert source.index('"call quality="') < source.index('"open_camera_kit", "called"')
    # Init once per page, then open; 720p is the single re-init exception.
    assert "if (!initCalled && !initKit(videoQuality))" in source
    assert 'videoQuality = "720p";' in source
    assert "initCalled = false;" in source


def test_guided_capture_reports_every_failure_instead_of_staying_silent():
    source = (STATIC / "capture.js").read_text(encoding="utf-8")

    for expected in (
        "Guided camera is still loading…",
        "Guided camera unavailable on this device.",
        "camera_unavailable",
        "sdk_fail",
        "async_init_missing",
        "page_load",
        "button_click",
        "open_camera_kit",
        "face_quality_changed",
        "face_detection_captured",
        "camera_failed",
        "unsupported_resolution",
        "fetch_start",
        "fetch_response",
        "unhandledrejection",
        "/api/client-log",
        "now - lastQualityLog >= 2000",
    ):
        assert expected in source, expected
    # Ready = SDK present AND YMKAsyncInit ran; the button waits for both.
    assert "startButton.disabled = !attested || !kitReady;" in source


def test_async_init_watchdog_falls_back_to_an_existing_ymk_global():
    source = (STATIC / "capture.js").read_text(encoding="utf-8")

    assert 'var hasYmk = typeof YMK !== "undefined";' in source
    assert '" has_ymk=" + hasYmk' in source
    assert "async_init_fallback" in source
    assert "window.YMKAsyncInitFired || asyncInitFallback" in source
    # With YMK present the watchdog registers the kit instead of showing "unavailable".
    fallback = source.index("asyncInitFallback = true;")
    unavailable = source.index(
        'cameraUnavailable("Guided camera unavailable on this device.", "async_init_missing")'
    )
    assert fallback < unavailable
    assert "isLoaded" not in source


def test_lifecycle_and_camera_events_are_registered_and_logged():
    source = (STATIC / "capture.js").read_text(encoding="utf-8")

    for event in (
        "opened",
        "loading",
        "loaded",
        "closed",
        "faceDetectionStarted",
        "cameraOpened",
        "cameraClosed",
        "cameraFailed",
        "unsupportedResolution",
        "faceQualityChanged",
        "faceDetectionCaptured",
    ):
        assert f'YMK.addEventListener("{event}"' in source, event
    for event in (
        "opened",
        "loading",
        "loaded",
        "closed",
        "face_detection_started",
        "camera_opened",
        "camera_closed",
    ):
        assert f'logLifecycle("{event}"' in source, event


def test_capture_template_defines_the_sdk_hooks_before_the_script():
    template = (TEMPLATES / "capture.html").read_text(encoding="utf-8")

    assert "window.__ymkScriptState" in template
    assert "window.__ymkScriptLoadedAt" in template
    assert "onload=" in template
    assert "onerror=" in template
    assert '"async_init"' in template
    assert template.index("window.SkinLedgerClientLog") < template.index(
        "plugins-media.makeupar.com/v2.5-camera-kit/sdk.js"
    )
