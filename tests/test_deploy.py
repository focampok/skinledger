"""P15 acceptance tests: deploy config, security headers, admin usage and demo."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from skinledger import config, copy, guards, seed, usage
from skinledger.config import CAMERA_KIT_ORIGINS
from skinledger.db import connect, db_path, init_db
from skinledger.web.app import app
from skinledger.web.routes.admin import files_outside_masks
from skinledger.web.routes.try_ import reset_invite_attempts

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src/skinledger/web/templates"


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = config.settings
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "youcam_mock", True)
    monkeypatch.setattr(settings, "invite_code", SecretStr("invite-ok"))
    monkeypatch.setattr(settings, "admin_token", SecretStr("admin-ok"))
    monkeypatch.setattr(settings, "seed_sample_on_start", False)
    monkeypatch.setattr(settings, "railway_environment", None)
    init_db()
    return settings


@pytest.fixture
def web(env):
    with TestClient(app, base_url="https://testserver") as client:
        yield client


# -- health, headers and CSP ------------------------------------------------


def test_healthz_returns_only_ok(web):
    response = web.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_security_headers_are_strict(web):
    for path in ("/", "/healthz", "/static/app.js"):
        response = web.get(path)
        assert response.status_code == 200, path
        headers = response.headers
        csp = headers["content-security-policy"]
        directives = {
            part.strip().split(" ", 1)[0]: part.strip()
            for part in csp.split(";")
            if part.strip()
        }

        assert "'unsafe-inline'" not in directives["script-src"]
        for origin in CAMERA_KIT_ORIGINS:
            assert origin in directives["script-src"]
        assert directives["img-src"] == "img-src 'self' blob: data:"
        assert directives["frame-ancestors"] == "frame-ancestors 'none'"
        assert headers["permissions-policy"] == "camera=(self)"
        assert "max-age=31536000" in headers["strict-transport-security"]
        assert headers["referrer-policy"] == "same-origin"
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"


def test_templates_have_no_inline_scripts_or_event_handlers():
    for path in TEMPLATES.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert "<script>" not in text, path
        assert not re.search(r'on(?:load|error|click)="', text), path


def test_privacy_page_keeps_its_text_and_ends_with_the_disclaimer(web):
    response = web.get("/privacy")

    assert response.status_code == 200
    assert copy.PRIVACY_TEXT in response.text
    assert copy.DISCLAIMER in response.text
    template = (TEMPLATES / "privacy.html").read_text(encoding="utf-8")
    assert template.index("{{ privacy_text }}") < template.index("{{ disclaimer }}")


# -- admin usage -------------------------------------------------------------


def test_admin_usage_is_header_only_and_hides_unauthorized(web):
    assert web.get("/admin/usage").status_code == 404
    assert web.get("/admin/usage?token=admin-ok").status_code == 404
    assert (
        web.get("/admin/usage", headers={"X-Admin-Token": "wrong"}).status_code
        == 404
    )

    response = web.get("/admin/usage", headers={"X-Admin-Token": "admin-ok"})

    assert response.status_code == 200
    assert copy.ADMIN_VISITOR_UNITS_TOTAL in response.text
    assert copy.ADMIN_FILES_OUTSIDE in response.text
    assert copy.ADMIN_UNAVAILABLE in response.text


def test_admin_usage_reports_counts_not_visitor_data(env, web):
    conn = connect(db_path())
    try:
        person_id = conn.execute(
            "INSERT INTO persons (display_name, owner_token_hash) VALUES (?, ?)",
            ("Private Person", guards.owner_token_hash("owner")),
        ).lastrowid
        conn.execute(
            "INSERT INTO captures (person_id, owner_token_hash, captured_at, data_label, "
            "source, status, error_code, units_charged) "
            "VALUES (?, ?, ?, 'REAL', 'upload', 'error', 'error_no_face', 0)",
            (
                person_id,
                guards.owner_token_hash("owner"),
                usage.utc_now_iso(),
            ),
        )
        conn.execute(
            "INSERT INTO api_usage (owner_token_hash, day, units, mode, is_admin) "
            "VALUES (?, ?, 16, 'real', 0)",
            (guards.owner_token_hash("owner"), usage.guatemala_today()),
        )
        conn.execute(
            "INSERT INTO api_usage (owner_token_hash, day, units, mode, is_admin) "
            "VALUES (?, ?, 16, 'real', 1)",
            (guards.owner_token_hash("owner"), usage.guatemala_today()),
        )
        conn.commit()
    finally:
        conn.close()
    (env.data_dir / "stray.txt").write_text("x", encoding="utf-8")

    response = web.get("/admin/usage", headers={"X-Admin-Token": "admin-ok"})

    assert response.status_code == 200
    assert "Private Person" not in response.text
    assert "error_no_face" in response.text
    assert files_outside_masks(env.data_dir) == 1
    assert copy.ADMIN_FILES_OUTSIDE in response.text


# -- production startup ------------------------------------------------------


def test_production_startup_refuses_missing_config(env, monkeypatch, caplog):
    monkeypatch.setattr(config.settings, "railway_environment", "production")
    monkeypatch.setattr(config.settings, "youcam_mock", True)
    monkeypatch.setattr(config.settings, "invite_code", SecretStr(""))
    monkeypatch.setattr(config.settings, "admin_token", SecretStr("super-secret-admin"))

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError) as excinfo:
            with TestClient(app):
                pass

    message = str(excinfo.value)
    logged = " ".join(record.getMessage() for record in caplog.records)
    for name in ("YOUCAM_MOCK", "INVITE_CODE"):
        assert name in message
        assert name in logged
    assert "super-secret-admin" not in message
    assert "super-secret-admin" not in logged


def test_production_startup_accepts_a_configured_environment(env, monkeypatch):
    monkeypatch.setattr(config.settings, "railway_environment", "production")
    monkeypatch.setattr(config.settings, "youcam_mock", False)
    monkeypatch.setattr(config.settings, "invite_code", SecretStr("invite-ok"))
    monkeypatch.setattr(config.settings, "admin_token", SecretStr("admin-ok"))

    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"ok": True}


def test_seed_sample_on_start_is_idempotent(env, monkeypatch, capsys):
    monkeypatch.setattr(config.settings, "seed_sample_on_start", True)

    with TestClient(app) as client:
        assert client.get("/people").status_code == 200
    with TestClient(app):
        pass

    conn = connect(db_path())
    try:
        demos = conn.execute(
            "SELECT COUNT(*) FROM persons WHERE is_demo_public = 1"
        ).fetchone()[0]
        captures = conn.execute("SELECT COUNT(*) FROM captures").fetchone()[0]
        products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    finally:
        conn.close()
    assert demos == 1
    assert captures == 7
    assert products == 2
    assert "admin-ok" not in capsys.readouterr().out


# -- demo page and shared links ---------------------------------------------


def test_demo_page_explains_the_sample_and_links_try(env, web):
    seed.main(["--sample-person"])
    conn = connect(db_path())
    try:
        demo_id = conn.execute(
            "SELECT id FROM persons WHERE is_demo_public = 1"
        ).fetchone()["id"]
    finally:
        conn.close()

    response = web.get("/demo")

    assert response.status_code == 200
    assert "Sample user (SIMULATED)" in response.text
    assert "/try" in response.text
    assert "Devpost" in response.text
    assert "2 analyses per person" in response.text
    assert f"/people/{demo_id}/timeline" in response.text
    assert copy.DISCLAIMER in response.text
    assert 'href="/demo"' in web.get("/").text
    assert 'href="/demo"' in web.get("/try").text


# -- proxy headers, cookies and Docker artifacts ----------------------------


def test_try_rate_limit_keys_on_the_forwarded_client_ip(env):
    reset_invite_attempts()
    proxied = ProxyHeadersMiddleware(app, trusted_hosts="*")

    with TestClient(proxied, base_url="https://testserver") as client:
        for _ in range(10):
            response = client.post(
                "/try",
                data={"invite_code": "wrong"},
                headers={"X-Forwarded-For": "198.51.100.7"},
            )
            assert response.status_code == 400

        blocked = client.post(
            "/try",
            data={"invite_code": "wrong"},
            headers={"X-Forwarded-For": "198.51.100.7"},
        )
        other = client.post(
            "/try",
            data={"invite_code": "wrong"},
            headers={"X-Forwarded-For": "203.0.113.9"},
        )

    assert blocked.status_code == 429
    assert other.status_code == 400


def test_owner_and_invite_cookies_are_secure(env, web):
    owner = web.post(
        "/people/new", data={"display_name": "Ana"}, follow_redirects=False
    )
    owner_cookie = next(
        value
        for value in owner.headers.get_list("set-cookie")
        if value.startswith(f"{guards.OWNER_COOKIE}=")
    )
    assert "Secure" in owner_cookie

    invite = web.post(
        "/try", data={"invite_code": "invite-ok"}, follow_redirects=False
    )
    invite_cookie = next(
        value
        for value in invite.headers.get_list("set-cookie")
        if value.startswith(f"{guards.INVITE_COOKIE}=")
    )
    assert "Secure" in invite_cookie


def test_dockerfile_and_railway_use_the_deploy_settings():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    railway = (ROOT / "railway.json").read_text(encoding="utf-8")

    assert "python:3.12-slim" in dockerfile
    assert "DATA_DIR=/data" in dockerfile
    assert "USER appuser" in dockerfile
    assert "--proxy-headers" in dockerfile
    assert "--forwarded-allow-ips='*'" in dockerfile
    assert "--no-access-log" in dockerfile
    assert '"/healthz"' in railway
