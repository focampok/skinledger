"""P01 acceptance tests: shell routes, footer copy, secret hygiene and the PWA service worker."""

import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from skinledger import copy
from skinledger.config import Settings
from skinledger.web.app import app

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/skinledger/web/static"

client = TestClient(app)


def test_healthz_returns_ok():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_home_page_shows_exact_disclaimer_and_attribution():
    response = client.get("/")
    assert response.status_code == 200
    assert copy.DISCLAIMER in response.text
    assert copy.POWERED_BY in response.text


def test_offline_page_is_available_for_the_service_worker():
    response = client.get("/offline")
    assert response.status_code == 200
    assert copy.DISCLAIMER in response.text


def test_service_worker_is_served_with_root_scope():
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["service-worker-allowed"] == "/"


def test_settings_repr_and_str_hide_secrets(monkeypatch):
    monkeypatch.setenv("YOUCAM_API_KEY", "fake-youcam-key-value")
    monkeypatch.setenv("INVITE_CODE", "fake-invite-code-value")
    monkeypatch.setenv("ADMIN_TOKEN", "fake-admin-token-value")

    settings = Settings(_env_file=None)
    rendered = f"{settings!s} {settings!r}"

    for secret in ("fake-youcam-key-value", "fake-invite-code-value", "fake-admin-token-value"):
        assert secret not in rendered


def test_service_worker_never_references_private_paths():
    source = (STATIC / "sw.js").read_text(encoding="utf-8")
    for path in ("/api", "/media", "/try"):
        assert path not in source


def test_python_multipart_is_not_a_dependency():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "python-multipart" not in pyproject


def test_manifest_is_valid_and_complete():
    manifest = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["name"] == "SkinLedger"
    assert manifest["short_name"] == "SkinLedger"
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert {icon["sizes"] for icon in manifest["icons"]} >= {"192x192", "512x512"}


def test_icons_are_png_with_expected_sizes():
    for size in (192, 512):
        path = STATIC / "icons" / f"icon-{size}.png"
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.size == (size, size)
