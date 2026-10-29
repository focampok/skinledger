"""P15a acceptance tests: CSP reports, safe logging and report-only mode."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from skinledger import config
from skinledger.db import init_db
from skinledger.web.app import app
from skinledger.web.routes.csp import (
    MAX_BODY_BYTES,
    MAX_REPORTS_PER_WINDOW,
    reset_rate_limit,
)
from skinledger.web.security import content_security_policy

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _reset_csp_bucket():
    reset_rate_limit()
    yield
    reset_rate_limit()


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = config.settings
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "youcam_mock", True)
    monkeypatch.setattr(settings, "invite_code", SecretStr("invite-ok"))
    monkeypatch.setattr(settings, "admin_token", SecretStr("admin-ok"))
    monkeypatch.setattr(settings, "csp_report_only", False)
    init_db()
    return settings


@pytest.fixture
def web(env):
    with TestClient(app, base_url="https://testserver") as client:
        yield client


def _legacy(**overrides: str) -> str:
    report = {
        "effective-directive": "script-src-elem",
        "blocked-uri": "https://evil.example/x.js?token=secret",
        "document-uri": "https://skinledger.focampo.com/people/2/timeline?token=secret",
        "script-sample": "alert(1)",
    }
    report.update(overrides)
    return json.dumps({"csp-report": report})


def _post_legacy(web: TestClient, **overrides: str):
    return web.post(
        "/csp-report",
        content=_legacy(**overrides),
        headers={"Content-Type": "application/csp-report"},
    )


def _messages(caplog) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if "csp.violation" in record.getMessage()
    ]


def test_legacy_report_logs_only_safe_fields(env, web, caplog):
    with caplog.at_level(logging.INFO, logger="skinledger.events"):
        response = _post_legacy(web)

    assert response.status_code == 204
    messages = _messages(caplog)
    assert len(messages) == 1
    message = messages[0]
    assert "directive=script-src-elem" in message
    assert "blocked=https://evil.example" in message
    assert "page=/people/2/timeline" in message
    assert "token=secret" not in message
    assert "alert(1)" not in message
    assert "script-sample" not in message


def test_reporting_api_array_logs_only_csp_violations(env, web, caplog):
    body = json.dumps(
        [
            {
                "type": "csp-violation",
                "body": {
                    "effectiveDirective": "img-src",
                    "blockedURL": "data:image/png;base64,abc",
                    "documentURL": "https://skinledger.focampo.com/page?x=1",
                },
            },
            {"type": "deprecation", "body": {"id": "ignored"}},
        ]
    )

    with caplog.at_level(logging.INFO, logger="skinledger.events"):
        response = web.post(
            "/csp-report",
            content=body,
            headers={"Content-Type": "application/reports+json"},
        )

    assert response.status_code == 204
    messages = _messages(caplog)
    assert len(messages) == 1
    assert "directive=img-src" in messages[0]
    assert "blocked=data" in messages[0]
    assert "page=/page" in messages[0]
    assert "base64" not in messages[0]


def test_blocked_uris_are_reduced(env, web, caplog):
    cases = {
        "inline": "inline",
        "eval": "eval",
        "blob:https://example.com/uuid": "blob",
        "data:text/html,<b>": "data",
        "https://cdn.example/a.js?q=1": "https://cdn.example",
    }

    with caplog.at_level(logging.INFO, logger="skinledger.events"):
        for raw in cases:
            assert _post_legacy(web, **{"blocked-uri": raw}).status_code == 204

    messages = _messages(caplog)
    assert len(messages) == len(cases)
    for (raw, expected), message in zip(cases.items(), messages, strict=True):
        assert f"blocked={expected}" in message, raw
        assert "https://example.com/uuid" not in message
        assert "<b>" not in message
        assert "q=1" not in message


def test_oversized_and_invalid_reports_are_ignored(env, web, caplog):
    with caplog.at_level(logging.INFO, logger="skinledger.events"):
        too_large = web.post(
            "/csp-report",
            content=b"x" * (MAX_BODY_BYTES + 1),
            headers={"Content-Type": "application/csp-report"},
        )
        wrong_type = web.post(
            "/csp-report",
            content=_legacy(),
            headers={"Content-Type": "text/plain"},
        )
        malformed = web.post(
            "/csp-report",
            content="{",
            headers={"Content-Type": "application/csp-report"},
        )
        not_a_list = web.post(
            "/csp-report",
            content=json.dumps({"type": "csp-violation"}),
            headers={"Content-Type": "application/reports+json"},
        )

    assert too_large.status_code == 204
    assert wrong_type.status_code == 204
    assert malformed.status_code == 204
    assert not_a_list.status_code == 204
    assert _messages(caplog) == []


def test_rate_limit_is_per_client_ip(env, caplog):
    reset_rate_limit()
    proxied = ProxyHeadersMiddleware(app, trusted_hosts="*")

    with TestClient(proxied, base_url="https://testserver") as client:
        with caplog.at_level(logging.INFO, logger="skinledger.events"):
            for _ in range(MAX_REPORTS_PER_WINDOW):
                response = client.post(
                    "/csp-report",
                    content=_legacy(),
                    headers={
                        "Content-Type": "application/csp-report",
                        "X-Forwarded-For": "198.51.100.7",
                    },
                )
                assert response.status_code == 204
            blocked = client.post(
                "/csp-report",
                content=_legacy(),
                headers={
                    "Content-Type": "application/csp-report",
                    "X-Forwarded-For": "198.51.100.7",
                },
            )
            other = client.post(
                "/csp-report",
                content=_legacy(),
                headers={
                    "Content-Type": "application/csp-report",
                    "X-Forwarded-For": "203.0.113.9",
                },
            )

    assert blocked.status_code == 204
    assert other.status_code == 204
    assert len(_messages(caplog)) == MAX_REPORTS_PER_WINDOW + 1


def test_csp_header_has_reporting_directives_and_no_wasm_eval(env, web):
    response = web.get("/")

    csp = response.headers["content-security-policy"]
    assert "report-uri /csp-report" in csp
    assert "report-to csp-endpoint" in csp
    assert "'wasm-unsafe-eval'" not in csp
    report_to = json.loads(response.headers["report-to"])
    assert report_to["group"] == "csp-endpoint"
    assert report_to["endpoints"][0]["url"].endswith("/csp-report")
    source = (ROOT / "src/skinledger/web/security.py").read_text(encoding="utf-8")
    assert "wasm-unsafe-eval" in source


def test_report_only_switch_sends_the_same_policy(env, monkeypatch, web):
    monkeypatch.setattr(config.settings, "csp_report_only", True)

    response = web.get("/")

    assert "Content-Security-Policy" not in response.headers
    assert response.headers["content-security-policy-report-only"] == (
        content_security_policy()
    )
    assert response.headers["permissions-policy"] == "camera=(self)"
    assert "csp-endpoint" in response.headers["report-to"]
